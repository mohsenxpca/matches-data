"""Web push for new Egyptaway posts via OneSignal (runs every 30 minutes on GitHub Actions, .github/workflows/notify.yml).

Picks the newest live post from the last few hours that we haven't pushed yet and sends it to all subscribers, with a
daily cap, a minimum gap between pushes and quiet hours at night so people don't switch notifications off.
Env: ONESIGNAL_API_KEY (GitHub secret, REST API key), PER_DAY (default 6), GAP_MIN (default 90), DRY_RUN=1 to only print.
"""
import datetime, html, json, os, re, sys
import requests
import football as f

APP_ID = "c6f8318f-a6ce-4e8d-b9f0-f329f31e2a72"
PER_DAY = int(os.environ.get("PER_DAY") or 6)
GAP_MIN = int(os.environ.get("GAP_MIN") or 90)
QUIET = range(0, 9)  # Cairo hours with no pushes
LOOKBACK_H = 4


def snippet(body):
    body = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", body or "", flags=re.S | re.I)
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.S | re.I):
        t = html.unescape(re.sub(r"<[^>]+>", " ", p))
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 40:
            return t[:110].rsplit(" ", 1)[0] + "…" if len(t) > 110 else t
    return "اضغط واقرأ التفاصيل على ايجبتاوى"


def first_image(body):
    m = re.search(r'<img[^>]+src="(https://[^"]+)"', body or "")
    return html.unescape(m.group(1)) if m else None


def main():
    key = f.secret("ONESIGNAL_API_KEY")
    dry = os.environ.get("DRY_RUN") == "1"
    force = os.environ.get("FORCE") == "1"  # manual test: ignore quiet hours, gap and daily cap
    if not key and not dry:
        print("ONESIGNAL_API_KEY secret is missing, nothing sent")
        return
    try:
        state = json.load(open("notify_sent.json", encoding="utf-8"))
    except Exception:
        state = {"sent": []}
    now = datetime.datetime.now(f.CAIRO)
    today = now.date().isoformat()
    if now.hour in QUIET and not force:
        print("quiet hours")
        return
    sent_today = [s for s in state["sent"] if s.get("at", "").startswith(today)]
    if len(sent_today) >= PER_DAY and not force:
        print(f"daily cap reached ({PER_DAY})")
        return
    if state["sent"] and not force:
        last = datetime.datetime.fromisoformat(state["sent"][-1]["at"])
        if (now - last).total_seconds() < GAP_MIN * 60:
            print("last push was less than", GAP_MIN, "minutes ago")
            return
    done = {s["url"] for s in state["sent"]}
    tok = f.token()
    since = (now - datetime.timedelta(hours=24 if force else LOOKBACK_H)).isoformat(timespec="seconds")
    res = f.api("GET", f"/blogs/{f.BLOG}/posts", tok, {"status": "live", "startDate": since, "maxResults": 10,
                                                      "fetchBodies": "true", "fetchImages": "true"})
    posts = [p for p in res.get("items", []) if p.get("url") and p["url"] not in done]
    if not posts:
        print("no new posts to push")
        return
    p = sorted(posts, key=lambda x: x["published"])[-1]
    title = html.unescape(p["title"])
    url = p["url"].replace("http://", "https://")
    msg = {"app_id": APP_ID, "target_channel": "push", "included_segments": ["Total Subscriptions"],
           "headings": {"en": title, "ar": title}, "contents": {"en": snippet(p.get("content")), "ar": snippet(p.get("content"))},
           "web_url": url + "?utm_source=push&utm_medium=onesignal", "name": "auto " + url.split("/")[-1][:40]}
    img = first_image(p.get("content"))
    if img:
        msg["chrome_web_image"] = img
    if dry:
        print(json.dumps(msg, ensure_ascii=False, indent=1))
        return
    r = requests.post("https://api.onesignal.com/notifications?c=push", json=msg, timeout=30,
                      headers={"Authorization": "Key " + key, "Content-Type": "application/json"})
    print("OneSignal", r.status_code, r.text[:300])
    if r.status_code >= 400:
        sys.exit(1)
    if not r.json().get("id"):
        print("not sent (no subscribers yet?)")
        return
    state["sent"].append({"url": p["url"], "title": title, "at": now.isoformat(timespec="seconds")})
    state["sent"] = state["sent"][-300:]
    json.dump(state, open("notify_sent.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PUSHED", title, url)


if __name__ == "__main__":
    main()
