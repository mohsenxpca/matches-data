"""Prayer times + weather page for each of Egypt's 27 governorates (/p/prayer-weather-<slug>.html).

Every page carries its own data: Aladhan timings and the month's calendar computed for the governorate capital's
coordinates (Egyptian General Authority of Survey method), and Open-Meteo current weather + 7-day forecast for the same
point. Runs with services.yml; page ids live in services_pages.json under "gov".
Usage: python governorates.py                 update all pages
       python governorates.py --html cairo    print one page
       python governorates.py --create        create the pages that have no id yet (then updates them)
"""
import datetime, json, math, sys, time
import requests
import services as S
from egypt_govs import GOVS, gov_url, gov_links_html

E, fmt, CSS, SITE = S.E, S.fmt, S.CSS, S.SITE
IMG = S.HERO_IMGS["prayer"]
UV = [(3, "منخفض"), (6, "متوسط"), (8, "عالي"), (11, "عالي جدًا"), (99, "خطير")]


def nearest(slug, n=6):
    me = next(g for g in GOVS if g[0] == slug)
    return sorted((g for g in GOVS if g[0] != slug), key=lambda g: math.hypot(g[3] - me[3], g[4] - me[4]))[:n]


def weather_all():
    d = S.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": ",".join(str(g[3]) for g in GOVS), "longitude": ",".join(str(g[4]) for g in GOVS),
        "current": "temperature_2m,apparent_temperature,weather_code,relative_humidity_2m,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,sunrise,sunset",
        "timezone": "Africa/Cairo", "forecast_days": 7})
    return {g[0]: x for g, x in zip(GOVS, d if isinstance(d, list) else [d])}


