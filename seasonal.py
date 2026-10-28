"""Seasonal Egyptian pages (mohsen 2026-10-28): official holidays and the Ramadan imsakiya, with countdowns.

Holidays come from date.nager.at (Egypt, includes the government's moved dates) plus Eid al-Fitr from the Hijri
calendar (aladhan), marked as expected until the cabinet announces it. Imsakiya = aladhan Hijri calendar for Ramadan of
the coming Hijri year, Egyptian method. Updated with services.yml; page ids in services_pages.json under "seasonal".
Usage: python seasonal.py | python seasonal.py --html holidays
"""
import datetime, json, sys, time
import requests
import services as S

E, CSS, SITE = S.E, S.CSS, S.SITE
AR_NAMES = {"Christmas Day (Orthodox)": "عيد الميلاد المجيد", "Revolution Day 2011 / National Police Day": "عيد ثورة 25 يناير وعيد الشرطة",
            "Easter Monday": "شم النسيم", "Sinai Liberation Day": "عيد تحرير سيناء", "Labour Day": "عيد العمال",
            "Eid Al-Adha": "عيد الأضحى", "Eid al-Adha": "عيد الأضحى", "Eid al-Fitr": "عيد الفطر", "Eid Al-Fitr": "عيد الفطر",
            "Islamic New Year": "رأس السنة الهجرية", "June 30 Revolution": "ذكرى ثورة 30 يونيو", "Revolution Day": "عيد ثورة 23 يوليو",
            "Prophet Muhammad's Birthday": "المولد النبوي الشريف", "Armed Forces Day": "عيد القوات المسلحة (6 أكتوبر)",
            "Arafat Day": "وقفة عرفات"}
DAYS = S.AR_DAYS


def ar_date(d):
    return f"{DAYS[d.weekday()]} {d.day} {S.AR_MONTHS[d.month - 1]} {d.year}"


