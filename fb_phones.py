"""Auto-publish phone articles (from Review + Egyptaway) to the Facebook Page with:
1. 100% Clean, Watermark-Free Base Images (strips/bypasses 'رفيو', 'ايجبتاوى', GSMArena, Gizmochina, SamMobile watermarks).
2. Custom Transparent «موبايل بالعربى» Calligraphy Watermark (img/mobile_belaraby_wm.png) whose font color
   automatically adapts to match and contrast with each individual photo's palette and background brightness.
3. Facebook Policy & Anti-Spam Guard:
   - Never posts multiple posts back-to-back (max 1 post per auto run).
   - Randomized 75-130 minute gap between posts, and safe daily cap.
   - Automatic alternation between Link posts (Title + Image + Link) and Complete Native No-Link posts (~1/3 of posts)
     as a natural separator.
"""
import argparse, colorsys, datetime, difflib, hashlib, html, io, json, os, random, re, sys, urllib.parse
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, features
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None
HAS_RAQM = bool(features.check("raqm"))
import football as f

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REVIEW_BLOG = "2997328666613207792"
EA_BLOG = "8325646053257070334"
DEFAULT_PAGE_ID = "1959788610952661"  # صفحة موبايل بالعربى
STATE_FILE = os.path.join(BASE_DIR, "notify_sent.json")
REVIEW_STATE_FILE = os.path.join(BASE_DIR, "review_posted.json")
LOCAL_FB_FILE = os.path.join(BASE_DIR, ".fb_token.json")
WM_MASK_PATH = os.path.join(BASE_DIR, "img", "mobile_belaraby_wm.png")
AR_FONT_PATH = os.path.join(BASE_DIR, "fonts", "NotoKufiArabic.ttf")
AR_FONT_URL = "https://github.com/google/fonts/raw/main/ofl/notokufiarabic/NotoKufiArabic%5Bwght%5D.ttf"
IMG_DIR = os.path.join(BASE_DIR, "img")
CDN = "https://cdn.jsdelivr.net/gh/mohsenxpca/matches-data@main/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
_RESOLVED_TOKEN_CACHE = {}

MIN_GAP_MINUTES = 75
MAX_GAP_MINUTES = 130
DAILY_CAP = 10

PHONE_LABELS = {
    "هواتف", "أخبار هواتف", "اخبار هواتف", "موبايلات", "اسعار الموبايلات", "أسعار الموبايلات",
    "سامسونج", "أبل", "ابل", "شاومي", "ريلمي", "ريلمى", "اوبو", "أوبو", "فيفو", "هونر",
    "انفنكس", "انفينكس", "تكنو", "تيكنو", "ون بلس", "وان بلس", "هواوي", "موتورولا",
    "بيكسل", "نوكيا", "سوني", "اسوس", "ناثينج", "ريد ماجيك"
}

NON_PHONE_EA_LABELS = {
    "أخبار الكورة", "مواعيد المباريات", "الدوري المصري", "الزمالك", "الأهلي",
    "رصد الأعطال", "ذهب وعملات", "مواقيت الصلاة", "الطقس",
    "العاب", "ألعاب", "أخبار الألعاب", "تحميل ألعاب", "شحن ألعاب", "عروض",
    "طرق الربح", "كمبيوتر", "الذكاء الاصطناعى", "شروحات", "تطبيقات", "تقنية", "اندرويد"
}

REAL_PHONE_BRAND_RX = re.compile(
    r"(جالاكسي|جلاكسي|سامسونج|آيفون|ايفون|شاومي|ريدمي|بوكو|ريلمي|ريلمى|"
    r"أوبو|اوبو|فيفو|هونر|انفنكس|انفينكس|تكنو|تيكنو|ون بلس|وان بلس|موتورولا|بيكسل|هواوي|ريد ماجيك|ناثينج|نثينج|"
    r"\bgalaxy\b|\biphone\b|\bsamsung\b|\bxiaomi\b|\bredmi\b|\bpoco\b|\brealme\b|\boppo\b|\bvivo\b|"
    r"\biqoo\b|\bhonor\b|\binfinix\b|\btecno\b|\boneplus\b|\bmotorola\b|\bpixel\b|\bhuawei\b|"
    r"\bredmagic\b|\bnothing\s*phone\b|\bone\s*ui\b|\bhyperos\b|\bcoloros\b|\bmagic\s*os\b|\bios\s*\d+|"
    r"معالج(?:ات)?\s*الهواتف|\bsnapdragon\b|\bdimensity\b|\bexynos\b|أفضل\s*هاتف|أفضل\s*هواتف|مقارنة\s*هواتف)",
    re.I
)

ENGAGEMENT_QUESTIONS = [
    "💬 شاركنا رأيك في التعليقات: شايف المواصفات دي مناسبة ولا كنت تتوقع أفضل؟",
    "💬 إيه أكتر ميزة لفتت نظرك في الموبايل ده؟ شاركنا رأيك!",
    "💬 من وجهة نظرك، هل الهاتف ده هينافس بقوة في فئته السعرية؟",
    "💬 لو بتفكر تجدد موبايلك قريب، هل الموديل ده هيكون ضمن اختياراتك؟",
    "💬 تفضل الشركة دي في الموبايلات ولا ليك تجربة أفضل مع ماركة تانية؟"
]

PROMO_SKIP_RX = re.compile(
    r"(موضوع يهمك|يمكنك أيضاً قراءة|يمكنك ايضا قراءة|اقرأ أيضاً|اقرأ ايضا|شاهد أيضاً|قد يهمك|"
    r"لمتابعة كافة التفاصيل|مقالات ذات صلة|مراجعات أخرى قد تهمك|تغطيات ومراجعات أخرى|"
    r"أدواتنا المجانية|أداة مقارنة الهواتف|جدول أسعار الموبايلات المحدث|أفضل هاتف لميزانيتك|"
    r"قارن الآن في أداة|المصادر الرسمية|المصدر التقني المعلن|هذه المراجعة مبنية على المواصفات|"
    r"تنويه تحريري|في هذا المقال|نستعرض في هذا|الخلاصة السريعة في سطرين|https?://|\bwww\.)",
    re.I
)

FB_VIRAL_STYLES = [
    ("debate", "أسلوب النقاش والجدل: ابدأ بسؤال أو جملة مثيرة للنقاش عن الهاتف/الميزة، اعرض 3-4 حقائق سريعة، واختم بسؤال يخلي المتابعين يتجادلوا في الكومنتات (مثلاً: هل يستحق ولا أوفر برايسد؟ سامسونج ولا منافس تاني؟)."),
    ("breakdown", "أسلوب الخلاصة في 30 ثانية: ابدأ بجملة تلخص أهم مفاجأة في الخبر، بعدها نقاط قصيرة جداً (✅ المميزات / ⚠️ الملاحظات أو أبرز الأرقام)، واختم بسؤال مباشر للمتابعين."),
    ("breaking", "أسلوب الخبر العاجل الخاطف: ابدأ بهوك قوي يوقف السكرول عن أحدث تسريب أو تحديث، اذكر أهم 3 تفاصيل رقمية بوضوح، واختم بسؤال تفاعلي قصير."),
    ("buyer", "أسلوب نصيحة قبل الشراء: ابدأ بسؤال (لو بتفكر تغير موبايلك..)، لخص مين اللي الموبايل ده مناسب ليه ومين لأ بناءً على الحقائق، واختم بسؤال عن اختيار المتابعين.")
]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fp:
            state = json.load(fp)
    except Exception:
        state = {}
    for k in ("sent", "indexed", "tg", "fb", "fb_history", "fb_stories"):
        state.setdefault(k, [])
    return state


