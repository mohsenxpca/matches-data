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
import datetime, difflib, html, io, json, os, random, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

BLOG = "8325646053257070334"
SITE = "https://www.egyptaway.com"
CAIRO = ZoneInfo("Africa/Cairo")
HEAD = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36",
        "Accept-Language": "ar,en;q=0.8"}
COUNT = int(os.environ.get("COUNT", "2"))
PREVIEWS = int(os.environ.get("PREVIEWS") if os.environ.get("PREVIEWS") is not None else 2)  # 'match time & channel' articles for tomorrow's big matches
FAST = os.environ.get("FAST") == "1"  # breaking-news run (every 2h): newest story first, published within the next ~1.5h
DRY = os.environ.get("DRY_RUN") == "1"
DAY_CAP = int(os.environ.get("DAY_CAP") or 200)  # same cap as blogger_api.py on Mohsen's PC; a manual run can raise it
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
BANNED = ["يلا كورة", "يلاكورة", "yallakora", "يلا كوره"]
# فلترة صارمة لمنع أي أخبار سياسية أو حروب أو شؤون فنية (قرار محسن 2026-10-31)
BANNED_TOPICS_REGEX = (
    r"رئيس الجمهورية|السيسي|الرئيس|الحكومة|مجلس الوزراء|رئيس الوزراء|مدبولي|وزير الخارجية|"
    r"البرلمان|مجلس النواب|مجلس الشيوخ|أحزاب|انتخابات|سياسي|سياسة|دبلوماسي|سفير|سفارة|مباحثات|"
    r"مستشار|لقاء|استقبل|استقبال|مؤتمر صحفي|بيان رسمي|زيارة رسمية|قمة|اتفاقية دولية|معاهدة|شأن سياسي|"
    r"حرب|حروب|معركة|معارك|عسكري|جيش|قوات|صواريخ|صاروخ|طائرات حربية|غارة|غارات|قصف|انفجار|استهداف|"
    r"هجوم|مسيرة|مسيّرة|طائرة مسيرة|مسيرات|مقذوف|شهداء|قتلى|جرحى|إيران|طهران|إسرائيل|تل أبيب|"
    r"غزة|لبنان|حزب الله|الحوثي|اليمن|سوريا|روسيا|أوكرانيا|الشرق الأوسط|نووي|أسلحة|دبابات|غارات جوية|"
    r"فنان|فنانة|ممثل|ممثلة|نجوم الفن|مطرب|مطربة|مغني|مغنية|غناء|أغنية|كليب|فيديو كليب|رقص|راقصة|"
    r"مهرجان الجونة|مهرجان القاهرة|مسلسل|مسلسلات|فيلم|أفلام|سينما|دراما|تيك توك|مشاهير|زواج الفنان|طلاق الفنان|فستان|"
    r"قتل|مقتل|جريم|اغتصاب|تحرش|انتحار|ذبح|طعن|مخدرات|إرهاب|ارهاب|فضيحة|فيديو إباحي|اباحي|شذوذ|فضايح"
)

PRIORITY = ["egyptian-league", "egypt-cup", "african-champions-league", "african-confederation-cup", "can-qualifiers",
            "world-cup-qualifiers", "egypt-national-team", "saudi-league", "epl", "la-liga", "uefa-champions-league",
            "serie-a", "bundesliga", "ligue-1"]
LABELS = {"egyptian-league": "الدوري المصري", "egypt-cup": "الدوري المصري"}
MATCHES_PAGE = SITE + "/p/matches-today.html"
EGYNOW = SITE + "/2024/03/egynow.html"
PEX = "https://images.pexels.com/photos/{i}/pexels-photo-{i}.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop"
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
        if r.status_code in (429, 500, 502, 503) or "RESOURCE_EXHAUSTED" in r.text or "rateLimitExceeded" in r.text:
            print(f"⚠️ [Google OAuth / Blogger Quota] Status {r.status_code}. Skipping run peacefully.")
            sys.exit(0)
        cid = secret("BLOGGER_CLIENT_ID")
        sys.exit(f"Google login failed ({r.status_code}): {r.text[:200]} | client_id looks "
                 f"{'OK' if cid.endswith('.apps.googleusercontent.com') else 'WRONG'}, "
                 f"client_secret starts {'GOCSPX-' if secret('BLOGGER_CLIENT_SECRET').startswith('GOCSPX-') else 'with something else'}, "
                 f"refresh_token starts {'1//' if secret('BLOGGER_REFRESH_TOKEN').startswith('1//') else 'with something else'}")
    return r.json()["access_token"]


_FRESH = {}  # access tokens last ~1 hour; long runs (slow Gemini) get a new one transparently


def api(method, path, tok, params=None, body=None):
    def call(t):
        for i in range(3):  # network hiccups / Blogger 5xx: retry instead of failing the whole run
            try:
                r = requests.request(method, "https://www.googleapis.com/blogger/v3" + path, params=params, json=body,
                                     headers={"Authorization": "Bearer " + t}, timeout=60)
                if r.status_code < 500 or i == 2 or method == "POST":  # a POST may have gone through: never repeat it
                    return r
            except requests.ConnectionError:  # nothing was sent, safe to retry any method
                if i == 2:
                    raise
            time.sleep(10 * (i + 1))
    r = call(_FRESH.get(tok, tok))
    if r.status_code == 401:
        _FRESH[tok] = token()
        r = call(_FRESH[tok])
    if r.status_code >= 400:
        if r.status_code == 429 or "rateLimitExceeded" in r.text or "RESOURCE_EXHAUSTED" in r.text or "dailyLimitExceeded" in r.text:
            print(f"⚠️ [Blogger API Quota] تم استنفاد الحد اليومي لنشر بلوجر (Google Blogger API 429 rateLimitExceeded).")
            print("   سيتم التخطي بسلام بدون فشل وسيعاود النشر تلقائياً فور تجدد كوتا جوجل اليومية.")
            sys.exit(0)
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