def prayers(lat, lon, now):
    t = S.get(f"https://api.aladhan.com/v1/timings/{now:%d-%m-%Y}", params={"latitude": lat, "longitude": lon, "method": 5})["data"]
    cal = S.get(f"https://api.aladhan.com/v1/calendar/{now.year}/{now.month}", params={"latitude": lat, "longitude": lon, "method": 5})["data"]
    h = t["date"]["hijri"]
    return {k: t["timings"][k][:5] for k, _ in S.PRAYERS}, f'{h["day"]} {h["month"]["ar"]} {h["year"]} هـ', cal


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def page(slug, gov, cap, now, T, hijri, cal, W, cairo_T):
    day = S.stamp(now).split(" الساعة")[0]
    nxt = next(((ar, T[k]) for k, ar in S.PRAYERS if k != "Sunrise" and T[k] > now.strftime("%H:%M")), ("الفجر", T["Fajr"]))
    cards = "".join(f'<div class="sv-card"><div class="k">{ar}</div><div class="v">{T[k]}</div></div>' for k, ar in S.PRAYERS)
    head = "".join(f"<th>{ar}</th>" for _, ar in S.PRAYERS)
    t2 = ""
    for d in cal:
        g = d["date"]["gregorian"]
        on = ' class="on"' if int(g["day"]) == now.day else ""
        t2 += f"<tr{on}><td>{int(g['day'])} {S.AR_MONTHS[now.month - 1]}</td><td>{d['date']['hijri']['day']} {E(d['date']['hijri']['month']['ar'])}</td>" + \
              "".join(f"<td>{d['timings'][k][:5]}</td>" for k, _ in S.PRAYERS) + "</tr>"
    cur, dd = W["current"], W["daily"]
    ic, tx = S.WCODE.get(cur["weather_code"], ("🌡️", ""))
    temp, feel = round(cur["temperature_2m"]), round(cur["apparent_temperature"])
    rain0 = dd["precipitation_probability_max"][0] or 0
    uv0 = dd["uv_index_max"][0] or 0
    uv_t = next(t for lim, t in UV if uv0 < lim)
    wt = "".join(f"<tr{' class=on' if i == 0 else ''}><td>{S.AR_DAYS[(now + datetime.timedelta(days=i)).weekday()]}</td>"
                 f"<td>{S.WCODE.get(dd['weather_code'][i], ('🌡️', ''))[0]} {S.WCODE.get(dd['weather_code'][i], ('', ''))[1]}</td>"
                 f"<td>{round(dd['temperature_2m_max'][i])}°</td><td>{round(dd['temperature_2m_min'][i])}°</td>"
                 f"<td>{dd['precipitation_probability_max'][i] or 0}%</td></tr>" for i in range(7))
    sunrise, sunset = dd["sunrise"][0][-5:], dd["sunset"][0][-5:]
    diff = mins(T["Maghrib"]) - mins(cairo_T["Maghrib"])
    vs = "" if slug == "cairo" else (
        f"<p>أذان المغرب في {gov} النهارده {'قبل' if diff < 0 else 'بعد'} القاهرة بـ "
        f"{'دقيقة واحدة' if abs(diff) == 1 else 'دقيقتين' if abs(diff) == 2 else f'{abs(diff)} دقائق' if abs(diff) <= 10 else f'{abs(diff)} دقيقة'}"
        f" ({T['Maghrib']} في {cap} و{cairo_T['Maghrib']} في القاهرة)، والفرق ده بسبب اختلاف مكان المحافظة شرقًا وغربًا وشمالًا وجنوبًا"
        f" عن القاهرة، وبيتغير على مدار السنة.</p>" if diff else f"<p>أذان المغرب في {gov} النهارده في نفس ميعاد القاهرة تقريبًا ({T['Maghrib']}).</p>")
    near = "".join(f'<a href="{gov_url(g[0])}">{g[1]}</a>' for g in nearest(slug))
    desc = (f"مواقيت الصلاة في {gov} اليوم: الفجر {T['Fajr']} والمغرب {T['Maghrib']}، والطقس الآن {temp}° {tx}"
            f" مع توقعات 7 أيام وإمساكية شهر {S.AR_MONTHS[now.month - 1]} لـ{cap}.")
    js_next = (f"<script>(function(){{var T={json.dumps(T)},N={json.dumps(dict(S.PRAYERS))},n=new Date(new Date().toLocaleString('en-US',{{timeZone:'Africa/Cairo'}})),"
               "h=('0'+n.getHours()).slice(-2)+':'+('0'+n.getMinutes()).slice(-2),k=['Fajr','Dhuhr','Asr','Maghrib','Isha'].find(function(x){return T[x]>h})||'Fajr';"
               "document.getElementById('sv-next').textContent=N[k]+' '+T[k];})();</script>")
    tool = (f'<div class="sv-tool"><b>أخرج إمتى؟</b> اختار اليوم: <select id="sv-d">'
            + "".join(f'<option value="{i}">{S.AR_DAYS[(now + datetime.timedelta(days=i)).weekday()]}</option>' for i in range(7))
            + '</select><div class="out" id="sv-o"></div></div>'
            f"<script>(function(){{var X={json.dumps([round(v) for v in dd['temperature_2m_max']])},M={json.dumps([round(v) for v in dd['temperature_2m_min']])},"
            f"R={json.dumps([v or 0 for v in dd['precipitation_probability_max']])},s=document.getElementById('sv-d'),o=document.getElementById('sv-o');"
            "function f(){var i=+s.value,x=X[i],m=M[i],r=R[i];o.textContent='العظمى '+x+'° والصغرى '+m+'°: '+(r>=50?'غالبًا هتمطر، خد شمسية. ':'')+"
            "(x>=33?'حر، لبس خفيف واشرب مية كتير':x>=26?'الجو دافي، لبس خفيف':x>=20?'الجو لطيف، وخد جاكيت خفيف بالليل':'الجو برد، البس تقيل')}"
            "s.onchange=f;f();})();</script>")
    return f"""{CSS}<span class="ea-desc" hidden>{E(desc)}</span><div class="sv">
<div class="sv-hero">مواقيت الصلاة في {gov} اليوم <b>{day}</b> الموافق <b>{hijri}</b><br>الصلاة الجاية: <b id="sv-next">{nxt[0]} {nxt[1]}</b> · الجو دلوقتي <b>{ic} {temp}°</b> {tx}<br><small>محسوبة لمدينة {cap} · آخر تحديث: {S.stamp(now)} بتوقيت القاهرة</small></div>
{IMG}
<h2>مواقيت الصلاة في {gov} النهارده</h2>
<div class="sv-grid">{cards}</div>
{js_next}
{vs}
<h2>حالة الطقس في {gov} الآن</h2>
<div class="sv-grid"><div class="sv-card"><div class="k">الحرارة</div><div class="v">{ic} {temp}°</div><div class="k">{tx}</div></div>
<div class="sv-card"><div class="k">الإحساس الفعلي</div><div class="v">{feel}°</div></div>
<div class="sv-card"><div class="k">الرطوبة</div><div class="v">{cur['relative_humidity_2m']}%</div></div>
<div class="sv-card"><div class="k">الرياح</div><div class="v">{round(cur['wind_speed_10m'])}</div><div class="k">كم/س</div></div>
<div class="sv-card"><div class="k">احتمال المطر النهارده</div><div class="v">{rain0}%</div></div>
<div class="sv-card"><div class="k">الأشعة فوق البنفسجية</div><div class="v">{round(uv0)}</div><div class="k">{uv_t}</div></div></div>
<p>الشمس بتشرق في {cap} النهارده الساعة {sunrise} وبتغرب {sunset}، والعظمى المتوقعة {round(dd['temperature_2m_max'][0])}° والصغرى {round(dd['temperature_2m_min'][0])}°.</p>
{tool}
<h2>توقعات الطقس في {gov} لمدة 7 أيام</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>اليوم</th><th>الحالة</th><th>العظمى</th><th>الصغرى</th><th>المطر</th></tr></thead><tbody>{wt}</tbody></table></div>
<h2>إمساكية ومواقيت الصلاة في {gov} لشهر {S.AR_MONTHS[now.month - 1]} {now.year}</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>اليوم</th><th>هجري</th>{head}</tr></thead><tbody>{t2}</tbody></table></div>
<p class="sv-note">مواقيت الصلاة محسوبة لإحداثيات مدينة {cap} بطريقة الهيئة المصرية العامة للمساحة (الفجر 19.5° والعشاء 17.5°)، والمدن البعيدة عن العاصمة ممكن تفرق دقيقة أو اتنين. بيانات الطقس من نماذج الأرصاد العالمية Open-Meteo وبتتحدث كل كام ساعة.</p>
{S.faq([(f"ميعاد صلاة الفجر النهارده في {gov} كام؟", f"الفجر النهارده في {cap} الساعة {T['Fajr']} والشروق {T['Sunrise']}."),
        (f"ميعاد أذان المغرب في {gov} النهارده؟", f"أذان المغرب في {cap} النهارده الساعة {T['Maghrib']}، والعشاء {T['Isha']}."),
        (f"درجة الحرارة في {gov} النهارده كام؟", f"الحرارة دلوقتي {temp}° ({tx})، والعظمى المتوقعة {round(dd['temperature_2m_max'][0])}° والصغرى {round(dd['temperature_2m_min'][0])}°."),
        (f"هل في مطر في {gov} النهارده؟", f"احتمال المطر النهارده في {cap} حوالي {rain0}%."),
        ("الصفحة بتتحدث إمتى؟", "المواقيت بتتحدث كل يوم، والطقس كل كام ساعة.")])}
<h2>محافظات قريبة من {gov}</h2><div class="sv-links">{near}</div>
<div class="sv-links"><a href="{SITE}/p/prayer-times-egypt.html">مواقيت الصلاة في مصر</a><a href="{SITE}/p/weather-egypt.html">الطقس في مصر</a><a href="{SITE}/p/ramadan-imsakia-egypt.html">إمساكية رمضان</a><a href="{SITE}/p/official-holidays-egypt.html">الإجازات الرسمية</a></div>
{gov_links_html(slug)}</div>"""


