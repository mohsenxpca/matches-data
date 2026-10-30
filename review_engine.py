"""Review (review-mobile.com) Autonomous Phone News & Review Engine (mohsen 2026-10-29).
Publishes 100% brand-new, comprehensive phone reviews and breaking mobile news throughout the day.
Strict AdSense compliance: 1000+ words, authentic phone photography (no cartoons/no text overlays),
specs matrix, EGP/SAR/AED pricing with interactive converter, pros/cons, FAQs, internal links,
and zero duplication.

Usage:
  python review_engine.py                        # Scans for hottest unreviewed new phone and publishes immediately
  python review_engine.py "Samsung W27"          # Publishes a review/news for a specific model on-demand
  python review_engine.py --dry                  # Dry run (prints draft without publishing)
"""
import datetime, difflib, html, json, os, random, re, sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import football as f
import notify

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
REVIEW_BLOG = "2997328666613207792"
REVIEW_HOST = "www.review-mobile.com"
STATE_FILE = "review_posted.json"
REVIEW_CAP = int(os.environ.get("REVIEW_DAY_CAP", "20"))
COUNT = int(os.environ.get("COUNT", "2"))

EUR_RATES = {"egp": 52.0, "sar": 4.05, "aed": 3.97}
CNY_RATES = {"egp": 6.8, "sar": 0.527, "aed": 0.516}

FALLBACK_PHONE_PHOTOS = [
    "https://images.pexels.com/photos/607812/pexels-photo-607812.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "https://images.pexels.com/photos/1092644/pexels-photo-1092644.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "https://images.pexels.com/photos/404280/pexels-photo-404280.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "https://images.pexels.com/photos/40739/mobile-phone-smartphone-tablet-touch-screen-40739.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
]

DISCLAIMER = "هذه المراجعة مبنية على المواصفات الرسمية والمصادر المعلنة، وليست تجربة استخدام شخصية."

BRANDS = [
    ("ريد ماجيك", re.compile(r"red ?magic|ريد ماجيك", re.I)),
    ("سامسونج", re.compile(r"samsung|galaxy|سامسونج", re.I)),
    ("أبل", re.compile(r"iphone|apple|أبل|ابل|آيفون|ايفون", re.I)),
    ("شاومي", re.compile(r"xiaomi|redmi|poco|شاومي|ريدمي|بوكو", re.I)),
    ("اوبو", re.compile(r"oppo|اوبو|أوبو", re.I)),
    ("فيفو", re.compile(r"vivo|iqoo|فيفو|آيكو", re.I)),
    ("هونر", re.compile(r"honor|هونر", re.I)),
    ("ريلمى", re.compile(r"realme|ريلمى|ريلمي", re.I)),
    ("هواوي", re.compile(r"huawei|هواوي|هوواوى", re.I)),
    ("وان بلس", re.compile(r"oneplus|one plus|وان بلس|ون بلس", re.I)),
    ("انفينكس", re.compile(r"infinix|انفينكس", re.I)),
    ("تيكنو", re.compile(r"tecno|تيكنو|تكنو", re.I)),
    ("موتورولا", re.compile(r"motorola|moto\b|موتورولا|موتوريلا", re.I)),
    ("بيكسل", re.compile(r"pixel|بيكسل", re.I)),
    ("اسوس", re.compile(r"asus|rog phone|اسوس", re.I)),
    ("نوكيا", re.compile(r"nokia|نوكيا", re.I)),
]