def save_state(state):
    for k in ("sent", "indexed", "tg", "fb", "fb_history", "fb_stories"):
        if k in state:
            state[k] = state[k][-400:]
    with open(STATE_FILE, "w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=1)


def first_image(body, post=None):
    m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', body or "", flags=re.I)
    if m:
        return html.unescape(m.group(1))
    if post and post.get("images"):
        try:
            return post["images"][0]["url"]
        except Exception:
            pass
    return None


SAMSUNG_RX = re.compile(
    r"(سامسونج|جالاكسي|جلاكسي|جود\s*لوك|بيكسبي|نوكس|إكسينوس|"
    r"\bsamsung\b|\bgalaxy\b|\bone\s*ui\b|\bgood\s*lock\b|\bbixby\b|\bknox\b|\bexynos\b|"
    r"\bsmart\s*switch\b|\bgalaxy\s*ai\b|\bgalaxy\s*store\b|"
    r"samsung\s*(?:notes|wallet|health|gallery|internet|pay|pass|members|camera|dex|flow|cloud))",
    re.I
)

NON_PHONE_DEVICE_RX = re.compile(
    r"(لابتوب|لابتوبات|حاسوب|حواسيب|\blaptop\b|\bmacbook\b|\bgooglebook\b|\bchromebook\b|"
    r"تلفزيون|تلفاز|غسالة|ثلاجة|مكنسة|مكيف|ساعة\s*ذكية|ساعات\s*ذكية|\bsmartwatch\b|\bsmart\s*band\b|\bwatch\b|"
    r"\bwalkie[\s-]?talkie\b|سماعة|سماعات|\bearbuds\b|\bbuds\b|\bfreeclip\b|\bheadphones\b|"
    r"شاحن|كابل|كابلات|\bcharger\b|\bcable\b|سيارة|\bzeekr\b|"
    r"موبايل\s*ليجندز|ببجي|\bpubg\b|فري\s*فاير|\bfree\s*fire\b|شحن\s*(?:ماسات|شدات|جواهر)|"
    r"حساسية|سرعة\s*البيك|فريم|\bfps\b|أكواد\s*فودافون|العاب|ألعاب|لعبة|\bmlbb\b|\bgta\b|فيفا|دريم\s*ليج|روبلوكس|"
    r"مكالمات\s*مزعجة|حظر\s*المكالمات|\brobocalls\b|بطاقتك|المطارات|هويتك|راكن\s*في\s*الدرج|قديم.*كمبيوتر|"
    r"تشفير\s*كمي|\bqencrypt\b|واي\s*فاي\s*نيبال|\bwifi\s*nepal\b|نقل\s*محادثات\s*واتساب|واتساب|فيسبوك|إنستجرام|تيك\s*توك|"
    r"تقسيم\s*الشاشة|تطبيقين\s*على\s*شاشة|كنا\s*بنعشقها|مميزات\s*قديمة|بدون\s*انترنت|خفيفة\s*للموبايل)",
    re.I
)

MODEL_KEY_RX = re.compile(
    r"\b((?:galaxy|iphone|xiaomi|redmi|poco|honor|vivo|oppo|realme|oneplus|huawei|pixel|motorola|moto|infinix|tecno|redmagic|nothing|iqoo|one\s*ui)"
    r"(?:\s+[a-z0-9+]+){1,3})\b",
    re.I
)


def _normalize_ar(text):
    t = html.unescape(text or "").lower()
    t = re.sub(r"[📱📌⚙️💬🔥⚡🚀]", " ", t)
    t = re.sub(r"[إأآا]", "ا", t)
    t = re.sub(r"[ىي]", "ي", t)
    t = re.sub(r"ة", "ه", t)
    t = re.sub(r"[^\w\s\u0600-\u06FF]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_model_keys(title):
    keys = set()
    for m in MODEL_KEY_RX.findall(html.unescape(title or "")):
        norm = re.sub(r"\s+", " ", m.strip().lower())
        # Keep only model keys that include a digit or specific sub-series (avoid generic 'galaxy phone')
        if re.search(r"\d|\b(ultra|fold|flip|pro|max|plus|mini|air|neo|lite|magic|reno|razr|edge)\b", norm):
            # Take first 3 tokens max so 'galaxy z fold 9' or 'honor magic v7' match cleanly
            parts = norm.split()
            keys.add(" ".join(parts[:3]))
            if len(parts) >= 2 and re.search(r"\d", parts[1]):
                keys.add(" ".join(parts[:2]))
    return keys


def fetch_recent_live_fb_posts(limit=30):
    """Fetches the actual live recent posts from the Facebook Page to prevent ANY duplicate posts or race conditions."""
    tok, page = get_fb_credentials()
    if not tok or not page:
        return []
    try:
        r = requests.get(
            f"https://graph.facebook.com/{page}/posts",
            params={"fields": "id,created_time,message", "limit": limit, "access_token": tok},
            timeout=15
        )
        if r.ok:
            return r.json().get("data", [])
    except Exception as ex:
        print(f"  [Live FB check warning] {ex}")
    return []


def is_duplicate_on_fb(title, url, state, live_posts):
    """Checks exact URL, title similarity, and phone model overlap against BOTH local state and live Facebook posts."""
    clean_url = (url or "").replace("http://", "https://").strip()
    if clean_url in set(state.get("fb", [])):
        return True, "URL already in state['fb']"

    norm_t = _normalize_ar(title)
    cand_models = _extract_model_keys(title)

    # Check against recent 40 entries in fb_history
    recent_titles = [(h.get("title") or "", h.get("url") or "") for h in state.get("fb_history", [])[-40:]]
    # Check against live posts currently on Facebook Page
    for lp in (live_posts or []):
        msg = lp.get("message") or ""
        if clean_url and clean_url in msg:
            return True, "URL already live on Facebook Page"
        first_line = msg.splitlines()[0] if msg.splitlines() else ""
        if first_line:
            recent_titles.append((first_line, ""))

    for prev_t, prev_u in recent_titles:
        if prev_u and prev_u.replace("http://", "https://").strip() == clean_url:
            return True, "URL matched in fb_history"
        norm_prev = _normalize_ar(prev_t)
        if not norm_prev:
            continue
        ratio = difflib.SequenceMatcher(None, norm_t, norm_prev).ratio()
        if ratio >= 0.58:
            return True, f"similar title ({ratio:.2f}) to '{prev_t[:45]}'"
        if cand_models:
            prev_models = _extract_model_keys(prev_t)
            overlap = cand_models & prev_models
            if overlap:
                return True, f"same phone model {overlap} already posted in '{prev_t[:45]}'"

    return False, "unique"


def is_samsung_post(post):
    title = html.unescape(post.get("title", ""))
    labels = set(post.get("labels") or [])
    if "سامسونج" in labels:
        return True
    return bool(SAMSUNG_RX.search(title))


def is_phone_post(post, blog_id=None):
    """Strict smartphone-only filter:
       - Allows ALL Samsung phone news, Samsung apps (Good Lock, Galaxy AI, etc.), and One UI updates.
       - Rejects ALL games (PUBG, Free Fire, MLBB, etc.), accessories, laptops, watches, earbuds, and generic tips.
       - For non-Samsung posts, requires an explicit smartphone brand/model/hardware topic.
    """
    url = post.get("url", "")
    title = html.unescape(post.get("title", ""))
    labels = set(post.get("labels") or [])

    # Always reject non-phone devices, games, and generic fluff
    if NON_PHONE_DEVICE_RX.search(title):
        # Exception ONLY if it's an explicit Samsung phone/One UI/Good Lock update or app
        if not (is_samsung_post(post) and re.search(r"(one\s*ui|good\s*lock|جود\s*لوك|galaxy\s*[sazmf]|تحديث|تطبيق|هاتف|هواتف|جالاكسي)", title, re.I)):
            return False

    # Samsung phones, Samsung apps, and One UI updates ALWAYS pass
    if is_samsung_post(post):
        if not re.search(r"(لابتوب|حاسوب|laptop|googlebook|تلفزيون|غسالة|ثلاجة|مكنسة|مكيف)", title, re.I):
            return True

    # On Egyptaway, reject non-phone sections immediately
    if blog_id != REVIEW_BLOG and "review-mobile.com" not in url:
        if labels & NON_PHONE_EA_LABELS:
            return False
        if not (labels & PHONE_LABELS):
            return False

    # Must explicitly be about a real smartphone brand, phone model, or mobile chipset
    return bool(REAL_PHONE_BRAND_RX.search(title))


def _is_white_backdrop(im):
    rgb = im.convert("RGB")
    w, h = rgb.size
    pts = [
        (3, 3), (w - 4, 3), (3, h - 4), (w - 4, h - 4),
        (w // 2, 3), (3, h // 2), (w - 4, h // 2)
    ]
    bright = 0
    for x, y in pts:
        r, g, b = rgb.getpixel((max(0, min(w - 1, x)), max(0, min(h - 1, y))))
        if r >= 236 and g >= 236 and b >= 236 and max(r, g, b) - min(r, g, b) <= 14:
            bright += 1
    return bright >= 5


def _format_raw_phone_image_1200x675(raw_im, src_url=""):
    """Formats a raw phone photo to 1200x675 while trimming off source-site watermarks (GSMArena/Gizmochina/SamMobile)
       and WITHOUT adding any 'رفيو' or 'ايجبتاوى' watermarks or badges.
    """
    im = raw_im.convert("RGB")
    w, h = im.size
    low_u = (src_url or "").lower()

    # If portrait or studio white-background render: place cleanly on 1200x675 studio/blurred canvas without any text/watermark
    white_bg = _is_white_backdrop(im)
    is_portrait_or_sq = (w / max(1, h)) < 1.25

    if white_bg or is_portrait_or_sq:
        if white_bg:
            # Trim bottom 6% if GSMArena/Gizmochina studio shot has corner logo
            if any(k in low_u for k in ("gsmarena", "gizmochina", "91mobiles", "mysmartprice")):
                im = im.crop((0, 0, w, int(h * 0.93)))
                w, h = im.size
            canvas = Image.new("RGBA", (1200, 675), (248, 250, 252, 255))
            arr_bg = np.zeros((675, 1200, 4), dtype=np.uint8)
            for y in range(675):
                v = int(252 - (y / 675.0) * 12)
                arr_bg[y, :, 0] = v
                arr_bg[y, :, 1] = min(255, v + 1)
                arr_bg[y, :, 2] = min(255, v + 3)
                arr_bg[y, :, 3] = 255
            canvas = Image.fromarray(arr_bg)
        else:
            if any(k in low_u for k in ("gsmarena", "gizmochina", "sammobile", "phonearena")):
                im = im.crop((0, 0, w, int(h * 0.90)))
                w, h = im.size
            bg = ImageOps.fit(im, (1200, 675), method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(28))
            bg = ImageEnhance.Brightness(bg).enhance(0.62)
            canvas = bg.convert("RGBA")

        scale = min(900 / max(1, w), 575 / max(1, h))
        if w < 250:
            scale = min(scale, 2.75)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        scaled = im.resize((nw, nh), Image.Resampling.LANCZOS)
        scaled = ImageEnhance.Sharpness(scaled).enhance(1.12)
        scaled = ImageEnhance.Contrast(scaled).enhance(1.04)
        s_rgba = scaled.convert("RGBA")

        if white_bg:
            s_arr = np.array(s_rgba)
            cr, cg, cb = int(s_arr[2, 2, 0]), int(s_arr[2, 2, 1]), int(s_arr[2, 2, 2])
            tr, tg, tb = max(230, cr - 12), max(230, cg - 12), max(230, cb - 12)
            rgb_part = s_arr[:, :, :3].astype(np.int16)
            spread = np.max(rgb_part, axis=2) - np.min(rgb_part, axis=2)
            mask = (s_arr[:, :, 0] >= tr) & (s_arr[:, :, 1] >= tg) & (s_arr[:, :, 2] >= tb) & (spread <= 15)
            s_arr[mask, 3] = 0
            s_rgba = Image.fromarray(s_arr)

        px_x = (1200 - nw) // 2
        px_y = (675 - nh) // 2
        canvas.alpha_composite(s_rgba, (px_x, px_y))
        return canvas.convert("RGB")

    # Landscape photo: trim source site watermark margins at bottom/edges
    if "gsmarena" in low_u:
        bot_ratio = 0.845
    else:
        bot_ratio = 0.90

    im_c = im.crop((int(w * 0.015), int(h * 0.015), int(w * 0.985), int(h * bot_ratio)))
    target = ImageOps.fit(im_c, (1200, 675), method=Image.Resampling.LANCZOS, centering=(0.5, 0.46))
    target = ImageEnhance.Contrast(target).enhance(1.04)
    target = ImageEnhance.Color(target).enhance(1.02)
    target = ImageEnhance.Sharpness(target).enhance(1.08)
    return target


def _clean_fallback_watermarked_image(im, img_url=""):
    """If an existing image already had a 'رفيو' watermark (bottom-left y=545..675, top-right pill y=18..72)
       or an Egyptaway bottom banner, crops/cleans those zones so zero old watermark remains.
    """
    rgb = im.convert("RGB")
    w, h = rgb.size
    low = (img_url or "").lower()
    if "review-" in low:
        # Remove top-right pill (top 11%) and bottom-left Review watermark (bottom 18.5%)
        cropped = rgb.crop((int(w * 0.04), int(h * 0.115), int(w * 0.96), int(h * 0.81)))
        return ImageOps.fit(cropped, (1200, 675), method=Image.Resampling.LANCZOS)
    # Trim bottom 10% for any potential source watermark
    cropped = rgb.crop((int(w * 0.01), int(h * 0.01), int(w * 0.99), int(h * 0.91)))
    return ImageOps.fit(cropped, (1200, 675), method=Image.Resampling.LANCZOS)


def resolve_clean_base_image(post_url, img_url, content="", title=""):
    """Obtains a 100% watermark-free 1200x675 base PIL.Image for a phone article (no 'رفيو' or third-party watermark)."""
    clean_post_url = (post_url or "").replace("http://", "https://").strip()
    img_u = (img_url or first_image(content) or "").strip()

    # 1. If it's a Review article or a review-*.jpg image, check for pre-watermark raw-{slug}-0.jpg or original source photo
    m_slug = re.search(r"review-([a-z0-9-]+)-\d+\.jpg", img_u, re.I)
    if m_slug:
        slug = m_slug.group(1)
        local_raw = os.path.join(IMG_DIR, f"raw-{slug}-0.jpg")
        if os.path.exists(local_raw):
            try:
                return Image.open(local_raw).convert("RGB")
            except Exception:
                pass
        try:
            r_raw = requests.get(f"{CDN}img/raw-{slug}-0.jpg", headers=UA, timeout=12)
            if r_raw.status_code == 200 and len(r_raw.content) > 5000:
                return Image.open(io.BytesIO(r_raw.content)).convert("RGB")
        except Exception:
            pass

    if "review-mobile.com" in clean_post_url or "review-" in img_u:
        orig_source_url = ""
        cand_title = ""
        raw_photo_url = ""

        # Check review_posted.json
        if os.path.exists(REVIEW_STATE_FILE):
            try:
                rv_state = json.load(open(REVIEW_STATE_FILE, encoding="utf-8"))
                for item in reversed(rv_state.get("done", [])):
                    p_u = (item.get("post_url") or "").replace("http://", "https://")
                    if p_u and p_u == clean_post_url:
                        raw_photo_url = item.get("raw_photo") or ""
                        orig_source_url = item.get("url") or ""
                        cand_title = item.get("cand_title") or ""
                        break
            except Exception:
                pass

        # Also check article HTML for المصدر التقني المعلن link
        if not orig_source_url and content:
            m_src = re.search(r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>المصدر التقني المعلن</a>', content)
            if m_src:
                orig_source_url = html.unescape(m_src.group(1)).strip()

        raw_candidates = []
        if raw_photo_url:
            raw_candidates.append(raw_photo_url)

        if not raw_candidates and (orig_source_url or cand_title or title):
            try:
                import review_engine as re_eng
                src_u = orig_source_url
                if "news.google.com" in src_u:
                    src_u = re_eng.decode_gn_link(src_u) or src_u
                if src_u.startswith("http"):
                    _, extracted = re_eng.fetch_article_data(src_u)
                    raw_candidates.extend(extracted or [])
                if not raw_candidates:
                    extra = re_eng.lookup_real_phone_photos(cand_title or title)
                    raw_candidates.extend(extra or [])
            except Exception as ex:
                print(f"  [Raw source photo lookup warning] {ex}")

        for rc_url in raw_candidates[:3]:
            try:
                hdrs = {**UA, "Referer": "https://www.gsmarena.com/"} if "gsmarena" in rc_url.lower() else UA
                r = requests.get(rc_url, headers=hdrs, timeout=20)
                if r.status_code == 200 and len(r.content) > 4000:
                    raw_im = Image.open(io.BytesIO(r.content))
                    print(f"  ✨ Fetched un-watermarked original source photo: {rc_url[:80]}")
                    return _format_raw_phone_image_1200x675(raw_im, src_url=rc_url)
            except Exception:
                continue

    # 2. For Egyptaway / wsrv.nl / general phone image URLs: unwrap wsrv.nl to see original domain & download raw
    if img_u:
        underlying_url = img_u
        if "wsrv.nl" in img_u and "url=" in img_u:
            try:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(img_u).query)
                if qs.get("url"):
                    underlying_url = qs["url"][0]
            except Exception:
                pass

        for target_u in ([underlying_url, img_u] if underlying_url != img_u else [img_u]):
            try:
                hdrs = {**UA, "Referer": "https://www.gsmarena.com/"} if "gsmarena" in target_u.lower() else UA
                r = requests.get(target_u, headers=hdrs, timeout=22)
                if r.status_code == 200 and len(r.content) > 3000:
                    im = Image.open(io.BytesIO(r.content))
                    if "review-" in target_u.lower():
                        return _clean_fallback_watermarked_image(im, target_u)
                    return _format_raw_phone_image_1200x675(im, src_url=target_u)
            except Exception:
                continue

    return None


def _get_dominant_hue(im):
    """Finds the dominant color hue (0.0..1.0) of the phone photo using circular weighted mean in HSV space."""
    small = im.resize((64, 36), Image.Resampling.BILINEAR).convert("RGB")
    arr = np.array(small, dtype=np.float32) / 255.0
    hues = []
    weights = []
    for row in arr:
        for r, g, b in row:
            h, s, v = colorsys.rgb_to_hsv(float(r), float(g), float(b))
            if s > 0.14 and 0.12 < v < 0.95:
                hues.append(h)
                weights.append((s ** 1.1) * v)
    if not hues:
        return None
    angles = np.array(hues) * 2.0 * np.pi
    w = np.array(weights)
    sin_m = float(np.sum(np.sin(angles) * w))
    cos_m = float(np.sum(np.cos(angles) * w))
    mean_angle = float(np.arctan2(sin_m, cos_m))
    if mean_angle < 0:
        mean_angle += 2.0 * np.pi
    return mean_angle / (2.0 * np.pi)


def apply_mobile_belaraby_watermark(im):
    """Stamps the transparent «موبايل بالعربى» calligraphy watermark onto the 1200x675 image,
       dynamically adapting the calligraphy font color and shadow/halo to harmonize and contrast with the photo.
    """
    canvas = im.convert("RGBA")
    if not os.path.exists(WM_MASK_PATH):
        return canvas.convert("RGB")

    wm_orig = Image.open(WM_MASK_PATH).convert("RGBA")
    target_h = 138
    target_w = int(wm_orig.width * (target_h / wm_orig.height))
    wm_mask = wm_orig.resize((target_w, target_h), Image.Resampling.LANCZOS)
    alpha = np.array(wm_mask)[:, :, 3].astype(np.float32) * 0.95

    # Position at bottom-left corner
    x = 34
    y = canvas.height - target_h - 22

    patch = np.array(canvas.crop((x, y, x + target_w, y + target_h)).convert("RGB"), dtype=np.float32)
    lum = 0.299 * patch[:, :, 0] + 0.587 * patch[:, :, 1] + 0.114 * patch[:, :, 2]
    avg_lum = float(np.mean(lum))
    dom_h = _get_dominant_hue(im)

    if avg_lum < 142:
        # Dark or medium-dark corner -> luminous pastel/tint of the photo's dominant hue + dark outline/drop-shadow
        if dom_h is not None:
            sat = 0.32 if avg_lum < 95 else 0.24
            r, g, b = colorsys.hsv_to_rgb(dom_h, sat, 1.0)
            fg_color = (int(r * 255), int(g * 255), int(b * 255))
        else:
            fg_color = (248, 250, 255)
        sh_color = (8, 12, 22)
        sh_scale = 0.85
    else:
        # Bright or light corner -> rich deep jewel/ink shade of the photo's dominant hue + crisp white halo
        if dom_h is not None:
            r, g, b = colorsys.hsv_to_rgb(dom_h, 0.85, 0.34)
            fg_color = (int(r * 255), int(g * 255), int(b * 255))
        else:
            fg_color = (16, 56, 44)
        sh_color = (255, 255, 255)
        sh_scale = 0.88

    # Soft outer shadow / halo for guaranteed readability on any background texture
    sh_arr = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    sh_arr[:, :, 0], sh_arr[:, :, 1], sh_arr[:, :, 2] = sh_color
    sh_arr[:, :, 3] = np.clip(alpha * sh_scale, 0, 255).astype(np.uint8)
    sh_im_tight = Image.fromarray(sh_arr).filter(ImageFilter.GaussianBlur(2.5))
    sh_im_wide = Image.fromarray(sh_arr).filter(ImageFilter.GaussianBlur(6))

    # Colored calligraphy strokes (transparent background)
    fg_arr = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    fg_arr[:, :, 0], fg_arr[:, :, 1], fg_arr[:, :, 2] = fg_color
    fg_arr[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    fg_im = Image.fromarray(fg_arr)

    canvas.alpha_composite(sh_im_wide, (x + 2, y + 2))
    canvas.alpha_composite(sh_im_tight, (x + 1, y + 1))
    canvas.alpha_composite(fg_im, (x, y))
    print(f"  🎨 Applied «موبايل بالعربى» watermark (bg_lum={avg_lum:.1f}, font_rgb={fg_color})")
    return canvas.convert("RGB")


def prepare_fb_branded_jpeg(post_url, img_url, content="", title="", save_preview_path=None):
    """End-to-end: resolves a clean watermark-free phone photo, applies the adaptive «موبايل بالعربى»
       calligraphy watermark, and returns JPEG bytes ready for Facebook upload.
    """
    base_im = resolve_clean_base_image(post_url, img_url, content=content, title=title)
    if base_im is None:
        return None
    branded = apply_mobile_belaraby_watermark(base_im)
    if save_preview_path:
        try:
            branded.save(save_preview_path, format="JPEG", quality=93, optimize=True)
        except Exception:
            pass
    buf = io.BytesIO()
    branded.save(buf, format="JPEG", quality=93, optimize=True)
    return buf.getvalue()


def get_fb_credentials():
    """Returns (page_token, page_id), resolving a User token to a Page token automatically if needed."""
    tok = f.secret("FB_PAGE_TOKEN")
    page = f.secret("FB_PAGE_ID") or DEFAULT_PAGE_ID
    if not tok and os.path.exists(LOCAL_FB_FILE):
        try:
            cfg = json.load(open(LOCAL_FB_FILE, encoding="utf-8"))
            tok = (cfg.get("page_token") or cfg.get("token") or "").strip()
            page = (cfg.get("page_id") or page).strip()
        except Exception:
            pass
    if not tok:
        return "", page
    cache_key = f"{page}:{tok[:24]}"
    if cache_key in _RESOLVED_TOKEN_CACHE:
        return _RESOLVED_TOKEN_CACHE[cache_key], page
    try:
        r = requests.get("https://graph.facebook.com/me/accounts",
                         params={"fields": "id,name,access_token", "access_token": tok}, timeout=15)
        if r.ok:
            data = r.json().get("data", [])
            for p in data:
                if p.get("id") == page and p.get("access_token"):
                    _RESOLVED_TOKEN_CACHE[cache_key] = p["access_token"]
                    return p["access_token"], page
            if data and data[0].get("access_token"):
                _RESOLVED_TOKEN_CACHE[cache_key] = data[0]["access_token"]
                return data[0]["access_token"], data[0].get("id") or page
    except Exception:
        pass
    _RESOLVED_TOKEN_CACHE[cache_key] = tok
    return tok, page


def _extract_clean_article_facts(title, content):
    """Extracts clean, blog-boilerplate-free paragraphs, bullets, and specs from article HTML."""
    soup = BeautifulSoup(content or "", "html.parser")
    for tag in soup.find_all(["script", "style", "details"]):
        tag.decompose()
    # Remove any internal-link callout boxes injected by interlink_engine.py
    for box in soup.find_all(["div", "p", "aside"]):
        txt_box = box.get_text(" ", strip=True)
        if re.search(r"(موضوع يهمك|يمكنك أيضاً قراءة|يمكنك ايضا قراءة|اقرأ أيضاً|أدواتنا المجانية|قارن الآن في أداة)", txt_box):
            if len(txt_box) < 350:
                box.decompose()

    bullets = []
    tldr = soup.select_one(".rv-tldr, .ea-tldr")
    if tldr:
        for li in tldr.find_all("li"):
            txt = re.sub(r"\s+", " ", li.get_text(" ", strip=True)).strip()
            if txt and not PROMO_SKIP_RX.search(txt):
                bullets.append(txt)

    paras = []
    for p in soup.find_all("p"):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if len(txt) < 40 or PROMO_SKIP_RX.search(txt):
            continue
        txt = re.sub(r"https?://\S+", "", txt).strip()
        if txt and txt not in paras:
            paras.append(txt)
        if len(paras) >= 4:
            break

    specs = []
    table = soup.find("table")
    if table:
        for tr in table.find_all("tr"):
            cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)).strip() for c in tr.find_all(["th", "td"])]
            if len(cells) >= 2 and cells[0] and cells[1]:
                if any(k in cells[0] for k in ("المواصفة", "البند", "العنصر")):
                    continue
                if len(cells[0]) <= 30 and len(cells[1]) <= 110 and not PROMO_SKIP_RX.search(cells[1]):
                    specs.append(f"{cells[0]}: {cells[1]}")
            if len(specs) >= 6:
                break

    return bullets, paras, specs


def _sanitize_fb_text(text, allow_url=False):
    """Final safety filter: removes any accidental blog phrases or unwanted URLs from Facebook copy."""
    lines = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            lines.append("")
            continue
        if PROMO_SKIP_RX.search(s):
            continue
        if not allow_url:
            s = re.sub(r"https?://\S+", "", s).strip()
            if not s:
                continue
        lines.append(s)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def _build_hashtags(title):
    t = (title or "").lower()
    tags = ["#موبايل_بالعربي"]
    if any(k in t for k in ("سامسونج", "جالاكسي", "samsung", "galaxy", "one ui")):
        tags.extend(["#سامسونج", "#جالاكسي"])
    elif any(k in t for k in ("آيفون", "ايفون", "أبل", "ابل", "iphone", "apple")):
        tags.extend(["#آيفون", "#أبل"])
    elif any(k in t for k in ("شاومي", "ريدمي", "بوكو", "xiaomi", "redmi", "poco")):
        tags.append("#شاومي")
    elif any(k in t for k in ("هونر", "honor")):
        tags.append("#هونر")
    elif any(k in t for k in ("أوبو", "اوبو", "oppo")):
        tags.append("#أوبو")
    elif any(k in t for k in ("فيفو", "vivo")):
        tags.append("#فيفو")
    elif any(k in t for k in ("ريلمي", "ريلمى", "realme")):
        tags.append("#ريلمي")
    else:
        tags.append("#هواتف")
    return " ".join(tags[:4])


def _gemini_fb_copy(title, bullets, paras, specs, mode="native"):
    """Uses Gemini to craft a true Facebook-native, high-engagement post in friendly Egyptian/Arabic social tone."""
    if not f.secret("GEMINI_API_KEY"):
        return None
    facts_parts = [f"العنوان: {title}"]
    if bullets:
        facts_parts.append("أهم النقاط:\n- " + "\n- ".join(bullets[:4]))
    if specs:
        facts_parts.append("المواصفات:\n- " + "\n- ".join(specs[:6]))
    if paras:
        facts_parts.append("تفاصيل إضافية:\n" + "\n".join(paras[:3]))
    facts_text = "\n\n".join(facts_parts)[:2400]

    style_idx = int(hashlib.md5(title.encode("utf-8")).hexdigest(), 16) % len(FB_VIRAL_STYLES)
    style_name, style_desc = FB_VIRAL_STYLES[style_idx]

    if mode == "link":
        prompt = f"""أنت مدير سوشيال ميديا محترف لصفحة فيسبوك تقنية شهيرة اسمها «موبايل بالعربى».
اكتب نص **بوست فيسبوك قصير وخاطف للانتباه** (مش مقال موقع!) بالعامية المصرية الراقية المبسطة عشان تشجع الناس تضغط على الرابط وتعلق.

القواعد الصارمة:
- السطر الأول: جملة «هوك» قوية ومثيرة للفضول توقف السكرول (مع إيموجي واحد مناسب).
- السطر التاني: سطر أو سطرين بحد أقصى بأهم معلومة أو رقم مثير من الحقائق فقط (لا تخترع أرقاماً).
- السطر التالت: دعوة طبيعية للقراءة زي: «التفاصيل والمواصفات كاملة من هنا 👇» (بدون وضع أي رابط لأن الرابط سيضاف تلقائياً تحت النص).
- ممنوع تماماً عبارات المواقع والمدونات مثل: (موضوع يهمك، اقرأ أيضاً، في هذا المقال، خاتمة، المصادر).
- ممنوع تماماً إدخال حروف إنجليزية داخل كلمة عربية (مثل عandك) — اكتب بعربية سليمة تماماً.
- الطول الإجمالي: 25 إلى 50 كلمة فقط.

رجّع JSON بالشكل ده فقط:
{{"post": "نص بوست الفيسبوك هنا"}}

الحقائق:
{facts_text}
"""
    else:
        prompt = f"""أنت مدير سوشيال ميديا محترف لصفحة فيسبوك تقنية شهيرة اسمها «موبايل بالعربى».
اكتب **بوست فيسبوك كامل بدون أي روابط** مصمم خصيصاً لزيادة التفاعل والكومنتات والمشاركات (Engagement & Reach) على فيسبوك.

الأسلوب المطلوب للبوست ده: {style_desc}

القواعد الصارمة:
- اكتب بأسلوب فيسبوك طبيعي وجذاب (عامية مصرية راقية ومفهومة لكل العرب، سطور قصيرة ومريحة للعين على الموبايل).
- السطر الأول لازم يكون Hook قوي يوقف السكرول ويشد القارئ يضغط «عرض المزيد».
- اعرض أهم 3 أو 4 تفاصيل/مواصفات/أسعار حقيقية من الحقائق فقط (ممنوع اختراع أي رقم أو سعر مش موجود) في نقاط سريعة بإيموجي أنيق.
- اختم بسؤال نقاش قوي ومحدد يخلي الناس ترد في الكومنتات.
- ضيف في آخر سطر 3 هاشتاجات مناسبة منها #موبايل_بالعربي.
- ممنوع تماماً وضع أي روابط أو أسماء مواقع، وممنوع نهائياً عبارات المقالات مثل (موضوع يهمك، يمكنك أيضاً قراءة، في هذا المقال، تنويه تحريري).
- الطول: 80 إلى 140 كلمة فقط.

رجّع JSON بالشكل ده فقط:
{{"post": "نص بوست الفيسبوك الكامل هنا"}}

الحقائق:
{facts_text}
"""
    try:
        res = f.gemini(prompt)
        if isinstance(res, dict) and res.get("post"):
            cleaned = _sanitize_fb_text(res["post"], allow_url=False)
            if len(cleaned) >= 35:
                print(f"  ✍️ Generated viral Facebook copy via Gemini (mode={mode}, style={style_name})")
                return cleaned
    except Exception as ex:
        print(f"  [Gemini FB copy fallback] {ex}")
    return None


_COMMENT_PERM_CACHE = {}


def _token_can_comment(tok):
    """Checks whether the Facebook Page token has 'pages_manage_engagement' to post first comments."""
    if not tok:
        return False
    k = tok[:24]
    if k in _COMMENT_PERM_CACHE:
        return _COMMENT_PERM_CACHE[k]
    try:
        r = requests.get("https://graph.facebook.com/debug_token",
                         params={"input_token": tok, "access_token": tok}, timeout=12)
        if r.ok:
            scopes = set(r.json().get("data", {}).get("scopes") or [])
            ok = "pages_manage_engagement" in scopes
            _COMMENT_PERM_CACHE[k] = ok
            return ok
    except Exception:
        pass
    return False


def post_first_comment_link(fb_post_id, clean_url, tok):
    """Posts the article URL as the first comment under the Facebook post."""
    if not fb_post_id or not clean_url or not tok:
        return False
    msg = f"🔗 التفاصيل والمواصفات الكاملة من هنا:\n{clean_url}"
    try:
        r = requests.post(
            f"https://graph.facebook.com/{fb_post_id}/comments",
            data={"message": msg, "access_token": tok},
            timeout=25
        )
        if r.ok:
            print(f"  💬 First comment posted with link! comment_id={r.json().get('id')}")
            return True
        print(f"  ⚠️ First comment failed ({r.status_code}): {r.text[:180]}")
    except Exception as ex:
        print(f"  ⚠️ First comment exception: {ex}")
    return False


def build_link_caption(title, url, content="", link_in_comment=True):
    """Builds an engaging Facebook hook. When link_in_comment=True, puts ZERO links in the post body
       and directs readers to the first comment for maximum Facebook organic reach.
    """
    clean_title = html.unescape(title or "").strip()
    clean_url = (url or "").replace("http://", "https://").strip()
    bullets, paras, specs = _extract_clean_article_facts(clean_title, content)

    ai_hook = _gemini_fb_copy(clean_title, bullets, paras, specs, mode="link")
    if link_in_comment:
        tags = _build_hashtags(clean_title)
        if ai_hook:
            # Replace any generic 'من هنا' CTA with 'في أول تعليق'
            hook = re.sub(r"التفاصيل[^\n]*من هنا[^\n]*", "👇 رابط التفاصيل والمواصفات الكاملة في أول تعليق", ai_hook)
            if "أول تعليق" not in hook and "التعليقات" not in hook:
                hook += "\n\n👇 رابط التفاصيل والمواصفات الكاملة في أول تعليق"
            return _sanitize_fb_text(f"{hook}\n\n{tags}", allow_url=False)
        teaser = bullets[0] if bullets else (paras[0][:140].rsplit(" ", 1)[0] + "…" if paras else "")
        if teaser:
            return _sanitize_fb_text(f"🔥 {clean_title}\n\n{teaser}\n\n👇 رابط التفاصيل والمواصفات الكاملة في أول تعليق\n\n{tags}", allow_url=False)
        return _sanitize_fb_text(f"🔥 {clean_title}\n\n👇 رابط التفاصيل والمواصفات الكاملة في أول تعليق\n\n{tags}", allow_url=False)

    # Fallback when token doesn't have pages_manage_engagement yet
    if ai_hook:
        return f"{ai_hook}\n\n{clean_url}"
    teaser = bullets[0] if bullets else (paras[0][:140].rsplit(" ", 1)[0] + "…" if paras else "")
    if teaser:
        return f"🔥 {clean_title}\n\n{teaser}\n\n👇 التفاصيل كاملة من هنا:\n{clean_url}"
    return f"🔥 {clean_title}\n\n👇 التفاصيل كاملة من هنا:\n{clean_url}"


def build_native_nolink_caption(title, content):
    """Builds a complete, viral, link-free Facebook post (zero blog boilerplate, zero links)."""
    clean_title = html.unescape(title or "").strip()
    bullets, paras, specs = _extract_clean_article_facts(clean_title, content)

    ai_post = _gemini_fb_copy(clean_title, bullets, paras, specs, mode="native")
    if ai_post:
        return ai_post

    # Clean fallback if Gemini is unavailable
    parts = [f"🔥 {clean_title}"]
    if bullets:
        parts.append("\n".join(f"✅ {b}" for b in bullets[:3]))
    elif paras:
        parts.append(paras[0])
    if specs:
        parts.append("⚙️ أبرز الأرقام والمواصفات:\n" + "\n".join(f"▪️ {s}" for s in specs[:5]))
    elif len(paras) > 1:
        parts.append(paras[1])

    q_idx = int(hashlib.md5(clean_title.encode("utf-8")).hexdigest(), 16) % len(ENGAGEMENT_QUESTIONS)
    parts.append(ENGAGEMENT_QUESTIONS[q_idx])
    parts.append(_build_hashtags(clean_title))

    return _sanitize_fb_text("\n\n".join(parts), allow_url=False)


def choose_next_mode(state, requested_mode="auto"):
    """Alternates between 'link' posts and full 'native' (no-link) posts so the page never looks like a link farm."""
    if requested_mode in ("link", "native"):
        return requested_mode
    hist = state.get("fb_history", [])
    if not hist:
        return "link"
    recent_modes = [h.get("mode", "link") for h in hist[-2:]]
    if len(recent_modes) == 2 and all(m == "link" for m in recent_modes):
        return "native"
    return "link"


def check_timing_policy(state, now, force=False):
    if force:
        return True, "forced"
    hist = state.get("fb_history", [])
    today = now.date().isoformat()
    today_posts = [h for h in hist if (h.get("at") or "").startswith(today)]
    if len(today_posts) >= DAILY_CAP:
        return False, f"daily cap reached ({len(today_posts)}/{DAILY_CAP} posts today)"
    if hist:
        last_at_str = hist[-1].get("at")
        if last_at_str:
            try:
                last_at = datetime.datetime.fromisoformat(last_at_str)
                if last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=f.CAIRO)
                seed_int = int(hashlib.md5(last_at_str.encode("utf-8")).hexdigest()[:8], 16)
                req_gap_min = MIN_GAP_MINUTES + (seed_int % (MAX_GAP_MINUTES - MIN_GAP_MINUTES + 1))
                elapsed_min = (now - last_at).total_seconds() / 60.0
                if elapsed_min < req_gap_min:
                    return False, f"last FB post was {int(elapsed_min)}m ago (waiting for {req_gap_min}m natural gap)"
            except Exception:
                pass
    return True, "ok"


