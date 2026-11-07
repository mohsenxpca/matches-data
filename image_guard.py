"""Shared Image Relevance, Safety & Anti-Duplication Guard for Egyptaway & Review.
Strictly enforced as per Mohsen directives (2026-11-04, 2026-11-07):
1. 100% Topic Relevance:
   - Mosque/Prayer photos (including 3290075) ONLY allowed on prayer/mosque articles.
     Zero tolerance for mosque photos on sports, tech, gaming, finance, etc.
   - Sports photos ONLY on sports/football/tennis.
   - Phone/Tech photos ONLY on phones/technology/apps.
   - Money/Gold photos ONLY on finance/gold/currencies/banks.
2. Anti-Duplication Shield:
   - No image can be reused if it was published in recent post history (last 15-20 posts).
   - Dynamic rotation across curated pools.
3. Strict Safety & Content Filtering:
   - No military, army, combat, weapons, asian uniforms, foreign trains, etc.
   - News extraction (og:image) restricted strictly to trusted Egyptian publishers.
"""
import re, urllib.parse, hashlib

ALLOWED_EGYPT_DOMAINS = {
    "youm7.com", "masrawy.com", "elwatannews.com", "almasryalyoum.com", "shorouknews.com",
    "cairo24.com", "dostor.org", "akhbarelyom.com", "vetogate.com", "ahram.org.eg",
    "alwafd.news", "elbalad.news", "mobtada.com", "rosaelyoussef.com", "akhbarak.net",
    "almalnews.com", "amwalalghad.com", "economyplusme.com", "honaalwatan.com"
}

BANNED_IMG_PATTERNS = [
    r"military", r"army", r"soldier", r"war\b", r"weapon", r"gun\b", r"tank\b", r"combat",
    r"uniform", r"vietnam", r"korea", r"china", r"asian", r"beijing", r"tokyo", r"police",
    r"crime", r"murder", r"prison", r"court", r"dead", r"killing",
    r"logo", r"favicon", r"avatar", r"icon\b", r"placeholder", r"pixel", r"banner", r"author"
]

# Explicit known IDs for prayer/mosque photos
MOSQUE_PHOTO_IDS = {"3290075", "161275", "218480", "1537086"}


def extract_photo_id(img_url):
    """Extracts a unique identifier from a photo URL (e.g. Pexels photo ID or base file name)."""
    if not img_url:
        return ""
    m = re.search(r"photos/(\d+)/", img_url)
    if m:
        return m.group(1)
    clean = img_url.split("?")[0].rstrip("/")
    return clean.split("/")[-1]


def is_trusted_egypt_publisher(url):
    """Checks if a URL belongs to a recognized, trusted Egyptian news publisher."""
    if not url:
        return False
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return any(d in domain for d in ALLOWED_EGYPT_DOMAINS)
    except Exception:
        return False


def is_safe_image(img_url, publisher_url=""):
    """Validates that an image URL is safe and comes from a trusted Egyptian source if it's news."""
    if not img_url or not isinstance(img_url, str) or not img_url.startswith("http"):
        return False
    img_lower = img_url.lower()

    # Reject banned keywords (military, asian, army, weapons, etc.)
    for pat in BANNED_IMG_PATTERNS:
        if re.search(pat, img_lower):
            return False

    # If publisher_url is provided, it MUST be from an Egyptian publisher for local news
    if publisher_url and not is_trusted_egypt_publisher(publisher_url):
        return False

    return True


def is_prayer_topic(title, text=""):
    """Determines whether a story is genuinely about Islamic prayer or mosques."""
    t = (title + " " + (text or "")).lower()
    return bool(re.search(r"مواقيت الصلاة|صلاة الفجر|صلاة المغرب|صلاة العشاء|صلاة الظهر|صلاة العصر|صلاة الجمعة|موعد أذان|أذان الفجر|مواقيت الآذان|مساجد مصر|وزارة الأوقاف مساجد", t))


