"""Egyptaway Instant Breaking Trends Engine for Egypt (mohsen 2026-10-29).
Publishes hot general Egyptian trends and breaking public interest news IMMEDIATELY (no scheduling delay)
to rank first in Google Search, Google News, and Google Discover before competitors.

Monitors and covers:
- Government decisions & adjustments (تغيير الساعة، التوقيت الشتوي والصيفي، قرارات مجلس الوزراء)
- Weather alerts & meteorological forecasts (بيان الأرصاد الجوية، النوات، موجات الطقس والسيول)
- Official holidays & vacations (الإجازات الرسمية، عطلات البنوك، إجازات المدارس)
- Public subsidies & supplies (بطاقات التموين، إضافة المواليد، أسعار الخبز، معارض أهلاً رمضان)
- School & university news (مواعيد الامتحانات، إجازة نصف العام، نتائج الشهادات)
- Public transportation decisions (مواعيد المترو والقطارات، أسعار التذاكر)
- Breaking viral search trends across Egyptian news & Google Trends Egypt

Usage:
  python egypt_trends.py                     # Auto-detects the hottest unposted Egyptian trend and publishes immediately
  python egypt_trends.py "تغيير الساعة"       # Publishes a breaking post about a specific topic immediately
  python egypt_trends.py --dry               # Dry run (prints draft without publishing)
"""
import datetime, difflib, html, json, os, random, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import football as f
import notify

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
STATE_FILE = "egypt_trends_posted.json"
DAY_CAP = int(os.environ.get("EGYPT_TRENDS_DAY_CAP", "30"))

# Curated high-res natural photography fallbacks (no text overlays)
TREND_PHOTO_POOLS = {
    "clock": "https://images.pexels.com/photos/1198264/pexels-photo-1198264.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "weather": "https://images.pexels.com/photos/1118873/pexels-photo-1118873.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "supply": "https://images.pexels.com/photos/264636/pexels-photo-264636.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "transport": "https://images.pexels.com/photos/221387/pexels-photo-221387.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "education": "https://images.pexels.com/photos/207691/pexels-photo-207691.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "money": "https://images.pexels.com/photos/259027/pexels-photo-259027.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "holidays": "https://images.pexels.com/photos/1029141/pexels-photo-1029141.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "cairo": "https://images.pexels.com/photos/3290075/pexels-photo-3290075.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
}

# Cross-link suggestions to relevant Egyptaway hub pages
HUB_LINKS = {
    "prayer": ('<p>ولمعرفة التوقيت الدقيق ومواعيد الصلاة بعد التعديل، تابع صفحة '
               '<a href="https://www.egyptaway.com/p/prayer-times-egypt.html">مواقيت الصلاة اليوم في مصر</a> '
               'المحدثة لحظة بلحظة بتوقيت القاهرة والمحافظات.</p>'),
    "weather": ('<p>ويمكنك متابعة خريطة الطقس ودرجات الحرارة المتوقعة في جميع المدن عبر صفحة '
                '<a href="https://www.egyptaway.com/p/weather-egypt.html">حالة الطقس اليوم في مصر</a>.</p>'),
    "holidays": ('<p>للاطلاع على جدول الإجازات الرسمية المتبقية مدفوعة الأجر للقطاعين الحكومي والخاص، راجع صفحة '
                 '<a href="https://www.egyptaway.com/p/official-holidays-egypt.html">الإجازات الرسمية في مصر 2026</a>.</p>'),
    "gold": ('<p>تابع أيضاً التحديثات اللحظية لأسعار الذهب والعملات في السوق المصري عبر صفحة '
             '<a href="https://www.egyptaway.com/p/gold-prices-egypt.html">أسعار الذهب اليوم في مصر</a>.</p>')
}

AVOID_REGEX = r"قتل|مقتل|جريم|اغتصاب|تحرش|انتحار|ذبح|طعن|مخدرات|إرهاب|ارهاب|فضيحة|فيديو إباحي|اباحي|شذوذ|فضايح|sex|porn|murder|suicide"

TREND_QUERIES = [
    "تغيير الساعة OR التوقيت الشتوي OR التوقيت الصيفي when:24h",
    "الأرصاد الجوية OR درجات الحرارة OR سقوط الأمطار when:24h",
    "إجازة رسمية OR عطلة رسمية OR إجازة البنوك when:24h",
    "بطاقات التموين OR وزارة التموين OR صرف السلع when:24h",
    "وزارة التربية والتعليم OR امتحانات OR جدول الامتحانات when:24h",
    "مواعيد المترو OR مواعيد القطارات OR السكة الحديد when:24h",
    "زيادة المرتبات OR صرف المعاشات OR تكافل وكرامة when:24h",
]

