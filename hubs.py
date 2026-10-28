"""Evergreen Egyptian service pages built from the latest news (mohsen 2026-10-28): salaries & pensions, exam schedules,
train times. Sources: the newest Sada El Balad (elbalad.news) stories on each topic, found via Google News RSS
(their own search is disallowed in robots.txt). We take facts only (dates, times, amounts) and Gemini writes the page in
our words; every number must appear in the sources (football.check). The source links are listed at the bottom.
Runs every 6 hours (hubs.yml). Page ids in services_pages.json under "hubs".
Usage: python hubs.py | python hubs.py --only trains | DRY_RUN=1 python hubs.py --only salaries
"""
import datetime, html, json, os, re, sys, time, urllib.parse
import requests
from bs4 import BeautifulSoup
import football as f
import services as S

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
TOPICS = {
    "salaries": {"q": ["مواعيد صرف مرتبات", "صرف معاشات"], "name": "مواعيد صرف المرتبات والمعاشات", "must": r"مرتب|معاش|رواتب|أجور|حافز",
                 "focus": "مواعيد صرف مرتبات الشهر الحالي والجاي للعاملين بالدولة، ومواعيد صرف المعاشات، وأماكن الصرف، وأي زيادات أو حد أدنى للأجور مذكور"},
    "exams": {"q": ["جدول امتحانات", "مواعيد امتحانات"], "name": "جداول ومواعيد الامتحانات", "must": r"امتحان",
              "focus": "جداول ومواعيد الامتحانات القادمة (الثانوية العامة والدبلومات والإعدادية والابتدائية والجامعات والتيرم)، ومواعيد النتايج لو مذكورة"},
    "trains": {"q": ["مواعيد قطارات", "مواعيد القطارات"], "name": "مواعيد القطارات في مصر", "must": r"قطار",
               "focus": "مواعيد قيام ووصول القطارات بين المحافظات (القاهرة والإسكندرية والصعيد والقناة) وأسعار التذاكر لو مذكورة، في جدول واضح"},
}
LINKS = [("salaries", "مواعيد المرتبات", "/p/salaries-egypt.html"), ("exams", "جداول الامتحانات", "/p/exams-egypt.html"),
         ("trains", "مواعيد القطارات", "/p/trains-egypt.html"), ("h", "الإجازات الرسمية", "/p/official-holidays-egypt.html"),
         ("g", "أسعار الذهب", "/p/gold-prices-egypt.html"), ("c", "أسعار العملات", "/p/currency-prices-egypt.html")]

PROMPT = """أنت محرر خدمات في موقع ايجبتاوى المصري. اكتب محتوى صفحة ثابتة بتتحدث باستمرار عن «{name}»، من الأخبار اللي تحت بس.

قواعد صارمة:
- استخدم المعلومات اللي في «المصادر» بس، وركّز على: {focus}.
- ممنوع تخترع أي تاريخ أو ساعة أو مبلغ أو رقم. أي رقم لازم يكون مكتوب في المصادر بالظبط. اكتب الأرقام بالأرقام.
- ممنوع تنسخ جمل من المصادر: أعد الصياغة بالكامل. وممنوع تذكر اسم أي موقع أو جريدة.
- لو فيه مواعيد كتير، حطها في جدول HTML (<table><tr><th>..</th></tr><tr><td>..</td></tr></table>).
- لو معلومة لسه مش رسمية أو متوقعة، قول كده بوضوح.
- ابدأ بفقرة قصيرة فيها أهم معلومة دلوقتي (أقرب موعد).
- الطول: من 500 لـ 900 كلمة، بعناوين h2 (من 3 لـ 6) وفقرات <p> وجداول. من غير صور ومن غير روابط.

رجّع JSON بالشكل ده بالظبط:
{{"title": "عنوان الصفحة أقل من 65 حرف وفيه السنة", "slug": "x", "desc": "وصف للبحث من 140 لـ 160 حرف", "headline": "أهم معلومة دلوقتي في سطر واحد أقل من 90 حرف", "body": "<p>..</p><h2>..</h2>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
تاريخ النهارده: {today}

المصادر:
{src}
"""


def gn_items(q):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " site:elbalad.news when:14d") + "&hl=ar&gl=EG&ceid=EG:ar"
    x = requests.get(url, headers=UA, timeout=30).text
    out = []
    for t, l, d in re.findall(r"<item><title>(.*?)</title><link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>", x, re.S):
        try:
            when = datetime.datetime.strptime(d, "%a, %d %b %Y %H:%M:%S %Z")
        except Exception:
            continue
        out.append((when, html.unescape(t).rsplit(" - ", 1)[0], l))
    return out


