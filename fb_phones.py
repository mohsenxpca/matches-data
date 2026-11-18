"""Auto-publish phone articles (from Review + Egyptaway) to the Facebook Page with Facebook Policy & Anti-Spam Guard.

Features requested by Mohsen (2026-11-18):
1. Link Posts (~2/3 of posts):
   - Article Title
   - Article Image (uploaded as a Facebook Page photo post)
   - Article Link right underneath
2. Complete Native No-Link Posts (~1/3 of posts, automatic separator after every 1-2 link posts):
   - Article Title + Image + full article summary/specs & interactive question, with ZERO external links,
     protecting page reach and complying with Facebook's anti-spam/engagement policies.
3. Natural Non-Consecutive Timing:
   - Never posts multiple posts back-to-back.
   - Enforces a randomized 75-130 minute gap between posts, max 1 post per automatic run, and a safe daily cap.

Can also be run manually:
  python fb_phones.py                           # auto mode (respects gap & alternates link / native no-link)
  python fb_phones.py --force                   # publish 1 new phone post immediately (bypass time gap)
  python fb_phones.py --force --mode link       # publish 1 link post immediately
  python fb_phones.py --force --mode native     # publish 1 full no-link post immediately
  python fb_phones.py --url "https://..."       # publish a specific article URL immediately
  python fb_phones.py --dry                     # preview without posting
"""
import argparse, datetime, hashlib, html, io, json, os, random, re, sys
import requests
from bs4 import BeautifulSoup
from PIL import Image
import football as f

REVIEW_BLOG = "2997328666613207792"
EA_BLOG = "8325646053257070334"
DEFAULT_PAGE_ID = "1959788610952661"  # صفحة موبايل بالعربى
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify_sent.json")
LOCAL_FB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fb_token.json")
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


def _download_jpeg_bytes(img_url):
    """Downloads any article image (WebP/PNG/JPEG/wsrv/jsdelivr) and converts to clean RGB JPEG bytes for Facebook."""
    if not img_url:
        return None
    try:
        r = requests.get(img_url, headers=UA, timeout=25)
        if r.status_code != 200 or not r.content:
            return None
        im = Image.open(io.BytesIO(r.content))
        if im.mode != "RGB":
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue()
    except Exception as ex:
        print(f"  [FB image convert warning] {ex}")
        return None


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

    # 1. Extract TL;DR / Quick takeaways if available
    bullets = []
    tldr = soup.select_one(".rv-tldr, .ea-tldr")
    if tldr:
        for li in tldr.find_all("li"):
            txt = re.sub(r"\s+", " ", li.get_text(" ", strip=True)).strip()
            if txt and not PROMO_SKIP_RX.search(txt):
                bullets.append(f"• {txt}")

    # 2. Extract clean narrative paragraphs
    paras = []
    for p in soup.find_all("p"):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if len(txt) < 45 or PROMO_SKIP_RX.search(txt):
            continue
        # Strip any accidental raw URLs
        txt = re.sub(r"https?://\S+", "", txt).strip()
        if txt not in paras:
            paras.append(txt)
        if len(paras) >= 3:
            break

    # 3. Extract up to 5 key specs from specification table if present
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

    # Pick a deterministic-yet-varied engagement question
    q_idx = int(hashlib.md5(clean_title.encode("utf-8")).hexdigest(), 16) % len(ENGAGEMENT_QUESTIONS)
    parts.append(ENGAGEMENT_QUESTIONS[q_idx])

    full_text = "\n\n".join(parts)
    # Final safety guard: ensure zero URLs exist in native post
    full_text = re.sub(r"https?://\S+", "", full_text).strip()
    return full_text


def choose_next_mode(state, requested_mode="auto"):
    """Alternates between 'link' posts and full 'native' (no-link) posts so the page never looks like a link farm."""
    if requested_mode in ("link", "native"):
        return requested_mode
    hist = state.get("fb_history", [])
    if not hist:
        return "link"
    # Every 3rd post (after 2 consecutive link posts) -> publish a full link-free native post
    recent_modes = [h.get("mode", "link") for h in hist[-2:]]
    if len(recent_modes) == 2 and all(m == "link" for m in recent_modes):
        return "native"
    return "link"