def decode_gn_link(link):
    """Decodes Google News RSS redirect link to original publisher URL."""
    try:
        aid = link.split("/articles/")[1].split("?")[0]
        h = requests.get(f"https://news.google.com/rss/articles/{aid}", headers=HEAD, timeout=20).text
        sg_m = re.search(r'data-n-a-sg="([^"]+)"', h)
        ts_m = re.search(r'data-n-a-ts="([^"]+)"', h)
        if not sg_m or not ts_m:
            return None
        sg, ts = sg_m.group(1), ts_m.group(1)
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts), sg]
        r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", timeout=20,
                          headers={**HEAD, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                          data="f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])))
        return json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]
    except Exception:
        return None


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
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": key},
                         params={"pageSize": 200}, timeout=30)
        if r.status_code != 200:
            print(f"⚠️ [Gemini Models] Status {r.status_code}: {r.text[:120]}. Using fallback models.")
            _MODELS = ["gemini-1.5-flash-8b", "gemini-1.5-flash"]
            return _MODELS
        names = [m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception as e:
        print(f"⚠️ [Gemini Models] Network error ({e}). Using fallback models.")
        _MODELS = ["gemini-1.5-flash-8b", "gemini-1.5-flash"]
        return _MODELS

    def ver(n):
        return tuple(int(x) for x in re.findall(r"\d+", n.split("-flash")[0]))
    flash = sorted((n for n in names if re.fullmatch(r"gemini-[\d.]+-flash", n)), key=ver, reverse=True)
    lite = sorted((n for n in names if re.fullmatch(r"gemini-[\d.]+-flash-lite", n)), key=ver, reverse=True)
    # Mohsen 2026-10-28: paid key on a ~$3/month budget -> Flash-Lite only (cheap; the lengthen pass makes up for
    # shorter drafts). Set GEMINI_TIER=flash in a workflow to put the bigger Flash models back first.
    if os.environ.get("GEMINI_TIER") == "flash":
        _MODELS = flash[:1] + lite[:1] + flash[1:2] + lite[1:2]
    else:
        _MODELS = lite[:2]
    _MODELS = _MODELS or [n for n in names if "flash" in n][:3] or names[:1]
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
                    print(f"  {model} error {r.status_code}: {r.text[:200]}")
                    continue
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
            out = json.loads(re.sub(r"^```(json)?|```$", "", txt))
            if isinstance(out, list):
                out = out[0] if out and isinstance(out[0], dict) else {}
            out["faq"] = [{"q": str(x.get("q") or x.get("question") or ""), "a": str(x.get("a") or x.get("answer") or "")}
                          for x in (out.get("faq") or []) if isinstance(x, dict) and (x.get("q") or x.get("question")) and (x.get("a") or x.get("answer"))]
            for k in ("title", "slug", "desc", "body", "kicker", "headline"):
                out[k] = str(out.get(k) or "")
            return out
        except ValueError:
            print("  Gemini returned broken JSON, retrying:", txt[:120].replace("\n", " "))
            continue
    # every model is down or out of quota: don't crash the job (and email Mohsen); callers see an empty draft that
    # fails the checks, and their loops stop on _DOWN so the next scheduled run simply tries again
    global _DOWN
    _DOWN = True
    print("Gemini unavailable right now - skipping, the next run will try again")
    return {"title": "", "slug": "", "desc": "", "body": "", "kicker": "", "headline": "", "faq": []}


_DOWN = False


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


PREVIEW_PROMPT = """أنت محرر رياضي في موقع ايجبتاوى المصري. اكتب مقال «موعد المباراة والقناة الناقلة» قبل الماتش ده بيوم.

قواعد صارمة:
- استخدم «بيانات الماتش» تحت بس. ممنوع تخترع تشكيل أو إصابات أو تصريحات أو أرقام أو نتايج مش مكتوبة تحت.
- اكتب كل الأرقام بالأرقام (17:00، 21 نقطة، 2-1)، مش بالحروف.
- ممنوع تذكر اسم أي موقع.
- العنوان لازم يبدأ بـ «موعد مباراة» وفيه اسم الفريقين والقناة.
- المحتوى: الموعد بتوقيت القاهرة، القناة، البطولة والجولة، موقف الفريقين في الجدول لو موجود، آخر نتايج كل فريق المكتوبة تحت، وأهمية الماتش، ونصيحة للمتابعة القانونية على القناة الرسمية.
- الطول: الـ body من 450 لـ 700 كلمة (اكتب كتير: كل قسم 3 فقرات)، بعناوين h2 (من 3 لـ 5) وفقرات <p>. من غير صور ومن غير روابط.

رجّع JSON بالشكل ده بالظبط:
{{"title": "موعد مباراة .. أقل من 65 حرف", "kicker": "3-5 كلمات زي: الدوري المصري · الجولة 8", "slug": "3 to 6 english words with hyphens", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "إمتى ماتش ..؟", "a": ".."}}, {{"q": "القناة الناقلة ..؟", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
بيانات الماتش:
{facts}
"""

BIG = ["الأهلي", "الزمالك", "بيراميدز", "المصري", "مصر", "ليفربول", "ريال مدريد", "برشلونة", "مانشستر سيتي",
       "مانشستر يونايتد", "أرسنال", "الهلال", "النصر", "الاتحاد", "بايرن ميونخ", "باريس سان جيرمان"]


def preview_candidates(data, done_keys):
    """Tomorrow's matches (Cairo) with a big team, Egyptian clubs first."""
    tmr = (datetime.datetime.now(CAIRO) + datetime.timedelta(days=1)).date().isoformat()
    out = []
    for m in data.get("matches", []):
        if m["d"] != tmr:
            continue
        key = f"{m['d']}|{m['h']}|{m['a']}|p"
        if key in done_keys:
            continue
        rank = min([BIG.index(t) for t in (m["h"], m["a"]) if t in BIG] or [99])
        if rank < 99:
            out.append((rank, key, m))
    return [(k, m) for _, k, m in sorted(out)]


def match_facts(m, data):
    def last(team, n=3):
        rows = [x for x in data.get("matches", []) if team in (x["h"], x["a"]) and x.get("s") and x["d"] < m["d"]]
        rows.sort(key=lambda x: x["d"], reverse=True)
        return "، ".join(f"{x['h']} {x['s']} {x['a']} ({x['l']}، {x['d']})" for x in rows[:n]) or "مش متاح"
    lines = [f"البطولة: {m['l']}", f"الجولة: {m.get('r') or '-'}", f"اليوم: {m['d']}", f"الساعة بتوقيت القاهرة: {m['t']}",
             f"صاحب الأرض: {m['h']}", f"الضيف: {m['a']}", f"القناة الناقلة: {m.get('c') or 'لم تُعلن'}",
             f"آخر نتايج {m['h']}: {last(m['h'])}", f"آخر نتايج {m['a']}: {last(m['a'])}"]
    try:
        st = json.load(open("standings.json", encoding="utf-8"))["rows"]
        if m["l"] == "الدوري المصري":
            for i, r in enumerate(st, 1):
                if r["team"] in (m["h"], m["a"]):
                    lines.append(f"ترتيب {r['team']} في الدوري: المركز {i} برصيد {r['pts']} نقطة من {r['p']} ماتش (له {r['gf']} وعليه {r['ga']})")
    except Exception:
        pass
    return "\n".join(lines)


LENGTHEN_PROMPT = """المقال ده قصير ({words} كلمة) ومحتاج يبقى حوالي {target} كلمة (مش أكتر من كده بكتير). طوّله بنفس الأسلوب والعناوين:
- زوّد معلومات مفيدة جديدة من «المصادر» تحت بس (تفاصيل، مواعيد، خطوات، معنى الخبر للقارئ)، وممكن قسم h2 واحد أو اتنين جداد.
- ممنوع الحشو والتكرار والجمل العامة اللي ملهاش لازمة: كل فقرة لازم فيها معلومة. خليه سهل القراية وفقرات قصيرة.
- ممنوع تخترع أي رقم أو تاريخ أو اسم أو تصريح مش موجود في المصادر. اكتب الأرقام بالأرقام. ممنوع اسم أي موقع.
- رجّع المقال كامل بعد التطويل (مش الإضافة بس).

رجّع JSON بالشكل ده بالظبط: {{"body": "<h2>..</h2><p>..</p>..."}}

المقال الحالي:
{body}

المصادر:
{src}
"""


def lengthen(art, src, min_words):
    """Second pass when the writer (often the lite model when Flash is busy) came back too short: ask it to expand the
    same article from the same sources. Updates art['body'] in place; the normal checks still run on the result."""
    words = len(BeautifulSoup(art.get("body", ""), "html.parser").get_text(" ").split())
    if not art.get("body") or words >= min_words + 50 or words < 80:
        return
    try:
        out = gemini(LENGTHEN_PROMPT.format(words=words, target=min_words + 70, body=art["body"], src=src[:9000]))
    except Exception as e:
        print("  lengthen failed:", e)
        return
    new = out.get("body") or ""
    n2 = len(BeautifulSoup(new, "html.parser").get_text(" ").split())
    print(f"  lengthened {words} -> {n2} words")
    if n2 > words:
        art["body"] = new


# Deduplication Shield (درع منع التكرار الدلالي والمحتوى)
_RAW_BOILERPLATE = [
    "موعد", "مباراة", "مباريات", "القنوات", "الناقلة", "القناة", "الدوري", "المصري", "الإنجليزي",
    "الإسباني", "السعودي", "الإيطالي", "الفرنسي", "الألماني", "أبطال", "أوروبا", "إفريقيا", "افريقيا",
    "كأس", "بطولة", "تشكيل", "تشكيلة", "التشكيل", "المتوقع", "الرسمي", "اليوم", "الليلة", "الان",
    "الآن", "ضد", "أمام", "امام", "مع", "في", "من", "على", "إلى", "عن", "هذا", "هذه", "تم",
    "كان", "أن", "إن", "هل", "بعد", "قبل", "عند", "خلال", "بين", "حول", "كل", "ما", "لا",
    "أو", "ثم", "له", "لها", "به", "بها", "منه", "منها", "فيه", "فيها", "عليه", "عليها",
    "الجديد", "الجديدة", "رسميا", "تفاصيل", "أول", "أخر", "آخر", "بسبب", "تطورات", "موقف",
    "رسالة", "قرار", "بيان", "عاجل", "يكشف", "تحذير", "مفاجأة", "شاهد", "فيديو", "تقرير",
    "طريق", "طريقة", "كيف", "أبرز", "أهم", "تعرف", "لـ", "خطوة", "بشأن", "عقب", "أثناء",
    "تعلن", "يعلن", "يعلنها", "توضيح", "توضح", "يلتقي", "يواجه", "مواجهة", "يستعد", "استعدادا",
    "ناقلة", "قناة", "قنوات", "دوري", "كاس", "بطوله", "تشكيله", "رسمي", "متوقع"
]

_DEDUP_BOILERPLATE = set()
for _b in _RAW_BOILERPLATE:
    _nb = norm(_b)
    _DEDUP_BOILERPLATE.add(_nb)
    if _nb.startswith("ال") and len(_nb) > 4:
        _DEDUP_BOILERPLATE.add(_nb[2:])

def _dedup_stem(w):
    while len(w) > 4 and (w.startswith("و") or w.startswith("ف") or w.startswith("ب") or w.startswith("ل") or w.startswith("ك")):
        w = w[1:]
    if w.startswith("ال") and len(w) > 4:
        w = w[2:]
    return w

def extract_core_entities(text):
    text_norm = norm(text)
    words = re.findall(r'\b[\u0621-\u064A\w]{3,}\b', text_norm)
    entities = set()
    for w in words:
        sw = _dedup_stem(w)
        if sw not in _DEDUP_BOILERPLATE and len(sw) >= 3:
            entities.add(sw)
    return entities

def strip_boilerplate(text):
    words = [_dedup_stem(w) for w in norm(text).split() if _dedup_stem(w) not in _DEDUP_BOILERPLATE]
    return " ".join(words)

def is_semantic_duplicate(new_title, existing_titles, new_slug=None, existing_slugs=None):
    """الدرع الدلالي: يكشف المقالات المكررة حتى لو قام الذكاء الاصطناعي بإعادة صياغة العنوان تماماً."""
    ent_new = extract_core_entities(new_title)
    stripped_new = strip_boilerplate(new_title)

    # 1. مطابقة الـ slug لمنع التكرار المباشر أو اللاحقات الرقمية في بلوجر
    if new_slug and existing_slugs:
        clean_new = re.sub(r'[_\-\d]+', '', new_slug.lower())
        for es in existing_slugs:
            clean_es = re.sub(r'[_\-\d]+', '', es.lower())
            if clean_new and clean_new == clean_es:
                return True, f"نفس الرابط الثابت (Slug) موجود مسبقاً: {new_slug} ~ {es}"

    for ext in existing_titles:
        ent_ext = extract_core_entities(ext)
        common = ent_new.intersection(ent_ext)
        stripped_ext = strip_boilerplate(ext)

        s_ratio = difflib.SequenceMatcher(None, stripped_new, stripped_ext).ratio() if stripped_new and stripped_ext else 0
        raw_ratio = difflib.SequenceMatcher(None, norm(new_title), norm(ext)).ratio()

        # أ. تطابق 3 كيانات جوهرية أو أكثر (اسم الناديين، الشخصيات، المكان والحدث)
        if len(common) >= 3:
            return True, f"تطابق في {len(common)} كيانات جوهرية ({common}) مع: {ext}"

        # ب. تطابق كيانين جوهريين مع تقارب في الصياغة العامة أو النص المجرد
        if len(common) >= 2:
            jaccard = len(common) / len(ent_new.union(ent_ext)) if ent_new.union(ent_ext) else 0
            if s_ratio >= 0.40 or jaccard >= 0.20 or raw_ratio >= 0.45:
                return True, f"تطابق في الكيانات ({common}) مع تشابه نصي مع: {ext}"

        # ج. نسبة تشابه عالية في النص الأساسي
        if s_ratio >= 0.65 or raw_ratio >= 0.60:
            return True, f"نسبة تطابق مرتفعة مع مقال منشور: {ext}"

    return False, ""


def check(art, src, tbl_text, existing, min_words=700):
    lengthen(art, src + "\n" + (tbl_text or ""), min_words)
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
    if words < min_words:
        errs.append(f"الـ body {words} كلمة بس، لازم {min_words + 50} على الأقل")
    t = art.get("title", "")
    if not t or len(t) > 70:
        errs.append("العنوان لازم أقل من 70 حرف")

    # فحص التكرار عبر درع الحماية الدلالي
    is_dup, dup_reason = is_semantic_duplicate(t, existing, new_slug=art.get("slug"))
    if is_dup:
        errs.append(f"الموضوع منشور مسبقاً ({dup_reason})")

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+){2,6}", art.get("slug", "")):
        errs.append("الـ slug لازم 3-7 كلمات إنجليزي صغير بشرطات")
    if not (110 <= len(art.get("desc", "")) <= 175):
        errs.append("الوصف لازم 140-160 حرف")
    return errs


