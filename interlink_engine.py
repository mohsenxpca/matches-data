# -*- coding: utf-8 -*-
"""Autonomous Smart Contextual Interlinking Engine for GitHub Actions & Local Runs.
Mohsen 2026 - Comprehensive Internal Linking & Anchor Text Architecture.

Key Capabilities:
1. Cleans bad/generic anchors (e.g., 'قواعد اللعبة', 'مللي أمبير', 'مليون دولار', 'الهاتف الجديد') and replaces them with real, descriptive target titles.
2. Weaves articles into strict topical silos (Phones to Phones, Housing to Housing, Sports to Sports, Banking to Banking).
3. Ensures every article has at least 2 relevant article links + 1 service hub link.
4. Preserves Blogger formatting, slugs, dates, and layouts via Blogger PATCH API.
"""
import argparse, datetime, io, json, os, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
from pathlib import Path
from bs4 import BeautifulSoup
import requests

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

BLOGS = {
    "review": {
        "blog_id": "2997328666613207792",
        "domain": "www.review-mobile.com",
        "hubs": [
            ("https://www.review-mobile.com/p/compare-phones_01466757070.html", "أداة مقارنة الهواتف الذكية راس براس"),
            ("https://www.review-mobile.com/p/best-phone-for-budget.html", "دليل أفضل هواتف للشراء حسب الميزانية"),
            ("https://www.review-mobile.com/p/mobile-reviews-hub.html", "فهرس مراجعات ومواصفات الهواتف")
        ]
    },
    "egyptaway": {
        "blog_id": "8325646053257070334",
        "domain": "www.egyptaway.com",
        "hubs": [
            ("https://www.egyptaway.com/p/mobile-prices-egypt.html", "جدول أسعار الموبايلات المحدث في مصر"),
            ("https://www.egyptaway.com/p/gold-prices-egypt.html", "أسعار الذهب اليوم في مصر عيار 21"),
            ("https://www.egyptaway.com/p/currency-prices-egypt.html", "أسعار العملات والدولار في البنوك المصرية"),
            ("https://www.egyptaway.com/p/matches-today.html", "جدول مواعيد مباريات اليوم والقنوات الناقلة"),
            ("https://www.egyptaway.com/p/egyptian-league-table.html", "جدول ترتيب الدوري المصري الممتاز"),
            ("https://www.egyptaway.com/p/bank-certificates-egypt.html", "حاسبة أرباح وفوائد شهادات البنوك المصرية"),
            ("https://www.egyptaway.com/p/housing-egypt.html", "دليل طروحات الإسكان الاجتماعي وبوابة مسكن"),
            ("https://www.egyptaway.com/p/download-games.html", "دليل تحميل وتنزيل الألعاب الرسمية")
        ]
    }
}

GENERIC_BAD_ANCHORS = {
    "قواعد اللعبة", "الهاتف الجديد", "مللي أمبير", "مليون دولار", "إطلاق هاتف",
    "Snapdragon", "شاشة AMOLED", "هواتف أندرويد", "قدرات الشحن", "اتصالات e",
    "شاشة بمعدل", "عطل مفاجئ", "تحديث جديد", "في مصر", "يغير قواعد اللعبة",
    "قواعد المنافسة", "مللي أمبير وشحن", "شاشة كبيرة", "أداء قوي", "معالج قوي",
    "بطارية ضخمة", "كاميرا احترافية", "سعر منافس", "الفئة المتوسطة", "الفئة الاقتصادية"
}

TRAILING_TRIM = {"في", "من", "إلى", "على", "عن", "مع", "أو", "ثم", "هل", "ما", "كل", "إن", "أن", "بعد", "قبل", "بين", "حول"}


def clean_title_for_anchor(title):
    t = title.strip()
    t = re.sub(r'^(?:تسريب|تسريبات|مفاجأة|عاجل|رسمياً|بالأرقام|تفاصيل|خاص|شاهد|تقرير|بالفيديو)[:\.\s\-]+', '', t)
    t = re.sub(r'[\.\s\-\:؟\?]+$', '', t)
    t = re.sub(r'[\.\s\-]+(?:التفاصيل|التفاصيل الكاملة|تعرف عليها|هل يستحق؟|ما القصة؟|كل ما تريد معرفته)$', '', t)
    t = t.strip()
    if len(t) > 55:
        words = t[:55].split()
        if len(words) > 1:
            words = words[:-1]
        while words and words[-1] in TRAILING_TRIM:
            words.pop()
        t = " ".join(words)
    return re.sub(r'[\.\s\-\:؟\?]+$', '', t).strip()