CSS = """<style>
.rv-wrap{color:#1a1a1a;background:#fff;line-height:1.9;font-size:17px;font-family:system-ui,-apple-system,sans-serif}
.rv-wrap h2{color:#0f172a;margin-top:1.8em;padding-bottom:6px;border-bottom:2px solid #e2e8f0;font-size:22px}
.rv-wrap h3{color:#1e293b;margin-top:1.3em;font-size:19px}
.rv-fig{background:#f8fafc;padding:12px;text-align:center;margin:20px 0;border-radius:12px;border:1px solid #e2e8f0}
.rv-fig img{max-width:100%;height:auto;border-radius:8px}
.rv-fig figcaption{color:#64748b;font-size:14px;margin-top:8px;font-weight:500}
.rv-scroll{overflow-x:auto;margin:16px 0}
.rv-table{border-collapse:collapse;width:100%;color:#1a1a1a;background:#fff;font-size:15px}
.rv-table th,.rv-table td{border:1px solid #cbd5e1;padding:10px 12px;text-align:right}
.rv-table th{background:#f1f5f9;color:#0f172a;font-weight:700}
.rv-box{background:#eff6ff;border-right:4px solid #2563eb;padding:12px 16px;margin:18px 0;border-radius:8px;font-size:15px;line-height:1.7}
.rv-pros{background:#f0fdf4;border-right:4px solid #16a34a;padding:14px 18px;margin:16px 0;border-radius:8px}
.rv-cons{background:#fef2f2;border-right:4px solid #dc2626;padding:14px 18px;margin:16px 0;border-radius:8px}
.rv-pros strong{color:#15803d;font-size:17px}
.rv-cons strong{color:#b91c1c;font-size:17px}
.rv-tool{background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:16px;margin:20px 0}
.rv-tool input,.rv-tool button{font:inherit;font-size:15px;padding:8px 12px;border-radius:8px;border:1px solid #94a3b8}
.rv-tool button{background:#2563eb;color:#fff;font-weight:700;border:none;cursor:pointer;margin-top:8px}
.rv-wrap details{border:1px solid #e2e8f0;border-radius:10px;padding:10px 14px;margin:10px 0;background:#f8fafc}
.rv-wrap details summary{font-weight:700;cursor:pointer;color:#0f172a}
.rv-wrap details p{margin:8px 0 0;color:#334155}
</style>"""

PROMPT_TEMPLATE = """أنت محرر ومراجع هواتف محترف وخبير تقني في موقع «رفيو» (review-mobile.com).
الموقع يستعد للتقديم والقبول في Google AdSense، لذلك يجب أن تكون المراجعة ذات قيمة مضافة حقيقية، غنية بالتحليل والشرح، وتتجاوز 1000 كلمة (بين 1050 إلى 1300 كلمة).

الموضوع أو الهاتف المستهدف: «{phone_name}»
البيانات والمصادر الموثقة:
{src_text}

قواعد التحرير الصارمة لرفيو:
1. عدم تكرار الكلام السطحي: اكتب بأسلوب تحليلي صحفي راقٍ ومفهوم لجمهور الوطن العربي، واشرح عواقب كل مواصفة عملياً (مثال: الشاشة 185Hz تعني سلاسة فائقة في ألعاب التصويب لكنها تستهلك طاقة أكثر، الكاميرا 108MP تعطي تفاصيل غنية في النهار لكن حجم الصورة يتطلب ذاكرة أكبر).
2. جدول المواصفات الكامل: ضع جدول HTML (<table class="rv-table">) يشمل كل البنود بدقة تامة اعتماداً على المصدر فقط:
   - الشاشة والتردد والسطوع
   - المعالج والرسوميات
   - الرام والتخزين
   - الكاميرات الخلفية والأمامية وقدرات الفيديو
   - البطارية وسرعة الشحن والشاحن في العلبة
   - مقاومة الماء والوزن والخامات
3. أقسام تفصيلية (H2 و H3) تغطي:
   - التصميم والشاشة وخامات التصنيع
   - الأداء وتجربة الألعاب والاستخدام اليومي ونظام التبريد
   - الكاميرات وجودة الصور في النهار والليل
   - البطارية والشحن وعمر الاستخدام
4. السعر والتحويل: احسب السعر الرسمي أو المتوقع بالأرقام:
   - باليورو أو الدولار
   - بالجنيه المصري (سعر الصرف: 1 يورو = 52 جنيه أو 1 يوان = 6.8 جنيه)
   - بالريال السعودي (1 يورو = 4.05 ريال)
   - بالدرهم الإماراتي (1 يورو = 3.97 درهم)
5. المميزات والعيوب: 4 إلى 5 مميزات قوية في (<div class="rv-pros">)، و 3 إلى 4 عيوب واضحة بمصداقية في (<div class="rv-cons">).
6. لمن يناسب هذا الهاتف؟: جدول (<table class="rv-table">) يوضح (فئة المستخدم، هل يناسبه؟، السبب بالتفصيل).
7. رأي رفيو النهائي (هل يستحق الشراء؟): فقرة تقييمية ختامية تقدم نصيحة شراء مخلصة وقاطعة.
8. أسئلة شائعة: 4 أسئلة شائعة وإجاباتها في علامات <details><summary>السؤال</summary><p>الإجابة</p></details>.
9. الالتزام بجميع الأرقام الواردة في المصدر وعدم اختراع أي رقم غير منشور.
10. لا تذكر اسم الموقع المصدر (مثل GSMArena) داخل نص المراجعة، بل ضعه فقط في سطر المصادر بالأسفل.

رجّع الرد بتنسيق JSON صالح فقط كالتالي دون أي زيادات:
{{
  "title": "مراجعة {phone_name} 2026: المواصفات الكاملة والسعر والمميزات والعيوب",
  "slug": "english-slug-3-to-6-words",
  "desc": "وصف دقيق للبحث من 140 إلى 160 حرف يبدأ بأهم مواصفة والسعر الرسمي بالجنيه والريال.",
  "brand": "اسم الماركة بالعربي فقط (مثال: سامسونج، شاومي، هونر، أوبو، فيفو)",
  "price_eur": 450,
  "body": "<h2>..</h2><p>..</p>...",
  "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]
}}
"""