def holidays(now):
    rows = []
    for y in (now.year, now.year + 1):
        for h in S.get(f"https://date.nager.at/api/v3/PublicHolidays/{y}/EG"):
            d = datetime.date.fromisoformat(h["date"])
            rows.append((d, AR_NAMES.get(h["name"], h["localName"]), False))
        if not any("الفطر" in n for d, n, _ in rows if d.year == y):
            hy = S.get("https://api.aladhan.com/v1/gToH/" + f"01-06-{y}")["data"]["hijri"]["year"]
            for hyear in (int(hy) - 1, int(hy)):
                g = S.get(f"https://api.aladhan.com/v1/hToG/01-10-{hyear}")["data"]["gregorian"]
                d = datetime.date(int(g["year"]), int(g["month"]["number"]), int(g["day"]))
                if d.year == y:
                    for i in range(3):
                        rows.append((d + datetime.timedelta(days=i), "عيد الفطر (متوقع فلكيًا)", True))
        time.sleep(1)
    rows.sort()
    # merge consecutive days of the same holiday
    merged = []
    for d, n, exp in rows:
        if merged and merged[-1][1] == n and (d - merged[-1][2]).days == 1:
            merged[-1][2] = d
        else:
            merged.append([d, n, d, exp])
    today = now.date()
    up = [m for m in merged if m[2] >= today]
    nxt = up[0] if up else None
    def span(m):
        return ar_date(m[0]) if m[0] == m[2] else f"من {ar_date(m[0])} لـ {ar_date(m[2])} ({(m[2] - m[0]).days + 1} أيام)"
    tr = "".join(f"<tr{' class=on' if m is nxt else ''}><td><b>{E(m[1])}</b></td><td>{span(m)}</td><td>{'✔️ اتعدّت' if m[2] < today else ''}</td></tr>"
                 for m in merged if m[0].year == today.year)
    tr2 = "".join(f"<tr><td><b>{E(m[1])}</b></td><td>{span(m)}</td></tr>" for m in merged if m[0].year == today.year + 1)
    js = (f"<script>(function(){{var T=new Date('{nxt[0].isoformat()}T00:00:00+02:00'),o=document.getElementById('sv-cd');function f(){{var s=Math.max(0,(T-new Date())/1000|0),d=s/86400|0,h=s%86400/3600|0,m=s%3600/60|0;o.textContent=d+' يوم و'+h+' ساعة و'+m+' دقيقة'}}f();setInterval(f,30000)}})();</script>"
          if nxt else "")
    count_left = len([m for m in merged if m[0] >= today and m[0].year == today.year])
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">الإجازة الرسمية الجاية: <b>{E(nxt[1]) if nxt else '-'}</b> · {span(nxt) if nxt else ''}<br>فاضل عليها: <b id="sv-cd">-</b><br><small>باقي {count_left} إجازة رسمية في {today.year} · آخر تحديث {ar_date(today)}</small></div>
{js}
<h2>جدول الإجازات الرسمية في مصر {today.year}</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>المناسبة</th><th>الموعد</th><th></th></tr></thead><tbody>{tr}</tbody></table></div>
<h2>الإجازات الرسمية في مصر {today.year + 1} (مبدئي)</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>المناسبة</th><th>الموعد</th></tr></thead><tbody>{tr2}</tbody></table></div>
<p class="sv-note">الحكومة المصرية ساعات بتنقل إجازة المناسبة ليوم خميس أو أحد علشان تبقى متصلة بالويك إند، والمواعيد هنا بتتحدث لما ده يتعلن. مواعيد الأعياد الإسلامية محسوبة فلكيًا، والموعد النهائي بيتحدد برؤية الهلال وقرار مجلس الوزراء.</p>
<h2>مين بياخد الإجازات دي؟</h2>
<p>الإجازات الرسمية بتسري على العاملين في الحكومة والقطاع العام، والقطاع الخاص غالبًا بيمشي عليها بقرار من وزارة العمل. البنوك والبورصة بيعلنوا إجازاتهم بشكل منفصل، وبتكون قريبة من المواعيد دي.</p>
{S.faq([("إيه الإجازة الرسمية الجاية في مصر؟", f"الإجازة الجاية هي {nxt[1]} {span(nxt)}." if nxt else "هيتعلن قريب."),
        (f"كام إجازة رسمية فاضلة في {today.year}؟", f"فاضل {count_left} مناسبة عليها إجازة رسمية في {today.year}."),
        ("ليه موعد الإجازة بيتغير عن تاريخ المناسبة؟", "مجلس الوزراء بينقل بعض الإجازات ليوم خميس أو أحد علشان تتصل بإجازة آخر الأسبوع.")])}
