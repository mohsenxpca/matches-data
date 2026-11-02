"""Watchdog & Publishing Health Monitor for Egyptaway & Review.
Monitors both sites 24/7 to ensure publishing NEVER stalls.

Capabilities:
1. Live Pulse Check: Reads public Atom feeds of both sites to calculate exact minutes since last live post.
2. GitHub Workflow Inspection: Checks GitHub Actions runs for failures, errors, or stalled workflows.
3. Self-Healing Auto-Kick: If a site has not published within the threshold (2h day / 3h night),
   automatically triggers publishing workflows via GitHub API.
4. Instant Alerts: Sends Telegram notification + creates a GitHub Issue (Mohsen receives email on phone).
5. Anti-Spam State: Only alerts once per stall event, and sends a recovery message once new post is live.
"""
import argparse, datetime, json, os, re, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

CAIRO = ZoneInfo("Africa/Cairo")
REPO = "mohsenxpca/matches-data"
STATE_FILE = "watchdog_state.json"

SITES = {
    "egyptaway": {
        "name": "ايجبتاوى",
        "domain": "www.egyptaway.com",
        "feed": "https://www.egyptaway.com/feeds/posts/default?max-results=3",
        "day_max_gap_min": 120,    # 2 hours
        "night_max_gap_min": 180,  # 3 hours
        "recovery_workflows": ["phone_news.yml", "tech.yml", "service_news.yml"]
    },
    "review": {
        "name": "رفيو موبايل",
        "domain": "www.review-mobile.com",
        "feed": "https://www.review-mobile.com/feeds/posts/default?max-results=3",
        "day_max_gap_min": 120,    # 2 hours
        "night_max_gap_min": 180,  # 3 hours
        "recovery_workflows": ["review.yml"]
    }
}


def get_token():
    """Gets GitHub Token from environment (fine-grained, repo, or GITHUB_TOKEN)."""
    return (
        os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_PAT")
        or ""
    ).strip()


def gh_api(path, method="GET", body=None, token=None):
    """Interacts with GitHub REST API."""
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "User-Agent": "egyptaway-watchdog",
        "Accept": "application/vnd.github+json"
    }
    tok = token or get_token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"

    data = json.dumps(body).encode("utf-8") if body else None
    if data:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 204 or resp.code == 204:
                return {"status": 204, "ok": True}
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {"status": resp.status, "ok": True}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return {"error": e.code, "message": err_msg}
    except Exception as e:
        return {"error": -1, "message": str(e)}