def post_phone_to_fb(title, url, image_url=None, content=None, mode="link", dry=False, record_state=True, preview_path=None):
    """Publishes a phone article to the Facebook Page with clean image + «موبايل بالعربى» adaptive watermark."""
    clean_title = html.unescape(title or "").strip()
    clean_url = (url or "").replace("http://", "https://").strip()
    img = image_url or first_image(content)

    state = load_state() if record_state else None
    actual_mode = choose_next_mode(state or {}, mode)

    tok, page = get_fb_credentials()
    can_comment = _token_can_comment(tok) if tok else False
    use_comment_link = can_comment or dry

    if actual_mode == "native" and content:
        caption = build_native_nolink_caption(clean_title, content)
    else:
        actual_mode = "link"
        caption = build_link_caption(clean_title, clean_url, content=content, link_in_comment=use_comment_link)

    jpg_bytes = prepare_fb_branded_jpeg(clean_url, img, content=content, title=clean_title, save_preview_path=preview_path)

    if dry:
        print(f"[DRY FB - mode={actual_mode.upper()}, link_in_comment={use_comment_link}, token_has_comment_perm={can_comment}] Would post to Facebook Page ({page}):")
        print(f"  Source Image: {img}")
        print(f"  Branded JPEG: {'Ready (' + str(len(jpg_bytes)) + ' bytes)' if jpg_bytes else 'Failed'}")
        print("  Caption:\n" + "\n".join("    " + line for line in caption.splitlines()))
        if actual_mode == "link" and use_comment_link:
            print(f"  First Comment: 🔗 التفاصيل والمواصفات الكاملة من هنا: {clean_url}")
        return False

    if not tok or not page:
        print(f"Facebook: (missing FB_PAGE_TOKEN or FB_PAGE_ID) skipped '{clean_title[:60]}'")
        return False

    if state and clean_url in state["fb"]:
        print(f"Facebook: already posted {clean_url}")
        return True

    ok = False
    fb_post_id = ""
    if jpg_bytes:
        try:
            r = requests.post(
                f"https://graph.facebook.com/{page}/photos",
                data={"caption": caption, "access_token": tok},
                files={"source": ("mobile_belaraby.jpg", jpg_bytes, "image/jpeg")},
                timeout=40
            )
            if r.ok:
                fb_post_id = r.json().get("post_id") or r.json().get("id") or ""
                print(f"✅ Facebook Photo Posted [{actual_mode.upper()}]: {clean_title} | fb_id={fb_post_id}")
                ok = True
            else:
                print(f"  FB binary photo upload failed ({r.status_code}): {r.text[:180]}")
        except Exception as ex:
            print(f"  FB binary photo upload exception: {ex}")

    if not ok:
        try:
            feed_data = {"message": caption, "access_token": tok}
            if actual_mode == "link":
                feed_data["link"] = clean_url
            r = requests.post(
                f"https://graph.facebook.com/{page}/feed",
                data=feed_data,
                timeout=30
            )
            if r.ok:
                fb_post_id = r.json().get("id") or ""
                print(f"✅ Facebook Feed Posted [{actual_mode.upper()}]: {clean_title} | fb_id={fb_post_id}")
                ok = True
            else:
                print(f"❌ Facebook post failed ({r.status_code}): {r.text[:200]}")
        except Exception as ex:
            print(f"❌ Facebook feed exception: {ex}")

    if ok and actual_mode == "link" and use_comment_link and fb_post_id:
        post_first_comment_link(fb_post_id, clean_url, tok)

    if ok and state is not None:
        now_iso = datetime.datetime.now(f.CAIRO).isoformat(timespec="seconds")
        if clean_url not in state["fb"]:
            state["fb"].append(clean_url)
        state.setdefault("fb_history", []).append({
            "url": clean_url,
            "title": clean_title,
            "mode": actual_mode,
            "at": now_iso,
            "fb_id": fb_post_id
        })
        save_state(state)

    return ok


