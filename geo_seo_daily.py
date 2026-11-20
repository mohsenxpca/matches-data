"""Daily SEO & GEO High-Intent Long-Tail Engine for Egyptaway & Review Mobile.

Implements the daily SEO & GEO (Generative Engine Optimization) checklist:
1. Discovers real Egyptian multi-attribute & question queries via Google Suggest (gl=eg, hl=ar).
2. Avoids any duplicate/cannibalized topics by checking live blog posts + geo_seo_posted.json.
3. Structures every article for AI Overviews, ChatGPT, Perplexity & Google Search:
   - Direct Answer summary box at the top (GEO citation-ready).
   - Strict H2/H3 question hierarchy with concise direct answers first.
   - Real comparison/criteria table + interactive tool + 5 <details> FAQs.
   - Internal links to core Money/Hub pages & related live articles.
   - Branded 1200x675 16:9 image via image_guard.
4. Publishes max 1 post/day on Review Mobile and max 1 post/day on Egyptaway.
"""
import argparse, datetime, difflib, html, json, os, random, re, sys, urllib.parse
from zoneinfo import ZoneInfo
import requests
import football as fb
import image_guard

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CAIRO = ZoneInfo("Africa/Cairo")
STATE_FILE = "geo_seo_posted.json"
DRY = os.environ.get("DRY_RUN") in ("1", "true", "True")

SITES = {
    "review": {
        "blog_id": "2997328666613207792",
        "domain": "www.review-mobile.com",
        "seeds": [
            "افضل موبايل ببطارية",
            "افضل موبايل للتصوير بسعر",
            "افضل موبايل للالعاب بسعر",
            "موبايل سامسونج في حدود",
            "موبايل شاومي في حدود",
            "موبايل اوبو في حدود",
            "الفرق بين هاتف",
            "موبايل ضد الكسر والماء بسعر",
            "حل مشكلة سخونة الهاتف",
            "ايهما افضل سامسونج ام شاومي",
        ],
        "hubs": [
            ("https://www.review-mobile.com/p/compare-phones_01466757070.html", "أداة مقارنة الهواتف الذكية"),
            ("https://www.review-mobile.com/p/best-phone-for-budget.html", "دليل أفضل هواتف حسب الميزانية"),
            ("https://www.review-mobile.com/p/mobile-reviews-hub.html", "فهرس مراجعات الهواتف"),
        ],
        "default_label": "اخرى",
        "pool": "phones",
    },
    "egyptaway": {
        "blog_id": "8325646053257070334",
        "domain": "www.egyptaway.com",
        "seeds": [
            "افضل طرق الربح من الانترنت بدون",
            "حل مشكلة بطء لعبة",
            "افضل اعدادات ببجي موبايل",
            "كيفية شحن شدات ببجي",
            "خطوات التحويل عبر انستاباي",
            "حد السحب اليومي فودافون كاش",
            "شروط التقديم على شقق الاسكان",
            "طريقة حساب فوائد شهادات البنك",
            "كيفية حماية حساب واتساب من",
            "افضل تطبيقات تعلم الانجليزية",
        ],
        "hubs": [
            ("https://www.egyptaway.com/p/mobile-prices-egypt.html", "جدول أسعار الموبايلات في مصر"),
            ("https://www.egyptaway.com/p/bank-certificates-egypt.html", "حاسبة أرباح شهادات البنوك"),
            ("https://www.egyptaway.com/p/download-games.html", "دليل تحميل الألعاب الرسمية"),
            ("https://www.egyptaway.com/p/housing-egypt.html", "دليل طروحات الإسكان الاجتماعي"),
        ],
        "default_label": "منوعات",
        "pool": "general",
    },
}

BANNED_RE = re.compile(
    r"سياس|حرب|جيش|عسكر|إسرائيل|غزة|انتخاب|وزير|رئيس|مغني|مطرب|فيلم|مسلسل|رقص|قمار|رهان|مراهنات|مهكر|تهكير|mod\s*apk",
    re.I,
)