def check_site_pulse(site_key):
    """Fetches Atom feed and returns minutes since last post, post title, and post URL."""
    cfg = SITES[site_key]
    req = urllib.request.Request(cfg["feed"], headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    now = datetime.datetime.now(CAIRO)
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            root = ET.fromstring(r.read())
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entry = root.find("atom:entry", ns)
            if entry is not None:
                title = (entry.find("atom:title", ns).text or "").strip()
                pub_str = entry.find("atom:published", ns).text
                pub_dt = datetime.datetime.fromisoformat(pub_str).astimezone(CAIRO)
                diff_sec = (now - pub_dt).total_seconds()
                diff_min = max(0, int(diff_sec / 60))
                link_el = entry.find("atom:link[@rel='alternate']", ns)
                url = link_el.get("href", "") if link_el is not None else ""
                return {
                    "ok": True,
                    "diff_min": diff_min,
                    "last_title": title,
                    "last_url": url,
                    "last_published": pub_dt.strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception as e:
        return {"ok": False, "error": str(e), "diff_min": 9999, "last_title": "", "last_url": "", "last_published": ""}

    return {"ok": False, "error": "No entries found", "diff_min": 9999, "last_title": "", "last_url": "", "last_published": ""}


def check_github_workflows():
    """Inspects recent workflow runs for failures or issues."""
    data = gh_api("/actions/runs?per_page=35")
    runs = data.get("workflow_runs", [])
    if not runs:
        return {"ok": False, "runs": [], "failed": [], "stuck": []}

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    failed = []
    stuck = []

    for r in runs:
        created = datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        age_hours = (now_utc - created).total_seconds() / 3600

        # Only care about recent runs (last 4 hours)
        if age_hours > 4:
            continue

        if r.get("conclusion") == "failure":
            failed.append({
                "name": r.get("name"),
                "path": r.get("path"),
                "url": r.get("html_url"),
                "created_at": r.get("created_at")
            })
        elif r.get("status") == "in_progress" and age_hours > 0.6:  # running > 36 mins
            stuck.append({
                "name": r.get("name"),
                "path": r.get("path"),
                "url": r.get("html_url"),
                "created_at": r.get("created_at")
            })

    return {"ok": True, "failed": failed, "stuck": stuck, "total_recent": len(runs)}


def send_telegram(msg):
    """Sends Telegram alert if TELEGRAM_BOT_TOKEN is present."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not tok:
        return False
    channel = os.environ.get("TELEGRAM_ADMIN_CHAT") or "@egyptaway1"
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    payload = {"chat_id": channel, "text": msg, "parse_mode": "HTML"}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 201)
    except Exception as e:
        print("Telegram send failed:", e)
        return False


def create_github_issue(title, body):
    """Creates a GitHub issue to notify Mohsen via email."""
    tok = get_token()
    if not tok:
        print("No GitHub token to open issue.")
        return False
    res = gh_api("/issues", method="POST", body={"title": title, "body": body})
    if "html_url" in res:
        print("Created GitHub issue alert:", res["html_url"])
        return True
    print("Failed to create issue:", res)
    return False


def dispatch_workflow(wf_file, inputs=None):
    """Dispatches a GitHub Actions workflow to revive publishing."""
    tok = get_token()
    if not tok:
        print(f"Cannot dispatch {wf_file}: No GitHub token available.")
        return False
    body = {"ref": "main", "inputs": inputs or {}}
    res = gh_api(f"/actions/workflows/{wf_file}/dispatches", method="POST", body=body)
    if res == {} or res.get("status") in (200, 204) or "error" not in res:
        print(f"Successfully dispatched workflow: {wf_file}")
        return True
    print(f"Failed to dispatch {wf_file}:", res)
    return False


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"alerts": {}, "last_posts": {}}


def save_state(st):
    try:
        json.dump(st, open(STATE_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception as e:
        print("Warning saving state:", e)


def main():
    parser = argparse.ArgumentParser(description="Watchdog & Publishing Monitor")
    parser.add_argument("--kick", action="store_true", help="Force kick publishing workflows immediately")
    parser.add_argument("--status-only", action="store_true", help="Only display status table without taking action")
    args = parser.parse_args()

    now = datetime.datetime.now(CAIRO)
    is_night = (0 <= now.hour < 9)
    state = load_state()

    print("=" * 65)
    print(f"👁️  حارس ومراقب النشر الذكي — {now.strftime('%Y-%m-%d %H:%M:%S')} بتوقيت القاهرة")
    print("=" * 65)

    site_results = {}
    stalled_sites = []

    for key, cfg in SITES.items():
        pulse = check_site_pulse(key)
        site_results[key] = pulse
        limit = cfg["night_max_gap_min"] if is_night else cfg["day_max_gap_min"]

        diff = pulse["diff_min"]
        is_stalled = diff > limit or args.kick

        status_icon = "🔴 متوقف ومغيب" if is_stalled else ("🟡 متأخر قليلاً" if diff > (limit * 0.75) else "🟢 نشط وممتاز")
        print(f"\n[{cfg['name']} ({cfg['domain']})]")
        print(f"  • الحالة: {status_icon}")
        print(f"  • آخر مقال منشور: منذ {diff} دقيقة (الحد المسموح: {limit} دقيقة)")
        print(f"  • العنوان: {pulse['last_title']}")
        if pulse.get("last_url"):
            print(f"  • الرابط: {pulse['last_url']}")

        if is_stalled:
            stalled_sites.append((key, cfg, diff, limit, pulse))

        # Check for recovery
        prev_alert = state["alerts"].get(key)
        if prev_alert and not is_stalled and pulse["last_title"] != prev_alert.get("last_title"):
            # Site recovered!
            recovery_msg = (
                f"✅ <b>بشرى: عاد النشر للعمل على {cfg['name']}</b>\n\n"
                f"تم نشر مقال جديد الآن بنجاح:\n"
                f"📰 <b>{pulse['last_title']}</b>\n"
                f"🔗 {pulse['last_url']}\n"
                f"⏰ الوقت: {now.strftime('%H:%M:%S')}"
            )
            print(f"  ✨ {cfg['name']} عاد للنشر! إرسال إشعار التعافي...")
            send_telegram(recovery_msg)
            del state["alerts"][key]

    # Check GitHub Actions Workflows
    wf_health = check_github_workflows()
    print("\n" + "-" * 65)
    print(f"⚙️  حالة سيرفرات ومهام GitHub Actions:")
    if wf_health["ok"]:
        if wf_health["failed"]:
            print(f"  ⚠️  يوجد {len(wf_health['failed'])} مهمة فشلت مؤخراً:")
            for fl in wf_health["failed"]:
                print(f"     - ❌ {fl['name']} ({fl['url']})")
        else:
            print(f"  ✅ لا توجد أي مهام فاشلة في آخر 4 ساعات.")

        if wf_health["stuck"]:
            print(f"  ⏳ يوجد {len(wf_health['stuck'])} مهمة معلقة:")
            for st in wf_health["stuck"]:
                print(f"     - 🔄 {st['name']}")
    else:
        print("  ℹ️  تعذر فحص قائمة المهام من جيت هب مباشرة (قد يكون بسبب قيود الاتصال أو غياب التوكن).")

    print("-" * 65)

    if args.status_only:
        save_state(state)
        return

    # Self-Healing & Actions
    if stalled_sites:
        for key, cfg, diff, limit, pulse in stalled_sites:
            print(f"\n🚨 تدخل عاجل لإحياء النشر على: {cfg['name']} (متأخر {diff} دقيقة)!")
            
            # 1. Trigger recovery workflows
            for wf in cfg["recovery_workflows"]:
                print(f"  🚀 تشغيل خطة الإنقاذ: إطلاق workflow [{wf}]...")
                dispatch_workflow(wf)

            # 2. Alert Mohsen (Anti-Spam: once per stall)
            already_alerted = state["alerts"].get(key, {}).get("alerted")
            last_alert_time = state["alerts"].get(key, {}).get("time", 0)

            # Only alert once every 90 minutes for the same stall
            if not already_alerted or (time.time() - last_alert_time > 5400):
                hours_ago = round(diff / 60, 1)
                alert_text = (
                    f"🚨 <b>تنبيه حارس النشر: تأخر النشر على {cfg['name']}</b>\n\n"
                    f"الموقع لم ينشر أي مقال جديد منذ <b>{hours_ago} ساعة ({diff} دقيقة)</b>!\n"
                    f"الحد الأقصى المسموح: {limit} دقيقة.\n"
                    f"آخر مقال: {pulse['last_title']}\n\n"
                    f"🛠️ <b>الإجراء التلقائي المتخذ:</b>\n"
                    f"تم تشغيل مهام الإحياء والإنقاذ تلقائياً الآن ({', '.join(cfg['recovery_workflows'])}).\n"
                    f"جاري الرصد والمتابعة اللحظية."
                )
                print(f"  📢 إرسال تنبيه عاجل لمحسن...")
                send_telegram(alert_text)
                create_github_issue(
                    title=f"🚨 تنبيه تأخر النشر على موقع {cfg['name']} (منذ {hours_ago} ساعة)",
                    body=f"رصد حارس النشر أن موقع {cfg['name']} لم ينشر أي مقال جديد منذ {diff} دقيقة ({hours_ago} ساعة).\n\n"
                         f"آخر مقال: {pulse['last_title']} ({pulse['last_url']})\n\n"
                         f"تم تفعيل الإجراء التلقائي لتشغيل {cfg['recovery_workflows']} فوراً لإحياء النشر."
                )
                state["alerts"][key] = {
                    "alerted": True,
                    "time": time.time(),
                    "diff_min": diff,
                    "last_title": pulse["last_title"]
                }
    else:
        print("\n🎉 ممتاز! النشر شغال بانتظام على الموقعين وبدون أي تأخير.")

    save_state(state)
    print("=" * 65)


if __name__ == "__main__":
    main()
