"""Homepage thumbnails for new posts (mohsen 2026-11-01), every 20 minutes on GitHub Actions (thumbfix.yml).

The theme draws the homepage cards from the feed's media$thumbnail, and Blogger only sets that when the post's first image
is hosted by Google. Our engines use wsrv.nl / Pexels / jsdelivr images, so those cards started empty and the theme had to
fetch every post page to find a picture (slow, and blurry when resized). Once a post is live, Blogger renders its first image
through lh3.googleusercontent.com/blogger_img_proxy/... (the og:image of the post page). This swaps the first image's src for
that Google-hosted link through the API: same picture, same URL and date, and the card gets a real thumbnail.
Same idea as thumbs.py on mohsen's PC. Env: DRY_RUN=1, HOURS (default 48).
"""
import datetime, os, re, sys, time
import requests
import football as f

BLOGS = {"egyptaway": ("8325646053257070334", "https://www.egyptaway.com"),
         "review": ("2997328666613207792", "https://www.review-mobile.com")}
GOOGLE_HOSTED = re.compile(r"(?i)^https?://([a-z0-9-]+\.)*(googleusercontent\.com|blogspot\.com|ggpht\.com)/")
FIRST_IMG = re.compile(r"""(?is)(<img\b[^>]*?\bsrc=)(["'])([^"']+)(\2)""")
PROXY = re.compile(r"(https://lh3\.googleusercontent\.com/blogger_img_proxy/[A-Za-z0-9_\-]+)")
DRY = os.environ.get("DRY_RUN") == "1"
HOURS = int(os.environ.get("HOURS") or 48)


def via_translate(url):
    """Cloudflare's Bot Fight Mode answers GitHub runners with 403, so read the page through Google Translate's proxy
    (www.egyptaway.com -> www-egyptaway-com.translate.goog); it keeps the og:image meta as is."""
    host, path = re.match(r"https?://([^/]+)(/.*)?$", url).groups()
    return "https://" + host.replace("-", "--").replace(".", "-") + ".translate.goog" + (path or "/") + \
        "?_x_tr_sl=ar&_x_tr_tl=en&_x_tr_hl=en"


def proxy_for(url):
    """Google-hosted link Blogger made for the post's first image, or None."""
    r = None
    for u in (url, via_translate(url)):
        try:
            r = requests.get(u, headers=f.HEAD, timeout=40)
        except requests.RequestException as e:
            print("  page error:", e)
            continue
        if r.status_code == 200:
            break
    if r is None or r.status_code != 200:
        print("  page not readable", r.status_code if r is not None else "", url)
        return None
    og = re.search(r"""<meta[^>]+property=['"]og:image['"][^>]+content=['"]([^'"]+)""", r.text) or \
        re.search(r"""<meta[^>]+content=['"]([^'"]+)['"][^>]+property=['"]og:image""", r.text)
    m = PROXY.search(og.group(1) if og else "")
    return m.group(1) + "=s1600" if m else None


def main():
    tok = f.token()
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=HOURS)).isoformat()
    fixed = 0
    for name, (blog, site) in BLOGS.items():
        try:
            res = f.api("GET", f"/blogs/{blog}/posts", tok, {"status": "live", "startDate": since, "maxResults": 60,
                                                             "fetchBodies": "true", "fields": "items(id,url,content)"})
        except RuntimeError as e:
            print(name, "skipped:", e)
            continue
        items = res.get("items", [])
        todo = [p for p in items if (m := FIRST_IMG.search(p.get("content", ""))) and not GOOGLE_HOSTED.match(m.group(3))]
        print(f"{name}: {len(items)} live posts in the last {HOURS}h, {len(todo)} without a Google-hosted first image")
        for p in todo:
            new = proxy_for(p["url"])
            if not new:
                print("  no proxy yet:", p["url"])
                continue
            html = p["content"]
            m = FIRST_IMG.search(html)
            if DRY:
                print("  DRY would fix", p["url"])
                continue
            out = f.api("PATCH", f"/blogs/{blog}/posts/{p['id']}", tok, None, {"content": html[:m.start(3)] + new + html[m.end(3):]})
            if out.get("url") != p["url"]:
                print("  WARNING url changed:", p["url"], "->", out.get("url"))
            else:
                print("  fixed", p["url"])
                fixed += 1
            time.sleep(1)
    print("done:", fixed, "fixed")


if __name__ == "__main__":
    sys.exit(main())
