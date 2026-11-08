"""Daily Egyptaway health check & auto-fix engine -> GitHub issue (Mohsen gets it by email).

Runs daily at 6:00 AM Cairo Time (04:00 UTC).
- Checks the latest posts and all pages for:
  1. Broken internal links (links pointing to 404/non-existent posts/pages).
     -> AUTOMATICALLY replaces them immediately with closest matching live posts or official hub pages!
  2. Direct Google Play images (play-lh.googleusercontent.com)
     -> AUTOMATICALLY proxies them through wsrv.nl to prevent slowing down the homepage.
  3. Images that do not load / broken media.
  4. Posts without any image.
- Updates affected posts/pages on Blogger via API PATCH immediately.
- Creates/updates a GitHub Issue with full details of what was fixed and what remains.
"""
import concurrent.futures as cf
import datetime
import difflib
import os
import re
import sys
import time
import urllib.parse
import requests

BLOG = "8325646053257070334"
SITE = "www.egyptaway.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
N_POSTS = int(os.environ.get("N_POSTS") or 300)


def sec(n):
    return os.environ.get(n, "").strip().strip('"')


def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": sec("BLOGGER_CLIENT_ID"),
        "client_secret": sec("BLOGGER_CLIENT_SECRET"),
        "refresh_token": sec("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token"
    }, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google login failed ({r.status_code}): {r.text[:150]}")
    return r.json()["access_token"]


def listing(tok, kind, n):
    out, page = [], None
    while len(out) < n:
        q = {"maxResults": min(100, n - len(out)), "fetchBodies": "true", "status": "live"}
        if page:
            q["pageToken"] = page
        r = requests.get(
            f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/{kind}",
            params=q,
            headers={"Authorization": "Bearer " + tok},
            timeout=90
        ).json()
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
        r = requests.get(
            f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/posts",
            params=q,
            headers={"Authorization": "Bearer " + tok},
            timeout=90
        ).json()
        urls |= {i["url"].split("?")[0] for i in r.get("items", [])}
        page = r.get("nextPageToken")
        if not page:
            return urls


def path(u):
    p = urllib.parse.urlparse(u)
    return urllib.parse.unquote(p.path).rstrip("/")


def img_ok(u):
    try:
        r = requests.get(u, headers=UA, timeout=25, stream=True)
        ok = r.status_code < 400 and r.headers.get("content-type", "").startswith("image")
        r.close()
        return ok
    except Exception:
        return False


def find_best_replacement(broken_href, known_paths):
    pth = path(broken_href)
    slug = pth.split("/")[-1].replace(".html", "").replace("-", " ").strip().lower()

    # 1. Close match on known paths
    matches = difflib.get_close_matches(pth, list(known_paths), n=1, cutoff=0.5)
    if matches:
        return f"https://{SITE}{matches[0]}"

    # 2. Topical keyword matching to high-value hubs
    if any(k in slug for k in ["مباراة", "مباريات", "كورة", "اهلي", "زمالك", "دوري", "match", "football"]):
        return f"https://{SITE}/p/matches-today.html"
    if any(k in slug for k in ["ذهب", "دولار", "عيار", "عملات", "صرف", "gold", "currency"]):
        return f"https://{SITE}/p/gold-prices-egypt.html"
    if any(k in slug for k in ["ترتيب", "الدوري المصري", "standings"]):
        return f"https://{SITE}/p/egyptian-league-table.html"
    if any(k in slug for k in ["لعبة", "تحميل", "العاب", "game", "download"]):
        return f"https://{SITE}/p/download-games.html"
    if any(k in slug for k in ["صلاة", "فجر", "مواقيت", "prayer"]):
        return f"https://{SITE}/p/prayer-times-egypt.html"
    if any(k in slug for k in ["طقس", "أرصاد", "حرارة", "weather"]):
        return f"https://{SITE}/p/weather-egypt.html"

    # 3. Fallback to homepage
    return f"https://{SITE}/"


def patch_content(tok, kind, item_id, new_content):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/{kind}/{item_id}"
    r = requests.patch(
        url,
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"content": new_content},
        timeout=45
    )
    return r.status_code == 200


