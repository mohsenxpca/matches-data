"""Phone spec catalog for review-mobile.com's comparison tool (/p/compare-phones.html), built ONLY from Review's own posts
(the spec tables in our reviews, which already cite official sources) + Egyptaway's Egypt prices (prices/phones.json).
No third-party spec database is copied. A field missing in our review stays empty.
Output: review_specs.json (served to the page through jsDelivr). Runs daily (review_specs.yml) so each new review joins.
Usage: python review_specs.py            (Blogger API, needs BLOGGER_* secrets)
       python review_specs.py raw.json   (from a local dump of posts)
"""
import html, json, os, re, sys
import requests

BLOG = "2997328666613207792"
FIELDS = [  # key, Arabic label, keywords in our table labels
    ("screen", "الشاشة", ["الشاشة", "حجم الشاشة", "الدقة"]),
    ("chip", "المعالج", ["المعالج", "الشريحة"]),
    ("mem", "الرامات والتخزين", ["الرام", "الذاكرة", "التخزين"]),
    ("rear", "الكاميرا الخلفية", ["الكاميرا الخلفية", "الكاميرات الخلفية", "الكاميرا الرئيسية", "الكاميرات", "📷", "الكاميرا"]),
    ("front", "الكاميرا الأمامية", ["الأمامية", "السيلفي"]),
    ("battery", "البطارية والشحن", ["البطارية", "الشحن"]),
    ("os", "نظام التشغيل", ["النظام", "نظام التشغيل"]),
    ("body", "التصميم والوزن", ["الأبعاد", "الوزن", "التصميم", "الهيكل", "السمك", "السُمك"]),
    ("protect", "المقاومة والحماية", ["المقاومة", "الحماية", "المتانة"]),
    ("conn", "الاتصال", ["الاتصال", "الشبكة", "الاتصالات"]),
    ("audio", "الصوت", ["الصوت"]),
    ("colors", "الألوان", ["الألوان"]),
    ("price", "السعر في المراجعة", ["السعر"]),
]
SKIP_TITLE = re.compile(r"أفضل|افضل|مقارنة|قائمة|دليل|أرخص (هواتف|موبايلات)|ارخص (هواتف|موبايلات)|ضد الماء|vs\b|top|\b(watch|fit|band|buds|earbuds)\b|ساعة|سماعة", re.I)
EMOJI = re.compile(r"[^\w\s/()+\-.،,]", re.U)


def secret(n):
    return os.environ.get(n, "").strip().strip('"')