<div class="sv-links"><a href="{SITE}/p/ramadan-imsakia-egypt.html">إمساكية رمضان</a><a href="{SITE}/p/prayer-times-egypt.html">مواقيت الصلاة</a><a href="{SITE}/p/weather-egypt.html">الطقس</a><a href="{SITE}/p/matches-today.html">مباريات اليوم</a></div></div>"""
    return body


def imsakia(now):
    hy = int(S.get(f"https://api.aladhan.com/v1/gToH/{now:%d-%m-%Y}")["data"]["hijri"]["year"])
    first = S.get(f"https://api.aladhan.com/v1/hToG/01-09-{hy}")["data"]["gregorian"]
    start = datetime.date(int(first["year"]), int(first["month"]["number"]), int(first["day"]))
    if start + datetime.timedelta(days=30) < now.date():
        hy += 1
    days = S.get(f"https://api.aladhan.com/v1/hijriCalendarByCity/{hy}/9", params={"city": "Cairo", "country": "Egypt", "method": 5})["data"]
    g0 = days[0]["date"]["gregorian"]
    d0 = datetime.date(int(g0["year"]), int(g0["month"]["number"]), int(g0["day"]))
    tr = ""
    for i, d in enumerate(days, 1):
        g = d["date"]["gregorian"]
        gd = datetime.date(int(g["year"]), int(g["month"]["number"]), int(g["day"]))
        t = d["timings"]
        fajr = datetime.datetime.strptime(t["Fajr"][:5], "%H:%M")
        imsak = (fajr - datetime.timedelta(minutes=10)).strftime("%H:%M")
        tr += f"<tr><td>{i}</td><td>{DAYS[gd.weekday()]} {gd.day} {S.AR_MONTHS[gd.month - 1]}</td><td>{imsak}</td><td>{t['Fajr'][:5]}</td><td>{t['Dhuhr'][:5]}</td><td>{t['Asr'][:5]}</td><td><b>{t['Maghrib'][:5]}</b></td><td>{t['Isha'][:5]}</td></tr>"
    js = (f"<script>(function(){{var T=new Date('{d0.isoformat()}T00:00:00+02:00'),o=document.getElementById('sv-cd');function f(){{var s=(T-new Date())/1000|0;if(s<=0){{o.textContent='رمضان كريم 🌙';return}}var d=s/86400|0,h=s%86400/3600|0;o.textContent=d+' يوم و'+h+' ساعة'}}f();setInterval(f,60000)}})();</script>")
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">إمساكية شهر رمضان {hy} هـ في القاهرة<br>أول أيام رمضان المتوقع فلكيًا: <b>{ar_date(d0)}</b><br>فاضل على رمضان: <b id="sv-cd">-</b><br><small>المواعيد بتوقيت القاهرة وبطريقة الهيئة المصرية العامة للمساحة · آخر تحديث {ar_date(now.date())}</small></div>
{js}
<h2>إمساكية رمضان {d0.year} في القاهرة</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>اليوم</th><th>التاريخ</th><th>الإمساك</th><th>الفجر</th><th>الظهر</th><th>العصر</th><th>المغرب (الفطار)</th><th>العشاء</th></tr></thead><tbody>{tr}</tbody></table></div>
<p class="sv-note">الإمساك قبل الفجر بـ 10 دقايق. أول يوم رمضان محسوب فلكيًا، والموعد النهائي بتعلنه دار الإفتاء بعد استطلاع الهلال. ولمواعيد المحافظات التانية شوف <a href="{SITE}/p/prayer-times-egypt.html">مواقيت الصلاة في محافظات مصر</a>.</p>
{S.faq([(f"إمتى أول يوم رمضان {d0.year}؟", f"أول أيام رمضان {hy} هـ متوقع فلكيًا يوم {ar_date(d0)}، والموعد النهائي بعد رؤية الهلال."),
        ("ميعاد الفطار في أول يوم رمضان كام؟", f"أذان المغرب في القاهرة أول يوم رمضان الساعة {days[0]['timings']['Maghrib'][:5]}."),
        ("ميعاد السحور والإمساك أول يوم كام؟", f"الإمساك الساعة {(datetime.datetime.strptime(days[0]['timings']['Fajr'][:5], '%H:%M') - datetime.timedelta(minutes=10)).strftime('%H:%M')} والفجر {days[0]['timings']['Fajr'][:5]}.")])}
<div class="sv-links"><a href="{SITE}/p/official-holidays-egypt.html">الإجازات الرسمية</a><a href="{SITE}/p/prayer-times-egypt.html">مواقيت الصلاة</a><a href="{SITE}/p/prayer-sa.html">مواقيت الصلاة في السعودية</a></div></div>"""
    return body, d0, hy


def build(only=None):
    now = datetime.datetime.now(S.CAIRO)
    out = {}
    if not only or "holidays" in only:
        out["holidays"] = holidays(now)
    if not only or "imsakia" in only:
        out["imsakia"] = imsakia(now)[0]
    return out


def main():
    if "--html" in sys.argv:
        k = sys.argv[sys.argv.index("--html") + 1]
        print(build([k])[k])
        return
    ids = S.PAGES.get("seasonal", {})
    tok = S.token()
    for k, body in build().items():
        pid = (ids.get(k) or {}).get("id")
        if not pid:
            print("no page id for", k)
            continue
        r = requests.patch(f"https://www.googleapis.com/blogger/v3/blogs/{S.BLOG}/pages/{pid}",
                           headers={"Authorization": "Bearer " + tok}, json={"content": body}, timeout=60)
        print(k, r.status_code if r.status_code >= 400 else "updated")


if __name__ == "__main__":
    main()