def check_timing_policy(state, now, force=False):
    """Checks Facebook anti-spam timing rules:
       - Daily cap
       - Randomized 75 to 130 minute gap since the last post
    """
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
                # Deterministic random gap (75..130 min) based on last post timestamp
                seed_int = int(hashlib.md5(last_at_str.encode("utf-8")).hexdigest()[:8], 16)
                req_gap_min = MIN_GAP_MINUTES + (seed_int % (MAX_GAP_MINUTES - MIN_GAP_MINUTES + 1))
                elapsed_min = (now - last_at).total_seconds() / 60.0
                if elapsed_min < req_gap_min:
                    return False, f"last FB post was {int(elapsed_min)}m ago (waiting for {req_gap_min}m natural gap)"
            except Exception:
                pass
    return True, "ok"


def post_phone_to_fb(title, url, image_url=None, content=None, mode="link", dry=False, record_state=True):
    """Publishes a phone article to the Facebook Page in either:
       - mode='link': Title + Article Photo + Link underneath
       - mode='native': Full native link-free post + Article Photo (separator post)
    """
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

    if dry:
        print(f"[DRY FB - mode={actual_mode.upper()}] Would post to Facebook Page ({page}):")
        print(f"  Image  : {img}")
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
    # 1. Preferred: Upload photo binary to /{page_id}/photos
    if img:
        jpg_bytes = _download_jpeg_bytes(img)
        if jpg_bytes:
            try:
                r = requests.post(
                    f"https://graph.facebook.com/{page}/photos",
                    data={"caption": caption, "access_token": tok},
                    files={"source": ("article.jpg", jpg_bytes, "image/jpeg")},
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

        # 2. Fallback: pass image URL directly to /{page_id}/photos
        if not ok:
            try:
                r = requests.post(
                    f"https://graph.facebook.com/{page}/photos",
                    data={"url": img, "caption": caption, "access_token": tok},
                    timeout=30
                )
                if r.ok:
                    fb_post_id = r.json().get("post_id") or r.json().get("id") or ""
                    print(f"✅ Facebook Photo (URL) Posted [{actual_mode.upper()}]: {clean_title} | fb_id={fb_post_id}")
                    ok = True
                else:
                    print(f"  FB URL photo post failed ({r.status_code}): {r.text[:180]}")
            except Exception as ex:
                print(f"  FB URL photo exception: {ex}")

    # 3. Last fallback if no image worked: post to /{page_id}/feed
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


def post_by_url(target_url, mode="auto", dry=False):
    """Fetches a specific post URL and posts it to Facebook."""
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
        return post_phone_to_fb(title, clean_url, image_url=img, content=body_html, mode=mode, dry=dry)
    except Exception as ex:
        print(f"Failed to fetch URL {clean_url}: {ex}")
        return False


def run_auto(dry=False, force=False, mode="auto", lookback_hours=24, max_per_run=1):
    """Scans Review and Egyptaway for recent live phone posts and publishes at most 1 post
       when the natural time gap condition is satisfied, alternating link and native no-link posts.
    """
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

    # Pick newest unposted candidate first so the page always shares fresh phone content
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
            record_state=True
        )
        if ok:
            posted_count += 1
            state = load_state()

    return posted_count


def main():
    ap = argparse.ArgumentParser(description="Auto-publish phone articles to Facebook Page (Policy-compliant spacing + native separator posts)")
    ap.add_argument("--url", default="", help="Specific article URL to publish immediately")
    ap.add_argument("--mode", choices=["auto", "link", "native"], default="auto",
                    help="Post mode: 'link' (Title+Photo+Link), 'native' (Full No-Link Post+Photo), or 'auto' (alternates automatically)")
    ap.add_argument("--hours", type=int, default=24, help="Lookback window in hours for auto mode")
    ap.add_argument("--max", type=int, default=1, help="Max posts to share in a single run (default 1 for non-consecutive posting)")
    ap.add_argument("--force", action="store_true", help="Bypass the 75-130 min time gap check for an immediate post")
    ap.add_argument("--dry", action="store_true", help="Dry run without posting")
    args = ap.parse_args()

    dry = args.dry or os.environ.get("DRY_RUN") == "1"
    force = args.force or os.environ.get("FORCE") == "1"
    if args.url:
        post_by_url(args.url, mode=args.mode, dry=dry)
    else:
        run_auto(dry=dry, force=force, mode=args.mode, lookback_hours=args.hours, max_per_run=args.max)


if __name__ == "__main__":
    main()
