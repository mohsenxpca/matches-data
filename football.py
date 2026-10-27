"""Write and schedule original football news posts on Egyptaway (blog 8325646053257070334).

Runs daily on GitHub Actions (.github/workflows/football.yml):
  1. picks the most important new headlines from news.json (Egyptian football first),
  2. reads the story's facts, asks Gemini to write a fresh article in our own words,
  3. checks it automatically (every number must come from the source or the matches table,
     no source-site name, title not a repeat, long enough), and retries once if a check fails,
  4. schedules it on Blogger at a random time today, hours apart from the others.

Secrets: GEMINI_API_KEY, BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN.
Env: COUNT (posts per run, default 2), DRY_RUN=1 (write files to out/ instead of publishing).
"""
import datetime, difflib, html, json, os, random, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

BLOG = "8325646053257070334"
SITE = "https://www.egyptaway.com"
CAIRO = ZoneInfo("Africa/Cairo")
HEAD = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36",
        "Accept-Language": "ar,en;q=0.8"}
COUNT = int(os.environ.get("COUNT", "2"))
DRY = os.environ.get("DRY_RUN") == "1"
DAY_CAP = int(os.environ.get("DAY_CAP") or 10)  # same cap as blogger_api.py on Mohsen's PC; a manual run can raise it
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
BANNED = ["يلا كورة", "يلاكورة", "yallakora", "يلا كوره"]
PRIORITY = ["egyptian-league", "egypt-cup", "african-champions-league", "african-confederation-cup", "can-qualifiers",
            "world-cup-qualifiers", "egypt-national-team", "saudi-league", "epl", "la-liga", "uefa-champions-league",
            "serie-a", "bundesliga", "ligue-1"]
LABELS = {"egyptian-league": "الدوري المصري", "egypt-cup": "الدوري المصري"}
MATCHES_PAGE = SITE + "/p/matches-today.html"
EGYNOW = SITE + "/2024/03/egynow.html"
PEX = "https://images.pexels.com/photos/{i}/pexels-photo-{i}.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1000&amp;h=563&amp;fit=crop"
IMAGES = [  # checked by eye 2026-10-27
    (19875973, "جمهور كرة قدم في المدرجات بيرفع أعلام مصر"),
    (36227922, "ملعب كرة قدم وقت الغروب والمدرجات فيها جمهور"),
    (30651230, "ملعب كرة قدم مليان جمهور تحت الكشافات بالليل"),
    (26694125, "مدرجات ملعب كرة قدم مليانة جمهور قبل الماتش"),
    (34649310, "مدرجات حمرا فاضية في ملعب كرة قدم"),
    (3148452, "لاعبين كرة قدم بيتنافسوا على الكورة في ماتش قدام جمهور"),
    (1171084, "ملعب كرة قدم أخضر متصور من فوق"),
    (114296, "كورة قدم على النجيلة في ملعب وقت الغروب"),
    (274422, "لاعبين بيتنافسوا على الكورة في ماتش كرة قدم"),
]
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


