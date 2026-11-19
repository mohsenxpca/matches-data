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
import argparse, colorsys, datetime, hashlib, html, io, json, os, random, re, sys, urllib.parse
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import football as f

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REVIEW_BLOG = "2997328666613207792"
EA_BLOG = "8325646053257070334"
DEFAULT_PAGE_ID = "1959788610952661"  # صفحة موبايل بالعربى
STATE_FILE = os.path.join(BASE_DIR, "notify_sent.json")
REVIEW_STATE_FILE = os.path.join(BASE_DIR, "review_posted.json")
LOCAL_FB_FILE = os.path.join(BASE_DIR, ".fb_token.json")
WM_MASK_PATH = os.path.join(BASE_DIR, "img", "mobile_belaraby_wm.png")
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
    "رصد الأعطال", "ذهب وعملات", "مواقيت الصلاة", "الطقس"
}

PHONE_TITLE_RX = re.compile(
    r"(هاتف|هواتف|موبايل|موبايلات|جالاكسي|آيفون|ايفون|سامسونج|شاومي|ريدمي|بوكو|ريلمي|ريلمى|"
    r"أوبو|اوبو|فيفو|هونر|انفنكس|انفينكس|تكنو|تيكنو|ون بلس|وان بلس|موتورولا|بيكسل|هواوي|ريد ماجيك|ناثينج|"
    r"\bgalaxy\b|\biphone\b|\bsamsung\b|\bxiaomi\b|\bredmi\b|\bpoco\b|\brealme\b|\boppo\b|\bvivo\b|"
    r"\biqoo\b|\bhonor\b|\binfinix\b|\btecno\b|\boneplus\b|\bmotorola\b|\bpixel\b|\bhuawei\b|"
    r"\bredmagic\b|\bnothing\s*phone\b|\bone\s*ui\b|\bios\s*\d+)",
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
    r"(أدواتنا المجانية|أداة مقارنة الهواتف|جدول أسعار الموبايلات المحدث|أفضل هاتف لميزانيتك|"
    r"قارن الآن في أداة|المصادر الرسمية|المصدر التقني المعلن|هذه المراجعة مبنية على المواصفات|"
    r"تنويه تحريري|مراجعات أخرى قد تهمك|تغطيات ومراجعات أخرى|https?://|\bwww\.)",
    re.I
)


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fp:
            state = json.load(fp)
    except Exception:
        state = {}
    for k in ("sent", "indexed", "tg", "fb", "fb_history"):
        state.setdefault(k, [])
    return state


def save_state(state):
    for k in ("sent", "indexed", "tg", "fb", "fb_history"):
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


def is_phone_post(post, blog_id=None):
    url = post.get("url", "")
    if blog_id == REVIEW_BLOG or "review-mobile.com" in url:
        return True
    labels = set(post.get("labels") or [])
    if labels & PHONE_LABELS:
        return True
    if labels & NON_PHONE_EA_LABELS:
        return False
    title = html.unescape(post.get("title", ""))
    return bool(PHONE_TITLE_RX.search(title))


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