def decode(link):
    """Google News RSS links -> the publisher URL (same flow the news.google.com page uses)."""
    aid = link.split("/articles/")[1].split("?")[0]
    h = requests.get(f"https://news.google.com/rss/articles/{aid}", headers=UA, timeout=30).text
    sg = re.search(r'data-n-a-sg="([^"]+)"', h).group(1)
    ts = re.search(r'data-n-a-ts="([^"]+)"', h).group(1)
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                            "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts), sg]
    r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", timeout=30,
                      headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                      data="f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])))
    return json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]


def article(url):
    s = BeautifulSoup(requests.get(url, headers=UA, timeout=30).text, "html.parser")
    b = s.select_one("div[itemprop=articleBody]") or s.select_one("article")
    if not b:
        return ""
    return "\n".join(t for t in (x.get_text(" ", strip=True) for x in b.find_all(["p", "li", "td", "h2", "h3"])) if len(t) > 15)


def sources(topic):
    items = []
    for q in TOPICS[topic]["q"]:
        items += gn_items(q)
        time.sleep(1)
    seen, out = set(), []
    for when, t, l in sorted(items, reverse=True):
        if t in seen or not re.search(TOPICS[topic]["must"], t):
            continue
        seen.add(t)
        try:
            u = decode(l)
            tx = article(u)
        except Exception as e:
            print("  source failed:", t[:50], e)
            continue
        if len(tx) > 400:
            out.append({"t": t, "u": u, "when": when, "text": tx})
        if len(out) >= 4:
            break
        time.sleep(1)
    return out


def build(topic, existing):
    now = datetime.datetime.now(S.CAIRO)
    src = sources(topic)
    if not src:
        print(topic, "no sources")
        return None
    srctext = "\n\n".join(f"[{x['when']:%Y-%m-%d}] {x['t']}\n{x['text'][:3500]}" for x in src)
    T = TOPICS[topic]
    extra, art, errs = "", None, ["no draft"]
    for _ in range(2):
        art = f.gemini(PROMPT.format(name=T["name"], focus=T["focus"], extra=extra, today=f"{now:%Y-%m-%d}", src=srctext))
        errs = f.check(art, srctext + f" {now.year} {now.year + 1} {now.day} {now.month}", "", existing, min_words=400)
        errs = [e for e in errs if "العنوان" not in e]  # page titles repeat by design
        if not errs:
            break
        print("  retry:", errs)
        extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
    if errs:
        print(topic, "SKIPPED", errs)
        return None
    E = html.escape
    srcs = " · ".join(f'<a href="{E(x["u"])}" rel="nofollow noopener" target="_blank">{E(x["t"][:60])}</a>' for x in src)
    links = '<div class="sv-links">' + "".join(f'<a href="{S.SITE}{u}">{t}</a>' for k, t, u in LINKS if k != topic) + "</div>"
    body = (f'{S.CSS}<div class="sv"><div class="sv-hero"><b>{E(art.get("headline") or art["title"])}</b><br>'
            f'<small>آخر تحديث: {S.stamp(now)} · الصفحة بتتحدث لوحدها كل 6 ساعات من آخر الأخبار</small></div>'
            + art["body"].replace("<table", '<div class="sv-wrap"><table class="sv-t"').replace("</table>", "</table></div>")
            + S.faq([(q["q"], q["a"]) for q in art.get("faq", [])[:4]])
            + f'<p class="sv-note">المصادر: {srcs}</p>' + links + "</div>")
    return art, body


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else list(TOPICS)
    tok = f.token()
    existing = [p["t"] for p in f.site_posts(tok)]
    ids = S.PAGES.get("hubs", {})
    for topic in only:
        res = build(topic, existing)
        if not res:
            continue
        art, body = res
        if dry:
            os.makedirs("out", exist_ok=True)
            open(f"out/hub-{topic}.html", "w", encoding="utf-8").write(f"<h1>{html.escape(art['title'])}</h1>" + body)
            print("DRY", topic, art["title"], "|", art.get("headline"))
            continue
        pid = (ids.get(topic) or {}).get("id")
        if not pid:  # first good run creates the page (English title first so Blogger makes the /p/<topic>-egypt.html URL)
            p = f.api("POST", f"/blogs/{f.BLOG}/pages", tok, {"isDraft": "false"}, {"title": f"{topic} egypt", "content": body})
            pid = p["id"]
            pages = json.load(open("services_pages.json", encoding="utf-8"))
            pages.setdefault("hubs", {})[topic] = {"id": pid, "url": p.get("url")}
            json.dump(pages, open("services_pages.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(topic, "created", p.get("url"))
        f.api("PATCH", f"/blogs/{f.BLOG}/pages/{pid}", tok, None, {"content": body, "title": art["title"]})
        print(topic, "updated |", art["title"])


if __name__ == "__main__":
    main()