def post_by_url(target_url, mode="auto", dry=False, preview_path=None):
    """Fetches a specific post URL and posts it to Facebook with the «موبايل بالعربى» watermark."""
    clean_url = target_url.strip()
    try:
        r = requests.get(clean_url, headers=UA, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        og_title = soup.find("meta", property="og:title")
        h1 = soup.find("h1")
        title = (og_title["content"].strip() if og_title and og_title.get("content")
                 else (h1.get_text(" ", strip=True) if h1 else clean_url))
        og_img = soup.find("meta", property="og:image")
        img = og_img["content"].strip() if og_img and og_img.get("content") else None
        body_box = soup.select_one(".rv-wrap, .ea-wrap, .post-body, article")
        body_html = str(body_box) if body_box else r.text
        if not img:
            art_img = soup.select_one(".post-body img, article img, .rv-wrap img, .ea-wrap img")
            if art_img and art_img.get("src"):
                img = art_img["src"].strip()
        return post_phone_to_fb(title, clean_url, image_url=img, content=body_html, mode=mode, dry=dry, preview_path=preview_path)
    except Exception as ex:
        print(f"Failed to fetch URL {clean_url}: {ex}")
        return False


def _ensure_ar_font():
    if os.path.exists(AR_FONT_PATH) and os.path.getsize(AR_FONT_PATH) > 10000:
        return AR_FONT_PATH
    try:
        os.makedirs(os.path.dirname(AR_FONT_PATH), exist_ok=True)
        r = requests.get(AR_FONT_URL, headers=UA, timeout=25)
        if r.status_code == 200 and len(r.content) > 10000:
            with open(AR_FONT_PATH, "wb") as fp:
                fp.write(r.content)
            return AR_FONT_PATH
    except Exception:
        pass
    for p in (r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return p
    return None


def _load_ar_font(size, bold=False):
    path = _ensure_ar_font()
    if not path:
        return ImageFont.load_default()
    try:
        fnt = ImageFont.truetype(path, size)
        if bold:
            try:
                fnt.set_variation_by_name("Bold")
            except Exception:
                pass
        return fnt
    except Exception:
        return ImageFont.load_default()


def _shape_ar(text):
    if not text:
        return ""
    if HAS_RAQM:
        return text
    if arabic_reshaper and get_display:
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            pass
    return text


def _ar_textlength(draw, text, font):
    if HAS_RAQM:
        try:
            return draw.textlength(text, font=font, direction="rtl", language="ar")
        except Exception:
            return draw.textlength(text, font=font)
    return draw.textlength(_shape_ar(text), font=font)


def _draw_ar_text(draw, xy, text, font, fill):
    if HAS_RAQM:
        try:
            draw.text(xy, text, font=font, fill=fill, direction="rtl", language="ar")
            return
        except Exception:
            pass
    draw.text(xy, _shape_ar(text), font=font, fill=fill)


def _wrap_ar_lines(draw, text, font, max_w, max_lines=3):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if _ar_textlength(draw, cand, font) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def _extract_story_bullets(content):
    """Extracts 2-3 short, punchy highlights from the phone article for the Story card."""
    soup = BeautifulSoup(content or "", "html.parser")
    for tag in soup.find_all(["script", "style", "details"]):
        tag.decompose()
    bullets = []
    tldr = soup.select_one(".rv-tldr, .ea-tldr")
    if tldr:
        for li in tldr.find_all("li"):
            txt = re.sub(r"\s+", " ", li.get_text(" ", strip=True)).strip()
            if txt and not PROMO_SKIP_RX.search(txt):
                bullets.append(txt[:95] + ("…" if len(txt) > 95 else ""))
            if len(bullets) >= 3:
                break
    if len(bullets) < 2:
        table = soup.find("table")
        if table:
            for tr in table.find_all("tr"):
                cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)).strip() for c in tr.find_all(["th", "td"])]
                if len(cells) >= 2 and cells[0] and cells[1]:
                    if any(k in cells[0] for k in ("المواصفة", "البند", "العنصر")):
                        continue
                    item = f"{cells[0]}: {cells[1]}"
                    if len(item) <= 85 and not PROMO_SKIP_RX.search(item):
                        bullets.append(item)
                if len(bullets) >= 3:
                    break
    return bullets[:3]