PROMPT_TEMPLATE = """أنت محرر شؤون مصرية وتقارير خدمية في موقع ايجبتاوى. موضوع «{topic_title}» عليه اهتمام وبحث واسع في الشارع المصري الآن.
اكتب خبراً أصلياً شاملاً وواضحاً وسريع الفهم بالعربي البسيط والمفهوم لجمهور مصر والوطن العربي، بناءً على «النص المصدر» فقط.

قواعد مهنية صارمة:
- الحقيقة والمصداقية المطلقة: اعتمد 100% على الحقائق والأرقام والقرارات والمواعيد المذكورة في المصدر. ممنوع اختراع أي رقم أو تاريخ أو تفاصيل غير موجودة.
- اكتب كل الأرقام بالأرقام (مثل: 60 دقيقة، 18 درجة، 10 أيام).
- أسلوب صحفي متماسك: صغ المقال بأسلوب شيق يبدأ بالمعلومة الأساسية التي يبحث عنها القارئ (ماذا حدث ومتى وكيف يؤثر عليه؟).
- القيمة المضافة: اشرح الإجراءات والخطوات العملية بوضوح (كيف يضبط ساعته؟ كيف يتعامل مع الطقس؟ مواعيد الإجازة ومن تشملهم؟).
- ممنوع ذكر اسم الموقع المصدر (مثل اليوم السابع أو مصراوي أو صدى البلد) داخل النص.
- الطول: الـ body من 650 لـ 850 كلمة، مقسم بـ 4 إلى 5 عناوين فرعية <h2> وفقرات <p>، وقوائم <ul> لو مناسبة.

رجّع ردك على هيئة JSON صالح فقط بالشكل التالي دون أي نصوص إضافية:
{{"title": "عنوان جذاب وصادق وواضح يبدأ بالحدث أقل من 65 حرف", "kicker": "2-4 كلمات للتصنيف", "slug": "english-slug-3-to-6-words", "desc": "وصف دقيق للبحث من 140 لـ 160 حرف يبدأ بأهم معلومة", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}

عنوان الموضوع المستهدف: {topic_title}

النص المصدر الموثق:
{src_text}
"""


def pick_fallback_photo(text):
    t = text.lower()
    if re.search(r"ساعة|توقيت|الشتوي|الصيفي|تأخير|تقديم", t):
        return TREND_PHOTO_POOLS["clock"]
    if re.search(r"طقس|أرصاد|مطر|حرارة|شتاء|سيول|رياح|نوة", t):
        return TREND_PHOTO_POOLS["weather"]
    if re.search(r"تموين|سلع|خبز|معرض|أهلا رمضان|سكر|زيت", t):
        return TREND_PHOTO_POOLS["supply"]
    if re.search(r"مترو|قطار|سكة حديد|مواصلات|تذكرة|تذاكر", t):
        return TREND_PHOTO_POOLS["transport"]
    if re.search(r"مدارس|جامعات|امتحانات|تعليم|نتيجة|تنسيق|دراسة", t):
        return TREND_PHOTO_POOLS["education"]
    if re.search(r"مرتب|معاش|فلوس|صرف|بنوك|مالية|تكافل", t):
        return TREND_PHOTO_POOLS["money"]
    if re.search(r"إجازة|عطلة|أعياد|رسمية|مناسبة", t):
        return TREND_PHOTO_POOLS["holidays"]
    return TREND_PHOTO_POOLS["cairo"]


def pick_hub_callout(text):
    t = text.lower()
    if re.search(r"ساعة|توقيت|الشتوي|الصيفي|صلاة", t):
        return HUB_LINKS["prayer"]
    if re.search(r"طقس|أرصاد|مطر|حرارة|شتاء", t):
        return HUB_LINKS["weather"]
    if re.search(r"إجازة|عطلة|رسمية", t):
        return HUB_LINKS["holidays"]
    if re.search(r"ذهب|دولار|أسعار|عملات", t):
        return HUB_LINKS["gold"]
    return ""


