"""Autonomous In-Text Contextual Internal Linking Engine (mohsen 2026-11-02).
Runs daily on GitHub Actions (and locally) to weave all site articles into a fully
crawlable internal linking mesh for Google Search Console and SEO topical authority.

Strict contextual anchor text inside body paragraphs (<p>):
- Never inserts 'مقالات قد تهمك' or generic blocks; links directly on natural topical phrases.
- Links to permanent high-value service hubs (League table, matches, gold, currency, prayer, weather).
- Links cross-articles to relevant live articles covering the same topic/entity.
- Preserves all dates, URLs, slugs, labels, and formatting via Blogger PATCH.

Usage:
  python interlink_engine.py                         # Runs on yesterday's posts (dry run by default)
  python interlink_engine.py --days 1 --confirm      # Injects links in yesterday's posts and updates live
  python interlink_engine.py --all-missing --confirm # Scans all live posts on site and fixes posts with < 2 links
"""
import argparse, datetime, difflib, io, json, os, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

SITES = {
    "egyptaway": {
        "blog_id": "8325646053257070334",
        "domain": "www.egyptaway.com",
        "hubs": [
            {
                "url": "https://www.egyptaway.com/p/egyptian-league-table.html",
                "anchors": ["جدول ترتيب الدوري المصري", "ترتيب الدوري المصري", "جدول الدوري المصري", "الدوري المصري الممتاز", "الدوري المصري"],
                "topic": "sports"
            },
            {
                "url": "https://www.egyptaway.com/p/matches-today.html",
                "anchors": ["مواعيد مباريات اليوم", "جدول مباريات اليوم", "مباريات اليوم", "مباريات الليلة"],
                "topic": "sports"
            },
            {
                "url": "https://www.egyptaway.com/p/gold-prices-egypt.html",
                "anchors": ["أسعار الذهب اليوم في مصر", "أسعار الذهب في مصر", "سعر الذهب اليوم", "سعر جرام الذهب", "عيار 21", "سعر الذهب", "أسعار الذهب"],
                "topic": "economy"
            },
            {
                "url": "https://www.egyptaway.com/p/currency-prices-egypt.html",
                "anchors": ["أسعار العملات في مصر", "سعر الدولار اليوم في مصر", "أسعار الدولار في البنوك", "سعر الدولار اليوم", "سعر الدولار في مصر", "سعر الدولار", "أسعار العملات"],
                "topic": "economy"
            },
            {
                "url": "https://www.egyptaway.com/p/prayer-times-egypt.html",
                "anchors": ["مواقيت الصلاة في مصر", "مواقيت الصلاة اليوم", "مواعيد الصلاة في مصر", "مواقيت الصلاة"],
                "topic": "services"
            },
            {
                "url": "https://www.egyptaway.com/p/weather-egypt.html",
                "anchors": ["حالة الطقس في مصر", "درجات الحرارة المتوقعة في مصر", "هيئة الأرصاد الجوية", "حالة الطقس اليوم", "حالة الطقس", "درجات الحرارة المتوقعة"],
                "topic": "services"
            },
            {
                "url": "https://www.egyptaway.com/p/official-holidays-egypt.html",
                "anchors": ["الإجازات الرسمية في مصر", "مواعيد الإجازات الرسمية", "العطلات الرسمية في مصر", "الإجازات الرسمية"],
                "topic": "services"
            },
            {
                "url": "https://www.egyptaway.com/p/ramadan-imsakia-egypt.html",
                "anchors": ["إمساكية شهر رمضان", "إمساكية رمضان في مصر", "إمساكية رمضان"],
                "topic": "services"
            },
            {
                "url": "https://www.egyptaway.com/p/mobile-prices-egypt.html",
                "anchors": ["أسعار الموبايلات في مصر", "أسعار الهواتف في مصر", "جدول أسعار الموبايلات", "أسعار الموبايلات اليوم"],
                "topic": "tech"
            },
            {
                "url": "https://www.egyptaway.com/p/compare-phones.html",
                "anchors": ["مقارنة شاملة بين الموبايلات", "مقارنة الهواتف راس براس", "أداة مقارنة الموبايلات", "مقارنة بين هاتفين"],
                "topic": "tech"
            },
            {
                "url": "https://www.egyptaway.com/p/best-phone-for-budget.html",
                "anchors": ["أفضل موبايل لميزانيتك", "أحسن موبايل في الفئة المتوسطة", "أفضل هاتف للشراء", "ترشيحات الهواتف"],
                "topic": "tech"
            },
            {
                "url": "https://www.egyptaway.com/p/download-games.html",
                "anchors": ["تحميل ألعاب موبايل وكمبيوتر", "تنزيل ألعاب رسمية", "تحميل ألعاب الأندرويد", "تحميل ألعاب"],
                "topic": "games"
            },
            {
                "url": "https://www.egyptaway.com/p/pubg-uc-freefire-diamonds-prices.html",
                "anchors": ["أسعار شدات ببجي", "شحن شدات ببجي", "شحن جواهر فري فاير", "أسعار جواهر فري فاير"],
                "topic": "games"
            },
            {
                "url": "https://www.egyptaway.com/p/make-money-online-egypt.html",
                "anchors": ["طرق الربح من الإنترنت", "الربح من الموبايل", "الربح من الإنترنت في مصر", "الربح فودافون كاش"],
                "topic": "economy"
            },
            {
                "url": "https://www.egyptaway.com/p/ai-tools-arabic-guide.html",
                "anchors": ["أدوات الذكاء الاصطناعي", "مواقع الذكاء الاصطناعي المجانية", "تطبيقات الذكاء الاصطناعي"],
                "topic": "tech"
            },
            {
                "url": "https://www.egyptaway.com/p/instapay-fees-calculator.html",
                "anchors": ["حاسبة رسوم إنستاباي", "رسوم تحويل إنستاباي", "تطبيق إنستاباي", "الحد الأقصى للتحويل في إنستاباي"],
                "topic": "economy"
            },
            {
                "url": "https://www.egyptaway.com/p/is-it-down-egypt.html",
                "anchors": ["صفحة رصد الأعطال", "رصد الأعطال في مصر", "عطل فودافون", "عطل إنستاباي"],
                "topic": "services"
            },
            {
                "url": "https://www.egyptaway.com/p/bank-certificates-egypt.html",
                "anchors": ["شهادات البنوك المصرية", "أعلى عائد شهادات ادخار", "شهادات البنك الأهلي وبنك مصر"],
                "topic": "economy"
            },
            {
                "url": "https://www.egyptaway.com/p/fuel-prices-egypt.html",
                "anchors": ["أسعار البنزين والسولار", "أسعار البنزين اليوم في مصر", "لجنة التسعير التلقائي للوقود"],
                "topic": "economy"
            },
            {
                "url": "https://www.egyptaway.com/p/housing-egypt.html",
                "anchors": ["شقق الإسكان الاجتماعي", "سكن لكل المصريين", "كراسة شروط الإسكان"],
                "topic": "services"
            },
            {
                "url": "https://www.egyptaway.com/p/trains-egypt.html",
                "anchors": ["مواعيد القطارات", "قطارات السكة الحديد", "حجز تذاكر القطارات"],
                "topic": "services"
            },
            {
                "url": "https://www.egyptaway.com/p/salaries-egypt.html",
                "anchors": ["مواعيد صرف المرتبات", "جدول صرف المرتبات", "تبكير صرف المرتبات"],
                "topic": "economy"
            },
            {
                "url": "https://www.egyptaway.com/p/exams-egypt.html",
                "anchors": ["جداول الامتحانات", "نتائج الامتحانات", "موعد امتحانات نصف العام"],
                "topic": "services"
            }
        ]
    },
    "review": {
        "blog_id": "2997328666613207792",
        "domain": "www.review-mobile.com",
        "hubs": [
            {
                "url": "https://www.review-mobile.com/p/compare-phones_01466757070.html",
                "anchors": ["مقارنة شاملة بين الموبايلات", "مقارنة الهواتف راس براس", "أداة مقارنة الموبايلات", "مقارنة بين هاتفين"],
                "topic": "tech"
            },
            {
                "url": "https://www.review-mobile.com/p/best-phone-for-budget.html",
                "anchors": ["أفضل موبايل لميزانيتك", "أحسن موبايل في الفئة المتوسطة", "ترشيحات الهواتف حسب السعر", "أفضل هاتف للشراء"],
                "topic": "tech"
            },
            {
                "url": "https://www.review-mobile.com/p/mobile-reviews-hub.html",
                "anchors": ["دليل مراجعات الموبايلات", "مقارنة مواصفات الهواتف", "مراجعات الهواتف الذكية"],
                "topic": "tech"
            }
        ]
    }
}

