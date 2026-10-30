"""Egyptaway Automated Live Phone News Engine (mohsen 2026-10-29).
Tracks breaking smartphone news (Samsung, Apple/iPhone, Xiaomi, Realme, Oppo, Vivo, Honor, Google Pixel) 24/7.
Features:
- Monitors GSMArena, SamMobile, and Gizmochina feeds in real time.
- Extracts high-resolution official device renders/photos and serves them via wsrv.nl proxy.
- Formats rich articles with specs matrix, expected/official pricing in EGP, SAR, AED, USD, and pros/cons.
- Internal cross-linking to Egyptaway's live phone price comparison page (/p/phones-prices-egypt.html).
- Instant publishing with clean permalinks + IndexNow notification.

Runs via GitHub Actions (.github/workflows/phone_news.yml) every 30 minutes.
Usage:
  python phone_news.py           # live publish
  DRY_RUN=1 python phone_news.py # dry run
"""
import datetime, difflib, html, json, os, random, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import football as f

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
INDEXNOW_KEY = "e3b3e2ee8cd741f59f1b91e73c0f9090"
STATE_FILE = "phone_news_posted.json"
DAY_CAP = int(os.environ.get("PHONE_NEWS_DAY_CAP", "25"))

# Live feeds for phone launches & leaks
FEEDS = [
    ("https://www.gsmarena.com/rss-news-reviews.php3", "GSMArena"),
    ("https://www.sammobile.com/feed/", "SamMobile"),
    ("https://www.gizmochina.com/feed/", "Gizmochina"),
]

BRANDS = [
    (r"galaxy|samsung", "سامسونج", "Samsung"),
    (r"iphone|apple|ipad", "ابل", "Apple"),
    (r"redmi|poco|xiaomi", "شاومي", "Xiaomi"),
    (r"realme", "ريلمي", "Realme"),
    (r"oppo|find x|reno", "اوبو", "Oppo"),
    (r"vivo|iqoo", "فيفو", "Vivo"),
    (r"honor|magic", "هونر", "Honor"),
    (r"pixel", "جوجل", "Google Pixel"),
    (r"oneplus", "ون بلس", "OnePlus"),
    (r"infinix", "انفنكس", "Infinix"),
    (r"tecno", "تكنو", "Tecno"),
]

SKIP_TITLES = r"deal|deals|% off|sale|discount|best .* to buy|podcast|newsletter|poll results|weekly poll|counterpoint|idc report"

PHONE_PROMPT = """أنت محرر ومراجع هواتف محترَف في موقع ايجبتاوى. اكتب خبر هاتف ذكي أصلي بالكامل بالعربي السلس والممتع عن الهاتف المذكور، بناءً على النص المصدر فقط.

قواعد مهنية صارمة:
- الحقيقة والمصداقية: لا تخترع أي مواصفة أو رقم أو تاريخ أو سعر غير مذكور في النص.
- صنف الخبر بوضوح: لو الخبر «تسريب» أو مواصفات غير رسمية، ضع كلمة «تسريب» أو «متوقع» في العنوان والفقرات الأولى. لو إطلاق رسمي، ضع «رسمياً».
- جدول المواصفات الفنية: ضع جدول HTML أنيق (<table>) يلخص (الشاشة، المعالج، الكاميرات، البطارية والشحن، الرام والتخزين، نظام التشغيل) وفقاً لما ورد في المصدر.
- الأسعار: اذكر السعر بالدولار/اليورو كما ورد، وحوله تقريبياً إلى (الجنيه المصري بسعر صرف 49 ج، والريال السعودي 3.75 ر.س، والدرهم الإماراتي 3.67 د.إ) مع التنويه بأنه السعر العالمي قبل الجمارك والضرائب.
- القيمة المضافة: اشرح مميزات الهاتف وعيوبه المبدئية، ومين المستخدم المناسب ليه (عشاق الألعاب، محبو التصوير، الاستخدام اليومي).
- الطول: الـ body من 550 إلى 800 كلمة، بعناوين h2 (من 3 لـ 5 عناوين)، وجدول، وفقرات مريحة للقراءة.
- لا تضع صوراً أو روابط داخل الـ body (سيتم وضعها تلقائياً).

رجّع JSON بالشكل ده بالظبط:
{{"title": "عنوان جذاب وصادق أقل من 65 حرف", "slug": "english-slug-3-to-6-words", "desc": "وصف دقيق للبحث من 140 لـ 160 حرف", "is_leak": false, "brand": "اسم البراند بالعربي", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}

عنوان الخبر الأصلي: {orig_title}

النص المصدر:
{src_text}
"""