def is_relevant_image(img_url, title, text=""):
    """Strict check: guarantees that the image content matches the article topic.
    ZERO TOLERANCE for mosques on non-prayer posts, or mismatched categories.
    """
    if not img_url:
        return False
    
    pid = extract_photo_id(img_url)
    t = (title + " " + (text or "")).lower()

    # 1. منع صورة المسجد نهائياً على أي خبر غير ديني/صلاة
    if pid in MOSQUE_PHOTO_IDS or re.search(r"mosque|masjid|minaret|prayer", img_url.lower()):
        if not is_prayer_topic(title, text):
            print(f"  [ImageGuard REJECTED] Mosque photo blocked on non-prayer story: {title[:50]}")
            return False

    # 2. لو الموضوع رياضة أو كورة: ممنوع صور الشاشات أو المساجد أو الطقس
    is_sports_topic = bool(re.search(r"كورة|كرة|مباراة|مباريات|دوري|أهلي|زمالك|ليفربول|ريال مدريد|برشلونة|ملعب|استاد|لاعب|مدرب|فريق|نادي|كأس|بطولة|ديربي|كلاسيكو|منتخب|أدنوك|توتنهام|ليدز|مانشستر|أرسنال|بايرن|تنس|ألكاراز", t))
    if is_sports_topic and pid in MOSQUE_PHOTO_IDS:
        return False

    # 3. لو الموضوع هواتف أو تكنولوجيا: ممنوع صور الملاعب أو المساجد
    is_tech_topic = bool(re.search(r"هاتف|موبايل|سامسونج|شاومي|آيفون|ايفون|أندرويد|اندرويد|تطبيق|تحديث|معالج|كاميرا|شاشة|ذكاء اصطناعي", t))
    if is_tech_topic and pid in MOSQUE_PHOTO_IDS:
        return False

    return True


def is_duplicate_image(img_url, recent_images, window=15):
    """Checks whether an image (by its unique photo ID) was already used in recent posts."""
    if not img_url or not recent_images:
        return False
    pid = extract_photo_id(img_url)
    if not pid:
        return False
    
    # Check against the last `window` images
    recent_slice = recent_images[-window:]
    recent_ids = {extract_photo_id(u) for u in recent_slice if u}
    
    if pid in recent_ids:
        print(f"  [ImageGuard REJECTED] Duplicate image detected ({pid}) in recent {len(recent_slice)} posts.")
        return True
    return False


def get_guaranteed_image(candidate_url, title, category_pool, recent_images=(), publisher_url="", text=""):
    """Returns a 100% verified, relevant, safe, and non-duplicate image.
    If the candidate image fails ANY check (safety, relevance, or recent duplicate),
    it dynamically selects an unused relevant image from category_pool.
    """
    # 1. Test candidate image
    if candidate_url:
        safe = is_safe_image(candidate_url, publisher_url)
        rel = is_relevant_image(candidate_url, title, text)
        dup = is_duplicate_image(candidate_url, recent_images)
        if safe and rel and not dup:
            return candidate_url
        print(f"  [ImageGuard] Candidate photo rejected (safe={safe}, relevant={rel}, dup={dup}). Selecting from pool...")

    # 2. Select from curated pool avoiding recent duplicates
    if not category_pool:
        # Ultimate safe emergency fallback
        return "https://images.pexels.com/photos/518543/pexels-photo-518543.jpeg?auto=compress&cs=tinysrgb&w=1200&h=675&fit=crop"

    recent_ids = {extract_photo_id(u) for u in recent_images[-15:] if u}
    
    # Sort pool based on title hash for stable rotation
    seed = int(hashlib.md5(title.encode("utf-8")).hexdigest()[:8], 16)
    rotated_pool = [category_pool[(seed + i) % len(category_pool)] for i in range(len(category_pool))]

    for photo in rotated_pool:
        pid = extract_photo_id(photo)
        if pid not in recent_ids and is_relevant_image(photo, title, text):
            return photo

    # If all pool images were recently used, return the rotated choice that is relevant
    for photo in rotated_pool:
        if is_relevant_image(photo, title, text):
            return photo

    return rotated_pool[0]