# ------------------------------------------------------------------ helpers
def norm(s):
    s = re.sub(r"[ً-ْـ]", "", s or "")
    return re.sub(r"\s+", " ", s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")).strip()


def numbers(text):
    t = (text or "").translate(AR_DIGITS)
    return {n.lstrip("0") or "0" for n in re.findall(r"\d+(?:[.,]\d+)?", t)}


def secret(name):
    """Secret value, tolerant of pasted spaces / quotes / trailing commas."""
    return os.environ.get(name, "").strip().strip(",").strip().strip('"').strip("'").strip()


def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": secret("BLOGGER_CLIENT_ID"), "client_secret": secret("BLOGGER_CLIENT_SECRET"),
        "refresh_token": secret("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        cid = secret("BLOGGER_CLIENT_ID")
        sys.exit(f"Google login failed ({r.status_code}): {r.text[:200]} | client_id looks "
                 f"{'OK' if cid.endswith('.apps.googleusercontent.com') else 'WRONG'}, "
                 f"client_secret starts {'GOCSPX-' if secret('BLOGGER_CLIENT_SECRET').startswith('GOCSPX-') else 'with something else'}, "
                 f"refresh_token starts {'1//' if secret('BLOGGER_REFRESH_TOKEN').startswith('1//') else 'with something else'}")
    return r.json()["access_token"]


def api(method, path, tok, params=None, body=None):
    r = requests.request(method, "https://www.googleapis.com/blogger/v3" + path, params=params, json=body,
                         headers={"Authorization": "Bearer " + tok}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Blogger {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else {}


def site_posts(tok=None):
    """Recent Egyptaway posts (title, url, labels, published). Uses the API on GitHub (the site's
    public feed is blocked for datacenter IPs), the public feed otherwise."""
    if tok:
        res = api("GET", f"/blogs/{BLOG}/posts", tok, {"fetchBodies": "false", "maxResults": 200, "status": "live",
                                                    "fields": "items(title,url,labels,published)"})
        return [{"t": p.get("title", ""), "u": p.get("url", ""), "l": p.get("labels", []), "p": p.get("published", "")}
                for p in res.get("items", [])]
    r = requests.get(SITE + "/feeds/posts/summary", params={"alt": "json", "max-results": 150}, headers=HEAD, timeout=40)
    out = []
    for e in r.json().get("feed", {}).get("entry", []):
        url = next((l["href"] for l in e["link"] if l["rel"] == "alternate"), "")
        out.append({"t": e["title"]["$t"], "u": url, "l": [c["term"] for c in e.get("category", [])],
                    "p": e["published"]["$t"]})
    return out


def source_text(url):
    r = requests.get(url, headers=HEAD, timeout=40)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    box = s.select_one(".details") or s.select_one("article") or s
    paras = [p.get_text(" ", strip=True) for p in box.find_all("p")]
    paras = [p for p in paras if len(p) > 40 and not any(b in p for b in ("تابعنا", "اقرأ أيضا", "اقرأ أيضًا"))]
    return "\n".join(paras)


def team_matches(text, data):
    """Upcoming matches (next 7 days) for teams named in the story."""
    today = datetime.datetime.now(CAIRO).date()
    end = today + datetime.timedelta(days=7)
    nt = norm(text)
    rows = []
    for m in data.get("matches", []):
        try:
            d = datetime.date.fromisoformat(m["d"])
        except Exception:
            continue
        if not (today <= d <= end):
            continue
        if any(len(norm(x)) > 3 and norm(x) in nt for x in (m["h"], m["a"])):
            rows.append(m)
    rows.sort(key=lambda m: (m["d"], m["t"]))
    return rows[:6]


_MODELS = None


def models(key):
    """Flash models that support generateContent, newest first, then flash-lite ones (names change over time).
    The newest model is often overloaded on the free tier, so gemini() falls back down this list."""
    global _MODELS
    if _MODELS:
        return _MODELS
    if os.environ.get("GEMINI_MODEL"):
        _MODELS = [os.environ["GEMINI_MODEL"]]
        return _MODELS
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": key},
                     params={"pageSize": 200}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Gemini key problem ({r.status_code}): {r.text[:200]}")
    names = [m["name"].split("/", 1)[1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]

    def ver(n):
        return tuple(int(x) for x in re.findall(r"\d+", n.split("-flash")[0]))
    flash = sorted((n for n in names if re.fullmatch(r"gemini-[\d.]+-flash", n)), key=ver, reverse=True)
    lite = sorted((n for n in names if re.fullmatch(r"gemini-[\d.]+-flash-lite", n)), key=ver, reverse=True)
    # the big Flash models were overloaded/silent for minutes on the free tier (2026-10-27); lite answers in seconds
    _MODELS = (flash[:1] + lite[:1] + flash[1:2] + lite[1:2]) or [n for n in names if "flash" in n][:3] or names[:1]
    print("Gemini models to try:", _MODELS)
    return _MODELS


_THINK = {"thinkingConfig": {"thinkingLevel": "low"}}


def gemini(prompt):
    """Streams the answer (SSE) so long generations don't get their connection dropped;
    moves to the next model when one is overloaded or silent."""
    global _THINK
    key = secret("GEMINI_API_KEY")
    plan = [m for m in models(key) for _ in range(2)]
    for t, model in enumerate(plan):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
        cfg = {"temperature": 0.7, "responseMimeType": "application/json", "maxOutputTokens": 8192, **_THINK}
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
        t0 = time.time()
        try:
            with requests.post(url, params={"alt": "sse"}, headers={"x-goog-api-key": key}, json=body,
                               stream=True, timeout=(30, 240)) as r:
                if r.status_code == 400 and _THINK and "think" in r.text.lower():
                    _THINK = {}  # this model doesn't take thinkingLevel
                    continue
                if r.status_code in (404, 429, 500, 503):
                    print(f"  {model} busy/unavailable ({r.status_code})")
                    time.sleep(20)
                    continue
                if r.status_code != 200:
                    sys.exit(f"Gemini error {r.status_code}: {r.text[:300]}")
                parts, finish = [], ""
                # bytes, split on \n only: decoding first (latin-1 by default) turns Arabic bytes like 0x85
                # into line breaks and cuts the JSON chunks
                for raw in r.iter_lines():
                    line = raw.decode("utf-8", "replace") if raw else ""
                    if line.startswith("data:"):
                        try:
                            d = json.loads(line[5:])
                        except ValueError:
                            continue
                        if d.get("error"):
                            raise requests.exceptions.RequestException(str(d["error"])[:150])
                        for c in d.get("candidates", []):
                            finish = c.get("finishReason") or finish
                            for p in c.get("content", {}).get("parts", []):
                                if p.get("text") and not p.get("thought"):
                                    parts.append(p["text"])
        except requests.exceptions.RequestException as e:
            print(f"  {model} connection dropped:", type(e).__name__, f"after {int(time.time() - t0)}s")
            time.sleep(15)
            continue
        txt = "".join(parts).strip()
        print(f"  {model} wrote {len(txt)} chars in {int(time.time() - t0)}s (finish: {finish})")
        try:
            return json.loads(re.sub(r"^```(json)?|```$", "", txt))
        except ValueError:
            print("  Gemini returned broken JSON, retrying:", txt[:120].replace("\n", " "))
            continue
    raise RuntimeError("Gemini unavailable")


PROMPT = """أنت محرر رياضي في موقع ايجبتاوى المصري. اكتب خبر كرة قدم أصلي بالكامل بأسلوبنا عن الموضوع ده.

قواعد صارمة:
- استخدم المعلومات اللي في «النص المصدر» و«جدول المباريات» بس. ممنوع تضيف أي رقم أو نتيجة أو تاريخ أو سعر أو اسم لاعب مش موجود فيهم.
- ممنوع تنسخ جمل من المصدر: أعد الكتابة بالكامل بترتيب وصياغة مختلفة.
- ممنوع تذكر اسم أي موقع أو جريدة أو قناة كمصدر للخبر، وممنوع كلمة «يلا كورة».
- لو المصدر بيقول إن الخبر إشاعة أو مصدر غير رسمي، قول كده بوضوح. ممنوع «رسميًا» إلا لو المصدر قالها.
- اكتب كل الأرقام والسنين والنتائج بالأرقام (700، 2006، 4-0)، مش بالحروف.
- اللغة: عربي فصيح بسيط وقريب من المصري، فقرات قصيرة.
- القيمة المضافة: اشرح الخبر يعني إيه للفريق والجمهور، والخطوة الجاية، ولو فيه مباريات في الجدول اذكر مواعيدها والقنوات.
- الطول: الـ body لا يقل عن 750 كلمة، مقسم بعناوين h2 (من 4 لـ 6)، وفقرات <p>، وممكن <ul>. من غير صور ومن غير روابط.

رجّع JSON بالشكل ده بالظبط:
{{"title": "عنوان جذاب وصادق أقل من 65 حرف بدون اسم أي موقع", "kicker": "جملة قصيرة جدًا للصورة (3-5 كلمات) زي: كأس مصر · مواجهة تاريخية", "slug": "3 to 6 english words with hyphens", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "سؤال", "a": "إجابة من المعلومات المتاحة بس"}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
عنوان الخبر الأصلي: {title}

النص المصدر:
{src}

جدول المباريات (بتوقيت القاهرة):
{tbl}
"""


def check(art, src, tbl_text, existing):
    errs = []
    full = " ".join([art.get("title", ""), art.get("kicker", ""), art.get("body", ""), art.get("desc", "")] +
                    [f["q"] + " " + f["a"] for f in art.get("faq", [])])
    allowed = numbers(src) | numbers(tbl_text) | {str(datetime.date.today().year), str(datetime.date.today().year + 1)}
    bad = sorted(n for n in numbers(BeautifulSoup(full, "html.parser").get_text(" ")) if n not in allowed)
    if bad:
        errs.append("الأرقام دي مش موجودة في المصدر، احذفها: " + "، ".join(bad[:15]))
    spelled = re.findall(r"(?:مائة|مئة|مائتين|مئتين|ثلاثمائة|اربعمائة|أربعمائة|خمسمائة|ستمائة|سبعمائة|ثمانمائة|تسعمائة|ألفين|الفين|آلاف)", full)
    if len(spelled) > 2:
        errs.append("اكتب الأرقام بالأرقام مش بالحروف (" + "، ".join(sorted(set(spelled))[:6]) + ")")
    low = full.lower()
    if any(b.lower() in low for b in BANNED):
        errs.append("فيه اسم موقع المصدر، احذفه")
    if "رسميا" in norm(full) and "رسميا" not in norm(src):
        errs.append("كلمة رسميًا مش موجودة في المصدر، احذفها")
    words = len(BeautifulSoup(art.get("body", ""), "html.parser").get_text(" ").split())
    if words < 700:
        errs.append(f"الـ body {words} كلمة بس، لازم 750 على الأقل")
    t = art.get("title", "")
    if not t or len(t) > 70:
        errs.append("العنوان لازم أقل من 70 حرف")
    for e in existing:
        if difflib.SequenceMatcher(None, norm(t), norm(e)).ratio() >= 0.75:
            errs.append(f"العنوان شبه عنوان منشور قبل كده: {e}")
            break
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+){2,6}", art.get("slug", "")):
        errs.append("الـ slug لازم 3-7 كلمات إنجليزي صغير بشرطات")
    if not (120 <= len(art.get("desc", "")) <= 170):
        errs.append("الوصف لازم 140-160 حرف")
    return errs


CDN = "https://cdn.jsdelivr.net/gh/mohsenxpca/matches-data@main/"
try:
    TEAM_LOGOS = json.load(open("logos.json", encoding="utf-8"))["logos"]
except Exception:
    TEAM_LOGOS = {}


def story_teams(title, src):
    """Up to 2 teams the story is about: names in the title first (in order), then the most mentioned in the text."""
    nt, ns = norm(title), norm(src)
    keys = [k for k in TEAM_LOGOS if len(norm(k)) > 2]
    in_title = sorted((nt.find(norm(k)), k) for k in keys if norm(k) in nt)
    picked = []
    for _, k in in_title:
        if not any(norm(k) in norm(p) or norm(p) in norm(k) for p in picked):
            picked.append(k)
    if len(picked) < 2:
        counts = sorted(((ns.count(norm(k)), k) for k in keys if norm(k) in ns and k not in picked), reverse=True)
        for n, k in counts:
            if len(picked) >= 2 or (picked and n < 3):
                break
            if not any(norm(k) in norm(p) or norm(p) in norm(k) for p in picked):
                picked.append(k)
    return picked[:2]


def team_images(art, rows, teams):
    """Cover with the story's teams + (if any) a card for their next match. Files go to img/ and are served by jsDelivr."""
    import cover
    os.makedirs("img", exist_ok=True)
    out = []
    kicker = (art.get("kicker") or "أخبار الكورة").strip()[:40]
    p = f"img/{art['slug']}.jpg"
    if teams and cover.make_cover([(t, TEAM_LOGOS.get(t)) for t in teams], kicker, p):
        out.append((CDN + p, "شعار " + " و".join(teams)))
    nxt = next((m for m in rows if any(norm(t) in (norm(m["h"]), norm(m["a"])) for t in teams)), None) if teams else None
    if nxt:
        p2 = f"img/{art['slug']}-next.jpg"
        k2 = f"الماتش الجاي · {nxt['d'][8:]}/{nxt['d'][5:7]} الساعة {nxt['t']}"
        if cover.make_cover([(nxt["h"], TEAM_LOGOS.get(nxt["h"])), (nxt["a"], TEAM_LOGOS.get(nxt["a"]))], k2, p2):
            out.append((CDN + p2, f"مباراة {nxt['h']} و{nxt['a']} يوم {nxt['d']}"))
    return out


def build_html(art, rows, img, related, team_imgs=()):
    e = html.escape
    if team_imgs:
        first = f'<img src="{team_imgs[0][0]}" alt="{e(team_imgs[0][1])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px">'
    else:
        first = f'<img src="{PEX.format(i=img[0])}" alt="{e(img[1])}" width="1000" height="563" style="width:100%;height:auto;border-radius:12px">'
    tbl = ""
    if rows:
        trs = "".join(f"<tr><td>{e(m['d'][5:].replace('-', '/'))}</td><td>{e(m['t'])}</td><td>{e(m['h'])} × {e(m['a'])}</td>"
                      f"<td>{e(m.get('c') or '-')}</td></tr>" for m in rows)
        tbl = ('<h2>مواعيد المباريات الجاية</h2><button type="button" class="fbn-btn" '
               'onclick="var t=this.nextElementSibling;t.hidden=!t.hidden;this.textContent=t.hidden?\'اعرض المواعيد والقنوات\':\'اخفي المواعيد\';">اخفي المواعيد</button>'
               '<div><table class="fbn-t"><thead><tr><th>اليوم</th><th>الساعة</th><th>المباراة</th><th>القناة</th></tr></thead>'
               f'<tbody>{trs}</tbody></table><p>المواعيد بتوقيت القاهرة وممكن تتغير، وتابع التحديث لحظة بلحظة في '
               f'<a href="{MATCHES_PAGE}">صفحة مباريات اليوم والقنوات الناقلة</a>.</p></div>')
    else:
        tbl = (f'<p>وعشان ما يفوتكش ماتش، تابع <a href="{MATCHES_PAGE}">مواعيد مباريات اليوم والقنوات الناقلة</a> '
               '<button type="button" class="fbn-btn" onclick="location.href=this.previousElementSibling.href">افتح جدول المباريات</button></p>')
    links = f'<p>ولو بتدور على مكان تتابع فيه الماتشات، اقرأ <a href="{EGYNOW}">بديل ايجي ناو لمتابعة المباريات</a>'
    if related:
        links += f'، وشوف كمان <a href="{related["u"]}">{e(related["t"])}</a>'
    links += ".</p>"
    faq = "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{e(f['q'])}</summary><p>{e(f['a'])}</p></details>"
                                          for f in art.get("faq", [])[:4])
    style = ("<style>.fbn-t{width:100%;border-collapse:collapse;font-size:14px}.fbn-t th,.fbn-t td{border:1px solid #f3d9a8;padding:6px;text-align:center}"
             ".fbn-t th{background:#fff7ed}.fbn-btn{border:0;border-radius:999px;padding:7px 16px;margin:6px 0;font:inherit;font-weight:700;color:#fff;"
             "background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer}</style>")
    body = art["body"]
    # second image after the second h2, lazy: the next-match card, or a generic photo when the story has no team
    if len(team_imgs) > 1:
        second = f'<img src="{team_imgs[1][0]}" alt="{e(team_imgs[1][1])}" width="1200" height="675" loading="lazy" style="width:100%;height:auto;border-radius:12px">'
    elif team_imgs:
        second = ""
    else:
        img2 = random.choice([x for x in IMAGES if x != img])
        second = f'<img src="{PEX.format(i=img2[0])}" alt="{e(img2[1])}" width="1000" height="563" loading="lazy" style="width:100%;height:auto;border-radius:12px">'
    parts = body.split("<h2>")
    if second and len(parts) > 2:
        body = "<h2>".join(parts[:2]) + second + "<h2>" + "<h2>".join(parts[2:])
    return first + style + body + tbl + links + faq


def schedule_times(n, taken):
    """n random Cairo times today between now+20min and 23:00, at least 2.5h apart and away from taken times."""
    now = datetime.datetime.now(CAIRO)
    start = max(now + datetime.timedelta(minutes=20), now.replace(hour=11, minute=0, second=0, microsecond=0))
    end = now.replace(hour=23, minute=0, second=0, microsecond=0)
    out = []
    for _ in range(400):
        if len(out) == n or start >= end:
            break
        t = start + datetime.timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
        t = t.replace(second=0, microsecond=0)
        if all(abs((t - x).total_seconds()) >= 9000 for x in out) and all(abs((t - x).total_seconds()) >= 2700 for x in taken):
            out.append(t)
    return sorted(out)


def main():
    news = json.load(open("news.json", encoding="utf-8"))["news"]
    data = json.load(open("data.json", encoding="utf-8"))
    try:
        state = json.load(open("football_posted.json", encoding="utf-8"))
    except Exception:
        state = {"done": []}
    done_ids = {d["id"] for d in state["done"]}
    tok = None if DRY else token()
    posts = site_posts(tok)
    existing = [p["t"] for p in posts]
    today = datetime.datetime.now(CAIRO).date().isoformat()

    taken = []
    if not DRY:
        sched = api("GET", f"/blogs/{BLOG}/posts", tok, {"status": ["live", "scheduled"], "fetchBodies": "false",
                                                        "startDate": today + "T00:00:00+02:00", "maxResults": 50, "view": "ADMIN"})
        items = sched.get("items", [])
        for it in items:
            try:
                taken.append(datetime.datetime.fromisoformat(it["published"]).astimezone(CAIRO))
            except Exception:
                pass
        room = DAY_CAP - len([t for t in taken if t.date().isoformat() == today])
        if room <= 0:
            print(f"Egyptaway already has {len(taken)} posts today (cap {DAY_CAP}), nothing to do")
            return
        n_target = min(COUNT, room)
    else:
        n_target = COUNT

    cands = [x for x in news if x["id"] not in done_ids and x["s"] in PRIORITY]
    cands.sort(key=lambda x: (PRIORITY.index(x["s"]), -x["id"]))
    times = [] if DRY else schedule_times(n_target, taken)
    if not DRY and len(times) < n_target:
        n_target = len(times)
    made = 0
    used_imgs = []
    for c in cands:
        if made >= n_target:
            break
        if any(difflib.SequenceMatcher(None, norm(c["t"]), norm(d.get("t", ""))).ratio() > 0.6 for d in state["done"][-60:]):
            continue
        try:
            src = source_text(c["u"])
        except Exception as e:
            print("source failed", c["id"], e)
            continue
        if len(src) < 400:
            continue
        rows = team_matches(src + " " + c["t"], data)
        tbl_text = "\n".join(f"{m['d']} {m['t']} {m['l']}: {m['h']} × {m['a']} | القناة: {m.get('c') or '-'} | النتيجة: {m.get('s') or '-'}" for m in rows) or "لا يوجد"
        extra, art, errs = "", None, ["no draft"]
        for attempt in range(2):
            art = gemini(PROMPT.format(extra=extra, title=c["t"], src=src[:6000], tbl=tbl_text))
            errs = check(art, src + " " + c["t"], tbl_text, existing)
            if not errs:
                break
            print("  retry:", errs)
            extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
        state["done"].append({"id": c["id"], "t": c["t"], "at": today, "ok": not errs})
        if errs:
            print("SKIPPED", c["t"], errs)
            continue
        img = random.choice([x for x in IMAGES if x not in used_imgs])
        used_imgs.append(img)
        rel = next((p for p in posts if "أخبار الكورة" in p["l"] or "الدوري المصري" in p["l"]), None)
        teams = story_teams(c["t"] + " " + art["title"], src)
        try:
            timgs = team_images(art, rows, teams)
        except Exception as ex:
            print("  cover failed:", ex)
            timgs = []
        print("  teams:", teams, "| images:", len(timgs))
        html_out = build_html(art, rows, img, rel, timgs)
        labels = ["أخبار الكورة"] + ([LABELS[c["s"]]] if c["s"] in LABELS else [])
        if DRY:
            os.makedirs("out", exist_ok=True)
            open(f"out/{art['slug']}.html", "w", encoding="utf-8").write(f"<h1>{html.escape(art['title'])}</h1>\n" + html_out)
            print("DRY", art["title"], "->", f"out/{art['slug']}.html", "| desc:", art["desc"])
        else:
            when = times[made]
            d = api("POST", f"/blogs/{BLOG}/posts", tok, {"isDraft": "true"},
                    {"kind": "blogger#post", "title": art["slug"].replace("-", " "), "content": html_out, "labels": labels})
            api("POST", f"/blogs/{BLOG}/posts/{d['id']}/publish", tok, {"publishDate": when.isoformat()})
            api("PATCH", f"/blogs/{BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
            fin = api("GET", f"/blogs/{BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
            state["done"][-1].update({"url": fin.get("url"), "when": when.isoformat(), "title": art["title"], "desc": art["desc"]})
            print("SCHEDULED", when.strftime("%H:%M"), fin.get("status"), fin.get("url"), "|", art["title"])
        existing.append(art["title"])
        made += 1
    state["done"] = state["done"][-300:]
    json.dump(state, open("football_posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"done: {made} post(s)")


if __name__ == "__main__":
    main()