def decode_gn_link(link):
    """Decodes Google News RSS redirect link to original publisher URL."""
    try:
        aid = link.split("/articles/")[1].split("?")[0]
        h = requests.get(f"https://news.google.com/rss/articles/{aid}", headers=UA, timeout=20).text
        sg_m = re.search(r'data-n-a-sg="([^"]+)"', h)
        ts_m = re.search(r'data-n-a-ts="([^"]+)"', h)
        if not sg_m or not ts_m:
            return None
        sg, ts = sg_m.group(1), ts_m.group(1)
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts), sg]
        r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", timeout=20,
                          headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                          data="f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])))
        return json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]
    except Exception:
        return None


def fetch_publisher_article(url):
    """Fetches publisher URL, extracts real high-res news photo (og:image) and full factual text."""
    try:
        resp = requests.get(url, headers=UA, timeout=25)
        if resp.status_code != 200:
            return None, None
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Extract real news photo
        img_url = None
        og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og and og.get("content"):
            c = og["content"].strip()
            if c.startswith("http") and not any(x in c for x in ["default", "placeholder", "logo", "avatar", "icon"]):
                img_url = c

        if not img_url:
            for im in soup.find_all("img"):
                src = im.get("src") or im.get("data-src") or ""
                if src.startswith("http") and not any(x in src for x in ["icon", "logo", "avatar", "pixel", "banner"]):
                    w = int(im.get("width") or 0)
                    h = int(im.get("height") or 0)
                    if (w >= 400 or h >= 250) or (w == 0 and h == 0):
                        img_url = src
                        break

        # 2. Extract clean body text
        container = soup.find("article") or soup.find("div", class_=re.compile(r"article-body|story-body|post-content|entry-content", re.I)) or soup.find("main") or soup
        for unwanted in container.find_all(["script", "style", "iframe", "noscript", "nav", "aside", "header", "footer"]):
            unwanted.decompose()

        paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
        valid_paras = [p for p in paragraphs if len(p) > 50 and not re.search(r"اقرأ أيضا|تابعنا على|اشترك في|شاهد المزيد", p)]
        full_text = "\n\n".join(valid_paras)
        return img_url, full_text
    except Exception as ex:
        print(f"    Error reading publisher article {url}: {ex}")
        return None, None


def get_trend_candidates(custom_query=None):
    """Gathers fresh Egyptian trend candidates."""
    candidates = []
    seen_urls = set()

    # If user provided a specific topic on the command line
    if custom_query:
        print(f"🔍 Searching live Egyptian news for custom topic: «{custom_query}»")
        q_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(custom_query + ' when:48h')}&hl=ar&gl=EG&ceid=EG:ar"
        try:
            r = requests.get(q_url, headers=UA, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:8]:
                t = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if t and link and not re.search(AVOID_REGEX, t, re.I):
                    candidates.append({"t": t, "link": link, "type": "custom", "query": custom_query})
        except Exception as e:
            print(f"Custom query fetch failed: {e}")
        return candidates

    # 1. Google Trends Egypt RSS
    try:
        r = requests.get("https://trends.google.com/trending/rss?geo=EG", headers=UA, timeout=25)
        soup = BeautifulSoup(r.content, "xml")
        for it in soup.find_all("item")[:15]:
            q = (it.find("title").text if it.find("title") else "").strip()
            if not q or re.search(AVOID_REGEX, q, re.I):
                continue
            news_items = it.find_all(["news_item", "ht:news_item"])
            for n in news_items[:2]:
                u_node = n.find(["news_item_url", "ht:news_item_url"])
                t_node = n.find(["news_item_title", "ht:news_item_title"])
                link = u_node.text.strip() if u_node else ""
                t = t_node.text.strip() if t_node else q
                if link and link not in seen_urls and not re.search(AVOID_REGEX, t, re.I):
                    seen_urls.add(link)
                    candidates.append({"t": t, "link": link, "type": "trends", "query": q})
    except Exception as e:
        print(f"Google Trends fetch warning: {e}")

    # 2. Breaking Public Queries in Egypt
    for q_term in TREND_QUERIES:
        q_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_term)}&hl=ar&gl=EG&ceid=EG:ar"
        try:
            r = requests.get(q_url, headers=UA, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:4]:
                t = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if t and link and link not in seen_urls and not re.search(AVOID_REGEX, t, re.I):
                    seen_urls.add(link)
                    clean_q = q_term.split("when:")[0].replace("OR", "").strip()
                    candidates.append({"t": t, "link": link, "type": "public_query", "query": clean_q})
        except Exception:
            continue

    # 3. National Egyptian News Top Stories
    try:
        r = requests.get("https://news.google.com/rss/headlines/section/topic/NATION?hl=ar&gl=EG&ceid=EG:ar", headers=UA, timeout=20)
        soup = BeautifulSoup(r.content, "xml")
        for it in soup.find_all("item")[:8]:
            t = (it.find("title").text if it.find("title") else "").strip()
            link = (it.find("link").text if it.find("link") else "").strip()
            if t and link and link not in seen_urls and not re.search(AVOID_REGEX, t, re.I):
                seen_urls.add(link)
                candidates.append({"t": t, "link": link, "type": "nation", "query": "شؤون مصرية"})
    except Exception:
        pass

    return candidates