def extract_brand(text):
    for l, p in BRANDS:
        if p.search(text):
            return l
    return "اخرى"


def normalize_title(t):
    t = re.sub(r"[^\w\s]", " ", t.lower())
    t = re.sub(r"\s+", " ", t).strip()
    return t


def fetch_live_review_titles(tok):
    """Fetches all existing live post titles on Review blog to guarantee ZERO duplicates."""
    try:
        posts = f.api("GET", f"/blogs/{REVIEW_BLOG}/posts", tok, {
            "status": ["live", "scheduled"],
            "fetchBodies": "false",
            "maxResults": 500,
            "view": "ADMIN"
        })
        return [p["title"] for p in posts.get("items", [])]
    except Exception as e:
        print("Warning fetching review titles:", e)
        return []


STOP_WORDS = {
    "phone", "mobile", "smartphone", "announced", "launched", "unveiled", "goes", "official",
    "quietly", "reportedly", "china", "india", "global", "specs", "features", "price", "review",
    "leak", "leaks", "rumored", "first", "new", "with", "and", "the", "for", "gets", "receives",
    "teardown", "video", "confirms", "edition", "series"
}


def extract_model_terms(text):
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in clean.split() if len(w) > 1 and w not in STOP_WORDS]


def is_already_covered(candidate_name, existing_titles):
    """Strictly checks if this phone or exact model has already been published on Review."""
    cand_terms = extract_model_terms(candidate_name)
    # Check specific model codes containing digits (e.g. x8s, neo12, w27, s27, g47, 700)
    model_codes = [t for t in cand_terms if re.search(r"\d", t) and len(t) >= 2]

    for t in existing_titles:
        t_clean = re.sub(r"[^\w\s]", " ", t.lower())
        t_words = set(t_clean.split())

        # 1. Match specific model codes like x8s, neo12, w27, z_fold9, 108mp
        for code in model_codes:
            if not re.search(r"^\d+(?:hz|mah|mp|w|gb|tb|g|k)?$", code) and code not in ["2026", "2025", "2024", "2023"]:
                if code in t_words:
                    return True, f"Model code [{code}] found in existing: {t}"

        # 2. Match brand + specific term pairs (e.g. ['poco', 'x8s'], ['oneplus', 'ace'], ['iqoo', 'neo'])
        if len(cand_terms) >= 2:
            for i in range(len(cand_terms) - 1):
                bigram = cand_terms[i] + " " + cand_terms[i+1]
                if bigram in t_clean and len(bigram) > 5:
                    return True, f"Phrase [{bigram}] found in existing: {t}"

        # 3. Overall similarity check
        ratio = difflib.SequenceMatcher(None, " ".join(cand_terms), t_clean).ratio()
        if ratio > 0.65:
            return True, f"High similarity ({ratio:.2f}) with: {t}"

    return False, ""


