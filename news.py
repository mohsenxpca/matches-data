"""Collect Yallakora's latest football headlines into news.json (title, link, image, section).

Only headlines + links are kept (each item links back to the full story on Yallakora).
Runs on GitHub Actions (see .github/workflows/news.yml).
"""
import json, re, datetime
from urllib.parse import urljoin, unquote
import requests
from bs4 import BeautifulSoup

BASE = "https://www.yallakora.com/"
HEAD = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36",
        "Accept-Language": "ar,en;q=0.8"}
MAX = 30


def section(href):
    m = re.match(r"/([a-z0-9-]+)/(?:\d+/)?news/", href)
    return m.group(1) if m else ""


def main():
    proxy = "https://www-yallakora-com.translate.goog/?_x_tr_sl=ar&_x_tr_tl=ar&_x_tr_hl=ar"
    html_text = ""
    for target in (BASE, proxy):
        try:
            r = requests.get(target, headers=HEAD, timeout=35)
            if r.status_code == 200 and len(r.text) > 1000:
                html_text = r.text
                break
        except Exception as e:
            print(f"Warning fetching {target[:35]}: {e}")
    if not html_text:
        print("⚠️ Yallakora temporarily unreachable from this runner IP — keeping existing news.json intact.")
        return
    soup = BeautifulSoup(html_text, "html.parser")
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0].replace("https://www-yallakora-com.translate.goog", "")
        href = re.sub(r"\?_x_tr_[^\s\"']*", "", href)
        m = re.search(r"/news/(\d+)/", href)
        if not m or m.group(1) in seen:
            continue
        title = a.get("title") or ""
        if not title:
            t = a.find(["h3", "h4", "p"]) or a
            title = t.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 15:
            continue
        img = a.find("img")
        src = ""
        if img:
            src = (img.get("data-src") or img.get("src") or "").replace("\\", "/")
            if src.startswith("data:"):
                src = ""
        seen.add(m.group(1))
        items.append({"id": int(m.group(1)), "t": title, "u": urljoin(BASE, href),
                      "i": urljoin(BASE, src) if src else "", "s": section(href)})
    items.sort(key=lambda x: -x["id"])
    items = items[:MAX]
    if len(items) < 5:
        print(f"⚠️ Only {len(items)} headlines found — keeping existing news.json intact.")
        return
    old = []
    try:
        old = json.load(open("news.json", encoding="utf-8")).get("news", [])
    except Exception:
        pass
    if [x["id"] for x in old] == [x["id"] for x in items]:
        print("No new headlines")
        return
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump({"updated": now, "source": "yallakora.com", "news": items},
              open("news.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(items)} headlines, newest: {items[0]['t']}")


if __name__ == "__main__":
    main()
