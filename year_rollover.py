"""Annual Year Rollover Engine (mohsen 2026-11-03).
Runs every year in December (and via workflow_dispatch) to seamlessly rollover
all article titles and body content on Egyptaway and Review from the current year
to the upcoming year (e.g. 2026 -> 2027), or strip obsolete year mentions,
keeping all content fresh, evergreen, and optimized for Google Search & Discover.

Features:
- Scans all live posts on Egyptaway and Review.
- Updates titles and body text nodes (both English 2026 and Arabic ٢٠٢٦ numerals).
- NEVER alters URLs, slugs, publish dates, image sources, or HTML attributes.
- Safe dry-run mode by default; commits changes live with --confirm.
- Saves full audit log to year_rollover_log.json and prints Step Summary.

Usage:
  python year_rollover.py                          # Dry-run on both sites for upcoming year
  python year_rollover.py --confirm               # Apply live updates to both sites
  python year_rollover.py --site review --confirm # Review site only
  python year_rollover.py --from-year 2026 --to-year 2027 --confirm
"""
import argparse, datetime, difflib, io, json, os, re, sys, time
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CAIRO = ZoneInfo("Africa/Cairo")
SITES = {
    "egyptaway": {
        "name": "ايجبتاوى",
        "blog_id": "8325646053257070334",
        "domain": "www.egyptaway.com"
    },
    "review": {
        "name": "رفيو",
        "blog_id": "2997328666613207792",
        "domain": "www.review-mobile.com"
    }
}

EN_TO_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
AR_TO_EN = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def secret(key):
    v = os.environ.get(key)
    if v:
        return v.strip()
    return None


_FRESH_TOK = {}


def get_token():
    cid = secret("BLOGGER_CLIENT_ID")
    csec = secret("BLOGGER_CLIENT_SECRET")
    rtok = secret("BLOGGER_REFRESH_TOKEN")
    if cid and csec and rtok:
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": cid, "client_secret": csec,
            "refresh_token": rtok, "grant_type": "refresh_token"}, timeout=30)
        if r.status_code == 200:
            return r.json()["access_token"]
        print(f"Warning: OAuth refresh failed ({r.status_code}): {r.text[:100]}")

    # Local fallback for development/testing
    for candidate in [
        r"C:\Users\H\Documents\blogger-pipeline\token.json",
        os.path.join(os.path.dirname(__file__), "token.json"),
        os.path.join(os.path.dirname(__file__), "..", "blogger-pipeline", "token.json")
    ]:
        if os.path.exists(candidate):
            try:
                data = json.load(open(candidate, encoding="utf-8"))
                tok = data.get("access_token") or data.get("token")
                exp = data.get("expiry")
                # If expired and refresh_token exists, refresh
                if data.get("refresh_token") and data.get("client_id") and data.get("client_secret"):
                    rf = requests.post("https://oauth2.googleapis.com/token", data={
                        "client_id": data["client_id"], "client_secret": data["client_secret"],
                        "refresh_token": data["refresh_token"], "grant_type": "refresh_token"}, timeout=30)
                    if rf.status_code == 200:
                        return rf.json()["access_token"]
                if tok:
                    return tok
            except Exception as e:
                pass
    raise RuntimeError("No valid Blogger access token available.")


def api_call(method, path, tok, params=None, body=None):
    def call(t):
        for i in range(3):
            try:
                r = requests.request(method, "https://www.googleapis.com/blogger/v3" + path,
                                     params=params, json=body,
                                     headers={"Authorization": "Bearer " + t}, timeout=60)
                if r.status_code < 500 or i == 2:
                    return r
            except requests.ConnectionError:
                if i == 2: raise
            time.sleep(2 * (i + 1))
    r = call(_FRESH_TOK.get(tok, tok))
    if r and r.status_code == 401:
        _FRESH_TOK[tok] = get_token()
        r = call(_FRESH_TOK[tok])
    return r


def fetch_all_live_posts(tok, blog_id, max_posts=2500):
    posts, page = [], None
    while len(posts) < max_posts:
        q = {
            "maxResults": min(100, max_posts - len(posts)),
            "status": "live",
            "fetchBodies": "true"
        }
        if page:
            q["pageToken"] = page
        r = api_call("GET", f"/blogs/{blog_id}/posts", tok, params=q)
        if r.status_code != 200:
            print(f"Error fetching posts ({r.status_code}): {r.text[:120]}")
            break
        data = r.json()
        items = data.get("items", [])
        posts.extend(items)
        page = data.get("nextPageToken")
        if not page or not items:
            break
        time.sleep(0.3)
    return posts