def extract_phone_brand_or_topic(title, labels):
    t_lower = title.lower()
    for b in ["samsung", "سامسونج", "apple", "iphone", "آيفون", "ايفون", "أبل", "ابل",
              "xiaomi", "شاومي", "redmi", "ريدمي", "poco", "بوكو", "oppo", "أوبو", "اوبو",
              "vivo", "فيفو", "iqoo", "آيكو", "honor", "هونر", "realme", "ريلمي",
              "huawei", "هواوي", "oneplus", "ون بلس", "infinix", "إنفينكس", "tecno", "تكنو",
              "motorola", "موتورولا", "pixel", "بيكسل"]:
        if b in t_lower or any(b in l.lower() for l in labels):
            return b
    for l in labels:
        if l in ["أخبار الكورة", "الدوري المصري", "رياضة", "اقتصاد", "خدمات", "ألعاب", "أخبار تقنية"]:
            return l
    return "general"


def secret(name):
    return os.environ.get(name, "").strip().strip(",").strip().strip('"').strip("'").strip()


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
        print(f"Warning: OAuth refresh failed with status {r.status_code}: {r.text[:100]}")

    for candidate in [
        r"C:\Users\H\Documents\blogger-pipeline\token.json",
        os.path.join(os.path.dirname(__file__), "token.json"),
        os.path.join(os.path.dirname(__file__), "..", "blogger-pipeline", "token.json")
    ]:
        if os.path.exists(candidate):
            try:
                data = json.load(open(candidate, "r", encoding="utf-8"))
                if "access_token" in data:
                    return data["access_token"]
            except Exception:
                pass

    print("⚠️ [Google OAuth / Blogger Quota] Could not obtain Blogger API access token. Skipping peacefully.")
    sys.exit(0)


_FRESH_TOK = {}


def api_call(method, path, tok, params=None, body=None):
    def call(t):
        for i in range(3):
            try:
                r = requests.request(method, "https://www.googleapis.com/blogger/v3" + path, params=params, json=body,
                                     headers={"Authorization": "Bearer " + t}, timeout=60)
                if r.status_code < 500 or i == 2 or method == "POST":
                    return r
            except requests.ConnectionError:
                if i == 2: raise
            time.sleep(3 * (i + 1))
    r = call(_FRESH_TOK.get(tok, tok))
    if r.status_code == 401:
        _FRESH_TOK[tok] = get_token()
        r = call(_FRESH_TOK[tok])
    return r


def fetch_live_posts(tok, blog_id, max_posts=600, fetch_bodies=False):
    posts, page = [], None
    while len(posts) < max_posts:
        q = {"maxResults": min(100, max_posts - len(posts)), "status": "live", "fetchBodies": "true" if fetch_bodies else "false"}
        if page: q["pageToken"] = page
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
    return posts


def select_related_articles(post_url, post_title, post_labels, catalog, limit=2):
    brand_or_topic = extract_phone_brand_or_topic(post_title, post_labels)
    candidates = []
    clean_purl = post_url.split("?")[0]

    for other in catalog:
        o_url = other.get("url", "").split("?")[0]
        if not o_url or o_url == clean_purl:
            continue
        o_title = other.get("title", "")
        o_labels = other.get("labels", [])
        o_topic = extract_phone_brand_or_topic(o_title, o_labels)

        score = 0
        if brand_or_topic != "general" and o_topic == brand_or_topic:
            score += 10
        shared_labels = set(post_labels) & set(o_labels)
        score += len(shared_labels) * 3
        if "2026" in o_url:
            score += 2

        candidates.append((score, o_url, o_title))

    candidates.sort(key=lambda x: -x[0])
    selected = []
    for score, u, t in candidates:
        if len(selected) >= limit:
            break
        selected.append((u, clean_title_for_anchor(t)))
    return selected