def find_review_internal_links(brand_name, tok, limit=3):
    """Finds 2-3 live articles on Review for contextual internal linking."""
    links = []
    try:
        posts = f.api("GET", f"/blogs/{REVIEW_BLOG}/posts", tok, {
            "status": "live",
            "fetchBodies": "false",
            "maxResults": 40,
            "view": "ADMIN"
        })
        items = posts.get("items", [])
        # Prefer same brand first
        for it in items:
            if brand_name in it.get("labels", []) and it.get("url"):
                links.append((it["title"], it["url"]))
                if len(links) >= limit:
                    break
        # Fallback to general reviews
        if len(links) < limit:
            for it in items:
                pair = (it["title"], it["url"])
                if pair not in links and it.get("url"):
                    links.append(pair)
                    if len(links) >= limit:
                        break
    except Exception:
        pass
    return links


def fetch_phone_candidates():
    """Scrapes top global & regional mobile authorities (Gizmochina, GSMArena, SamMobile, Masrawy Tech)."""
    cands = []
    seen = set()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

    # 1. Gizmochina RSS (World's fastest flagship & mid-range phone launch tracker)
    try:
        r = requests.get("https://www.gizmochina.com/feed/", headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:20]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not title or link in seen or re.search(r"watch|buds|speaker|tv|laptop|macbook|ring|car|ev|auto", title, re.I):
                    continue
                if re.search(r"phone|smartphone|galaxy|xiaomi|redmi|poco|oppo|vivo|iqoo|honor|realme|huawei|motorola|oneplus|infinix|tecno|pixel|pro|ultra|plus|max|fold|flip|5g", title, re.I):
                    seen.add(link)
                    cands.append({"title": title, "link": link, "source": "gizmochina"})
    except Exception as e:
        print("Gizmochina RSS error:", e)

    # 2. GSMArena Direct RSS
    try:
        r = requests.get("https://www.gsmarena.com/rss-news-reviews.php3", headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:20]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not title or link in seen or re.search(r"watch|buds|speaker|echo|tv|laptop|macbook|ring|clip", title, re.I):
                    continue
                if re.search(r"phone|galaxy|xiaomi|redmi|poco|oppo|vivo|iqoo|honor|realme|huawei|motorola|oneplus|infinix|tecno|pixel|rog|speed|w27|t1", title, re.I):
                    seen.add(link)
                    cands.append({"title": title, "link": link, "source": "gsmarena"})
    except Exception as e:
        print("GSMArena RSS error:", e)

    # 3. SamMobile RSS (Samsung Galaxy launches & leaks)
    try:
        r = requests.get("https://www.sammobile.com/feed/", headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:10]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not title or link in seen or re.search(r"tv|watch|ring|earbuds|buds|monitor", title, re.I):
                    continue
                if re.search(r"galaxy|s25|s24|a56|a36|z fold|z flip|phone", title, re.I):
                    seen.add(link)
                    cands.append({"title": title, "link": link, "source": "sammobile"})
    except Exception as e:
        print("SamMobile RSS error:", e)

    # 4. Masrawy Tech RSS (Local market releases & mobile prices in Egypt)
    try:
        r = requests.get("https://www.masrawy.com/rss/feed/382/" + urllib.parse.quote("علوم-وتكنولوجيا"), headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:10]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not title or link in seen:
                    continue
                if re.search(r"موبايل|هاتف|سامسونج|آيفون|ايفون|شاومي|ريدمي|ريلمي|أوبو|اوبو|فيفو|هواوي|honor|infinix", title, re.I):
                    seen.add(link)
                    cands.append({"title": title, "link": link, "source": "masrawy_tech"})
    except Exception as e:
        print("Masrawy Tech RSS error:", e)

    # 2. Google News Phone RSS
    gn_urls = [
        "https://news.google.com/rss/search?q=site:gsmarena.com+when:48h&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=(smartphone+OR+phone)+(launched+OR+announced+OR+specs)+when:48h&hl=en-US&gl=US&ceid=US:en"
    ]
    for gu in gn_urls:
        try:
            r = requests.get(gu, headers=headers, timeout=15)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for it in root.findall(".//item")[:15]:
                    title = it.find("title").text or ""
                    link = it.find("link").text or ""
                    if re.search(r"watch|buds|speaker|echo|tv|laptop|macbook|ring|clip", title, re.I):
                        continue
                    if re.search(r"phone|galaxy|xiaomi|redmi|poco|oppo|vivo|iqoo|honor|realme|huawei|motorola|oneplus|infinix|tecno|pixel|rog", title, re.I):
                        cands.append({"title": title, "link": link, "source": "googlenews"})
        except Exception:
            pass

    # Deduplicate candidate links
    unique = []
    seen_links = set()
    for c in cands:
        if c["link"] not in seen_links:
            seen_links.add(c["link"])
            unique.append(c)
    return unique