ALLOWED_SINGLE_EN_WORDS = {
    "whatsapp", "minecraft", "fortnite", "roblox", "chatgpt", "gemini",
    "android", "iphone", "xiaomi", "samsung", "playstation", "rockstar",
    "efootball", "brawl", "binance", "windows", "chrome", "firefox", "steam"
}

GENERIC_BANNED = {
    "الباب أمام", "بشكل رسمي", "الخاص بك", "ما تحتاج", "كيفية عمل", "مصر والوطن العربي",
    "الخدمات المقدمة", "في الختام", "الجدير بالذكر", "من جانب آخر", "خطوات آمنة", "ألعابك المفضلة",
    "في سطرين", "كل ما تريد", "تعرف على", "التي تم", "التي كانت", "هذا المقال", "خلال الفترة",
    "في الوقت", "على مستوى", "من خلال", "في ظل", "من أجل", "على الرغم", "في حين", "إلى جانب",
    "عبر الإنترنت", "في مصر", "في العالم", "حول العالم", "بشكل عام", "دون الحاجة", "كل ما يخص",
    "مليار دولار", "مليون جنيه", "ألف جنيه", "دولار أمريكي", "شهريا", "سنويا", "يوميا"
}

TOPICAL_KEYWORDS = [
    "دوري", "مباراة", "مباريات", "أهلي", "اهلي", "زمالك", "منتخب", "صلاح", "مرموش", "كولر", "جوميز",
    "ذهب", "دولار", "عملات", "صلاة", "طقس", "أرصاد", "حرارة", "إجازات", "مرتبات", "معاشات", "تموين",
    "سكن", "إسكان", "شروط", "أكتوبر", "بدر", "شهادات", "بنك", "فائدة", "قطارات", "مترو",
    "لعبة", "ألعاب", "تحميل", "كود", "تحديث", "شحن", "ببجي", "فورتنايت", "ماينكرافت", "جاتا",
    "هاتف", "موبايل", "أندرويد", "آيفون", "سامسونج", "شاومي", "واتساب", "تطبيق", "ذكاء اصطناعي", "كروم"
]

