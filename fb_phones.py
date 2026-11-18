"""Auto-publish phone articles (from Review + Egyptaway) to the Facebook Page.

Format requested by Mohsen (2026-11-18):
- Article Title
- Article Image (uploaded as a Facebook Page photo post)
- Article Link right underneath

Works automatically:
1. Inside phone_news.py right after a new phone news article goes live on Egyptaway.
2. Inside review_engine.py right after a new phone review/news article goes live on Review.
3. Inside notify.py (every 30 mins on GitHub Actions) scanning both Review and Egyptaway for any new phone post.

Can also be run manually:
  python fb_phones.py                        # scan Review + Egyptaway for recent unposted phone articles
  python fb_phones.py --url "https://..."    # post a specific article URL to Facebook
  python fb_phones.py --dry                  # preview without posting
"""
import argparse, datetime, html, io, json, os, re, sys
import requests
from bs4 import BeautifulSoup
from PIL import Image
import football as f

REVIEW_BLOG = "2997328666613207792"
EA_BLOG = "8325646053257070334"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify_sent.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

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


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fp:
            state = json.load(fp)
    except Exception:
        state = {}
    for k in ("sent", "indexed", "tg", "fb"):
        state.setdefault(k, [])
    return state


def save_state(state):
    for k in ("sent", "indexed", "tg", "fb"):
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


def post_phone_to_fb(title, url, image_url=None, content=None, dry=False, record_state=True):
    """Publishes a phone article to the Facebook Page with:
       Title
       [Article Photo]
       Link right underneath
    """
    clean_title = html.unescape(title or "").strip()
    clean_url = (url or "").replace("http://", "https://").strip()
    img = image_url or first_image(content)

    # Exact caption structure requested by Mohsen: Title + Link underneath (with the photo attached)
    caption = f"{clean_title}\n\n{clean_url}"

    tok = f.secret("FB_PAGE_TOKEN")
    page = f.secret("FB_PAGE_ID")

    if dry:
        print(f"[DRY FB] Would post to Facebook Page:")
        print(f"  Title: {clean_title}")
        print(f"  Image: {img}")
        print(f"  Link : {clean_url}")
        return False

    if not tok or not page:
        print(f"Facebook: (missing FB_PAGE_TOKEN or FB_PAGE_ID) skipped '{clean_title[:60]}'")
        return False

    state = load_state() if record_state else None
    if state and clean_url in state["fb"]:
        print(f"Facebook: already posted {clean_url}")
        return True

    ok = False
    # 1. Preferred: Upload photo binary to /{page_id}/photos with caption = Title + Link
    if img:
        jpg_bytes = _download_jpeg_bytes(img)
        if jpg_bytes:
            try:
                r = requests.post(
                    f"https://graph.facebook.com/v21.0/{page}/photos",
                    data={"caption": caption, "access_token": tok},
                    files={"source": ("article.jpg", jpg_bytes, "image/jpeg")},
                    timeout=40
                )
                if r.ok:
                    print(f"✅ Facebook Photo Posted: {clean_title} | {clean_url}")
                    ok = True
                else:
                    print(f"  FB binary photo upload failed ({r.status_code}): {r.text[:180]}")
            except Exception as ex:
                print(f"  FB binary photo upload exception: {ex}")

        # 2. Fallback: pass image URL directly to /{page_id}/photos
        if not ok:
            try:
                r = requests.post(
                    f"https://graph.facebook.com/v21.0/{page}/photos",
                    data={"url": img, "caption": caption, "access_token": tok},
                    timeout=30
                )
                if r.ok:
                    print(f"✅ Facebook Photo (URL) Posted: {clean_title} | {clean_url}")
                    ok = True
                else:
                    print(f"  FB URL photo post failed ({r.status_code}): {r.text[:180]}")
            except Exception as ex:
                print(f"  FB URL photo exception: {ex}")

    # 3. Last fallback if no image worked: post to /{page_id}/feed
    if not ok:
        try:
            r = requests.post(
                f"https://graph.facebook.com/v21.0/{page}/feed",
                data={"message": caption, "link": clean_url, "access_token": tok},
                timeout=30
            )
            if r.ok:
                print(f"✅ Facebook Feed Posted: {clean_title} | {clean_url}")
                ok = True
            else:
                print(f"❌ Facebook post failed ({r.status_code}): {r.text[:200]}")
        except Exception as ex:
            print(f"❌ Facebook feed exception: {ex}")

    if ok and state is not None:
        if clean_url not in state["fb"]:
            state["fb"].append(clean_url)
            save_state(state)

    return ok


def post_by_url(target_url, dry=False):
    """Fetches a specific post URL (either via Blogger API or direct page scrape) and posts it to Facebook."""
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
        if not img:
            art_img = soup.select_one(".post-body img, article img, .rv-wrap img, .ea-wrap img")
            if art_img and art_img.get("src"):
                img = art_img["src"].strip()
        return post_phone_to_fb(title, clean_url, image_url=img, dry=dry)
    except Exception as ex:
        print(f"Failed to fetch URL {clean_url}: {ex}")
        return False


def run_auto(dry=False, lookback_hours=12, max_per_run=4):
    """Scans both Review and Egyptaway for recent live phone posts not yet shared on Facebook."""
    state = load_state()
    done_fb = set(state.get("fb", []))
    now = datetime.datetime.now(f.CAIRO)
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
                if not u or u in done_fb or u in state.get("fb", []):
                    continue
                if is_phone_post(p, blog_id=blog_id):
                    candidates.append((p.get("published", ""), site_name, p))
        except Exception as ex:
            print(f"Facebook scan warning ({site_name}): {ex}")

    candidates.sort(key=lambda x: x[0])
    print(f"Facebook Phone Auto-Poster: found {len(candidates)} new phone post(s) across Review & Egyptaway.")

    posted_count = 0
    for _, site_name, p in candidates[:max_per_run]:
        u = p["url"].replace("http://", "https://")
        img = first_image(p.get("content"), post=p)
        ok = post_phone_to_fb(p["title"], u, image_url=img, content=p.get("content"), dry=dry, record_state=False)
        if ok:
            state["fb"].append(u)
            posted_count += 1

    if posted_count > 0 and not dry:
        save_state(state)
    return posted_count


def main():
    ap = argparse.ArgumentParser(description="Auto-publish phone articles to Facebook Page (Title + Image + Link)")
    ap.add_argument("--url", default="", help="Specific article URL to publish immediately")
    ap.add_argument("--hours", type=int, default=12, help="Lookback window in hours for auto mode")
    ap.add_argument("--max", type=int, default=4, help="Max posts to share in a single run")
    ap.add_argument("--dry", action="store_true", help="Dry run without posting")
    args = ap.parse_args()

    dry = args.dry or os.environ.get("DRY_RUN") == "1"
    if args.url:
        post_by_url(args.url, dry=dry)
    else:
        run_auto(dry=dry, lookback_hours=args.hours, max_per_run=args.max)


if __name__ == "__main__":
    main()