def transform_text(text, from_yr, to_yr, mode="update"):
    """Safely transforms year references in plain text or titles."""
    if not text:
        return text, 0

    from_en = str(from_yr)
    to_en = str(to_yr)
    from_ar = from_en.translate(EN_TO_AR)
    to_ar = to_en.translate(EN_TO_AR)

    count = 0
    new_text = text

    if mode == "strip":
        # Remove year and clean extra spaces/separators
        patterns = [
            rf'\s*(?:[-–—|/:]\s*)?(?:لعام|سنة|عام)?\s*{re.escape(from_en)}\b',
            rf'\s*(?:[-–—|/:]\s*)?(?:لعام|سنة|عام)?\s*{re.escape(from_ar)}',
        ]
        for pat in patterns:
            sub, n = re.subn(pat, '', new_text)
            if n > 0:
                count += n
                new_text = sub
        # Clean double spaces
        new_text = re.sub(r'\s{2,}', ' ', new_text).strip()
    else:
        # Standard update: 2026 -> 2027 and ٢٠٢٦ -> ٢٠٢٧
        # English numerals
        pattern_en = rf'(?<!\d){re.escape(from_en)}(?!\d)'
        sub, n1 = re.subn(pattern_en, to_en, new_text)
        count += n1
        new_text = sub

        # Arabic numerals
        pattern_ar = rf'(?<![٠-٩]){re.escape(from_ar)}(?![٠-٩])'
        sub, n2 = re.subn(pattern_ar, to_ar, new_text)
        count += n2
        new_text = sub

    return new_text, count


def transform_html_body(html_content, from_yr, to_yr, mode="update"):
    """Replaces year mentions only inside text nodes of HTML, leaving attributes intact."""
    if not html_content:
        return html_content, 0

    soup = BeautifulSoup(html_content, "html.parser")
    total_replacements = 0

    # Process all text nodes
    for s in soup.find_all(string=True):
        parent_name = s.parent.name if s.parent else ""
        if parent_name in ["script", "style", "noscript", "svg", "path"]:
            continue
        
        orig_str = str(s)
        new_str, count = transform_text(orig_str, from_yr, to_yr, mode=mode)
        if count > 0:
            s.replace_with(new_str)
            total_replacements += count

    # Return modified HTML as string
    return str(soup), total_replacements


def process_post(post, from_yr, to_yr, mode="update"):
    """Inspects and returns updated post data if year needs transformation."""
    post_id = post["id"]
    orig_title = post.get("title", "")
    orig_body = post.get("content", "")
    post_url = post.get("url", "")

    new_title, title_changes = transform_text(orig_title, from_yr, to_yr, mode=mode)
    new_body, body_changes = transform_html_body(orig_body, from_yr, to_yr, mode=mode)

    if title_changes > 0 or body_changes > 0:
        return {
            "id": post_id,
            "url": post_url,
            "title_changed": title_changes > 0,
            "body_changed": body_changes > 0,
            "orig_title": orig_title,
            "new_title": new_title,
            "title_changes": title_changes,
            "body_changes": body_changes,
            "new_body": new_body
        }
    return None


def run_rollover(site_key, from_yr, to_yr, mode="update", confirm=False, max_posts=2500):
    site = SITES[site_key]
    site_name = site["name"]
    blog_id = site["blog_id"]
    print(f"\n========================================================")
    print(f"🚀 بدء فحص وتحديث موقع: {site_name} ({site['domain']})")
    print(f"   التحويل: {from_yr} ➔ {to_yr} (الوضع: {mode}) | وضع التنفيذ: {'تطبيق لايف (LIVE)' if confirm else 'معاينة تجريبية (DRY RUN)'}")
    print(f"========================================================")

    tok = get_token()
    posts = fetch_all_live_posts(tok, blog_id, max_posts=max_posts)
    print(f"إجمالي المقالات المنشورة في {site_name}: {len(posts)} مقال")

    updated_records = []
    for i, post in enumerate(posts):
        res = process_post(post, from_yr, to_yr, mode=mode)
        if res:
            updated_records.append(res)
            print(f"[{len(updated_records)}] مقال مرشح للتحديث:")
            print(f"   العنوان الأصلي : {res['orig_title']}")
            print(f"   العنوان الجديد : {res['new_title']}")
            print(f"   تعديلات العنوان: {res['title_changes']} | تعديلات المحتوى: {res['body_changes']}")
            print(f"   الرابط        : {res['url']}")

            if confirm:
                patch_payload = {}
                if res["title_changed"]:
                    patch_payload["title"] = res["new_title"]
                if res["body_changed"]:
                    patch_payload["content"] = res["new_body"]

                r = api_call("PATCH", f"/blogs/{blog_id}/posts/{res['id']}", tok, body=patch_payload)
                if r.status_code == 200:
                    print("   ✅ تم تحديث المقال على بلوجر بنجاح!")
                else:
                    print(f"   ❌ فشل تحديث المقال ({r.status_code}): {r.text[:120]}")
                time.sleep(0.5)

    print(f"\nنتيجة فحص {site_name}: تم رصد {len(updated_records)} مقال بحاجة للتحديث للعام الجديد.")
    return updated_records