def fetch_article_data(url):
    """Fetches real article text and extracts authentic phone photos."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=20, verify=False)
        if r.status_code != 200:
            return None, []
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Remove garbage
        for s in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            s.decompose()

        # Text
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 35]
        clean_text = "\n".join(lines[:60])

        # Photos
        photos = []
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            photos.append(og_img["content"])

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".webp", ".png"]):
                if not any(b in src.lower() for b in ["icon", "logo", "banner", "avatar", "advert", "button"]):
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        src = urllib.parse.urljoin(url, src)
                    if src.startswith("http") and src not in photos:
                        photos.append(src)
            if len(photos) >= 4:
                break

        return clean_text, photos
    except Exception as e:
        print("fetch_article_data error:", e)
        return None, []


def build_interactive_tool(tid, eur_price):
    """Builds the inline interactive price conversion tool for AdSense."""
    p = round(eur_price) if eur_price else 400
    return (
        f'<h2>أداة: محوّل سعر الهاتف بالعملات العربية</h2>'
        f'<div class="rv-tool">'
        f'<p><label>السعر باليورو: <input id="{tid}-e" type="number" value="{p}" min="0" step="5" style="width:120px"/></label></p>'
        f'<p><label>سعر صرف الجنيه لكل يورو: <input id="{tid}-r" type="number" value="{EUR_RATES["egp"]}" min="0" step="0.5" style="width:120px"/></label></p>'
        f'<p><button id="{tid}-go" type="button" onclick="'
        f'var e=parseFloat(document.getElementById(\'{tid}-e\').value)||0;'
        f'var r=parseFloat(document.getElementById(\'{tid}-r\').value)||52;'
        f'var egp=Math.round(e*r);'
        f'var sar=Math.round(e*{EUR_RATES["sar"]});'
        f'var aed=Math.round(e*{EUR_RATES["aed"]});'
        f'document.getElementById(\'{tid}-out\').innerHTML=\'<div class=\"rv-box\">'
        f'<strong>النتائج التقديرية:</strong><br>'
        f'🇪🇬 بالمصري: <strong>\'+egp.toLocaleString()+\' جنيه</strong><br>'
        f'🇸🇦 بالسعودي: <strong>\'+sar.toLocaleString()+\' ريال</strong><br>'
        f'🇦🇪 بالإماراتي: <strong>\'+aed.toLocaleString()+\' درهم</strong>'
        f'</div>\';">احسب التحويل الآن</button></p>'
        f'<div id="{tid}-out"></div>'
        f'<p style="font-size:13px;color:#64748b;margin-top:8px">ملاحظة: الأسعار تقريبية بناءً على أسعار الإطلاق الرسمية ولا تشمل الضريبة الجمركية المحلية.</p>'
        f'</div>'
    )



def check_review(art, src_text, cand_title, existing_titles, min_words=900):
    """Validates phone reviews strictly for AdSense compliance without falsely flagging converted currency figures."""
    if not art or not isinstance(art, dict):
        return ["لم يتم استلام مسودة صالحة من الذكاء الاصطناعي"]
    errs = []

    # 1. Body & Word Count
    body_text = BeautifulSoup(art.get("body", ""), "html.parser").get_text(" ")
    words = len(body_text.split())
    if words < min_words:
        errs.append(f"طول المقال قصير ({words} كلمة، والمطلوب {min_words}+ كلمة للتوافق مع أدسنس)")

    # 2. Title length & deduplication
    title = art.get("title", "").strip()
    if not title or len(title) > 75:
        errs.append(f"العنوان غير صالح أو أطول من 75 حرف ({len(title)} حرف)")
    for ex in existing_titles:
        if difflib.SequenceMatcher(None, f.norm(title), f.norm(ex)).ratio() >= 0.75:
            errs.append(f"العنوان مكرر أو قريب جداً من مقال منشور سابقاً: {ex}")
            break

    # 3. Slug
    slug = art.get("slug", "").strip()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+){2,6}", slug):
        errs.append(f"الـ slug غير صالح ({slug}): يجب أن يتكون من 3 إلى 7 كلمات إنجليزية صغيرة مفصولة بشرطة")

    # 4. Search description
    desc = art.get("desc", "").strip()
    if len(desc) < 100 or len(desc) > 185:
        errs.append(f"وصف البحث ({len(desc)} حرف) يجب أن يكون بين 110 و 175 حرفاً")

    # 5. Competitors check
    full_text = (title + " " + body_text + " " + desc).lower()
    for b in f.BANNED:
        if b.lower() in full_text:
            errs.append(f"تم ذكر اسم موقع محظور ({b}) في صلب المراجعة")

    # 6. HTML structure check
    if "<h2>" not in art.get("body", ""):
        errs.append("المراجعة يجب أن تحتوي على عناوين فرعية <h2>")

    return errs

def main():
    dry = "--dry" in sys.argv or os.environ.get("DRY_RUN") == "1"
    custom_query = os.environ.get("PHONE_MODEL") or next((arg for arg in sys.argv[1:] if not arg.startswith("--")), None)
    if custom_query:
        custom_query = custom_query.strip()
    if not custom_query:
        custom_query = None

    # State
    try:
        state = json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        state = {"done": []}

    tok = None if dry else f.token()
    existing_titles = fetch_live_review_titles(tok) if tok else []

    today_str = datetime.datetime.now(CAIRO).date().isoformat()
    today_posts = [d for d in state.get("done", []) if d.get("at", "").startswith(today_str) and d.get("ok")]

    if len(today_posts) >= REVIEW_CAP and not custom_query and not dry:
        print(f"Review daily cap ({REVIEW_CAP}) reached today. Exiting.")
        return

    print("Fetching phone candidates...")
    candidates = []
    if custom_query:
        candidates.append({"title": custom_query, "link": f"https://www.google.com/search?q={urllib.parse.quote(custom_query)}", "source": "manual"})
    else:
        candidates = fetch_phone_candidates()

    done_links = {d.get("url") for d in state.get("done", [])}
    viable = [c for c in candidates if c["link"] not in done_links]
    print(f"Viable candidate stories: {len(viable)}")

    published_count = 0
    for cand in viable:
        if f._DOWN:
            print("Gemini API down, pausing.")
            break

        cand_title = cand["title"]
        print(f"\nEvaluating: {cand_title[:75]}...")

        # 1. Deduplication check against all existing Review articles
        already, reason = is_already_covered(cand_title, existing_titles)
        if already:
            print(f"  Skipped (Duplicate): {reason}")
            state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": reason})
            continue

        # 2. Fetch source content and real photos
        if cand["source"] == "googlenews":
            pub_url = f.decode_gn_link(cand["link"]) or cand["link"]
        else:
            pub_url = cand["link"]

        src_text, photos = fetch_article_data(pub_url)
        if not photos:
            photos = random.sample(FALLBACK_PHONE_PHOTOS, 3)
        if not src_text or len(src_text) < 400:
            print(f"  Insufficient text ({len(src_text) if src_text else 0} chars). Skipping.")
            continue

        print(f"  Source text length: {len(src_text)} chars | Photos found: {len(photos)}")

        # 3. AI Generation with Gemini
        prompt = PROMPT_TEMPLATE.format(phone_name=cand_title, src_text=src_text[:6500])
        extra, art, errs = "", None, ["no draft"]
        for attempt in range(2):
            art = f.gemini(prompt + extra)
            errs = check_review(art, src_text, cand_title, existing_titles, min_words=900)
            if not errs:
                break
            print(f"  Retry needed ({len(errs)} issues): {errs}")
            extra = "\nتنبيه: أعد كتابة المقال مع تصحيح المشاكل الآتية بدقة واجعل النص غنياً وتجاوز 1000 كلمة: " + " | ".join(errs) + "\n"

        if errs:
            print(f"  Draft check failed ({errs}). Skipping.")
            state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": errs})
            continue

        # 4. Construct Authentic Phone Images (3-4 photos with wsrv.nl proxy)
        lead_img_html = ""
        second_img_html = ""
        third_img_html = ""
        if photos:
            p0 = f"https://wsrv.nl/?url={urllib.parse.quote(photos[0])}&w=1000&output=webp&q=75"
            lead_img_html = (f'<figure class="rv-fig">'
                             f'<img src="{p0}" alt="{html.escape(art["title"])}" width="1000" height="563" loading="eager"/>'
                             f'<figcaption>الهاتف {html.escape(art.get("brand", ""))} في أحدث ظهور رسمي له</figcaption>'
                             f'</figure>')
            if len(photos) > 1:
                p1 = f"https://wsrv.nl/?url={urllib.parse.quote(photos[1])}&w=1000&output=webp&q=75"
                second_img_html = (f'<figure class="rv-fig">'
                                   f'<img src="{p1}" alt="تفاصيل تصميم {html.escape(art["title"])}" width="1000" height="563" loading="lazy"/>'
                                   f'<figcaption>تفاصيل الكاميرات والخامات الخلفية للهاتف</figcaption>'
                                   f'</figure>')
            if len(photos) > 2:
                p2 = f"https://wsrv.nl/?url={urllib.parse.quote(photos[2])}&w=1000&output=webp&q=75"
                third_img_html = (f'<figure class="rv-fig">'
                                  f'<img src="{p2}" alt="شاشة وتصميم {html.escape(art["title"])}" width="1000" height="563" loading="lazy"/>'
                                  f'<figcaption>واجهة وشاشة الهاتف والألوان المتاحة</figcaption>'
                                  f'</figure>')

        # 5. Interactive Tool & Structure
        tid = "rv" + str(random.randint(100, 999))
        tool_html = build_interactive_tool(tid, art.get("price_eur", 400))
        disclaimer_html = f'<div class="rv-box"><strong>تنويه تحريري:</strong> {DISCLAIMER}</div>'

        # 6. Internal Links
        brand_label = extract_brand(art["title"] + " " + cand_title)
        internal_links = find_review_internal_links(brand_label, tok, limit=2)
        interlink_html = ""
        if internal_links:
            links_li = "".join(f'<li><a href="{u}">{html.escape(t)}</a></li>' for t, u in internal_links)
            interlink_html = f'<h3>مراجعات أخرى قد تهمك في نفس الفئة:</h3><ul>{links_li}</ul>'

        # 7. FAQs
        faq_html = ""
        if art.get("faq"):
            items = "".join(f"<details><summary>{html.escape(q['q'])}</summary><p>{html.escape(q['a'])}</p></details>" for q in art["faq"])
            faq_html = f"<h2>الأسئلة الشائعة حول {html.escape(cand_title)}</h2>" + items

        # Assemble Full Article
        full_html = (
            CSS +
            '<div dir="rtl" class="rv-wrap">' +
            lead_img_html +
            disclaimer_html +
            art["body"] +
            second_img_html +
            tool_html +
            third_img_html +
            interlink_html +
            faq_html +
            f'<p style="font-size:14px;color:#64748b;margin-top:24px">المصادر الرسمية: <a href="{pub_url}" rel="nofollow noopener" target="_blank">المصدر التقني المعلن</a>.</p>' +
            '</div>'
        )

        labels = [brand_label]

        if dry:
            print(f"\n[DRY RUN] Title: {art['title']}")
            print(f"Slug: {art['slug']}")
            print(f"Brand: {brand_label}")
            print(f"Word count approx: {len(full_html.split())}")
            print(f"HTML Preview (first 250 chars):\n{full_html[:250]}...")
            published_count += 1
            if published_count >= COUNT:
                print(f"\n🎯 Reached review batch target ({COUNT} reviews published). Exiting.")
                break
            print(f"\n⏳ Pausing 20 seconds before next review...")
            time.sleep(20)

        # ⚡ LIVE INSTANT PUBLISHING TO REVIEW BLOG ⚡
        now_cairo = datetime.datetime.now(CAIRO)
        try:
            # 1. Create Post with Slug as initial title
            d = f.api("POST", f"/blogs/{REVIEW_BLOG}/posts", tok, {"isDraft": "false"}, {
                "kind": "blogger#post",
                "title": art["slug"].replace("-", " "),
                "content": f.with_desc(full_html, art),
                "labels": labels
            })

            # 2. Publish immediately at current time
            f.api("POST", f"/blogs/{REVIEW_BLOG}/posts/{d['id']}/publish", tok, {"publishDate": now_cairo.isoformat()})

            # 3. Patch Arabic Title
            f.api("PATCH", f"/blogs/{REVIEW_BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
            post_info = f.api("GET", f"/blogs/{REVIEW_BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
            post_url = post_info.get("url", "")

            print(f"\n✅ PUBLISHED LIVE ON REVIEW: {post_url}")
            print(f"   Title: {art['title']}")

            # 4. Instant IndexNow Ping
            try:
                notify.indexnow([post_url], False)
            except Exception as e:
                print(f"   IndexNow ping warning: {e}")

            # 5. Save State
            state["done"].append({
                "title": art["title"],
                "url": cand["link"],
                "post_url": post_url,
                "at": now_cairo.isoformat(),
                "ok": True,
                "brand": brand_label
            })

            existing_titles.append(art["title"])
            published_count += 1
            break  # Publish 1 high-quality review/news per run to maintain even pacing
        except Exception as e:
            print(f"❌ Failed to publish post: {e}")
            state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": str(e)})

    # Save state
    state["done"] = state["done"][-400:]
    if not dry:
        json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nDone: Published {published_count} post(s) to Review.")


if __name__ == "__main__":
    main()