def main():
    tok = token()
    posts = listing(tok, "posts", N_POSTS)
    pages = listing(tok, "pages", 300)

    known_post_paths = {path(u) for u in all_urls(tok)}
    known_page_paths = {path(p["url"]) for p in pages}
    known = known_post_paths | known_page_paths

    bad_links = []
    fixed_links = []
    fixed_playlh = []
    no_img = []
    imgs = {}

    for item, kind in [(p, "posts") for p in posts] + [(pg, "pages") for pg in pages]:
        content = item.get("content", "")
        item_url = item.get("url", "")
        item_id = item.get("id")
        modified = False
        new_content = content

        # Check & Auto-fix broken internal links
        internal_hrefs = set(re.findall(r'href="(https?://(?:www\.)?egyptaway\.com/[^"#?]+)', content))
        for href in internal_hrefs:
            pth = path(href)
            if re.match(r"^/(\d{4}/\d\d/[^/]+\.html|p/[^/]+\.html)$", pth) and pth not in known:
                bad_links.append((item_url, href))
                replacement = find_best_replacement(href, known)
                if replacement:
                    new_content = new_content.replace(f'href="{href}"', f'href="{replacement}"')
                    fixed_links.append((item_url, href, replacement))
                    modified = True

        # Check & Auto-fix direct play-lh images
        srcs = re.findall(r'<img[^>]+src="([^"]+)"', content)
        if not srcs and "/p/" not in item_url:
            no_img.append(item_url)

        for s in srcs:
            s_clean = s.replace("&amp;", "&")
            if s_clean.startswith("https://play-lh.googleusercontent.com"):
                encoded = urllib.parse.quote(s_clean, safe="")
                safe_img = f"https://wsrv.nl/?url={encoded}&w=1000&output=webp&q=75"
                new_content = new_content.replace(s, safe_img)
                fixed_playlh.append((item_url, s_clean))
                modified = True
            imgs.setdefault(s_clean, set()).add(item_url)

        # Apply PATCH if broken links or images were fixed
        if modified and item_id:
            ok = patch_content(tok, kind, item_id, new_content)
            if ok:
                print(f"Fixed & updated Blogger {kind[:-1]}: {item_url}")
            else:
                print(f"Failed to update Blogger {kind[:-1]}: {item_url}")
            time.sleep(0.5)

    with cf.ThreadPoolExecutor(12) as ex:
        res = dict(zip(imgs, ex.map(img_ok, imgs)))
    bad_imgs = [(u, sorted(imgs[u])[:3]) for u, ok in res.items() if not ok]

    today = datetime.date.today().isoformat()
    lines = [
        f"تقرير فحص وصيانة ايجبتاوى اليومي ({today}) - فحص {len(posts)} مقال و{len(pages)} صفحة و{len(imgs)} صورة.",
        ""
    ]

    def sect(title, items, fmt):
        lines.append(f"### {title} ({len(items)})")
        lines.extend(fmt(x) for x in items[:60])
        if len(items) > 60:
            lines.append(f"... و{len(items) - 60} كمان")
        lines.append("")

    if fixed_links:
        sect("روابط مكسورة تم استبدالها وتصحيحها فوراً على الموقع", fixed_links, lambda x: f"- في `{x[0]}`:\n  - القديم: `{x[1]}`\n  - البديل الجديد: `{x[2]}`")
    if fixed_playlh:
        sect("صور جوجل بلاي تم تصحيحها لـ wsrv.nl فوراً", fixed_playlh, lambda x: f"- في `{x[0]}` ← `{x[1]}`")

    remaining_bad = len(bad_links) - len(fixed_links)
    if remaining_bad > 0:
        sect("روابط متبقية تحت المراجعة", bad_links[len(fixed_links):], lambda x: f"- في {x[0]} ← {x[1]}")

    sect("صور لا تفتح وتحتاج مراجعة", bad_imgs, lambda x: f"- {x[0]} (في: {', '.join(x[1])})")
    sect("مقالات بدون صور", no_img, lambda x: f"- {x}")

    total_issues = remaining_bad + len(bad_imgs) + len(no_img)
    total_fixed = len(fixed_links) + len(fixed_playlh)
    lines.append(f"**ملخص العمل:** تم تصحيح {total_fixed} رابط/صورة فوراً، متبقي {total_issues} ملاحظة.")

    body = "\n".join(lines)
    print(body)

    gh = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if gh and repo and (total_issues > 0 or total_fixed > 0):
        r = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            json={
                "title": f"تقرير صيانة ايجبتاوى اليومي {today} (تم تصحيح {total_fixed} مشكلة تلقائياً)",
                "body": body
            },
            headers={"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"},
            timeout=30
        )
        print("Issue created:", r.status_code, r.json().get("html_url"))


if __name__ == "__main__":
    main()