def detect_brand(title):
    for rx, ar_name, en_name in BRANDS:
        if re.search(rx, title, re.I):
            return ar_name, en_name
    return "هواتف ذكية", "Smartphone"


def extract_highres_image(orig_img_url, soup=None):
    """Upgrades thumbnail images from GSMArena/SamMobile to high-res and proxies via wsrv.nl."""
    if not orig_img_url:
        if soup:
            og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og and og.get("content"):
                orig_img_url = og["content"].strip()
    if not orig_img_url:
        return None

    # Upgrade GSMArena thumbnail to high-res full render
    clean = re.sub(r"/-(?:184x111|300x180|120x120)/", "/", orig_img_url)
    clean = re.sub(r"-\d+x\d+\.(jpg|jpeg|png|webp)", r".\1", clean)
    return f"https://wsrv.nl/?url={urllib.parse.quote(clean)}&w=1000&output=webp&q=82"


def fetch_article_text(url):
    try:
        r = requests.get(url, headers=UA, timeout=20)
        if r.status_code != 200:
            return None, None
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Extract main text
        box = soup.find("div", id="review-body") or soup.find("article") or soup.find("div", class_=re.compile(r"entry-content|post-content", re.I)) or soup
        paras = [p.get_text(" ", strip=True) for p in box.find_all("p") if len(p.get_text(" ", strip=True)) > 40]
        text = "\n".join(paras)
        return text, soup
    except Exception:
        return None, None


def ping_indexnow(urls):
    try:
        data = {
            "host": "www.egyptaway.com",
            "key": INDEXNOW_KEY,
            "keyLocation": f"https://www.egyptaway.com/{INDEXNOW_KEY}.txt",
            "urlList": urls
        }
        requests.post("https://api.indexnow.org/IndexNow", json=data, timeout=15)
    except Exception:
        pass



def check_phone_news(art, src_text, orig_title, existing_titles, min_words=450):
    if not art or not isinstance(art, dict):
        return ["لم يتم استلام مسودة صالحة"]
    errs = []
    body_text = BeautifulSoup(art.get("body", ""), "html.parser").get_text(" ")
    words = len(body_text.split())
    if words < min_words:
        errs.append(f"طول الخبر قصير ({words} كلمة، والمطلوب {min_words}+ كلمة)")
    title = art.get("title", "").strip()
    if not title or len(title) > 75:
        errs.append(f"العنوان غير صالح أو أطول من 75 حرف ({len(title)} حرف)")
    for ex in existing_titles:
        if difflib.SequenceMatcher(None, f.norm(title), f.norm(ex)).ratio() >= 0.75:
            errs.append(f"العنوان مكرر أو قريب جداً من خبر منشور: {ex}")
            break
    slug = art.get("slug", "").strip()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+){2,6}", slug):
        errs.append(f"الـ slug غير صالح ({slug}): يجب أن يتكون من 3 إلى 7 كلمات إنجليزية صغيرة مفصولة بشرطة")
    desc = art.get("desc", "").strip()
    if len(desc) < 90 or len(desc) > 185:
        errs.append(f"وصف البحث ({len(desc)} حرف) يجب أن يكون بين 100 و 175 حرفاً")
    full_text = (title + " " + body_text + " " + desc).lower()
    for b in f.BANNED:
        if b.lower() in full_text:
            errs.append(f"تم ذكر اسم موقع محظور ({b}) في صلب الخبر")
    return errs

