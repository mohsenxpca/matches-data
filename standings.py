"""Egyptian league table page on Egyptaway (/p/egyptian-league-table.html), refreshed automatically.

Reads the table, writes standings.json and, when it changed, rewrites the Blogger page with a plain HTML table
(indexable, no JavaScript needed). Runs on GitHub Actions (.github/workflows/standings.yml).
Usage: python standings.py            -> scrape + update page (needs the BLOGGER_* secrets)
       python standings.py --html     -> just print the page HTML (for a first manual publish)
"""
import datetime, html, json, os, re, sys
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

BLOG = "8325646053257070334"
PAGE_ID = os.environ.get("TABLE_PAGE_ID", "")
SITE = "https://www.egyptaway.com"
SRC = "https://www.yallakora.com/tour/160/"
HEAD = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36",
        "Accept-Language": "ar,en;q=0.8"}
CAIRO = ZoneInfo("Africa/Cairo")
AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def scrape():
    s = BeautifulSoup(requests.get(SRC, headers=HEAD, timeout=40).text, "html.parser")
    rows = []
    for a in s.find_all("a", href=True):
        if "groupstandingclip" not in a["href"]:
            continue
        item = a.find_parent("div", class_="item")
        if not item or "team" not in (item.get("class") or []):
            continue
        row = item.parent
        vals = [v for v in row.get_text("|", strip=True).split("|")]
        name = a.get_text(" ", strip=True)
        nums = [int(v) for v in vals if re.fullmatch(r"-?\d+", v)]
        if len(nums) < 4:
            continue
        p, gf, ga, pts = nums[-4:]
        if any(r["team"] == name for r in rows):
            continue
        rows.append({"team": name, "p": p, "gf": gf, "ga": ga, "gd": gf - ga, "pts": pts})
    if len(rows) < 10:
        raise SystemExit(f"only {len(rows)} rows read - layout changed?")
    rows.sort(key=lambda r: (-r["pts"], -r["gd"], -r["gf"]))
    return rows


def logos():
    try:
        return json.load(open("logos.json", encoding="utf-8"))["logos"]
    except Exception:
        return {}