def google_suggest(query):
    """Fetches real Egyptian autocomplete queries from Google Suggest."""
    url = "https://suggestqueries.google.com/complete/search"
    try:
        r = requests.get(
            url,
            params={"client": "firefox", "hl": "ar", "gl": "eg", "q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 1:
                return [s.strip() for s in data[1] if isinstance(s, str) and len(s.strip()) >= 8]
    except Exception as e:
        print(f"Suggest error ({query}): {e}")
    return []


def norm_text(s):
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s or "").lower()
    return re.sub(r"\s+", " ", s).strip()


def is_similar(title, existing_titles, threshold=0.65):
    nt = norm_text(title)
    for ex in existing_titles:
        if difflib.SequenceMatcher(None, nt, norm_text(ex)).ratio() >= threshold:
            return True
    return False


def fetch_site_posts(tok, blog_id, max_posts=150):
    posts = []
    page_token = None
    while len(posts) < max_posts:
        params = {"status": "LIVE", "maxResults": 100, "fetchBodies": "false"}
        if page_token:
            params["pageToken"] = page_token
        r = fb.api("GET", f"/blogs/{blog_id}/posts", tok, params=params)
        data = r if isinstance(r, dict) else (r.json() if hasattr(r, "json") else {})
        items = data.get("items", [])
        if not items:
            break
        posts.extend(items)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return posts


def pick_query_for_site(site_key, existing_titles, used_queries):
    cfg = SITES[site_key]
    seeds = list(cfg["seeds"])
    random.shuffle(seeds)

    for seed in seeds[:5]:
        suggestions = google_suggest(seed)
        random.shuffle(suggestions)
        for q in suggestions:
            if BANNED_RE.search(q):
                continue
            if q in used_queries:
                continue
            if is_similar(q, existing_titles, threshold=0.62):
                continue
            # Also get sub-questions / related suggestions for this query
            related = [r for r in google_suggest(q) if r != q and not BANNED_RE.search(r)][:5]
            return q, related
    return None, []


def detect_review_brand(text):
    t = text.lower()
    brands = [
        ("سامسونج", ["سامسونج", "samsung", "galaxy"]),
        ("شاومي", ["شاومي", "xiaomi", "redmi", "ريدمي", "poco", "بوكو"]),
        ("أبل", ["أبل", "ابل", "آيفون", "ايفون", "iphone", "apple"]),
        ("أوبو", ["أوبو", "اوبو", "oppo", "reno"]),
        ("فيفو", ["فيفو", "vivo", "iqoo"]),
        ("ريلمي", ["ريلمي", "realme"]),
        ("هونر", ["هونر", "honor"]),
        ("إنفينكس", ["إنفينكس", "انفينكس", "infinix"]),
        ("تكنو", ["تكنو", "tecno"]),
    ]
    for label, kws in brands:
        if any(k in t for k in kws):
            return label
    return "اخرى"


def detect_ea_label(text):
    t = text.lower()
    if any(k in t for k in ["ببجي", "فري فاير", "لعبة", "العاب", "ألعاب", "شحن"]):
        return "ألعاب"
    if any(k in t for k in ["الربح", "ربح"]):
        return "الربح"
    if any(k in t for k in ["اسكان", "إسكان", "شقق", "شهادات", "بنك", "فودافون كاش", "انستاباي", "إنستاباي"]):
        return "خدمات"
    return "منوعات"


PROMPT_TEMPLATE = """أنت خبير SEO و GEO (تحسين الظهور في Google Search ومحركات الذكاء الاصطناعي مثل ChatGPT وGoogle AI Overviews) في السوق المصري.
الموضوع المطلوب (كلمة بحث حقيقية من جوجل مصر): «{query}»
استعلامات وأسئلة ذات صلة يبحث عنها المستخدمون في مصر:
{related_block}

اكتب مقالاً شاملاً واحترافياً باللغة العربية السهلة (أكثر من 1050 كلمة) يلتزم حرفياً بقواعد SEO & GEO التالية:
1. العنوان (title): واضح وجذاب ومباشر أقل من 68 حرفاً، يتضمن السنة {year} لو مناسب، بدون مبالغة أو clickbait.
2. وصف البحث (desc): من 140 إلى 160 حرفاً بالضبط، يبدأ بأهم معلومة يبحث عنها القارئ.
3. هيكل المقال (body):
   - ابدأ مباشرة بصندوق **"الإجابة السريعة (الخلاصة)"** (`<div style="background:#f0fdf4;border:1px solid #86efac;border-right:5px solid #16a34a;border-radius:10px;padding:14px 16px;margin:14px 0;">`) يجيب على سؤال المقال في 3-4 أسطر مركزة (عشان محركات الذكاء الاصطناعي تقتبسه).
   - تسلسل هرمي واضح باستخدام `<h2>` للأسئلة الرئيسية (تشمل الأسئلة ذات الصلة) و`<h3>` للنقاط الفرعية.
   - تحت كل `<h2>`: اكتب فقرة `<p>` أولى قصيرة ومباشرة تجيب على العنوان فوراً، ثم اشرح التفاصيل والخطوات والأرقام العملية.
   - أضف جدول مقارنة أو معايير احترافي (`<table>`) يوضح الخيارات أو التكاليف أو الفروق بوضوح.
   - أضف قسماً عملياً: **"ما الذي يفرق فعلاً عند الاختيار / أخطاء شائعة تجنبها"** بمعلومات واقعية غير منسوخة.
   - أضف أداة تفاعلية صغيرة مفيدة (`<div class="ea-tool">`) بـ `<select>` أو `<input>` و`<button>` لحساب أو ترشيح الخيار الأنسب للقارئ.
   - ممنوع اختراع أي أسعار أو مواصفات أو أكواد غير مؤكدة؛ وإذا احتجت لذكر سعر/مواصفة متغيرة اكتب "بحسب التحديث الرسمي في السوق المصري" أو "راجع الموقع الرسمي".
   - ممنوع وضع صور أو روابط داخل `body` (سيتم إدراج الصور والروابط تلقائياً).
4. أضف 5 أسئلة شائعة (faq) دقيقة ومباشرة.

أرجع النتيجة بصيغة JSON فقط بهذا الشكل:
{{"title": "...", "slug": "english-slug-3-to-6-words", "desc": "...", "body": "...", "faq": [{{"q": "...", "a": "..."}}]}}
"""


def build_post_html(art, img_url, site_key, hubs, related_articles):
    desc = html.escape((art.get("desc") or "")[:160])
    title_esc = html.escape(art.get("title", ""))
    lead_img = (
        f'<img src="{img_url}" alt="{title_esc}" width="1200" height="675" '
        f'style="width:100%;height:auto;border-radius:12px;margin-bottom:16px">'
    )
    hidden_desc = f'<span class="ea-desc" hidden>{desc}</span>\n'

    # Internal links block (hub + 2 live related articles)
    links_html = '<div class="ea-internal-links" style="background:#f8fafc;border:1px solid #e2e8f0;border-right:4px solid #2563eb;border-radius:10px;padding:14px 16px;margin:20px 0;">'
    links_html += '<strong style="display:block;margin-bottom:8px;color:#0f172a;">روابط وأدلة ذات صلة:</strong><ul style="margin:0;padding-right:18px;">'
    for u, t in related_articles[:2]:
        links_html += f'<li><a href="{u}" style="color:#2563eb;font-weight:700;">{html.escape(t)}</a></li>'
    if hubs:
        hu, ht = hubs[0]
        links_html += f'<li><a href="{hu}" style="color:#0f172a;font-weight:700;">{html.escape(ht)}</a></li>'
    links_html += "</ul></div>"

    faq_html = "<h2>الأسئلة الشائعة</h2>" + "".join(
        f"<details style='border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin:8px 0;'>"
        f"<summary style='font-weight:700;cursor:pointer;'>{html.escape(q['q'])}</summary>"
        f"<p style='margin:8px 0 0;color:#334155;'>{html.escape(q['a'])}</p></details>"
        for q in art.get("faq", [])[:5]
    )

    body = art.get("body", "")
    # Insert internal links block before last H2 or at end of body
    body_full = hidden_desc + lead_img + body + links_html + faq_html
    return body_full


def process_site(site_key, tok, state, dry=False):
    cfg = SITES[site_key]
    blog_id = cfg["blog_id"]
    now = datetime.datetime.now(CAIRO)
    today_str = now.strftime("%Y-%m-%d")

    site_state = state.setdefault(site_key, {"last_date": "", "queries": []})
    if site_state.get("last_date") == today_str and not dry:
        print(f"[{site_key}] Already published today ({today_str}). Skipping.")
        return False

    live_posts = fetch_site_posts(tok, blog_id, max_posts=150)
    existing_titles = [p.get("title", "") for p in live_posts]

    query, related = pick_query_for_site(site_key, existing_titles, set(site_state.get("queries", [])))
    if not query:
        print(f"[{site_key}] No fresh query found.")
        return False

    print(f"[{site_key}] Selected query: {query}")
    print(f"[{site_key}] Related queries: {related}")

    related_block = "\n".join(f"- {r}" for r in related) if related else "- لا توجد استعلامات إضافية"
    prompt = PROMPT_TEMPLATE.format(query=query, related_block=related_block, year=now.year)
    art = fb.gemini(prompt)
    if not art or not art.get("title") or not art.get("body"):
        print(f"[{site_key}] Gemini generation failed.")
        return False

    if is_similar(art["title"], existing_titles, threshold=0.72):
        print(f"[{site_key}] Generated title too similar to existing post: {art['title']}")
        return False

    # Image selection + branding
    pool = image_guard.POOLS.get(cfg["pool"], image_guard.POOLS["general"])
    cand_img = image_guard.get_guaranteed_image(None, art["title"], pool, site=site_key)
    slug_clean = re.sub(r"[^a-z0-9\-]", "-", (art.get("slug") or f"geo-{site_key}").lower()).strip("-")[:55]
    slug_clean = f"{slug_clean}-{now:%m%d}"
    branded_cdn, _, _ = image_guard.brand_and_save_photo(cand_img, slug_clean, category=cfg["pool"])
    final_img = branded_cdn or cand_img

    # Pick 2 related live articles
    rel_articles = []
    q_words = [w for w in norm_text(query).split() if len(w) >= 3]
    for p in live_posts:
        pt = p.get("title", "")
        if any(w in norm_text(pt) for w in q_words):
            rel_articles.append((p.get("url", ""), pt))
        if len(rel_articles) >= 2:
            break
    if len(rel_articles) < 2:
        for p in live_posts[:5]:
            if (p.get("url", ""), p.get("title", "")) not in rel_articles:
                rel_articles.append((p.get("url", ""), p.get("title", "")))
            if len(rel_articles) >= 2:
                break

    full_html = build_post_html(art, final_img, site_key, cfg["hubs"], rel_articles)

    # Labels (strictly 1 label per Mohsen rules)
    if site_key == "review":
        label = detect_review_brand(art["title"] + " " + query)
    else:
        label = detect_ea_label(art["title"] + " " + query)

    if dry:
        print(f"[DRY RUN - {site_key}] Title: {art['title']}")
        print(f"[DRY RUN - {site_key}] Label: {label} | Slug: {slug_clean}")
        print(f"[DRY RUN - {site_key}] Img: {final_img}")
        print(f"[DRY RUN - {site_key}] Words approx: {len(re.sub(r'<[^>]+>', ' ', full_html).split())}")
        return True

    post_body = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": art["title"][:70],
        "content": full_html,
        "labels": [label],
    }
    res = fb.api("POST", f"/blogs/{blog_id}/posts", tok, body=post_body)
    data = res if isinstance(res, dict) else (res.json() if hasattr(res, "json") else {})
    post_url = data.get("url", "")
    if post_url:
        print(f"[{site_key}] PUBLISHED SEO/GEO POST: {post_url} | {art['title']}")
        site_state["last_date"] = today_str
        site_state["queries"] = (site_state.get("queries", []) + [query])[-200:]
        return True
    print(f"[{site_key}] Publish failed: {data}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Daily SEO & GEO High-Intent Publisher")
    parser.add_argument("--site", choices=["review", "egyptaway", "all"], default="all")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    dry = DRY or args.dry

    state = {}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            state = {}

    tok = fb.token()
    targets = ["egyptaway", "review"] if args.site == "all" else [args.site]
    changed = False
    for s in targets:
        if process_site(s, tok, state, dry=dry) and not dry:
            changed = True

    if changed:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