CDN = "https://cdn.jsdelivr.net/gh/mohsenxpca/matches-data@main/"
try:
    _logos_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos.json")
    TEAM_LOGOS = json.load(open(_logos_path, encoding="utf-8"))["logos"]
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


def make_player_action_shot(img_url, out_path, team_logo_url=None):
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        return False
    """Downloads player shot, flips horizontally (mirror) + slight angle tilt & crop, overlays club badge."""
    try:
        try_urls = [img_url.replace('/thumb/', '/original/'), img_url.replace('/thumb/', '/large/'), img_url]
        im = None
        for u in try_urls:
            try:
                r = requests.get(u, timeout=12, headers=HEAD)
                if r.status_code == 200 and len(r.content) > 1000:
                    im = Image.open(io.BytesIO(r.content)).convert('RGBA')
                    break
            except Exception:
                continue
        if not im:
            return False

        # 1. Flip horizontally (عكس كالمرآة)
        im = im.transpose(Image.FLIP_LEFT_RIGHT)

        # 2. Slight angle rotation (تغيير زاوية) + crop to avoid black edges
        angle = random.choice([-1.2, 1.2])
        rot = im.rotate(angle, resample=Image.BICUBIC)
        w, h = rot.size
        mx, my = int(w * 0.025), int(h * 0.025)
        cropped = rot.crop((mx, my, w - mx, h - my)).resize((1000, 563), Image.LANCZOS)

        # 3. Optional: Club logo badge in top corner
        if team_logo_url:
            try:
                lr = requests.get(team_logo_url, timeout=10, headers=HEAD)
                if lr.status_code == 200:
                    lg = Image.open(io.BytesIO(lr.content)).convert('RGBA')
                    lg.thumbnail((110, 110), Image.LANCZOS)
                    badge = Image.new('RGBA', (130, 130), (0, 0, 0, 0))
                    bd = ImageDraw.Draw(badge)
                    bd.ellipse((0, 0, 129, 129), fill=(255, 255, 255, 235), outline=(245, 158, 11, 255), width=3)
                    bx = (130 - lg.width) // 2
                    by = (130 - lg.height) // 2
                    badge.alpha_composite(lg, (bx, by))
                    cropped.alpha_composite(badge, (850, 20))
            except Exception:
                pass

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        cropped.convert('RGB').save(out_path, 'JPEG', quality=88, optimize=True)
        return True
    except Exception as ex:
        print('  make_player_action_shot failed:', ex)
        return False