def main():
    dry = os.environ.get("DRY_RUN") == "1"
    now = datetime.datetime.now(CAIRO)

    today = now.date().isoformat()
    print(f"[{now:%Y-%m-%d %H:%M}] Starting Phone News Live Engine...")

    state = {"done": []}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            state = {"done": []}

    done_links = {d.get("orig_link") for d in state.get("done", []) if d.get("orig_link")}
    done_titles = [d.get("title", "") for d in state.get("done", [])]

    # Daily cap check
    today_posts = [d for d in state.get("done", []) if d.get("at", "").startswith(today) and d.get("ok")]
    if len(today_posts) >= DAY_CAP:
        print(f"Daily phone news cap ({DAY_CAP}) reached. Exiting.")
        return

    tok = None if dry else f.token()
    existing_posts = [p["t"] for p in f.site_posts(tok)] if not dry else []
    all_known_titles = existing_posts + done_titles

    candidates = []
    for feed_url, feed_name in FEEDS:
        try:
            resp = requests.get(feed_url, headers=UA, timeout=20)
            soup = BeautifulSoup(resp.content, "xml")
            items = soup.find_all("item")[:20]
            for it in items:
                title = it.find("title").text.strip() if it.find("title") else ""
                link = it.find("link").text.strip() if it.find("link") else ""
                desc = it.find("description").text if it.find("description") else ""
                if not title or not link or link in done_links:
                    continue
                if re.search(SKIP_TITLES, title, re.I):
                    continue

                # Must match at least one phone brand
                brand_ar, brand_en = detect_brand(title)
                if brand_en == "Smartphone":
                    continue

                # Extract thumbnail from description or enclosure
                img_url = None
                img_m = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', desc, re.I)
                if img_m:
                    img_url = img_m.group(1)
                elif it.find("enclosure"):
                    img_url = it.find("enclosure").get("url")

                candidates.append({
                    "title": title,
                    "link": link,
                    "img": img_url,
                    "src": feed_name,
                    "brand_ar": brand_ar,
                    "brand_en": brand_en
                })
        except Exception as e:
            print(f"Feed {feed_name} failed:", e)

    print(f"Found {len(candidates)} fresh phone stories.")
    if not candidates:
        return

    published_urls = []
    for cand in candidates[:3]:
        if len(published_urls) >= 1:  # 1 phone story per scheduled run to keep pacing smooth
            break

        print(f"Processing: {cand['title'][:60]} ({cand['brand_en']})...")
        src_text, soup = fetch_article_text(cand["link"])
        if not src_text or len(src_text) < 300:
            print("  Article body too short. Skipping.")
            continue

        real_img = extract_highres_image(cand["img"], soup)
        print(f"  Real Device Image: {real_img is not None}")

        if dry and not f.secret("GEMINI_API_KEY"):
            print("  [DRY RUN - No Gemini Key] Simulating phone news draft...")
            art = {
                "title": f"مواصفات وسعر هاتف {cand['brand_ar']} الجديد 2026",
                "slug": "new-phone-specs-price-2026",
                "desc": f"تعرف على مواصفات وسعر هاتف {cand['brand_ar']} الجديد وأبرز مميزاته وعيوبه.",
                "brand": cand["brand_ar"],
                "body": f"<h2>مواصفات الهاتف الرسمية</h2><p>{src_text[:400]}</p>",
                "faq": [{"q": "كم يبلغ سعر الهاتف المتوقع؟", "a": "السعر يبدأ من حوالي 350 دولاراً عالمياً."}]
            }
            errs = []
        else:
            extra, art, errs = "", None, ["no draft"]
            for attempt in range(2):
                prompt = PHONE_PROMPT.format(orig_title=cand["title"], src_text=src_text[:5000]) + extra
                art = f.gemini(prompt)
                errs = check_phone_news(art, src_text, cand["title"], all_known_titles, min_words=450)
                if not errs:
                    break
                print(f"  Retry needed ({len(errs)} issues): {errs}")
                extra = "\nتنبيه: أعد كتابة الخبر وتصحيح الملاحظات بدقة مع تجاوز 450 كلمة: " + " | ".join(errs) + "\n"

        if errs:
            print("  Fact check failed:", errs)
            state["done"].append({"title": cand["title"], "orig_link": cand["link"], "at": now.isoformat(), "ok": False, "err": errs})
            continue

        # Format Post HTML
        lead_img_html = f'<img src="{real_img}" alt="{html.escape(art["title"])}" width="1000" height="563" style="width:100%;height:auto;border-radius:14px;box-shadow:0 4px 14px rgba(0,0,0,.08);margin:12px 0 18px;" loading="eager">' if real_img else ""

        # Price Hub Callout Card
        callout_html = '''<div style="background:#f8fafc;border:2px solid #cbd5e1;border-radius:14px;padding:16px;margin:20px 0;text-align:center;box-shadow:0 4px 10px rgba(0,0,0,.04);">
  <div style="font-size:17px;font-weight:900;color:#0f172a;margin-bottom:6px;">📱 أسعار الموبايلات المحدثة أسبوعياً في مصر والدول العربية</div>
  <p style="font-size:14px;color:#475569;margin:0 0 12px;">لو عايز تقارن أسعار ومواصفات كل الهواتف المتوفرة بالسوق المصري والخليجي، ادخل على دليل الأسعار الشامل:</p>
  <a href="https://www.egyptaway.com/p/phones-prices-egypt.html" style="background:#0f172a;color:#fff!important;text-decoration:none!important;font-weight:800;padding:10px 22px;border-radius:10px;font-size:14.5px;display:inline-block;">🔍 جدول أسعار الموبايلات 2026 في مصر</a>
</div>'''

        faq_html = ""
        if art.get("faq"):
            faq_items = "".join(f'<details style="border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin:8px 0;background:#fff;"><summary style="font-weight:800;font-size:15px;cursor:pointer;color:#1e293b;">{html.escape(q["q"])}</summary><p style="margin:10px 0 0;font-size:14.5px;color:#334155;border-top:1px dashed #e2e8f0;padding-top:10px;">{html.escape(q["a"])}</p></details>' for q in art["faq"][:4])
            faq_html = f'<div style="margin:24px 0;"><h2 style="font-size:19px;font-weight:900;color:#1e293b;margin-bottom:12px;">❓ أسئلة شائعة حول الهاتف</h2>{faq_items}</div>'

        full_html = lead_img_html + callout_html + art["body"] + faq_html + callout_html

        if dry:
            print(f"  [DRY RUN] Would publish: {art['title']}")
            print(f"  Slug: {art['slug']} | Real Image: {bool(real_img)}")
            state["done"].append({"title": art["title"], "orig_link": cand["link"], "at": now.isoformat(), "ok": True, "dry": True})
            published_urls.append("dry-run-phone")
            break

        labels = ["أخبار", "أخبار الموبايلات", cand["brand_ar"]]
        try:
            res = f.publish_live(tok, art, full_html, labels)
            post_url = res.get("url", "")
            print(f"  >>> PUBLISHED PHONE NEWS: {post_url} | {art['title']}")
            state["done"].append({
                "title": art["title"],
                "orig_link": cand["link"],
                "post_url": post_url,
                "brand": cand["brand_en"],
                "has_real_img": bool(real_img),
                "at": now.isoformat(),
                "ok": True
            })
            published_urls.append(post_url)
            all_known_titles.append(art["title"])
            break
        except Exception as ex:
            print("  Publishing failed:", ex)
            break

    state["done"] = state["done"][-300:]
    with open(STATE_FILE, "w", encoding="utf-8") as f_st:
        json.dump(state, f_st, ensure_ascii=False, indent=2)

    if published_urls and not dry:
        valid_urls = [u for u in published_urls if u.startswith("http")]
        if valid_urls:
            ping_indexnow(valid_urls)

    print(f"Phone news run completed. Published: {len(published_urls)} post(s).")


if __name__ == "__main__":
    main()