def build_story_image_bytes(base_im, title, content="", save_preview_path=None):
    """Creates a polished 1080x1920 vertical 9:16 Facebook Page Story image with:
       - Blurred phone-palette background
       - Transparent «موبايل بالعربى» calligraphy logo at top (adaptive color)
       - Clean un-watermarked phone hero card
       - Dark glassmorphism card with Arabic title + 2-3 highlights + page CTA
    """
    W, H = 1080, 1920
    dom_h = _get_dominant_hue(base_im)
    if dom_h is not None:
        ar, ag, ab = colorsys.hsv_to_rgb(dom_h, 0.52, 0.98)
        accent_rgb = (int(ar * 255), int(ag * 255), int(ab * 255))
        lr, lg, lb = colorsys.hsv_to_rgb(dom_h, 0.25, 1.0)
        logo_rgb = (int(lr * 255), int(lg * 255), int(lb * 255))
    else:
        accent_rgb = (56, 189, 248)
        logo_rgb = (248, 250, 255)

    # 1. Atmospheric blurred dark backdrop from the phone image itself
    bg = ImageOps.fit(base_im.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(46))
    bg = ImageEnhance.Brightness(bg).enhance(0.36)
    bg = ImageEnhance.Color(bg).enhance(1.15)
    canvas = bg.convert("RGBA")

    # Subtle vertical dark gradient scrim for crisp contrast
    grad = np.zeros((H, W, 4), dtype=np.uint8)
    for yy in range(H):
        # Slightly darker at top and bottom
        t = abs((yy / float(H)) - 0.35)
        a_val = int(min(185, 70 + t * 145))
        grad[yy, :, 0] = 8
        grad[yy, :, 1] = 12
        grad[yy, :, 2] = 22
        grad[yy, :, 3] = a_val
    canvas = Image.alpha_composite(canvas, Image.fromarray(grad))

    # 2. Transparent «موبايل بالعربى» calligraphy logo centered at top
    if os.path.exists(WM_MASK_PATH):
        wm_orig = Image.open(WM_MASK_PATH).convert("RGBA")
        wm_h = 152
        wm_w = int(wm_orig.width * (wm_h / wm_orig.height))
        wm_mask = wm_orig.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
        alpha = np.array(wm_mask)[:, :, 3].astype(np.float32) * 0.96

        sh_arr = np.zeros((wm_h, wm_w, 4), dtype=np.uint8)
        sh_arr[:, :, 0], sh_arr[:, :, 1], sh_arr[:, :, 2] = (6, 10, 18)
        sh_arr[:, :, 3] = np.clip(alpha * 0.85, 0, 255).astype(np.uint8)
        sh_im = Image.fromarray(sh_arr).filter(ImageFilter.GaussianBlur(5))

        fg_arr = np.zeros((wm_h, wm_w, 4), dtype=np.uint8)
        fg_arr[:, :, 0], fg_arr[:, :, 1], fg_arr[:, :, 2] = logo_rgb
        fg_arr[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
        fg_im = Image.fromarray(fg_arr)

        lx = (W - wm_w) // 2
        ly = 115
        canvas.alpha_composite(sh_im, (lx + 2, ly + 3))
        canvas.alpha_composite(fg_im, (lx, ly))

    # 3. Clean un-watermarked Hero Phone Photo Card (980x551) with rounded corners & shadow
    card_w, card_h = 980, 551
    hero = ImageOps.fit(base_im.convert("RGB"), (card_w, card_h), method=Image.Resampling.LANCZOS).convert("RGBA")
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), radius=36, fill=255)
    hero.putalpha(mask)

    hx, hy = (W - card_w) // 2, 325
    sh_card = Image.new("RGBA", (card_w + 60, card_h + 60), (0, 0, 0, 0))
    ImageDraw.Draw(sh_card).rounded_rectangle((30, 30, card_w + 30, card_h + 30), radius=36, fill=(0, 0, 0, 150))
    sh_card = sh_card.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(sh_card, (hx - 30, hy - 20))
    canvas.alpha_composite(hero, (hx, hy))

    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((hx, hy, hx + card_w, hy + card_h), radius=36, outline=(*accent_rgb, 115), width=3)

    # 4. Glassmorphism Info Card (Title + Highlights + CTA)
    bx1, by1, bx2, by2 = 50, 935, W - 50, 1735
    d.rounded_rectangle((bx1, by1, bx2, by2), radius=40, fill=(10, 16, 28, 195), outline=(*accent_rgb, 95), width=2)

    # Top-right accent bar inside card
    d.rounded_rectangle((bx2 - 140, by1 + 42, bx2 - 48, by1 + 52), radius=5, fill=(*accent_rgb, 240))

    # Headline (Right-aligned Arabic)
    clean_title = html.unescape(title or "").strip()
    f_title = _load_ar_font(44, bold=True)
    title_lines = _wrap_ar_lines(d, clean_title, f_title, max_w=(bx2 - bx1 - 96), max_lines=3)
    ty = by1 + 78
    for ln in title_lines:
        tw = _ar_textlength(d, ln, f_title)
        _draw_ar_text(d, (bx2 - 48 - tw, ty), ln, f_title, (255, 255, 255, 255))
        ty += 68

    # Divider
    ty += 16
    d.line([(bx1 + 48, ty), (bx2 - 48, ty)], fill=(255, 255, 255, 38), width=2)
    ty += 34

    # Highlights bullets
    bullets = _extract_story_bullets(content)
    f_bul = _load_ar_font(31, bold=False)
    for b_txt in bullets:
        b_lines = _wrap_ar_lines(d, b_txt, f_bul, max_w=(bx2 - bx1 - 135), max_lines=2)
        if not b_lines:
            continue
        # Accent bullet dot on the right
        d.ellipse((bx2 - 68, ty + 16, bx2 - 52, ty + 32), fill=(*accent_rgb, 245))
        for bl in b_lines:
            tw = _ar_textlength(d, bl, f_bul)
            _draw_ar_text(d, (bx2 - 84 - tw, ty), bl, f_bul, (226, 232, 240, 240))
            ty += 48
        ty += 18
        if ty > by2 - 140:
            break

    # Bottom CTA pill inside the card
    cta_raw = "التفاصيل الكاملة في أحدث بوست على الصفحة"
    f_cta = _load_ar_font(28, bold=True)
    cta_w = _ar_textlength(d, cta_raw, f_cta)
    pill_w = min(bx2 - bx1 - 80, int(cta_w) + 84)
    px1 = (W - pill_w) // 2
    py1 = by2 - 102
    py2 = by2 - 36
    d.rounded_rectangle((px1, py1, px1 + pill_w, py2), radius=33, fill=(*accent_rgb, 235))
    # Pick dark or light text on the pill depending on accent brightness
    acc_lum = 0.299 * accent_rgb[0] + 0.587 * accent_rgb[1] + 0.114 * accent_rgb[2]
    cta_ink = (10, 16, 28, 255) if acc_lum > 145 else (255, 255, 255, 255)
    _draw_ar_text(d, ((W - cta_w) // 2, py1 + 14), cta_raw, f_cta, cta_ink)

    out_rgb = canvas.convert("RGB")
    if save_preview_path:
        try:
            out_rgb.save(save_preview_path, format="JPEG", quality=92, optimize=True)
        except Exception:
            pass
    buf = io.BytesIO()
    out_rgb.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


def post_daily_story(title, url, image_url=None, content="", dry=False, force=False, preview_path=None):
    """Publishes 1 daily Facebook Page Photo Story via /{page_id}/photos (published=false) + /{page_id}/photo_stories."""
    state = load_state()
    now = datetime.datetime.now(f.CAIRO)
    today = now.date().isoformat()

    if not force:
        if any(s.get("date") == today for s in state.get("fb_stories", [])):
            print(f"Facebook Story: already posted today ({today}).")
            return False
        if now.hour < 11 and not dry:
            print("Facebook Story: waiting until after 11:00 AM Cairo time.")
            return False

    clean_title = html.unescape(title or "").strip()
    clean_url = (url or "").replace("http://", "https://").strip()
    base_im = resolve_clean_base_image(clean_url, image_url, content=content, title=clean_title)
    if base_im is None:
        print("Facebook Story: could not resolve clean base image.")
        return False

    story_bytes = build_story_image_bytes(base_im, clean_title, content=content, save_preview_path=preview_path)
    tok, page = get_fb_credentials()

    if dry:
        print(f"[DRY FB STORY] Would publish daily 9:16 Story to Page ({page}):")
        print(f"  Title: {clean_title}")
        print(f"  Bytes: {len(story_bytes)} bytes")
        if preview_path:
            print(f"  Saved preview: {preview_path}")
        return False

    if not tok or not page:
        print("Facebook Story: missing FB_PAGE_TOKEN / FB_PAGE_ID.")
        return False

    try:
        # Step 1: Upload unpublished photo
        r1 = requests.post(
            f"https://graph.facebook.com/{page}/photos",
            data={"published": "false", "access_token": tok},
            files={"source": ("story.jpg", story_bytes, "image/jpeg")},
            timeout=40
        )
        if not r1.ok or not r1.json().get("id"):
            print(f"❌ Facebook Story photo upload failed ({r1.status_code}): {r1.text[:200]}")
            return False
        photo_id = r1.json()["id"]

        # Step 2: Publish as Page Photo Story
        r2 = requests.post(
            f"https://graph.facebook.com/{page}/photo_stories",
            data={"photo_id": photo_id, "access_token": tok},
            timeout=30
        )
        if r2.ok and r2.json().get("success", True):
            story_id = r2.json().get("post_id") or photo_id
            print(f"✅ Facebook Daily Story Published! Title: {clean_title} | story_id={story_id}")
            state.setdefault("fb_stories", []).append({
                "date": today,
                "url": clean_url,
                "title": clean_title,
                "at": now.isoformat(timespec="seconds"),
                "story_id": story_id
            })
            save_state(state)
            return True
        else:
            print(f"❌ Facebook photo_stories publish failed ({r2.status_code}): {r2.text[:200]}")
            return False
    except Exception as ex:
        print(f"❌ Facebook Story exception: {ex}")
        return False


def run_daily_story(dry=False, force=False, lookback_hours=120, preview_path=None):
    """Checks if today's Facebook Page Story has been published; prioritizes Samsung phones, apps & updates first."""
    state = load_state()
    now = datetime.datetime.now(f.CAIRO)
    today = now.date().isoformat()
    if not force:
        if any(s.get("date") == today for s in state.get("fb_stories", [])):
            print(f"Facebook Daily Story: already published today ({today}).")
            return False
        if now.hour < 11 and not dry:
            print("Facebook Daily Story: waiting until 11:00 AM Cairo time.")
            return False

    done_story_urls = {s.get("url") for s in state.get("fb_stories", []) if s.get("url")}
    since = (now - datetime.timedelta(hours=lookback_hours)).isoformat(timespec="seconds")
    tok = f.token()

    candidates = []
    for blog_id, site_name in [(REVIEW_BLOG, "Review"), (EA_BLOG, "Egyptaway")]:
        try:
            res = f.api("GET", f"/blogs/{blog_id}/posts", tok, {
                "status": "live", "startDate": since, "maxResults": 40,
                "fetchBodies": "true", "fetchImages": "true"
            })
            items = res.get("items", []) if isinstance(res, dict) else []
            for p in items:
                u = (p.get("url") or "").replace("http://", "https://")
                if not u or u in done_story_urls:
                    continue
                if is_phone_post(p, blog_id=blog_id):
                    candidates.append((1 if is_samsung_post(p) else 0, p.get("published", ""), p))
        except Exception as ex:
            print(f"Facebook Story scan warning ({site_name}): {ex}")

    if not candidates:
        print("Facebook Daily Story: no recent phone article candidates found.")
        return False

    # Samsung phone/app/update articles first, then newest
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    is_sam, _, p = candidates[0]
    print(f"Facebook Daily Story selected (Samsung={bool(is_sam)}): {p['title']}")
    u = p["url"].replace("http://", "https://")
    img = first_image(p.get("content"), post=p)
    return post_daily_story(p["title"], u, image_url=img, content=p.get("content"), dry=dry, force=force, preview_path=preview_path)


def run_auto(dry=False, force=False, mode="auto", lookback_hours=120, max_per_run=1, preview_path=None):
    # Always check & publish the 1-per-day Facebook Page Story automatically (Samsung priority)
    try:
        run_daily_story(dry=dry, force=False, lookback_hours=120)
    except Exception as ex:
        print(f"Facebook Daily Story warning: {ex}")

    state = load_state()
    now = datetime.datetime.now(f.CAIRO)

    allowed, reason = check_timing_policy(state, now, force=force)
    if not allowed and not dry:
        print(f"Facebook Policy Guard: skipping run ({reason}).")
        return 0

    live_posts = fetch_recent_live_fb_posts(limit=30)
    # Extra live safety check against Facebook's own latest post timestamp
    if not force and not dry and live_posts:
        ct = live_posts[0].get("created_time")
        if ct:
            try:
                live_dt = datetime.datetime.strptime(ct, "%Y-%m-%dT%H:%M:%S%z").astimezone(f.CAIRO)
                live_elapsed = (now - live_dt).total_seconds() / 60.0
                if live_elapsed < MIN_GAP_MINUTES:
                    print(f"Facebook Live Policy Guard: latest live FB post was {int(live_elapsed)}m ago (<{MIN_GAP_MINUTES}m). Skipping.")
                    return 0
            except Exception:
                pass

    since = (now - datetime.timedelta(hours=lookback_hours)).isoformat(timespec="seconds")
    tok = f.token()

    candidates = []
    for blog_id, site_name in [(REVIEW_BLOG, "Review"), (EA_BLOG, "Egyptaway")]:
        try:
            res = f.api("GET", f"/blogs/{blog_id}/posts", tok, {
                "status": "live",
                "startDate": since,
                "maxResults": 40,
                "fetchBodies": "true",
                "fetchImages": "true"
            })
            items = res.get("items", []) if isinstance(res, dict) else []
            for p in items:
                u = (p.get("url") or "").replace("http://", "https://")
                if not u:
                    continue
                if not is_phone_post(p, blog_id=blog_id):
                    continue
                is_dup, dup_reason = is_duplicate_on_fb(p.get("title", ""), u, state, live_posts)
                if is_dup:
                    continue
                candidates.append((1 if is_samsung_post(p) else 0, p.get("published", ""), site_name, p))
        except Exception as ex:
            print(f"Facebook scan warning ({site_name}): {ex}")

    # Samsung phone articles ALWAYS get top priority, then newest
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    sam_count = sum(1 for c in candidates if c[0] == 1)
    print(f"Facebook Phone Auto-Poster: {len(candidates)} unposted phone post(s) available ({sam_count} Samsung).")

    posted_count = 0
    for is_sam, _, site_name, p in candidates[:max_per_run]:
        u = p["url"].replace("http://", "https://")
        img = first_image(p.get("content"), post=p)
        actual_mode = choose_next_mode(state, mode)
        ok = post_phone_to_fb(
            p["title"], u,
            image_url=img,
            content=p.get("content"),
            mode=actual_mode,
            dry=dry,
            record_state=True,
            preview_path=preview_path
        )
        if ok:
            posted_count += 1
            state = load_state()

    return posted_count


def main():
    ap = argparse.ArgumentParser(description="Auto-publish phone articles & daily Stories to Facebook Page with adaptive «موبايل بالعربى» watermark")
    ap.add_argument("--url", default="", help="Specific article URL to publish immediately")
    ap.add_argument("--story", action="store_true", help="Publish a 9:16 daily Story on the Facebook Page")
    ap.add_argument("--mode", choices=["auto", "link", "native"], default="auto",
                    help="Post mode: 'link' (Title+Photo+Link), 'native' (Full No-Link Post+Photo), or 'auto'")
    ap.add_argument("--hours", type=int, default=24, help="Lookback window in hours for auto mode")
    ap.add_argument("--max", type=int, default=1, help="Max posts to share in a single run")
    ap.add_argument("--force", action="store_true", help="Bypass the time gap / daily Story limit check")
    ap.add_argument("--dry", action="store_true", help="Dry run without posting")
    ap.add_argument("--preview", default="", help="Optional local path to save the JPEG preview")
    args = ap.parse_args()

    dry = args.dry or os.environ.get("DRY_RUN") == "1"
    force = args.force or os.environ.get("FORCE") == "1"
    if args.story:
        if args.url:
            r = requests.get(args.url.strip(), headers=UA, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            og_t = soup.find("meta", property="og:title")
            title = og_t["content"].strip() if og_t and og_t.get("content") else args.url.strip()
            og_i = soup.find("meta", property="og:image")
            img = og_i["content"].strip() if og_i and og_i.get("content") else None
            box = soup.select_one(".rv-wrap, .ea-wrap, .post-body, article")
            post_daily_story(title, args.url.strip(), image_url=img, content=str(box) if box else r.text,
                             dry=dry, force=force, preview_path=args.preview or None)
        else:
            run_daily_story(dry=dry, force=force, lookback_hours=max(36, args.hours), preview_path=args.preview or None)
    elif args.url:
        post_by_url(args.url, mode=args.mode, dry=dry, preview_path=args.preview or None)
    else:
        run_auto(dry=dry, force=force, mode=args.mode, lookback_hours=args.hours, max_per_run=args.max, preview_path=args.preview or None)


if __name__ == "__main__":
    main()
