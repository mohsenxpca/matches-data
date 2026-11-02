"""Monthly post on Egyptaway: which phones got cheaper or pricier in Egypt this month (real numbers from the weekly
prices/history/<date>.json snapshots that prices.yml saves). Runs from prices.yml on the first Thursday of each month;
does nothing until there are two snapshots at least 21 days apart. Reuses football.py's Gemini writer, checker and scheduler.
Usage: python monthly_prices.py            write + schedule the post
       python monthly_prices.py --facts    print the facts only
"""
import datetime, glob, html, json, os, random, sys
import football as f

SITE = f.SITE
PEX = f.PEX
IMGS = [(607812, "مجموعة موبايلات حديثة جنب بعض على ترابيزة"), (1092644, "موبايل في إيد شخص بيتصفح الشاشة"),
        (404280, "موبايل ذكي على مكتب جنب لابتوب")]

PROMPT = """أنت محرر تقني في موقع ايجبتاوى المصري. اكتب تقرير شهري: «أسعار الموبايلات في مصر الشهر ده: إيه اللي رخص وإيه اللي غلي».

قواعد صارمة:
- استخدم «البيانات» تحت بس. ممنوع تخترع أسعار أو أسباب أو مواصفات أو أرقام. ممكن تشرح بشكل عام إن الأسعار بتتأثر بالعرض والطلب وسعر الصرف من غير أرقام.
- اكتب كل الأرقام بالأرقام، مش بالحروف. ممنوع تذكر اسم أي موقع أو متجر.
- وضّح إن الأسعار هي أقل سعر معلن في المتاجر المصرية وقت الرصد، وإنها ممكن تختلف من متجر للتاني.
- مش نصيحة شراء مباشرة، بس ممكن تقول «لو كنت ناوي تشتري موبايل من الموبايلات اللي رخصت، الشهر ده فرصة».
- الطول: الـ body من 650 لـ 900 كلمة، بعناوين h2 (من 4 لـ 6) وفقرات <p>، وممكن <ul>. من غير صور ومن غير روابط ومن غير جداول (الجدول بيتضاف لوحده).

رجّع JSON بالشكل ده بالظبط:
{{"title": "أسعار الموبايلات في مصر .. أقل من 65 حرف", "kicker": "3-5 كلمات", "slug": "3 to 6 english words with hyphens", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
البيانات:
{facts}
"""


def snapshots():
    out = []
    for p in sorted(glob.glob("prices/history/*.json")):
        try:
            out.append((os.path.basename(p)[:10], json.load(open(p, encoding="utf-8"))))
        except Exception:
            pass
    return out


def changes():
    snaps = snapshots()
    if len(snaps) < 2:
        return None
    d1, new = snaps[-1]
    end = datetime.date.fromisoformat(d1)
    old_d, old = next(((d, s) for d, s in reversed(snaps[:-1]) if (end - datetime.date.fromisoformat(d)).days >= 21), (None, None))
    if not old:
        return None
    rows = []
    for name, cur in new.items():
        prev = old.get(name)
        if prev and cur and prev["p"] and cur["p"] and cur["p"] != prev["p"]:
            rows.append({"n": name, "b": cur.get("b", ""), "old": prev["p"], "new": cur["p"], "page": cur.get("page")})
    return old_d, d1, len(new), rows


def facts(ch):
    old_d, new_d, total, rows = ch
    down = sorted((r for r in rows if r["new"] < r["old"]), key=lambda r: r["new"] / r["old"])
    up = sorted((r for r in rows if r["new"] > r["old"]), key=lambda r: -r["new"] / r["old"])
    L = [f"الفترة: من {old_d} لـ {new_d}", f"عدد الموبايلات المرصودة: {total}، اللي سعرها اتغير: {len(rows)}، "
         f"اللي رخص: {len(down)}، اللي غلي: {len(up)}"]
    for title, lst in (("أكتر موبايلات رخصت", down[:10]), ("أكتر موبايلات غليت", up[:10])):
        L.append(title + ":")
        L += [f"- {r['n']} ({r['b']}): كان {r['old']} جنيه وبقى {r['new']} جنيه، الفرق {r['new'] - r['old']:+} جنيه "
              f"({(r['new'] - r['old']) / r['old'] * 100:+.0f}%)" for r in lst]
    return "\n".join(L), down, up


def table(rows, head):
    e = html.escape

    def name(r):
        return f'<a href="{SITE}/p/{r["page"]}.html">{e(r["n"])}</a>' if r.get("page") else e(r["n"])
    tr = "".join(f"<tr><td>{name(r)}</td><td>{r['old']:,}</td><td>{r['new']:,}</td><td>{r['new'] - r['old']:+,}</td></tr>" for r in rows)
    return (f"<h2>{head}</h2><div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse'><thead><tr>"
            "<th>الموبايل</th><th>السعر القديم</th><th>السعر الجديد</th><th>الفرق (جنيه)</th></tr></thead>"
            f"<tbody>{tr}</tbody></table></div>")


DONE = "prices/history/_reported.json"


def main():
    month = datetime.date.today().strftime("%Y-%m")
    done = json.load(open(DONE, encoding="utf-8")) if os.path.exists(DONE) else []
    if month in done and "--facts" not in sys.argv:
        print("already reported this month")
        return
    ch = changes()
    if not ch or not ch[3]:
        print("not enough price history yet")
        return
    fx, down, up = facts(ch)
    if "--facts" in sys.argv:
        print(fx)
        return
    tok = f.token()
    existing = [p["t"] for p in f.site_posts(tok)]
    extra, art, errs = "", None, ["no draft"]
    for _ in range(2):
        art = f.gemini(PROMPT.format(extra=extra, facts=fx))
        errs = f.check(art, fx, fx, existing, min_words=600)
        if not errs:
            break
        print("retry:", errs)
        extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
    if errs:
        raise SystemExit(f"skipped: {errs}")
    img = random.choice(IMGS)
    e = html.escape
    body = (f'<img src="{PEX.format(i=img[0])}" alt="{e(img[1])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px">'
            + art["body"]
            + (table(down[:10], "الموبايلات اللي رخصت الشهر ده") if down else "")
            + (table(up[:10], "الموبايلات اللي غليت الشهر ده") if up else "")
            + f'<p>شوف سعر أي موبايل بالتفصيل في <a href="{SITE}/p/mobile-prices-egypt.html">صفحة أسعار الموبايلات في مصر</a>، '
              '<button type="button" onclick="location.href=\'' + SITE + '/p/mobile-prices-egypt.html\'" style="border:0;border-radius:999px;padding:7px 16px;font:inherit;font-weight:700;color:#fff;background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer">قارن الأسعار</button></p>'
            + "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{e(q['q'])}</summary><p>{e(q['a'])}</p></details>" for q in art.get("faq", [])[:4])
            + '<p style="font-size:13px;color:#6b7280">المصادر: أقل سعر معلن في المتاجر المصرية وقت الرصد الأسبوعي، والأسعار ممكن تختلف من متجر للتاني.</p>')
    now = datetime.datetime.now(f.CAIRO)
    when = now.replace(hour=13, minute=random.randint(5, 55), second=0, microsecond=0)
    if when < now + datetime.timedelta(minutes=20):
        when = now + datetime.timedelta(minutes=random.randint(25, 60))
    fin = f.schedule(tok, art, body, ["أسعار الموبايلات", "أخبار"], when)
    json.dump(done + [month], open(DONE, "w", encoding="utf-8"))
    print("SCHEDULED", when.strftime("%Y-%m-%d %H:%M"), fin.get("url"), "|", art["title"])


if __name__ == "__main__":
    main()