STOP_WORDS = {
    "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "تم", "كان", "كانت", "أو", "ثم", "كل", "بعد", "قبل",
    "اليوم", "الآن", "رسمياً", "عاجل", "جديد", "أحدث", "أفضل", "أول", "2026", "2025", "2024",
    "الخلاصة", "سطرين", "تفاصيل", "تعرف", "مفاجأة", "كيف", "لماذا", "هل", "شاهد", "بالفيديو", "مقارنة", "شاملة", "مراجعة",
    "of", "the", "in", "on", "at", "to", "for", "and", "with", "from"
}


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


def is_topical_anchor(phrase):
    phrase = phrase.strip()
    if re.fullmatch(r'\d+', phrase):
        return False
    if len(phrase) < 4:
        return False
    # No dates with numbers (e.g. 29 أكتوبر)
    months_days = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
                   "السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
    if any(m in phrase for m in months_days) and re.search(r'\d+', phrase):
        return False
    # No numbers + time/period words
    if re.search(r'\b\d+\s*(مباراة|مباريات|أيام|يوم|شهور|شهر|سنة|سنوات|ساعات|ساعة|دقائق|دقيقة)\b', phrase):
        return False
    if phrase in GENERIC_BANNED:
        return False

    # English phrases
    if re.search(r'[A-Za-z]', phrase):
        # Single English word
        if " " not in phrase:
            return phrase.lower() in ALLOWED_SINGLE_EN_WORDS
        # Multi-word English phrase: must be specific (e.g. Call of Duty, Modern Warfare, GTA 6)
        return len(phrase) >= 5

    # Arabic topical filter
    return any(k in phrase for k in TOPICAL_KEYWORDS)