def build_html(rows, updated):
    e = html.escape
    L = logos()
    now = updated.astimezone(CAIRO)
    season = now.year if now.month >= 8 else now.year - 1
    stamp = f"{now.day} {AR_MONTHS[now.month - 1]} {now.year} الساعة {now:%H:%M}"
    top, bottom = rows[0], rows[-1]
    trs = []
    for i, r in enumerate(rows, 1):
        lg = L.get(r["team"])
        img = (f'<img src="https://wsrv.nl/?url={requests.utils.quote(lg, safe="")}&amp;w=48&amp;h=48&amp;output=webp" '
               f'alt="شعار {e(r["team"])}" width="24" height="24" loading="lazy">') if lg else ""
        cls = ' class="lt-top"' if i <= 3 else (' class="lt-bot"' if i > len(rows) - 3 else "")
        trs.append(f'<tr{cls}><td>{i}</td><td class="lt-team">{img}{e(r["team"])}</td><td>{r["p"]}</td>'
                   f'<td>{r["gf"]}</td><td>{r["ga"]}</td><td>{r["gd"]:+d}</td><td><b>{r["pts"]}</b></td></tr>')
    leaders = "، ".join(f'{e(r["team"])} ({r["pts"]} نقطة)' for r in rows[:3])
    return f"""<p>جدول ترتيب الدوري المصري الممتاز لموسم {season}-{season + 1} بيتحدّث لوحده بعد كل ماتش. <b>آخر تحديث: {stamp}</b> بتوقيت القاهرة.</p>
<p>في الصدارة دلوقتي <b>{e(top["team"])}</b> برصيد <b>{top["pts"]} نقطة</b> من {top["p"]} ماتش، وبعده {leaders.split("، ", 1)[1] if "، " in leaders else ""}. وفي ذيل الجدول {e(bottom["team"])} برصيد {bottom["pts"]} نقطة.</p>
<style>.lt{{width:100%;border-collapse:collapse;font-size:15px;margin:14px 0}}.lt th{{background:#1f2a44;color:#fff;padding:8px 4px}}.lt td{{padding:7px 4px;border-bottom:1px solid #f1f1f1;text-align:center}}.lt td.lt-team{{text-align:right;font-weight:700;white-space:nowrap}}.lt img{{vertical-align:middle;margin-left:6px;border-radius:50%;background:#fff}}.lt tr.lt-top td{{background:#fff7ed}}.lt tr.lt-bot td{{background:#fef2f2}}.lt-wrap{{overflow-x:auto}}.lt-btn{{border:0;border-radius:999px;padding:8px 18px;font:inherit;font-weight:700;color:#fff;background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer}}@media(max-width:600px){{.lt{{font-size:13px}}}}</style>
<div class="lt-wrap"><table class="lt"><thead><tr><th>#</th><th>الفريق</th><th>لعب</th><th>له</th><th>عليه</th><th>الفارق</th><th>النقاط</th></tr></thead><tbody>
{"".join(trs)}
</tbody></table></div>
<p><button type="button" class="lt-btn" onclick="var q=prompt('اكتب اسم فريقك');if(!q)return;var r=[].slice.call(document.querySelectorAll('.lt tbody tr')).find(function(t){{return t.textContent.indexOf(q.trim())>-1}});if(r){{r.scrollIntoView({{block:'center'}});r.style.outline='3px solid #f59e0b'}}else alert('الفريق مش موجود في الجدول')">دوّر على ترتيب فريقك</button></p>
<h2>إزاي بيتحسب ترتيب الدوري المصري؟</h2>
<p>الفوز بـ3 نقط، والتعادل بنقطة، والخسارة من غير نقط. ولو فريقين اتساووا في النقط، بيتقدّم صاحب فارق الأهداف الأحسن، وبعده الأكتر تسجيلًا. الفرق الأولى في الجدول بتنافس على اللقب والمشاركة الأفريقية، والفرق اللي في آخر الجدول مهددة بالهبوط.</p>
<h2>مواعيد ماتشات الجولة الجاية والقنوات</h2>
<p>كل مواعيد ماتشات الدوري المصري والقنوات الناقلة (ON Sport) موجودة في <a href="{SITE}/p/matches-today.html">صفحة مباريات اليوم والقنوات الناقلة</a>، ولو بتدوّر على طريقة تتابع بيها الماتشات اقرأ <a href="{SITE}/2024/03/egynow.html">بديل ايجي ناو لمتابعة المباريات</a>. وآخر الأخبار في قسم <a href="{SITE}/search/label/%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1%20%D8%A7%D9%84%D9%83%D9%88%D8%B1%D8%A9">أخبار الكورة</a>.</p>
<h2>أسئلة شائعة</h2>
<details><summary>مين متصدر الدوري المصري دلوقتي؟</summary><p>{e(top["team"])} متصدر برصيد {top["pts"]} نقطة بعد {top["p"]} ماتش (آخر تحديث {stamp}).</p></details>
<details><summary>الجدول ده بيتحدّث إمتى؟</summary><p>بيتحدّث لوحده كذا مرة في اليوم، وبعد نهاية كل ماتش بوقت قصير.</p></details>
<details><summary>فين أتفرج على ماتشات الدوري المصري؟</summary><p>ماتشات الدوري المصري بتتذاع على قنوات ON Sport، والمواعيد كلها في صفحة مباريات اليوم.</p></details>
"""


def token():
    def sec(n):
        return os.environ.get(n, "").strip().strip('"')
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": sec("BLOGGER_CLIENT_ID"), "client_secret": sec("BLOGGER_CLIENT_SECRET"),
        "refresh_token": sec("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google login failed ({r.status_code}): {r.text[:150]}")
    return r.json()["access_token"]


def main():
    rows = scrape()
    try:
        old = json.load(open("standings.json", encoding="utf-8"))
    except Exception:
        old = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    if "--html" in sys.argv:
        print(build_html(rows, now))
        return
    if old.get("rows") == rows:
        print("table unchanged")
        return
    json.dump({"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}, open("standings.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    if not PAGE_ID:
        print("no TABLE_PAGE_ID, saved standings.json only")
        return
    r = requests.patch(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/pages/{PAGE_ID}",
                       headers={"Authorization": "Bearer " + token()}, json={"content": build_html(rows, now)}, timeout=60)
    if r.status_code >= 400:
        sys.exit(f"page update failed {r.status_code}: {r.text[:200]}")
    print("page updated, leader:", rows[0]["team"], rows[0]["pts"])


if __name__ == "__main__":
    main()