def main():
    now_cairo = datetime.datetime.now(CAIRO)
    default_from = now_cairo.year
    default_to = now_cairo.year + 1

    parser = argparse.ArgumentParser(description="Annual Year Rollover Engine for Egyptaway & Review")
    parser.add_argument("--site", choices=["all", "egyptaway", "review"], default="all",
                        help="الموقع المستهدف (all أو egyptaway أو review)")
    parser.add_argument("--from-year", type=int, default=default_from,
                        help=f"السنة المراد استبدالها (الافتراضي: {default_from})")
    parser.add_argument("--to-year", type=int, default=default_to,
                        help=f"السنة الجديدة المستهدفة (الافتراضي: {default_to})")
    parser.add_argument("--mode", choices=["update", "strip"], default="update",
                        help="وضع التحديث: update لتغيير السنة أو strip لحذفها")
    parser.add_argument("--confirm", action="store_true",
                        help="تأكيد التحديث ونشره لايف على بلوجر (بدون هذا الخيار يعمل كـ dry-run)")
    parser.add_argument("--max-posts", type=int, default=2500,
                        help="أقصى عدد مقالات لفحصها لكل موقع")
    args = parser.parse_args()

    targets = list(SITES.keys()) if args.site == "all" else [args.site]
    all_results = {}

    for s_key in targets:
        records = run_rollover(
            site_key=s_key,
            from_yr=args.from_year,
            to_yr=args.to_year,
            mode=args.mode,
            confirm=args.confirm,
            max_posts=args.max_posts
        )
        all_results[s_key] = records

    # Save audit log
    log_file = "year_rollover_log.json"
    log_data = {
        "timestamp": now_cairo.isoformat(),
        "from_year": args.from_year,
        "to_year": args.to_year,
        "mode": args.mode,
        "confirmed": args.confirm,
        "summary": {s: len(r) for s, r in all_results.items()},
        "records": {
            s: [
                {
                    "id": item["id"],
                    "url": item["url"],
                    "orig_title": item["orig_title"],
                    "new_title": item["new_title"],
                    "title_changes": item["title_changes"],
                    "body_changes": item["body_changes"]
                }
                for item in r
            ]
            for s, r in all_results.items()
        }
    }
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    print(f"\n📁 تم حفظ سجل التحديث بالكامل في {log_file}")

    # GitHub Step Summary output if running in Actions
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as sm:
            sm.write(f"## 🎆 تقرير تحديث مقالات العام الجديد ({args.from_year} ➔ {args.to_year})\n\n")
            sm.write(f"- **تاريخ التشغيل:** `{now_cairo.strftime('%Y-%m-%d %H:%M:%S')}` (توقيت القاهرة)\n")
            sm.write(f"- **الوضع:** `{args.mode}` | **حالة النشر:** `{'✅ لايف (مؤكد)' if args.confirm else '🔍 تجريبي (Dry Run)'}`\n\n")
            
            for s_key, recs in all_results.items():
                s_name = SITES[s_key]["name"]
                sm.write(f"### موقع {s_name} ({len(recs)} مقال)\n\n")
                if not recs:
                    sm.write("لا توجد مقالات بحاجة لتعديل السنة.\n\n")
                    continue
                sm.write("| # | العنوان السابق | العنوان الجديد | الرابط |\n")
                sm.write("|---|---|---|---|\n")
                for i, r in enumerate(recs[:50], 1):
                    sm.write(f"| {i} | {r['orig_title']} | {r['new_title']} | [عرض المقال]({r['url']}) |\n")
                if len(recs) > 50:
                    sm.write(f"\n*(يوجد {len(recs) - 50} مقال آخر مسجل في ملف السجل)*\n\n")


if __name__ == "__main__":
    main()