def build_entity_map(posts):
    entity_to_posts = {}
    for p in posts:
        u = p.get("url", "").split("?")[0]
        t = p.get("title", "")
        pub = p.get("published", "")[:10]
        labels = p.get("labels", [])
        words = re.findall(r'[\w\u0621-\u064A]+', t)
        
        # 2-word, 3-word n-grams from title
        for n in (3, 2):
            for i in range(len(words) - n + 1):
                ngram = words[i:i+n]
                if ngram[0] in STOP_WORDS or ngram[-1] in STOP_WORDS:
                    continue
                phrase = " ".join(ngram)
                if is_topical_anchor(phrase):
                    entity_to_posts.setdefault(phrase, []).append((u, t, pub, labels))
                    
        # Distinct proper nouns
        for w in words:
            if len(w) >= 4 and not w.isdigit():
                if w.lower() in ALLOWED_SINGLE_EN_WORDS:
                    entity_to_posts.setdefault(w, []).append((u, t, pub, labels))
                elif w in {"الزمالك", "الأهلي", "ليفربول", "برشلونة", "مرموش", "كولر", "جوميز", "واتساب", "ماينكرافت", "فورتنايت", "روبلوكس"}:
                    entity_to_posts.setdefault(w, []).append((u, t, pub, labels))
                    
    return entity_to_posts


