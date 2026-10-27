"""Weekly Egyptaway health check -> GitHub issue (Mohsen gets it by email).

Checks the latest posts and all pages for: internal links to posts/pages that don't exist, images that don't load,
Google Play images used directly (they slow the homepage), and posts without any image.
Nothing is changed on the site; the issue lists what to fix.
Runs on GitHub Actions (.github/workflows/maintenance.yml). Needs the BLOGGER_* secrets and GITHUB_TOKEN.
"""
import concurrent.futures as cf, datetime, os, re, sys, urllib.parse
import requests

BLOG = "8325646053257070334"
SITE = "www.egyptaway.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
N_POSTS = int(os.environ.get("N_POSTS") or 300)


def sec(n):
    return os.environ.get(n, "").strip().strip('"')


def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": sec("BLOGGER_CLIENT_ID"), "client_secret": sec("BLOGGER_CLIENT_SECRET"),
        "refresh_token": sec("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google login failed ({r.status_code}): {r.text[:150]}")
    return r.json()["access_token"]


def listing(tok, kind, n):
    out, page = [], None
    while len(out) < n:
        q = {"maxResults": min(100, n - len(out)), "fetchBodies": "true", "status": "live"}
        if page:
            q["pageToken"] = page
        r = requests.get(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/{kind}", params=q,
                         headers={"Authorization": "Bearer " + tok}, timeout=90).json()
        out += r.get("items", [])
        page = r.get("nextPageToken")
        if not page:
            break
    return out


def all_urls(tok):
    urls, page = set(), None
    while True:
        q = {"maxResults": 500, "fetchBodies": "false", "status": "live", "fields": "items(url),nextPageToken"}
        if page:
            q["pageToken"] = page
        r = requests.get(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/posts", params=q,
                         headers={"Authorization": "Bearer " + tok}, timeout=90).json()
        urls |= {i["url"].split("?")[0] for i in r.get("items", [])}
        page = r.get("nextPageToken")
        if not page:
            return urls


def path(u):
    p = urllib.parse.urlparse(u)
    return urllib.parse.unquote(p.path).rstrip("/")  # links written with %20 vs spaces must compare equal


def img_ok(u):
    try:
        r = requests.get(u, headers=UA, timeout=25, stream=True)
        ok = r.status_code < 400 and r.headers.get("content-type", "").startswith("image")
        r.close()
        return ok
    except Exception:
        return False


def main():
    tok = token()
    posts = listing(tok, "posts", N_POSTS)
    pages = listing(tok, "pages", 300)
    known = {path(u) for u in all_urls(tok)} | {path(p["url"]) for p in pages}
    bad_links, no_img, playlh, imgs = [], [], [], {}
    for p in posts + pages:
        c = p.get("content", "")
        for href in set(re.findall(r'href="(https?://(?:www\.)?egyptaway\.com/[^"#?]+)', c)):
            pth = path(href)
            if re.match(r"^/(\d{4}/\d\d/[^/]+\.html|p/[^/]+\.html)$", pth) and pth not in known:
                bad_links.append((p["url"], href))
        srcs = re.findall(r'<img[^>]+src="([^"]+)"', c)
        if not srcs and "/p/" not in p["url"]:
            no_img.append(p["url"])
        for s in srcs:
            s = s.replace("&amp;", "&")
            if s.startswith("https://play-lh.googleusercontent.com"):
                playlh.append(p["url"])
            imgs.setdefault(s, set()).add(p["url"])
    with cf.ThreadPoolExecutor(12) as ex:
        res = dict(zip(imgs, ex.map(img_ok, imgs)))
    bad_imgs = [(u, sorted(imgs[u])[:3]) for u, ok in res.items() if not ok]

    today = datetime.date.today().isoformat()
    lines = [f"فحص {len(posts)} مقال و{len(pages)} صفحة و{len(imgs)} صورة على ايجبتاوى ({today}).", ""]
    def sect(title, items, fmt):
        lines.append(f"### {title} ({len(items)})")
        lines.extend(fmt(x) for x in items[:60])
        if len(items) > 60:
            lines.append(f"... و{len(items) - 60} كمان")
        lines.append("")
    sect("روابط داخلية لمقالات/صفحات مش موجودة", bad_links, lambda x: f"- في {x[0]} ← {x[1]}")
    sect("صور مش بتفتح", bad_imgs, lambda x: f"- {x[0]} (في: {', '.join(x[1])})")
    sect("صور جوجل بلاي مباشرة (لازم تعدي على wsrv.nl)", sorted(set(playlh)), lambda x: f"- {x}")
    sect("مقالات من غير صور", no_img, lambda x: f"- {x}")
    total = len(bad_links) + len(bad_imgs) + len(set(playlh)) + len(no_img)
    body = "\n".join(lines)
    print(body)
    if not total:
        print("all good, no issue opened")
        return
    gh = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if gh and repo:
        r = requests.post(f"https://api.github.com/repos/{repo}/issues", json={
            "title": f"تقرير صيانة ايجبتاوى {today}: {total} مشكلة", "body": body},
            headers={"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"}, timeout=30)
        print("issue:", r.status_code, r.json().get("html_url"))


if __name__ == "__main__":
    main()