def title(gov):
    return f"مواقيت الصلاة والطقس في {gov} اليوم: الفجر والمغرب وتوقعات 7 أيام"


def build(only=None):
    now = datetime.datetime.now(S.CAIRO)
    W = weather_all()
    P = {}
    for slug, gov, cap, lat, lon in GOVS:
        if only and slug not in only and slug != "cairo":
            continue
        P[slug] = prayers(lat, lon, now)
        time.sleep(0.4)
    return {slug: page(slug, gov, cap, now, *P[slug], W[slug], P["cairo"][0])
            for slug, gov, cap, *_ in GOVS if slug in P and (not only or slug in only)}


def api(method, path, tok, body=None, params=None):
    for wait in (30, 90, 240, 0):
        r = requests.request(method, f"https://www.googleapis.com/blogger/v3/blogs/{S.BLOG}{path}", params=params,
                             headers={"Authorization": "Bearer " + tok}, json=body, timeout=60)
        if r.status_code != 429 or not wait:
            break
        time.sleep(wait)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text[:200]}")
    return r.json() if r.text else {}


def main(token=None):
    if "--html" in sys.argv:
        k = sys.argv[sys.argv.index("--html") + 1]
        print(build([k])[k])
        return
    ids = S.PAGES.setdefault("gov", {})
    pages = build()
    tok = token() if token else S.token()
    for slug, gov, *_ in GOVS:
        pid = (ids.get(slug) or {}).get("id")
        if not pid:
            if "--create" not in sys.argv:
                print("no page id for", slug)
                continue
            p = api("POST", "/pages", tok, {"title": f"prayer weather {slug}", "content": pages[slug]}, {"isDraft": "false"})
            ids[slug] = {"id": p["id"], "url": p["url"]}
            json.dump(S.PAGES, open("services_pages.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            api("PATCH", f"/pages/{p['id']}", tok, {"title": title(gov)})
            print(slug, "created", p["url"])
        else:
            api("PATCH", f"/pages/{pid}", tok, {"content": pages[slug], "title": title(gov)})
            print(slug, "updated")
        time.sleep(2)


if __name__ == "__main__":
    main()