def fix_and_interlink_post(content, post_url, post_title, post_labels, site_key, catalog_by_url, catalog):
    domain = BLOGS[site_key]["domain"]
    hubs = BLOGS[site_key]["hubs"]

    soup = BeautifulSoup(content, "html.parser")
    modified = False
    fixes_made = []

    clean_post_url = post_url.split("?")[0]

    # 1. FIX BAD ANCHORS
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if domain in href and href != clean_post_url:
            txt = a.get_text(strip=True)
            is_bad = False
            for bad in GENERIC_BAD_ANCHORS:
                if bad.lower() == txt.lower() or (len(txt) < 4 and not txt.isdigit()):
                    is_bad = True
                    break
            if is_bad:
                dest_post = catalog_by_url.get(href)
                if dest_post:
                    better_anchor = clean_title_for_anchor(dest_post.get("title", ""))
                    if len(better_anchor) >= 5:
                        a.string = better_anchor
                        modified = True
                        fixes_made.append(f"Fixed bad anchor '{txt}' -> '{better_anchor}'")

    # 2. CHECK EXISTING ARTICLE LINKS
    existing_article_urls = set()
    existing_hub_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if domain in href and href != clean_post_url:
            if re.search(r"/\d{4}/\d{2}/", href):
                existing_article_urls.add(href)
            elif "/p/" in href:
                existing_hub_urls.add(href)

    # 3. IF LESS THAN 2 ARTICLE LINKS, INJECT RELEVANT LINKS
    needed_articles = max(0, 2 - len(existing_article_urls))
    if needed_articles > 0:
        candidates = select_related_articles(post_url, post_title, post_labels, catalog, limit=needed_articles + 2)
        injected = 0

        insert_target = soup.find("details") or soup.find("h3", string=re.compile(r"أسئلة شائعة|المصادر|الأسئلة الشائعة"))
        if not insert_target:
            p_tags = soup.find_all("p")
            if p_tags:
                insert_target = p_tags[-1]

        for u, anchor_text in candidates:
            if u in existing_article_urls or u == clean_post_url:
                continue
            if injected >= needed_articles:
                break

            callout = soup.new_tag("p", attrs={
                "class": "ea-rel-link",
                "style": "background:#f8fafc;padding:12px 16px;border-right:4px solid #2563eb;border-radius:6px;margin:18px 0;font-size:15px;line-height:1.75;"
            })
            callout.append("💡 ")
            strong = soup.new_tag("strong")
            strong.string = "موضوعات ذات صلة: "
            callout.append(strong)
            callout.append("يمكنك أيضاً قراءة ")
            new_a = soup.new_tag("a", href=u, attrs={"style": "color:#2563eb;font-weight:700;text-decoration:underline;"})
            new_a.string = anchor_text
            callout.append(new_a)
            callout.append(" لمتابعة كافة التفاصيل والتحديثات الرسمية.")

            if insert_target:
                insert_target.insert_before(callout)
            else:
                soup.append(callout)

            existing_article_urls.add(u)
            injected += 1
            modified = True
            fixes_made.append(f"Injected related article: '{anchor_text}' -> {u}")

    # 4. IF 0 HUB LINKS, INJECT A RELEVANT HUB LINK
    if len(existing_hub_urls) == 0 and hubs:
        best_hub = hubs[0]
        if site_key == "egyptaway":
            if any(k in post_title for k in ["ذهب", "صاغة", "عيار"]):
                best_hub = hubs[1]
            elif any(k in post_title for k in ["دولار", "عملات", "صرف"]):
                best_hub = hubs[2]
            elif any(k in post_title for k in ["مباراة", "دوري", "الأهلي", "الزمالك", "كورة"]):
                best_hub = hubs[3]
            elif any(k in post_title for k in ["شهادة", "بنك", "فائدة"]):
                best_hub = hubs[5]
            elif any(k in post_title for k in ["إسكان", "شقق", "سكن لكل المصريين"]):
                best_hub = hubs[6]
            elif any(k in post_title for k in ["لعبة", "تحميل", "العاب", "شحن"]):
                best_hub = hubs[7]
            else:
                best_hub = hubs[0]
        hub_url, hub_name = best_hub
        hub_card = soup.new_tag("p", attrs={
            "class": "ea-hub-link",
            "style": "background:#f1f5f9;padding:10px 14px;border-right:4px solid #0f172a;border-radius:6px;margin:16px 0;font-size:14px;"
        })
        hub_card.append("🔍 ")
        h_strong = soup.new_tag("strong")
        h_strong.string = "خدمة مميزة: "
        hub_card.append(h_strong)
        hub_card.append("تفضل بزيارة ")
        ha = soup.new_tag("a", href=hub_url, attrs={"style": "color:#0f172a;font-weight:700;text-decoration:underline;"})
        ha.string = hub_name
        hub_card.append(ha)
        hub_card.append(" للاطلاع على الجداول والتحديثات اليومية الحية.")

        soup.append(hub_card)
        existing_hub_urls.add(hub_url)
        modified = True
        fixes_made.append(f"Injected service hub link: '{hub_name}' -> {hub_url}")

    return str(soup) if modified else None, fixes_made