def make_club_logo_cover(teams, bg_img_url, out_path):
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        return False
    """Draws clean club logo(s) on a real stadium background without redundant text overlays."""
    try:
        r = requests.get(bg_img_url, timeout=15, headers=HEAD)
        if r.status_code != 200:
            return False
        bg = Image.open(io.BytesIO(r.content)).convert('RGBA').resize((1000, 563), Image.LANCZOS)
        blur = bg.filter(ImageFilter.GaussianBlur(3))
        dark = Image.new('RGBA', (1000, 563), (20, 28, 45, 130))
        bg = Image.alpha_composite(blur, dark)

        def fetch_logo(u, size=150):
            lr = requests.get(u, timeout=10, headers=HEAD)
            im = Image.open(io.BytesIO(lr.content)).convert('RGBA')
            im.thumbnail((size, size), Image.LANCZOS)
            return im

        d = ImageDraw.Draw(bg)
        cy = 281
        valid_teams = [t for t in teams if t and t[1]]
        if len(valid_teams) >= 2:
            xs = [710, 290]  # RTL: right is first team
            for (name, u), x in zip(valid_teams[:2], xs):
                r_disc = 95
                d.ellipse((x - r_disc, cy - r_disc, x + r_disc, cy + r_disc), fill=(255, 255, 255, 240), outline=(245, 158, 11), width=4)
                lg = fetch_logo(u, 140)
                bg.alpha_composite(lg, (x - lg.width // 2, cy - lg.height // 2))
            d.ellipse((500 - 36, cy - 36, 500 + 36, cy + 36), fill=(245, 158, 11), outline=(255, 255, 255), width=3)
            try:
                import cover
                f = cover.font(36, "Black")
                d.text((500, cy), "VS", font=f, fill=(31, 42, 68), anchor="mm")
            except Exception:
                d.text((500, cy), "VS", fill=(31, 42, 68), anchor="mm")
        elif len(valid_teams) == 1:
            name, u = valid_teams[0]
            r_disc = 115
            d.ellipse((500 - r_disc, cy - r_disc, 500 + r_disc, cy + r_disc), fill=(255, 255, 255, 245), outline=(245, 158, 11), width=4)
            lg = fetch_logo(u, 170)
            bg.alpha_composite(lg, (500 - lg.width // 2, cy - lg.height // 2))
        else:
            return False

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        bg.convert('RGB').save(out_path, 'JPEG', quality=88, optimize=True)
        return True
    except Exception as ex:
        print('  make_club_logo_cover failed:', ex)
        return False


def team_images(art, rows, teams):
    return []


def live_box(m):
    """Score box for a match article: kick-off countdown, then the live score (data.json is refreshed every 5 minutes
    by live.yml), then the final score. Score only, no stream links."""
    key = json.dumps({"d": m["d"], "t": m["t"], "h": m["h"], "a": m["a"]}, ensure_ascii=False)
    return ('<div class="fbn-live" style="border:2px solid #f59e0b;border-radius:14px;padding:12px;margin:12px 0;text-align:center;background:#fff7ed">'
            f'<b>{html.escape(m["h"])} × {html.escape(m["a"])}</b><div class="fbn-live-s" style="font-size:20px;font-weight:800;color:#c2410c;margin-top:6px">'
            f'الماتش {html.escape(m["d"][5:].replace("-", "/"))} الساعة {html.escape(m["t"])} بتوقيت القاهرة</div>'
            '<small style="color:#6b7280">النتيجة بتتحدث هنا لوحدها وقت الماتش</small></div>'
            "<script>(function(){var M=" + key + ",b=document.currentScript.previousElementSibling.querySelector('.fbn-live-s');"
            "function cairo(){return new Date(new Date().toLocaleString('en-US',{timeZone:'Africa/Cairo'}))}"
            "function show(x){var k=new Date(M.d+'T'+M.t+':00'),n=cairo(),m=(n-k)/60000,s=x&&x.s?x.s.split('-'):null;"
            "if(m<0){var h=Math.floor(-m/60),mm=Math.floor(-m%60);b.textContent='الماتش يبدأ بعد '+(h>=48?Math.floor(h/24)+' يوم':(h?h+' ساعة و':'')+mm+' دقيقة')+(x&&x.c&&x.c.indexOf('لم ت')!=0?' · على '+x.c:'')}"
            "else if(m<140){b.textContent=s?'النتيجة دلوقتي: '+M.h+' '+s[0]+' - '+s[1]+' '+M.a:'الماتش شغال دلوقتي'}"
            "else if(s){b.textContent='النتيجة النهائية: '+M.h+' '+s[0]+' - '+s[1]+' '+M.a}}"
            "function load(){fetch('https://raw.githubusercontent.com/mohsenxpca/matches-data/main/data.json').then(function(r){return r.json()})"
            ".then(function(d){show((d.matches||[]).filter(function(x){return x.d==M.d&&x.h==M.h&&x.a==M.a})[0])}).catch(function(){show(null)})}"
            "load();setInterval(load,120000);})();</script>")


def build_html(art, rows, img, related, team_imgs=(), real_img_url=None, live=None):
    e = html.escape
    if real_img_url:
        first = f'<img src="{real_img_url}" alt="{e(art["title"])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px">'
    elif team_imgs:
        first = f'<img src="{team_imgs[0][0]}" alt="{e(team_imgs[0][1])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px">'
    else:
        first = f'<img src="{PEX.format(i=img[0])}" alt="{e(img[1])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px">'
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
    links = f'<p>ولو بتدور على مكان تتابع فيه الماتشات، اقرأ <a href="{EGYNOW}">ايجي ناو بث مباشر مباريات اليوم</a>'
    if related:
        links += f'، وشوف كمان <a href="{related["u"]}">{e(related["t"])}</a>'
    links += ".</p>"
    faq = "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{e(f['q'])}</summary><p>{e(f['a'])}</p></details>"
                                          for f in art.get("faq", [])[:4])
    style = ("<style>.fbn-t{width:100%;border-collapse:collapse;font-size:14px}.fbn-t th,.fbn-t td{border:1px solid #f3d9a8;padding:6px;text-align:center}"
             ".fbn-t th{background:#fff7ed}.fbn-btn{border:0;border-radius:999px;padding:7px 16px;margin:6px 0;font:inherit;font-weight:700;color:#fff;"
             "background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer}</style>")
    body = art["body"]
    if live:  # after the first paragraph, so the homepage snippet still comes from the article text
        i = body.find("</p>")
        body = body[:i + 4] + live_box(live) + body[i + 4:] if i >= 0 else live_box(live) + body
    # second image after the second h2, lazy: the next-match card, or a generic photo when the story has no team
    if len(team_imgs) > 1:
        second = f'<img src="{team_imgs[1][0]}" alt="{e(team_imgs[1][1])}" width="1200" height="675" loading="lazy" style="width:100%;height:auto;border-radius:12px">'
    elif team_imgs:
        second = ""
    else:
        img2 = random.choice([x for x in IMAGES if x != img])
        second = f'<img src="{PEX.format(i=img2[0])}" alt="{e(img2[1])}" width="1200" height="675" loading="lazy" style="width:100%;height:auto;border-radius:12px">'
    parts = body.split("<h2>")
    if second and len(parts) > 2:
        body = "<h2>".join(parts[:2]) + second + "<h2>" + "<h2>".join(parts[2:])
    return first + body + tbl + links + faq + style  # style last: Blogger builds the homepage snippet from the first text


def schedule_times(n, taken):
    """n random Cairo times. 24/7 continuous publishing enabled."""
    now = datetime.datetime.now(CAIRO)
    if FAST:
        start = now + datetime.timedelta(minutes=10)
        end = now + datetime.timedelta(minutes=100)
        gap_out, gap_taken = 2700, 1500
    else:
        start = now + datetime.timedelta(minutes=20)
        end = now + datetime.timedelta(hours=6)
        gap_out, gap_taken = 5400, 2700
    out = []
    for _ in range(400):
        if len(out) == n or start >= end:
            break
        t = start + datetime.timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
        t = t.replace(second=0, microsecond=0)
        if all(abs((t - x).total_seconds()) >= gap_out for x in out) and all(abs((t - x).total_seconds()) >= gap_taken for x in taken):
            out.append(t)
    # Fallback so other workflows' posts never block scheduling slots
    for _ in range(400):
        if len(out) >= n:
            break
        t = start + datetime.timedelta(seconds=random.randint(0, max(60, int((end - start).total_seconds()))))
        t = t.replace(second=0, microsecond=0)
        if all(abs((t - x).total_seconds()) >= 180 for x in out):
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
        room = COUNT + PREVIEWS
        n_target = COUNT

    previews = preview_candidates(data, set(state.get("previews", [])))[:max(0, min(PREVIEWS, room - n_target))]
    cands = [x for x in news if x["id"] not in done_ids and x["s"] in PRIORITY]
    cands.sort(key=lambda x: (-x["id"],) if FAST else (PRIORITY.index(x["s"]), -x["id"]))
    if FAST:  # breaking mode: only stories from the latest news batch
        cands = cands[:15]
    times = [] if DRY else schedule_times(n_target + len(previews), taken)
    if not DRY and len(times) < n_target + len(previews):
        n_target = max(0, len(times) - len(previews))
    random.shuffle(times)  # previews and news interleaved through the day
    p_times, times = times[:len(previews)], sorted(times[len(previews):])
    made_prev = make_previews(previews, data, existing, state, tok, p_times, today)
    made = 0
    used_imgs = []
    for c in cands:
        if _DOWN:
            break
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
        p = f"img/{art['slug']}.jpg"
        raw_i = (c.get("i") or "").strip()
        first_logo = TEAM_LOGOS.get(teams[0]) if teams else None
        lead_img_url = None

        # 1. First priority: Real player action shot (mirrored + angle tilt)
        if raw_i and raw_i.startswith("http"):
            if make_player_action_shot(raw_i, p, first_logo):
                lead_img_url = CDN + p

        # 2. Second priority: Club logo on stadium background
        if not lead_img_url and teams:
            team_tuples = [(t, TEAM_LOGOS.get(t)) for t in teams if TEAM_LOGOS.get(t)]
            if team_tuples and make_club_logo_cover(team_tuples, PEX.format(i=img[0]), p):
                lead_img_url = CDN + p

        # 3. Third priority: Clean Pexels stadium photo
        if not lead_img_url:
            lead_img_url = PEX.format(i=img[0])

        print("  teams:", teams, "| lead_img:", lead_img_url[:60])
        html_out = build_html(art, rows, img, rel, (), real_img_url=lead_img_url)
        labels = ["رياضة", "أخبار الكورة"] + ([LABELS[c["s"]]] if c["s"] in LABELS else [])
        if DRY:
            os.makedirs("out", exist_ok=True)
            open(f"out/{art['slug']}.html", "w", encoding="utf-8").write(f"<h1>{html.escape(art['title'])}</h1>\n" + html_out)
            print("DRY", art["title"], "->", f"out/{art['slug']}.html", "| desc:", art["desc"])
        elif FAST:
            fin = publish_live(tok, art, html_out, labels)
            state["done"][-1].update({"url": fin.get("url"), "when": datetime.datetime.now(CAIRO).isoformat(), "title": art["title"], "desc": art["desc"]})
            print("PUBLISHED LIVE", fin.get("status"), fin.get("url"), "|", art["title"])
        else:
            when = times[made]
            d = api("POST", f"/blogs/{BLOG}/posts", tok, {"isDraft": "true"},
                    {"kind": "blogger#post", "title": art["slug"].replace("-", " "), "content": with_desc(html_out, art), "labels": labels})
            api("POST", f"/blogs/{BLOG}/posts/{d['id']}/publish", tok, {"publishDate": when.isoformat()})
            api("PATCH", f"/blogs/{BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
            fin = api("GET", f"/blogs/{BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
            state["done"][-1].update({"url": fin.get("url"), "when": when.isoformat(), "title": art["title"], "desc": art["desc"]})
            print("SCHEDULED", when.strftime("%H:%M"), fin.get("status"), fin.get("url"), "|", art["title"])
        existing.append(art["title"])
        made += 1
    state["done"] = state["done"][-300:]
    state["previews"] = state.get("previews", [])[-300:]
    json.dump(state, open("football_posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"done: {made} news post(s), {made_prev} match preview(s)")


ENTITY_HUBS = [
    ("https://www.egyptaway.com/p/egyptian-league-table.html", ["جدول ترتيب الدوري المصري", "ترتيب الدوري المصري", "جدول الدوري المصري"]),
    ("https://www.egyptaway.com/p/matches-today.html", ["جدول مباريات اليوم", "مواعيد مباريات اليوم", "مباريات اليوم"]),
    ("https://www.egyptaway.com/p/gold-prices-egypt.html", ["أسعار الذهب اليوم في مصر", "سعر الذهب اليوم", "أسعار الذهب في مصر", "سعر جرام الذهب"]),
    ("https://www.egyptaway.com/p/currency-prices-egypt.html", ["أسعار العملات في مصر", "سعر الدولار اليوم", "أسعار الدولار في البنوك"]),
    ("https://www.egyptaway.com/p/prayer-times-egypt.html", ["مواقيت الصلاة في مصر", "مواقيت الصلاة اليوم", "مواعيد الصلاة"]),
    ("https://www.egyptaway.com/p/weather-egypt.html", ["حالة الطقس في مصر", "درجات الحرارة المتوقعة", "حالة الطقس اليوم"]),
    ("https://www.egyptaway.com/p/mobile-prices-egypt.html", ["أسعار الموبايلات في مصر", "أسعار الهواتف في مصر", "جدول أسعار الموبايلات"]),
    ("https://www.egyptaway.com/p/best-phone-for-budget.html", ["أفضل موبايل لميزانيتك", "أحسن موبايل في الفئة المتوسطة", "ترشيحات الموبايلات"]),
    ("https://www.egyptaway.com/p/download-games.html", ["تحميل ألعاب موبايل وكمبيوتر", "تنزيل ألعاب رسمية", "صفحة تحميل الألعاب"]),
    ("https://www.egyptaway.com/p/pubg-uc-freefire-diamonds-prices.html", ["أسعار شدات ببجي", "شحن شدات ببجي", "شحن جواهر فري فاير"]),
    ("https://www.egyptaway.com/p/make-money-online-egypt.html", ["طرق الربح من الإنترنت", "الربح من الموبايل", "الربح فودافون كاش"]),
    ("https://www.egyptaway.com/p/ai-tools-arabic-guide.html", ["أدوات الذكاء الاصطناعي", "مواقع الذكاء الاصطناعي المجانية"]),
    ("https://www.egyptaway.com/p/instapay-fees-calculator.html", ["حاسبة رسوم إنستاباي", "رسوم تحويل إنستاباي", "تطبيق إنستاباي"]),
    ("https://www.egyptaway.com/p/is-it-down-egypt.html", ["صفحة رصد الأعطال", "رصد الأعطال في مصر"]),
    ("https://www.egyptaway.com/p/bank-certificates-egypt.html", ["شهادات البنوك المصرية", "أعلى عائد شهادات ادخار"]),
    ("https://www.egyptaway.com/p/fuel-prices-egypt.html", ["أسعار البنزين والسولار", "أسعار البنزين اليوم"]),
    ("https://www.egyptaway.com/p/housing-egypt.html", ["شقق الإسكان الاجتماعي", "سكن لكل المصريين"]),
    ("https://www.egyptaway.com/p/trains-egypt.html", ["مواعيد القطارات", "قطارات السكة الحديد"]),
    ("https://www.egyptaway.com/p/salaries-egypt.html", ["مواعيد صرف المرتبات", "جدول صرف المرتبات"]),
    ("https://www.egyptaway.com/p/exams-egypt.html", ["جداول الامتحانات", "نتائج الامتحانات"]),
    ("https://www.egyptaway.com/p/official-holidays-egypt.html", ["الإجازات الرسمية في مصر", "مواعيد الإجازات الرسمية"]),
]


def _enrich_seo_html(html_out, art):
    """Automatically injects Jump-to-Section IDs/TOC, Second-0 Entity Hub links, and JSON-LD Schema."""
    if not html_out or not isinstance(art, dict):
        return html_out
    out = html_out

    # 1. Second-0 Contextual Entity Hub Auto-Linker (up to 2 hub links inside <p> tags)
    linked_count = 0
    for hub_url, phrases in ENTITY_HUBS:
        if linked_count >= 2:
            break
        if hub_url in out:
            continue
        for ph in phrases:
            # Match phrase inside a <p> tag that does not already contain an <a> tag around it
            pattern = re.compile(r"(<p[^>]*>(?:(?!</p>|<a).)*?)(" + re.escape(ph) + r")((?:(?!</p>).)*?</p>)", re.DOTALL)
            if pattern.search(out):
                out = pattern.sub(r'\1<a href="' + hub_url + r'">\2</a>\3', out, count=1)
                linked_count += 1
                break

    # 2. Jump-to-Section IDs & Quick TOC Box (if >= 3 <h2> tags and no jump box yet)
    if 'id="sec-1"' not in out and 'class="ea-jump"' not in out and 'class="rv-jump"' not in out:
        headings = []
        def _h2_repl(m):
            idx = len(headings) + 1
            inner = m.group(1)
            clean_txt = re.sub(r"<[^>]+>", "", inner).strip()
            headings.append((f"sec-{idx}", clean_txt))
            return f'<h2 id="sec-{idx}">{inner}</h2>'
        out = re.sub(r"<h2>(.*?)</h2>", _h2_repl, out, flags=re.DOTALL)
        if len(headings) >= 3:
            items = "".join(f'<li><a href="#{hid}" style="color:#1565c0;text-decoration:none;font-weight:600">{html.escape(htxt)}</a></li>' for hid, htxt in headings)
            jump_box = (
                '<details class="ea-jump" open style="background:#f8fafc;border:1px solid #dbe4ff;border-right:4px solid #0d47a1;border-radius:10px;padding:10px 14px;margin:14px 0">'
                '<summary style="font-weight:800;cursor:pointer;color:#0d47a1">📌 عناصر الموضوع السريعة (اضغط للانتقال المباشر)</summary>'
                f'<ol style="margin:8px 0 0;padding-right:20px;line-height:1.75">{items}</ol></details>'
            )
            first_h2 = out.find('<h2 id="sec-1">')
            if first_h2 != -1:
                out = out[:first_h2] + jump_box + out[first_h2:]

    # 3. Full JSON-LD Schema (@graph: NewsArticle + Author E-E-A-T + FAQPage)
    if "application/ld+json" not in out and art.get("title"):
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', out)
        clean_imgs = [i.replace("&amp;", "&") for i in imgs[:3] if i.startswith("http")]
        now_iso = datetime.datetime.now(CAIRO).replace(microsecond=0).isoformat()
        is_rev = "rv-wrap" in out
        art_node = {
            "@type": "NewsArticle",
            "headline": art.get("title", "")[:110],
            "description": (art.get("desc") or art.get("title") or "").strip(),
            "datePublished": now_iso,
            "dateModified": now_iso,
            "inLanguage": "ar",
            "author": {
                "@type": "Person",
                "name": "محسن فاروق",
                "jobTitle": "رئيس التحرير",
                "url": "https://www.review-mobile.com" if is_rev else "https://www.egyptaway.com/p/editor-mohsen.html"
            },
            "publisher": {
                "@type": "Organization",
                "name": "رفيو موبايل" if is_rev else "ايجبتاوى",
                "url": "https://www.review-mobile.com" if is_rev else "https://www.egyptaway.com"
            }
        }
        if clean_imgs:
            art_node["image"] = clean_imgs
        graph = [art_node]
        faqs = art.get("faq") or []
        if not faqs:
            raw_faqs = re.findall(r"<details[^>]*>\s*<summary[^>]*>(.*?)</summary>\s*<p[^>]*>(.*?)</p>\s*</details>", out, flags=re.DOTALL | re.I)
            faqs = [{"q": re.sub(r"<[^>]+>", "", q).strip(), "a": re.sub(r"<[^>]+>", "", a).strip()} for q, a in raw_faqs]
        valid_faqs = [q for q in faqs if isinstance(q, dict) and q.get("q") and q.get("a")]
        if valid_faqs:
            graph.append({
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}}
                    for q in valid_faqs[:6]
                ]
            })
        schema_str = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
        out += f'<script type="application/ld+json">{schema_str}</script>'
    return out


def with_desc(html_out, art):
    """Blogger's API can't set the post's search description, so we tuck it into the post as a hidden span; the
    theme block <!-- ea meta description --> copies it into the page's meta description."""
    enriched = _enrich_seo_html(html_out, art)
    d = (art.get("desc") or "").strip()
    return enriched + (f'<span class="ea-desc" hidden>{html.escape(d)}</span>' if d else "")


def publish_live(tok, art, html_out, labels):
    """Publishes post LIVE immediately with clean slug URL and Arabic title (no scheduling delay)."""
    now = datetime.datetime.now(CAIRO)
    d = api("POST", f"/blogs/{BLOG}/posts", tok, {"isDraft": "true"},
            {"kind": "blogger#post", "title": art["slug"].replace("-", " "), "content": with_desc(html_out, art), "labels": list(dict.fromkeys(labels))})
    api("POST", f"/blogs/{BLOG}/posts/{d['id']}/publish", tok, {"publishDate": now.isoformat()})
    api("PATCH", f"/blogs/{BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
    return api("GET", f"/blogs/{BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})


def schedule(tok, art, html_out, labels, when):
    """Draft with the slug as title (Blogger builds the URL from it), schedule, then set the Arabic title."""
    d = api("POST", f"/blogs/{BLOG}/posts", tok, {"isDraft": "true"},
            {"kind": "blogger#post", "title": art["slug"].replace("-", " "), "content": with_desc(html_out, art), "labels": labels})
    api("POST", f"/blogs/{BLOG}/posts/{d['id']}/publish", tok, {"publishDate": when.isoformat()})
    api("PATCH", f"/blogs/{BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
    return api("GET", f"/blogs/{BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})


def make_previews(previews, data, existing, state, tok, times, today):
    """'Match time and channel' articles for tomorrow's big matches."""
    made = 0
    for (key, m), when in zip(previews, times or [None] * len(previews)):
        if _DOWN:
            break
        facts = match_facts(m, data)
        extra, art, errs = "", None, ["no draft"]
        for attempt in range(2):
            art = gemini(PREVIEW_PROMPT.format(extra=extra, facts=facts))
            errs = check(art, facts, facts, existing, min_words=300)
            if not errs:
                break
            print("  preview retry:", errs)
            extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
        if errs:
            print("PREVIEW SKIPPED", key, errs)
            continue
        state.setdefault("previews", []).append(key)
        rows = team_matches(m["h"] + " " + m["a"], data)
        p = f"img/{art['slug']}.jpg"
        team_tuples = [(m["h"], TEAM_LOGOS.get(m["h"])), (m["a"], TEAM_LOGOS.get(m["a"]))]
        bg_url = PEX.format(i=random.choice(IMAGES)[0])
        lead_img_url = None
        if make_club_logo_cover(team_tuples, bg_url, p):
            lead_img_url = CDN + p
        else:
            lead_img_url = bg_url
        html_out = build_html(art, rows, random.choice(IMAGES), None, (), real_img_url=lead_img_url, live=m)
        labels = ["رياضة", "أخبار الكورة", "مواعيد المباريات"] + (["الدوري المصري"] if m["l"] == "الدوري المصري" else [])
        if DRY:
            os.makedirs("out", exist_ok=True)
            open(f"out/{art['slug']}.html", "w", encoding="utf-8").write(f"<h1>{html.escape(art['title'])}</h1>\n" + html_out)
            print("DRY PREVIEW", art["title"])
        else:
            fin = schedule(tok, art, html_out, labels, when)
            print("PREVIEW SCHEDULED", when.strftime("%H:%M"), fin.get("url"), "|", art["title"])
        existing.append(art["title"])
        made += 1
    return made


if __name__ == "__main__":
    main()