def build_native_nolink_caption(title, content):
    """Builds a complete, rich, link-free Facebook post from the article HTML to act as a natural separator."""
    clean_title = html.unescape(title or "").strip()
    soup = BeautifulSoup(content or "", "html.parser")
    for tag in soup.find_all(["script", "style", "details"]):
        tag.decompose()

    bullets = []
    tldr = soup.select_one(".rv-tldr, .ea-tldr")
    if tldr:
        for li in tldr.find_all("li"):
            txt = re.sub(r"\s+", " ", li.get_text(" ", strip=True)).strip()
            if txt and not PROMO_SKIP_RX.search(txt):
                bullets.append(f"• {txt}")

    paras = []
    for p in soup.find_all("p"):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if len(txt) < 45 or PROMO_SKIP_RX.search(txt):
            continue
        txt = re.sub(r"https?://\S+", "", txt).strip()
        if txt not in paras:
            paras.append(txt)
        if len(paras) >= 3:
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
                    specs.append(f"▪️ {cells[0]}: {cells[1]}")
            if len(specs) >= 5:
                break

    parts = [f"📱 {clean_title}"]
    if paras:
        parts.append(paras[0])
    if bullets:
        parts.append("📌 أهم النقاط السريعة:\n" + "\n".join(bullets[:3]))
    if specs:
        parts.append("⚙️ أبرز المواصفات:\n" + "\n".join(specs[:5]))
    elif len(paras) > 1:
        parts.append(paras[1])
    if len(paras) > 2 and not specs:
        parts.append(paras[2])

    q_idx = int(hashlib.md5(clean_title.encode("utf-8")).hexdigest(), 16) % len(ENGAGEMENT_QUESTIONS)
    parts.append(ENGAGEMENT_QUESTIONS[q_idx])

    full_text = "\n\n".join(parts)
    full_text = re.sub(r"https?://\S+", "", full_text).strip()
    return full_text


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

    if actual_mode == "native" and content:
        caption = build_native_nolink_caption(clean_title, content)
    else:
        actual_mode = "link"
        caption = f"{clean_title}\n\n{clean_url}"

    tok, page = get_fb_credentials()
    jpg_bytes = prepare_fb_branded_jpeg(clean_url, img, content=content, title=clean_title, save_preview_path=preview_path)

    if dry:
        print(f"[DRY FB - mode={actual_mode.upper()}] Would post to Facebook Page ({page}):")
        print(f"  Source Image: {img}")
        print(f"  Branded JPEG: {'Ready (' + str(len(jpg_bytes)) + ' bytes)' if jpg_bytes else 'Failed'}")
        print("  Caption:\n" + "\n".join("    " + line for line in caption.splitlines()))
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


def run_auto(dry=False, force=False, mode="auto", lookback_hours=24, max_per_run=1, preview_path=None):
    state = load_state()
    now = datetime.datetime.now(f.CAIRO)

    allowed, reason = check_timing_policy(state, now, force=force)
    if not allowed and not dry:
        print(f"Facebook Policy Guard: skipping run ({reason}).")
        return 0

    done_fb = set(state.get("fb", []))
    since = (now - datetime.timedelta(hours=lookback_hours)).isoformat(timespec="seconds")
    tok = f.token()

    candidates = []
    for blog_id, site_name in [(REVIEW_BLOG, "Review"), (EA_BLOG, "Egyptaway")]:
        try:
            res = f.api("GET", f"/blogs/{blog_id}/posts", tok, {
                "status": "live",
                "startDate": since,
                "maxResults": 20,
                "fetchBodies": "true",
                "fetchImages": "true"
            })
            items = res.get("items", []) if isinstance(res, dict) else []
            for p in items:
                u = (p.get("url") or "").replace("http://", "https://")
                if not u or u in done_fb:
                    continue
                if is_phone_post(p, blog_id=blog_id):
                    candidates.append((p.get("published", ""), site_name, p))
        except Exception as ex:
            print(f"Facebook scan warning ({site_name}): {ex}")

    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"Facebook Phone Auto-Poster: {len(candidates)} unposted phone post(s) available.")

    posted_count = 0
    for _, site_name, p in candidates[:max_per_run]:
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
    ap = argparse.ArgumentParser(description="Auto-publish phone articles to Facebook Page with adaptive «موبايل بالعربى» watermark")
    ap.add_argument("--url", default="", help="Specific article URL to publish immediately")
    ap.add_argument("--mode", choices=["auto", "link", "native"], default="auto",
                    help="Post mode: 'link' (Title+Photo+Link), 'native' (Full No-Link Post+Photo), or 'auto'")
    ap.add_argument("--hours", type=int, default=24, help="Lookback window in hours for auto mode")
    ap.add_argument("--max", type=int, default=1, help="Max posts to share in a single run")
    ap.add_argument("--force", action="store_true", help="Bypass the 75-130 min time gap check")
    ap.add_argument("--dry", action="store_true", help="Dry run without posting")
    ap.add_argument("--preview", default="", help="Optional local path to save the branded JPEG preview")
    args = ap.parse_args()

    dry = args.dry or os.environ.get("DRY_RUN") == "1"
    force = args.force or os.environ.get("FORCE") == "1"
    if args.url:
        post_by_url(args.url, mode=args.mode, dry=dry, preview_path=args.preview or None)
    else:
        run_auto(dry=dry, force=force, mode=args.mode, lookback_hours=args.hours, max_per_run=args.max, preview_path=args.preview or None)


if __name__ == "__main__":
    main()