def run_pipeline(site_key="egyptaway", days=1, confirm=False, all_missing=False, backup_dir="backups"):
    conf = BLOGS.get(site_key)
    if not conf:
        sys.exit(f"Unknown site: {site_key}")
    blog_id = conf["blog_id"]
    domain = conf["domain"]

    print(f"\n=======================================================")
    print(f"Starting Smart Contextual Interlinking for {site_key} ({domain})")
    print(f"Mode: {'CONFIRM (Updating Blogger Live)' if confirm else 'DRY RUN (Preview only)'}")
    print(f"Target: {'All missing live posts' if all_missing else f'Posts from last {days} day(s)'}")
    print(f"=======================================================")

    tok = get_token()

    print("Fetching live posts catalog for entity indexing...")
    catalog = fetch_live_posts(tok, blog_id, max_posts=600, fetch_bodies=False)
    print(f"Catalog size: {len(catalog)} live posts.")

    catalog_by_url = {p.get("url", "").split("?")[0]: p for p in catalog}

    today = datetime.datetime.now(CAIRO).date()
    since_date = (today - datetime.timedelta(days=days)).isoformat()

    print(f"Fetching posts to evaluate (since: {since_date if not all_missing else 'ALL'})...")
    target_posts = []
    page = None
    target_limit = 500 if all_missing else max(50, days * 30)
    while len(target_posts) < target_limit:
        q = {"maxResults": min(100, target_limit - len(target_posts)), "status": "live", "fetchBodies": "true"}
        if page: q["pageToken"] = page
        r = api_call("GET", f"/blogs/{blog_id}/posts", tok, params=q)
        if r.status_code != 200: break
        items = r.json().get("items", [])
        for item in items:
            pub = item.get("published", "")[:10]
            if all_missing or pub >= since_date:
                target_posts.append(item)
            elif not all_missing and pub < since_date:
                page = None
                break
        page = r.json().get("nextPageToken")
        if not page or not items: break

    print(f"Found {len(target_posts)} post candidate(s) to check.")

    os.makedirs(backup_dir, exist_ok=True)
    today_str = today.isoformat()
    backup_file = os.path.join(backup_dir, f"interlink_backup_{site_key}_{today_str}.json")

    backups = []
    updated_count = 0
    total_fixes = 0
    log_entries = []

    for post in target_posts:
        pid = post.get("id")
        purl = post.get("url", "").split("?")[0]
        ptitle = post.get("title", "")
        pcontent = post.get("content", "")
        plabels = post.get("labels", [])
        pub_date = post.get("published", "")[:10]

        new_html, fixes = fix_and_interlink_post(pcontent, purl, ptitle, plabels, site_key, catalog_by_url, catalog)
        if not new_html or not fixes:
            continue

        print(f"\n[+] Post: {ptitle} ({pub_date})")
        print(f"    URL: {purl}")
        for fix in fixes:
            print(f"      • {fix}")

        backups.append({
            "id": pid,
            "url": purl,
            "title": ptitle,
            "published": post.get("published"),
            "content": pcontent
        })

        if confirm:
            patch_res = api_call("PATCH", f"/blogs/{blog_id}/posts/{pid}", tok, body={"content": new_html})
            if patch_res.status_code == 200:
                print("      ✓ Updated on Blogger successfully.")
                updated_count += 1
                total_fixes += len(fixes)
                log_entries.append({
                    "id": pid,
                    "url": purl,
                    "title": ptitle,
                    "at": datetime.datetime.now(CAIRO).isoformat(),
                    "fixes": fixes
                })
            else:
                print(f"      ❌ Blogger API Error ({patch_res.status_code}): {patch_res.text[:120]}")
            time.sleep(0.5)

    if backups and confirm:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backups, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Saved full backup of {len(backups)} post(s) to: {backup_file}")

    state_file = "interlink_posted.json"
    if confirm and log_entries:
        existing_done = []
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing_done = loaded.get("done", [])
                elif isinstance(loaded, list):
                    existing_done = loaded
            except Exception:
                pass
        if not isinstance(existing_done, list):
            existing_done = []
        existing_done.extend(log_entries)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"done": existing_done[-500:]}, f, ensure_ascii=False, indent=1)

    print(f"\n=======================================================")
    print(f"Summary for {site_key}:")
    print(f"  • Posts modified: {updated_count}")
    print(f"  • Total fixes/links applied: {total_fixes}")
    print(f"=======================================================\n")
    return updated_count, total_fixes


def parse_days(val):
    try:
        d = int(val)
        return d if d > 0 else 1
    except (ValueError, TypeError):
        return 1


def main():
    parser = argparse.ArgumentParser(description="Autonomous Smart Contextual Interlinking Engine")
    parser.add_argument("--site", choices=["egyptaway", "review", "all"], default="egyptaway", help="Target site")
    parser.add_argument("--days", type=parse_days, default=1, help="Evaluate posts published within the last N days (default: 1)")
    parser.add_argument("--all-missing", action="store_true", help="Scan all live posts on the site with < 2 internal links")
    parser.add_argument("--confirm", action="store_true", help="Apply updates to Blogger (default: dry run)")
    parser.add_argument("--dry", action="store_true", help="Force dry run (no changes)")
    args = parser.parse_args()

    confirm_mode = args.confirm and not args.dry

    if args.site == "all":
        for s in ["egyptaway", "review"]:
            run_pipeline(site_key=s, days=args.days, confirm=confirm_mode, all_missing=args.all_missing)
    else:
        run_pipeline(site_key=args.site, days=args.days, confirm=confirm_mode, all_missing=args.all_missing)


if __name__ == "__main__":
    main()