def main():
    dry = "--dry" in sys.argv or os.environ.get("DRY_RUN") == "1"
    custom_topic = os.environ.get("TOPIC") or next((arg for arg in sys.argv[1:] if not arg.startswith("--")), None)
    if custom_topic:
        custom_topic = custom_topic.strip()
    if not custom_topic:
        custom_topic = None

    print("=" * 65)
    print("🚀 EGYPTAWAY INSTANT BREAKING TRENDS ENGINE (نشر فوري)")
    print(f"⏰ Time: {datetime.datetime.now(CAIRO).strftime('%Y-%m-%d %H:%M')} Cairo")
    if custom_topic:
        print(f"🎯 Target Topic: «{custom_topic}»")
    print("=" * 65)

    # 1. Load posted state
    state = {"done": []}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            state = {"done": []}

    done_urls = {d.get("u") for d in state.get("done", []) if d.get("u")}
    done_titles = [d.get("t", "") for d in state.get("done", []) if d.get("t")]

    # 2. Fetch candidates
    cands = get_trend_candidates(custom_topic)
    print(f"Found {len(cands)} candidate trend stories.")

    if not cands:
        print("No new candidate trend found.")
        return

    # Filter candidates
    viable = []
    for c in cands:
        if c["link"] in done_urls:
            continue
        # Check title similarity
        if any(difflib.SequenceMatcher(None, f.norm(c["t"]), f.norm(dt)).ratio() > 0.82 for dt in done_titles):
            continue
        viable.append(c)

    print(f"Viable candidates after dedup: {len(viable)}")
    if not viable:
        print("All candidate stories have already been covered.")
        return

    # Check daily cap if automated
    today_str = datetime.datetime.now(CAIRO).date().isoformat()
    today_posts = [d for d in state.get("done", []) if d.get("at", "").startswith(today_str) and d.get("ok")]
    if len(today_posts) >= DAY_CAP and not custom_topic and not dry:
        print(f"Reached daily cap ({DAY_CAP} posts). Exiting.")
        return

    tok = None if dry else f.token()
    existing_site_titles = [p["t"] for p in f.site_posts(tok)] if tok else []

    published_count = 0
    for cand in viable:
        if f._DOWN:
            print("Gemini API down, pausing.")
            break

        print(f"\nProcessing Trend: {cand['t'][:75]}...")
        pub_url = decode_gn_link(cand["link"]) or cand["link"]
        print(f"  Publisher URL: {pub_url[:80]}")

        real_img, src_text = fetch_publisher_article(pub_url)
        if not src_text or len(src_text) < 450:
            print(f"  Insufficient text ({len(src_text) if src_text else 0} chars). Skipping.")
            continue

        print(f"  Source text length: {len(src_text)} chars | Real Photo: {bool(real_img)}")

        # AI Generation
        topic_title = cand.get("query") or cand["t"]
        prompt = PROMPT_TEMPLATE.format(topic_title=topic_title, src_text=src_text[:6500])

        extra, art, errs = "", None, ["no draft"]
        for attempt in range(2):
            art = f.gemini(prompt + extra)
            errs = f.check(art, src_text + " " + cand["t"], "", existing_site_titles, min_words=480)
            if not errs:
                break
            print(f"  Retry needed ({len(errs)} issues): {errs}")
            extra = "\nتنبيه: أعد كتابة المقال مع تصحيح المشاكل الآتية بدقة: " + " | ".join(errs) + "\n"

        if errs:
            print(f"  Draft check failed ({errs}). Skipping.")
            state["done"].append({"u": cand["link"], "t": cand["t"], "at": today_str, "ok": False, "reason": errs})
            continue

        # Choose lead photo: Real news photo first, or clean Pexels fallback
        if real_img:
            proxied_img = f"https://wsrv.nl/?url={urllib.parse.quote(real_img)}&w=1000&output=webp&q=80"
        else:
            proxied_img = pick_fallback_photo(art["title"] + " " + cand["t"])

        lead_img_html = f'<img src="{proxied_img}" alt="{html.escape(art["title"])}" width="1000" height="563" style="width:100%;height:auto;border-radius:12px;margin-bottom:16px">'

        # Interactive Callout & Summary Button
        summary_btn = ('<p><button type="button" onclick="this.nextElementSibling.hidden=!this.nextElementSibling.hidden" '
                       'style="border:0;border-radius:999px;padding:7px 18px;font:inherit;font-weight:700;color:#fff;'
                       'background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer;box-shadow:0 3px 10px rgba(234,88,12,0.25)">'
                       '⚡ الخلاصة في سطرين</button>'
                       f'<span hidden style="display:block;margin-top:10px;padding:12px 14px;border-radius:12px;background:#fff7ed;border:1px solid #fed7aa;font-size:14px;line-height:1.6">'
                       f'{html.escape(art.get("desc", ""))}</span></p>')

        # FAQs
        faq_html = ""
        if art.get("faq"):
            faq_items = "".join(f"<details style='margin:8px 0;padding:8px 12px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0'>"
                                f"<summary style='font-weight:700;cursor:pointer;color:#1e293b'>{html.escape(q['q'])}</summary>"
                                f"<p style='margin:6px 0 0;color:#475569'>{html.escape(q['a'])}</p></details>" for q in art["faq"][:4])
            faq_html = f"<h2>أسئلة شائعة حول {html.escape(art.get('kicker', 'الموضوع'))}</h2>" + faq_items

        # Hub Callout
        hub_callout = pick_hub_callout(art["title"] + " " + cand["t"])

        full_html = lead_img_html + summary_btn + art["body"] + hub_callout + faq_html

        # Labels
        labels = ["أخبار", "تريند مصر"]
        if cand.get("query") and len(cand["query"]) <= 20:
            labels.append(cand["query"])

        if dry:
            print(f"\n[DRY RUN] Title: {art['title']}")
            print(f"Slug: {art['slug']}")
            print(f"Desc: {art['desc']}")
            print(f"Photo: {proxied_img}")
            print(f"HTML Preview (first 250 chars):\n{full_html[:250]}...")
            published_count += 1
            break

        # ⚡ INSTANT LIVE PUBLISHING (نشر فوري بدون جدولة) ⚡
        now_cairo = datetime.datetime.now(CAIRO)
        try:
            # 1. Create Post with Slug as initial title
            d = f.api("POST", f"/blogs/{f.BLOG}/posts", tok, {"isDraft": "false"}, {
                "kind": "blogger#post",
                "title": art["slug"].replace("-", " "),
                "content": f.with_desc(full_html, art),
                "labels": list(dict.fromkeys(labels))
            })

            # 2. Publish immediately at current time
            f.api("POST", f"/blogs/{f.BLOG}/posts/{d['id']}/publish", tok, {"publishDate": now_cairo.isoformat()})

            # 3. Patch Arabic Title
            f.api("PATCH", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
            post_info = f.api("GET", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
            post_url = post_info.get("url", "")

            print(f"\n✅ PUBLISHED LIVE INSTANTLY: {post_url}")
            print(f"   Title: {art['title']}")

            # 4. Instant IndexNow Ping
            try:
                notify.indexnow([post_url], False)
            except Exception as e:
                print(f"   IndexNow ping warning: {e}")

            # 5. Instant Telegram Channel Post
            try:
                notify.telegram({"title": art["title"], "url": post_url, "content": full_html}, False)
            except Exception as e:
                print(f"   Telegram ping warning: {e}")

            # 6. Save State
            state["done"].append({
                "u": cand["link"],
                "t": cand["t"],
                "title": art["title"],
                "url": post_url,
                "at": now_cairo.isoformat(),
                "ok": True,
                "type": cand.get("type", "trend")
            })

            existing_site_titles.append(art["title"])
            published_count += 1
            break  # Post 1 breaking trend per run
        except Exception as e:
            print(f"❌ Failed to publish post: {e}")
            state["done"].append({"u": cand["link"], "t": cand["t"], "at": today_str, "ok": False, "reason": str(e)})

    # Save state
    state["done"] = state["done"][-350:]
    if not dry:
        json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nDone: Published {published_count} breaking Egypt trend post(s).")


if __name__ == "__main__":
    main()
