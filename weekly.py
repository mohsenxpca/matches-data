"""Weekly post on Egyptaway: how gold and the dollar moved in Egypt this week (real numbers from services_history.json).
Runs every Friday on GitHub Actions (.github/workflows/weekly.yml). Reuses football.py's Gemini writer, checker and scheduler.
"""
import datetime, html, json, random
import football as f

IMGS = [(8442325, "سبائك ذهب وبلاتين على خلفية سودا"), (8442326, "سبائك وعملات ذهب كتير جنب بعض"),
        (29336324, "سبيكة ذهب كبيرة فوق ورق دولارات"), (8442334, "سبائك وعملات ذهب لامعة")]
PEX = f.PEX
SITE = f.SITE

PROMPT = """أنت محرر اقتصادي في موقع ايجبتاوى المصري. اكتب مقال أسبوعي عن «حركة أسعار الذهب والدولار في مصر الأسبوع ده».

قواعد صارمة:
- استخدم «البيانات» تحت بس. ممنوع تخترع أسباب أو أرقام أو توقعات بأرقام. ممكن تشرح العوامل العامة اللي بتأثر على السعر من غير أرقام.
- اكتب كل الأرقام بالأرقام، مش بالحروف. ممنوع تذكر اسم أي موقع.
- وضّح إن أسعار الذهب محسوبة من البورصة العالمية وإن الصاغة بيزوّدوا المصنعية.
- مش نصيحة استثمار: ممنوع «اشتري دلوقتي» أو «بيع»، وقول إن القرار يرجع للقارئ.
- الطول: الـ body من 550 لـ 800 كلمة، بعناوين h2 (من 4 لـ 6) وفقرات <p>، وممكن <ul>. من غير صور ومن غير روابط.

رجّع JSON بالشكل ده بالظبط:
{{"title": "حركة الذهب والدولار في مصر .. أقل من 65 حرف", "kicker": "3-5 كلمات", "slug": "3 to 6 english words with hyphens", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
البيانات:
{facts}
"""


def facts(hist):
    days = [h for h in hist if h.get("g21") and h.get("fx")][-7:]
    if len(days) < 3:
        return None
    a, b = days[0], days[-1]
    lines = [f"الفترة: من {a['date']} لـ {b['date']}"]
    for k, n in (("g24", "جرام عيار 24"), ("g21", "جرام عيار 21")):
        lines.append(f"{n}: أول الفترة {a[k]:.0f} جنيه، آخر الفترة {b[k]:.0f} جنيه، الفرق {b[k] - a[k]:+.0f} جنيه، "
                     f"أعلى سعر {max(d[k] for d in days):.0f}، أقل سعر {min(d[k] for d in days):.0f}")
    lines.append(f"الجنيه الذهب (8 جرام عيار 21) آخر الفترة: {b['g21'] * 8:.0f} جنيه")
    lines.append(f"الأونصة عالميًا: أول الفترة {a['oz_usd']:.0f} دولار، آخرها {b['oz_usd']:.0f} دولار")
    for c, n in (("USD", "الدولار"), ("EUR", "اليورو"), ("SAR", "الريال السعودي"), ("AED", "الدرهم الإماراتي")):
        if c in a["fx"] and c in b["fx"]:
            lines.append(f"{n}: أول الفترة {a['fx'][c]:.2f} جنيه، آخرها {b['fx'][c]:.2f} جنيه، الفرق {b['fx'][c] - a['fx'][c]:+.2f}")
    lines.append("سعر جرام عيار 21 يوم بيوم: " + "، ".join(f"{d['date'][5:]}: {d['g21']:.0f}" for d in days))
    return "\n".join(lines)


def main():
    hist = json.load(open("services_history.json", encoding="utf-8"))
    fx = facts(hist)
    if not fx:
        print("not enough history yet")
        return
    tok = f.token()
    existing = [p["t"] for p in f.site_posts(tok)]
    extra, art, errs = "", None, ["no draft"]
    for _ in range(2):
        art = f.gemini(PROMPT.format(extra=extra, facts=fx))
        errs = f.check(art, fx, fx, existing, min_words=450)
        if not errs:
            break
        print("retry:", errs)
        extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
    if errs:
        raise SystemExit(f"skipped: {errs}")
    img = random.choice(IMGS)
    e = html.escape
    body = (f'<img src="{PEX.format(i=img[0])}" alt="{e(img[1])}" width="1000" height="563" style="width:100%;height:auto;border-radius:12px">'
            + art["body"]
            + f'<p>تابع السعر لحظة بلحظة في <a href="{SITE}/p/gold-prices-egypt.html">صفحة أسعار الذهب اليوم</a> و<a href="{SITE}/p/currency-prices-egypt.html">صفحة أسعار العملات</a>، '
              '<button type="button" onclick="location.href=\'' + SITE + '/p/gold-prices-egypt.html\'" style="border:0;border-radius:999px;padding:7px 16px;font:inherit;font-weight:700;color:#fff;background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer">احسب تمن ذهبك</button></p>'
            + "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{e(q['q'])}</summary><p>{e(q['a'])}</p></details>" for q in art.get("faq", [])[:4])
            + '<p style="font-size:13px;color:#6b7280">الأرقام محسوبة من سعر البورصة العالمية وسعر الصرف، ومش نصيحة استثمار.</p>')
    now = datetime.datetime.now(f.CAIRO)
    when = now.replace(hour=12, minute=random.randint(5, 55), second=0, microsecond=0)
    if when < now + datetime.timedelta(minutes=20):
        when = now + datetime.timedelta(minutes=random.randint(25, 60))
    fin = f.schedule(tok, art, body, ["أسعار الذهب والعملات", "أخبار"], when)
    print("SCHEDULED", when.strftime("%Y-%m-%d %H:%M"), fin.get("url"), "|", art["title"])


if __name__ == "__main__":
    main()