def inject_anchor_in_soup(soup, anchor_phrase, target_url):
    pattern = re.compile(rf"(?<![\w\u0621-\u064A])({re.escape(anchor_phrase)})(?![\w\u0621-\u064A])", re.IGNORECASE)
    for p in soup.find_all("p"):
        if p.find_parent(["nav", "footer", "header", "details", "table"]):
            continue
        for text_node in list(p.find_all(string=True)):
            if text_node.parent.name in ["a", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6", "button", "input"]:
                continue
            text = str(text_node)
            m = pattern.search(text)
            if m:
                start, end = m.span()
                before = text[:start]
                matched = text[start:end]
                after = text[end:]
                
                new_nodes = []
                if before:
                    new_nodes.append(soup.new_string(before))
                new_a = soup.new_tag("a", href=target_url)
                new_a.string = matched
                new_nodes.append(new_a)
                if after:
                    new_nodes.append(soup.new_string(after))
                
                curr = text_node
                for n in new_nodes:
                    curr.insert_after(n)
                    curr = n
                text_node.extract()
                return True
    return False


def link_article(html_content, post_url, entity_map, hubs, domain, post_title="", max_links=3):
    soup = BeautifulSoup(html_content, "html.parser")
    existing_hrefs = {a.get("href", "").split("?")[0] for a in soup.find_all("a") if a.get("href")}
    
    current_internal = len([h for h in existing_hrefs if domain in h and h != post_url])
    if current_internal >= max_links:
        return None, 0, []

    planned_links = []
    used_urls = set(existing_hrefs) | {post_url}
    used_anchors = set()
    full_text = soup.get_text(" ", strip=True)

    # 1. Match Hubs
    for hub in hubs:
        if current_internal >= max_links:
            break
        if hub["url"] in used_urls or hub["url"] == post_url:
            continue
        # Context guard for sports hubs
        if hub.get("topic") == "sports":
            if not any(k in full_text for k in ["دوري", "مباراة", "الأهلي", "الزمالك", "كأس", "كرة", "منتخب"]):
                continue
        for anchor in sorted(hub["anchors"], key=lambda a: -len(a)):
            if anchor in used_anchors:
                continue
            if inject_anchor_in_soup(soup, anchor, hub["url"]):
                used_urls.add(hub["url"])
                used_anchors.add(anchor)
                current_internal += 1
                planned_links.append((anchor, hub["url"], "صفحة خدمية ثابتة"))
                break

    # 2. Match Cross-Article Entities
    sorted_entities = sorted(entity_map.keys(), key=lambda x: -len(x))
    for ent in sorted_entities:
        if current_internal >= max_links:
            break
        if ent in used_anchors or not is_topical_anchor(ent):
            continue
        
        # Category check for sports club names like الأهلي / الزمالك
        if ent in {"الأهلي", "الزمالك", "ليفربول", "برشلونة", "ريال مدريد"}:
            if not any(k in full_text for k in ["دوري", "مباراة", "كأس", "كرة", "رياضة", "منتخب", "لاعب"]):
                continue

        candidates = [c for c in entity_map[ent] if c[0] not in used_urls and c[0] != post_url]
        if not candidates:
            continue
        target_url, target_title, target_pub, target_labels = candidates[0]
        if inject_anchor_in_soup(soup, ent, target_url):
            used_urls.add(target_url)
            used_anchors.add(ent)
            current_internal += 1
            planned_links.append((ent, target_url, target_title))

    if not planned_links:
        return None, 0, []

    return str(soup), len(planned_links), planned_links


def run_pipeline(site_key="egyptaway", days=1, confirm=False, all_missing=False, backup_dir="backups"):
    conf = SITES.get(site_key)
    if not conf:
        sys.exit(f"Unknown site: {site_key}")
    blog_id = conf["blog_id"]
    domain = conf["domain"]
    hubs = conf["hubs"]

    print(f"\n=======================================================")
    print(f"Starting Contextual Interlinking for {site_key} ({domain})")
    print(f"Mode: {'CONFIRM (Updating Blogger)' if confirm else 'DRY RUN (Preview only)'}")
    print(f"Target: {'All missing live posts' if all_missing else f'Posts from last {days} day(s)'}")
    print(f"=======================================================")

    tok = get_token()

    print("Fetching live posts catalog for entity indexing...")
    catalog = fetch_live_posts(tok, blog_id, max_posts=600, fetch_bodies=False)
    print(f"Catalog size: {len(catalog)} live posts.")

    entity_map = build_entity_map(catalog)
    print(f"Indexed {len(entity_map)} topical entity phrases.")

    today = datetime.datetime.now(CAIRO).date()
    since_date = (today - datetime.timedelta(days=days)).isoformat()

    print(f"Fetching posts to evaluate (since: {since_date if not all_missing else 'ALL'})...")
    target_posts = []
    page = None
    target_limit = 500 if all_missing else max(50, days * 25)
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
    total_links_injected = 0
    log_entries = []

    for post in target_posts:
        pid = post.get("id")
        purl = post.get("url", "").split("?")[0]
        ptitle = post.get("title", "")
        pcontent = post.get("content", "")
        pub_date = post.get("published", "")[:10]

        new_html, num_added, links_added = link_article(pcontent, purl, entity_map, hubs, domain, post_title=ptitle, max_links=3)
        if not new_html or num_added == 0:
            continue

        print(f"\n[+] Post: {ptitle} ({pub_date})")
        print(f"    URL: {purl}")
        print(f"    Added {num_added} contextual link(s):")
        for ent, target_url, target_desc in links_added:
            print(f"      • Anchor [{ent}] -> {target_url} ({target_desc[:35]})")

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
                total_links_injected += num_added
                log_entries.append({
                    "id": pid,
                    "url": purl,
                    "title": ptitle,
                    "at": datetime.datetime.now(CAIRO).isoformat(),
                    "links": links_added
                })
            else:
                print(f"      ✗ Failed to update Blogger ({patch_res.status_code}): {patch_res.text[:100]}")
            time.sleep(1)
        else:
            updated_count += 1
            total_links_injected += num_added

    if backups:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backups, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Saved full backup of {len(backups)} post(s) to: {backup_file}")

    state_file = "interlink_posted.json"
    if confirm and log_entries:
        existing_log = []
        if os.path.exists(state_file):
            try: existing_log = json.load(open(state_file, "r", encoding="utf-8"))
            except Exception: pass
        existing_log.extend(log_entries)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(existing_log[-500:], f, ensure_ascii=False, indent=1)

    print(f"\n=======================================================")
    print(f"Summary for {site_key}:")
    print(f"  • Posts modified: {updated_count}")
    print(f"  • Total in-text links added: {total_links_injected}")
    print(f"=======================================================\n")
    return updated_count, total_links_injected


def parse_days(val):
    try:
        d = int(val)
        return d if d > 0 else 1
    except (ValueError, TypeError):
        return 1


def main():
    parser = argparse.ArgumentParser(description="Autonomous Contextual In-Text Internal Linking Engine")
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