def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": secret("BLOGGER_CLIENT_ID"), "client_secret": secret("BLOGGER_CLIENT_SECRET"),
        "refresh_token": secret("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def posts():
    if len(sys.argv) > 1:
        return json.load(open(sys.argv[1], encoding="utf-8"))
    tok, out, page = token(), [], None
    while True:
        p = {"maxResults": 50, "status": "live", "fields": "nextPageToken,items(id,title,url,labels,published,content)"}
        if page:
            p["pageToken"] = page
        r = requests.get(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/posts", params=p,
                         headers={"Authorization": "Bearer " + tok}, timeout=60).json()
        out += r.get("items", [])
        page = r.get("nextPageToken")
        if not page:
            return out


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def field_of(label):
    lab = EMOJI.sub("", label).strip()
    if any(k in lab for k in ("الأمامية", "السيلفي")):
        return "front"
    for key, _, kws in FIELDS:
        if key != "front" and any(k.replace("📷", "") and k in lab for k in kws):
            return key
    if "📷" in label:
        return "rear"
    return None


BRAND_START = re.compile(r"^(Samsung|Galaxy|Apple|iPhone|Xiaomi|Redmi|POCO|Oppo|Reno|Vivo|iQOO|Realme|Honor|Huawei|Nova|OnePlus|"
                         r"Nothing|Google|Pixel|Motorola|Moto|Infinix|Tecno|Nokia|Asus|ROG|Zenfone|Sony|Xperia|ZTE|Nubia|"
                         r"Red ?Magic|Itel|Meizu|Lava|Ai\+|HMD|Fairphone)\b", re.I)


def _clean(name):
    name = re.sub(r"\s+(5G|4G)$", r" \1", name).strip(" -.(")
    if len(name) < 4 or not re.search(r"\d|[A-Z]{2}", name):
        return None
    return re.sub(r"\s+20\d\d$", "", name)  # "Galaxy F70 2026" -> "Galaxy F70"


def model_name(title):
    t = re.sub(r"^\s*(مراجعة|مواصفات|سعر)\s*(هاتف|موبايل)?\s*", "", title)
    m = re.search(r"[A-Za-z][A-Za-z0-9+ ()'\-.]{2,40}", re.split(r"\s*[:|–—،]\s*|\s+-\s+", t)[0])
    name = _clean(m.group(0)) if m else None
    if name:
        return name
    # news titles: «رسمياً: إطلاق Redmi M100 Pro بشاشة ...» -> the first Latin run that starts with a phone brand
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9+ ()'\-.]{2,40}", title):
        if BRAND_START.match(m.group(0).strip()):
            name = _clean(m.group(0).strip())
            if name:
                return name
    return None


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _rows(tbl):
    return [(tr, [text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]) for tr in re.findall(r"<tr.*?</tr>", tbl, re.S)]


def specs(content, name=""):
    """Rows of our spec tables (label|value). Only when those give fewer than 3 fields (news posts from
    review_engine use «الميزة | Phone X | previous gen»), fall back to 3+ column tables whose header names
    this phone, or whose 2nd header is a spec column, and take that phone's column."""
    out, key = {}, _norm(name)
    tables = re.findall(r"<table.*?</table>", content, re.S)[:3]

    def add(label, val):
        k = field_of(label) if len(label) <= 30 else None
        if k and val and val not in out.get(k, ""):
            out[k] = (out[k] + " · " + val) if k in out else val

    for tbl in tables:
        for tr, cells in _rows(tbl):
            if len(cells) == 2:
                add(cells[0], cells[1])
    if len([k for k in out if k != "price"]) >= 3:
        return out
    for tbl in tables:
        rows = _rows(tbl)
        if not rows or "<th" not in rows[0][0] or len(rows[0][1]) < 3:
            continue
        head = rows[0][1]
        hit = [j for j, h in enumerate(head[1:], 1) if key and _norm(h) and (key in _norm(h) or _norm(h) in key)]
        if hit:
            col = hit[0]
        elif re.search(r"المواصف|القيمة|التفاصيل", head[1]):
            col = 1
        else:
            continue
        for tr, cells in rows[1:]:
            if len(cells) > col:
                add(cells[0], cells[col])
    return out


def egypt_prices():
    p = os.path.join("prices", "phones.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    out = {}
    for x in d.get("phones", []):
        v = [r[1] for r in x.get("variants", []) if isinstance(r[1], (int, float)) and r[1] > 0]
        if v:
            out[re.sub(r"[^a-z0-9]", "", x["name"].lower().replace("samsung", ""))] = {"egp": min(v), "page": f"https://www.egyptaway.com/p/{x['slug']}.html"}
    return out


def main():
    P, prices, cat, seen = posts(), egypt_prices(), [], set()
    for p in sorted(P, key=lambda x: x.get("published", ""), reverse=True):
        if SKIP_TITLE.search(p["title"]):
            continue
        name = model_name(p["title"])
        sp = specs(p.get("content", ""), name or "")
        if not name or len([k for k in sp if k != "price"]) < 3:
            continue
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        if key in seen:
            continue
        seen.add(key)
        slug = p["url"].rstrip("/").rsplit("/", 1)[-1].replace(".html", "")
        pr = prices.get(key.replace("samsung", "")) or {}
        img = re.search(r'<img[^>]+src="([^"]+)"', p.get("content", ""))
        cat.append({"id": slug, "pid": p.get("id", ""), "big": thumb(img.group(1), 480) if img else "",
                    "n": name, "t": p["title"], "b": (p.get("labels") or [""])[0], "u": p["url"],
                    "s": sp, "egp": pr.get("egp"), "pp": pr.get("page"), "img": thumb(img.group(1)) if img else "",
                    "d": p.get("published", "")[:10], "ts": p.get("published", "")})
    data = {"fields": [[k, ar] for k, ar, _ in FIELDS], "phones": cat}
    json.dump(data, open("review_specs.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    side(cat)
    print("phones", len(cat))


def thumb(u, w=200):
    """Small, sharp sidebar thumbnail: Blogger images by size suffix, anything else through wsrv.nl."""
    u = html.unescape(u)
    if "blogger.googleusercontent.com" in u or "bp.blogspot.com" in u:
        return re.sub(r"/(s\d+[^/]*|w\d+[^/]*)/(?=[^/]+$)", f"/w{w}-h{w}-p-k-no-nu/", u)
    if "wsrv.nl" in u:
        return re.sub(r"([?&])w=\d+", rf"\g<1>w={w}", u)
    return "https://wsrv.nl/?url=" + requests.utils.quote(u, safe="") + f"&w={w}&h={w}&fit=contain&output=webp&q=80"


def side(cat):
    """review_side.json: the small data file the sidebar loads on every page."""
    latest = [{"n": p["n"], "u": p["u"], "img": p["img"]} for p in sorted(cat, key=lambda x: x.get("ts") or x["d"], reverse=True) if p["img"]][:9]
    prices = []
    pj = os.path.join("prices", "phones.json")
    if os.path.exists(pj):
        rev = {re.sub(r"[^a-z0-9]", "", p["n"].lower().replace("samsung", "")): p["u"] for p in cat}
        for x in json.load(open(pj, encoding="utf-8")).get("phones", []):
            v = [r[1] for r in x.get("variants", []) if isinstance(r[1], (int, float)) and r[1] > 0]
            if not v:
                continue
            k = re.sub(r"[^a-z0-9]", "", x["name"].lower().replace("samsung", ""))
            prices.append({"n": x["name"], "b": x["brand"], "egp": min(v), "img": thumb(x.get("img", "")) if x.get("img") else "",
                           "u": rev.get(k) or f"https://www.egyptaway.com/p/{x['slug']}.html"})
    search = [[p["n"], p["b"], p["u"]] for p in cat]
    json.dump({"latest": latest, "prices": prices, "search": search}, open("review_side.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
