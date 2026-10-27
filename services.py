"""Egyptaway service pages, refreshed automatically on GitHub Actions (.github/workflows/services.yml):
  /p/prayer-times-egypt.html   مواقيت الصلاة   (Aladhan, Egyptian General Authority of Survey method)
  /p/currency-prices-egypt.html أسعار العملات   (exchangerate-api open rates)
  /p/gold-prices-egypt.html     أسعار الذهب     (XAU/USD spot x USD/EGP, clearly labelled as world-market based)
  /p/weather-egypt.html         الطقس           (Open-Meteo)
Each page is plain HTML (indexable) rewritten through the Blogger API; a daily snapshot goes to services_history.json.
Usage: python services.py [--html KEY] [--only KEY,KEY]
"""
import datetime, html, json, os, sys, time
from zoneinfo import ZoneInfo
import requests

BLOG = "8325646053257070334"
SITE = "https://www.egyptaway.com"
CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (compatible; EgyptawayBot/1.0)"}
PAGES = json.load(open("services_pages.json", encoding="utf-8")) if os.path.exists("services_pages.json") else {}
AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
CITIES = [("Cairo", "القاهرة", 30.0444, 31.2357), ("Giza", "الجيزة", 30.0131, 31.2089), ("Alexandria", "الإسكندرية", 31.2001, 29.9187),
          ("Port Said", "بورسعيد", 31.2653, 32.3019), ("Suez", "السويس", 29.9668, 32.5498), ("Ismailia", "الإسماعيلية", 30.5965, 32.2715),
          ("Mansoura", "المنصورة", 31.0409, 31.3785), ("Tanta", "طنطا", 30.7865, 31.0004), ("Asyut", "أسيوط", 27.1783, 31.1859),
          ("Luxor", "الأقصر", 25.6872, 32.6396), ("Aswan", "أسوان", 24.0889, 32.8998), ("Hurghada", "الغردقة", 27.2579, 33.8116)]
PRAYERS = [("Fajr", "الفجر"), ("Sunrise", "الشروق"), ("Dhuhr", "الظهر"), ("Asr", "العصر"), ("Maghrib", "المغرب"), ("Isha", "العشاء")]
CURR = [("USD", "الدولار الأمريكي", "🇺🇸"), ("EUR", "اليورو", "🇪🇺"), ("SAR", "الريال السعودي", "🇸🇦"), ("AED", "الدرهم الإماراتي", "🇦🇪"),
        ("KWD", "الدينار الكويتي", "🇰🇼"), ("GBP", "الجنيه الإسترليني", "🇬🇧"), ("QAR", "الريال القطري", "🇶🇦"),
        ("JOD", "الدينار الأردني", "🇯🇴"), ("OMR", "الريال العماني", "🇴🇲"), ("BHD", "الدينار البحريني", "🇧🇭"), ("CNY", "اليوان الصيني", "🇨🇳"),
        ("TRY", "الليرة التركية", "🇹🇷")]
WCODE = {0: ("☀️", "صافي"), 1: ("🌤️", "صافي غالبًا"), 2: ("⛅", "غائم جزئيًا"), 3: ("☁️", "غائم"), 45: ("🌫️", "شبورة"), 48: ("🌫️", "شبورة"),
         51: ("🌦️", "رذاذ خفيف"), 53: ("🌦️", "رذاذ"), 55: ("🌧️", "رذاذ كثيف"), 61: ("🌧️", "مطر خفيف"), 63: ("🌧️", "مطر"), 65: ("🌧️", "مطر غزير"),
         80: ("🌦️", "زخات مطر"), 81: ("🌧️", "زخات مطر"), 82: ("⛈️", "زخات قوية"), 95: ("⛈️", "عاصفة رعدية"), 96: ("⛈️", "عاصفة رعدية"), 99: ("⛈️", "عاصفة رعدية")}

E = html.escape
CSS = ("<style>.sv{--n:#1f2a44;--g:#f59e0b;--o:#ea580c;--c:#fff7ed}.sv-hero{background:linear-gradient(135deg,#1f2a44,#2f3f66);color:#fff;border-radius:16px;"
       "padding:18px;margin:10px 0 16px}.sv-hero b{color:#f59e0b}.sv-hero small{opacity:.8}.sv-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:12px 0}"
       ".sv-card{border:1px solid #f3d9a8;border-radius:14px;padding:12px;text-align:center;background:#fff}.sv-card .k{font-size:13px;color:#6b7280}"
       ".sv-card .v{font-size:22px;font-weight:800;color:#1f2a44;margin-top:4px}.sv-t{width:100%;border-collapse:collapse;font-size:15px;margin:12px 0}"
       ".sv-t th{background:#1f2a44;color:#fff;padding:8px 5px}.sv-t td{padding:7px 5px;border-bottom:1px solid #f1f1f1;text-align:center}"
       ".sv-t tr.on td{background:#fff7ed;font-weight:700}.sv-wrap{overflow-x:auto}.sv-tool{background:#fff7ed;border:1px solid #f3d9a8;border-radius:14px;padding:14px;margin:14px 0}"
       ".sv-tool select,.sv-tool input{font:inherit;padding:8px;border:1px solid #f3d9a8;border-radius:10px;margin:4px;min-width:120px}"
       ".sv-tool .out{font-size:20px;font-weight:800;color:#c2410c;margin-top:8px}.sv-links{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}"
       ".sv-links a{background:#1f2a44;color:#fff!important;border-radius:999px;padding:7px 14px;text-decoration:none!important;font-size:14px}"
       ".sv-note{font-size:13px;color:#6b7280}</style>")


def get(url, **kw):
    for t in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=40, **kw)
            r.raise_for_status()
            return r.json()
        except Exception:
            if t == 2:
                raise
            time.sleep(5)


def stamp(now):
    return f"{AR_DAYS[now.weekday()]} {now.day} {AR_MONTHS[now.month - 1]} {now.year} الساعة {now:%H:%M}"


def fmt(x, d=2):
    return f"{x:,.{d}f}"


def links(skip):
    L = [("prayer", "مواقيت الصلاة", "/p/prayer-times-egypt.html"), ("currency", "أسعار العملات", "/p/currency-prices-egypt.html"),
         ("gold", "أسعار الذهب", "/p/gold-prices-egypt.html"), ("weather", "الطقس", "/p/weather-egypt.html"),
         ("m", "مواعيد المباريات", "/p/matches-today.html"), ("gsa", "الذهب في السعودية", "/p/gold-sa.html"),
         ("gae", "الذهب في الإمارات", "/p/gold-ae.html"), ("psa", "الصلاة في السعودية", "/p/prayer-sa.html")]
    return '<div class="sv-links">' + "".join(f'<a href="{SITE}{u}">{t}</a>' for k, t, u in L if k != skip) + "</div>"


def faq(items):
    return "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in items)


# ---------------------------------------------------------------- prayer
def prayer(now):
    rows, hijri = [], ""
    for en, ar, *_ in CITIES:
        d = get("https://api.aladhan.com/v1/timingsByCity", params={"city": en, "country": "Egypt", "method": 5})["data"]
        rows.append((ar, {k: d["timings"][k][:5] for k, _ in PRAYERS}))
        if not hijri:
            h = d["date"]["hijri"]
            hijri = f'{h["day"]} {h["month"]["ar"]} {h["year"]} هـ'
    cal = get(f"https://api.aladhan.com/v1/calendarByCity/{now.year}/{now.month}",
              params={"city": "Cairo", "country": "Egypt", "method": 5})["data"]
    cairo = rows[0][1]
    nxt = next(((ar, cairo[k]) for k, ar in PRAYERS if k != "Sunrise" and cairo[k] > now.strftime("%H:%M")), ("الفجر", cairo["Fajr"]))
    cards = "".join(f'<div class="sv-card"><div class="k">{ar}</div><div class="v">{cairo[k]}</div></div>' for k, ar in PRAYERS)
    t1 = "".join(f"<tr><td><b>{E(c)}</b></td>" + "".join(f"<td>{t[k]}</td>" for k, _ in PRAYERS) + "</tr>" for c, t in rows)
    t2 = ""
    for day in cal:
        g = day["date"]["gregorian"]
        on = ' class="on"' if int(g["day"]) == now.day else ""
        t2 += f"<tr{on}><td>{int(g['day'])} {AR_MONTHS[now.month - 1]}</td><td>{day['date']['hijri']['day']} {E(day['date']['hijri']['month']['ar'])}</td>" + \
              "".join(f"<td>{day['timings'][k][:5]}</td>" for k, _ in PRAYERS) + "</tr>"
    head = "".join(f"<th>{ar}</th>" for _, ar in PRAYERS)
    opts = "".join(f'<option value="{i}">{E(c)}</option>' for i, (c, _) in enumerate(rows))
    data = json.dumps([t for _, t in rows])
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">مواقيت الصلاة في القاهرة اليوم <b>{stamp(now).split(' الساعة')[0]}</b> الموافق <b>{hijri}</b><br>الصلاة الجاية: <b id="sv-next">{nxt[0]} {nxt[1]}</b><br><small>آخر تحديث: {stamp(now)} بتوقيت القاهرة</small></div>
<div class="sv-grid">{cards}</div>
<script>(function(){{var T={json.dumps(cairo)},N={json.dumps(dict(PRAYERS))},n=new Date(new Date().toLocaleString("en-US",{{timeZone:"Africa/Cairo"}})),h=("0"+n.getHours()).slice(-2)+":"+("0"+n.getMinutes()).slice(-2),k=["Fajr","Dhuhr","Asr","Maghrib","Isha"].find(function(x){{return T[x]>h}})||"Fajr";document.getElementById("sv-next").textContent=N[k]+" "+T[k];}})();</script>
<div class="sv-tool"><b>مواقيت الصلاة في محافظتك:</b> <select id="sv-city">{opts}</select><div class="out" id="sv-out"></div></div>
<script>(function(){{var D={data},N={json.dumps([ar for _, ar in PRAYERS])},K={json.dumps([k for k, _ in PRAYERS])},s=document.getElementById('sv-city'),o=document.getElementById('sv-out');function f(){{var t=D[s.value];o.innerHTML=K.map(function(k,i){{return N[i]+' '+t[k]}}).join(' · ')}}s.onchange=f;f();}})();</script>
<h2>مواقيت الصلاة اليوم في محافظات مصر</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>المحافظة</th>{head}</tr></thead><tbody>{t1}</tbody></table></div>
<h2>إمساكية ومواقيت الصلاة في القاهرة لشهر {AR_MONTHS[now.month - 1]} {now.year}</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>اليوم</th><th>هجري</th>{head}</tr></thead><tbody>{t2}</tbody></table></div>
<p class="sv-note">المواعيد محسوبة بطريقة الهيئة المصرية العامة للمساحة (زاوية الفجر 19.5° والعشاء 17.5°)، وممكن تختلف دقيقة أو اتنين عن تقويم المسجد اللي جنبك.</p>
<h2>إزاي بيتحسب ميعاد كل صلاة؟</h2>
<p>الفجر بيبدأ لما الشمس تكون تحت الأفق بزاوية معينة قبل الشروق، والظهر بعد ما الشمس تعدّي منتصف السما، والعصر لما ظل الحاجة يبقى قدها، والمغرب مع غروب الشمس، والعشاء لما يختفي الشفق الأحمر. وعشان كده المواعيد بتتغير كل يوم وبتختلف من محافظة للتانية حسب مكانها.</p>
{faq([("ميعاد صلاة الفجر النهارده في القاهرة كام؟", f"صلاة الفجر النهارده في القاهرة الساعة {cairo['Fajr']} والشروق {cairo['Sunrise']}."),
      ("ميعاد أذان المغرب النهارده كام؟", f"أذان المغرب في القاهرة النهارده الساعة {cairo['Maghrib']}."),
      ("المواعيد دي بتتحدث إمتى؟", "الصفحة بتتحدث لوحدها كل يوم بعد نص الليل.")])}
{links("prayer")}</div>"""
    return body, {"hijri": hijri, "cairo": cairo}


# ---------------------------------------------------------------- currency
def fx():
    d = get("https://open.er-api.com/v6/latest/USD")
    r = d["rates"]
    egp = r["EGP"]
    return {c: egp / r[c] for c, _, _ in CURR if c in r}, d.get("time_last_update_unix")


def currency(now, rates, prev):
    cards = "".join(f'<div class="sv-card"><div class="k">{f} {E(n)}</div><div class="v" data-fx="{c}">{fmt(rates[c])}</div><div class="k">جنيه</div></div>'
                    for c, n, f in CURR[:6] if c in rates)
    def chg(c):
        if not prev or c not in prev:
            return "-"
        d = rates[c] - prev[c]
        return ("▲ " if d > 0 else "▼ " if d < 0 else "") + fmt(abs(d), 3)
    tr = "".join(f"<tr><td>{f} <b>{E(n)}</b></td><td data-fx='{c}' data-n='3'>{fmt(rates[c], 3)}</td><td>{fmt(1 / rates[c], 4)}</td><td>{chg(c)}</td></tr>"
                 for c, n, f in CURR if c in rates)
    opts = "".join(f'<option value="{c}">{E(n)}</option>' for c, n, _ in CURR if c in rates)
    usd = rates["USD"]
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">سعر الدولار اليوم في مصر <b><span data-fx="USD">{fmt(usd)}</span> جنيه</b> · {stamp(now)}<br><small>سعر الصرف الرسمي في مصر · الصفحة بتشيّك على السعر كل دقيقة · آخر تحديث <span id="sv-upd">{now:%H:%M}</span></small></div>
<div class="sv-grid">{cards}</div>
<div class="sv-tool"><b>حوّل بين العملات والجنيه:</b><br><input id="sv-a" type="number" value="100" min="0"> <select id="sv-c">{opts}</select>
<select id="sv-d"><option value="1">إلى جنيه مصري</option><option value="0">من جنيه مصري</option></select><div class="out" id="sv-r"></div></div>
<script>(function(){{var R0={json.dumps({c: round(v, 5) for c, v in rates.items()})},N={json.dumps({c: n for c, n, _ in CURR})};function g(i){{return document.getElementById(i)}}function f(){{var R=(window.__G&&window.__G.fx)||R0,a=parseFloat(g('sv-a').value)||0,c=g('sv-c').value,r=R[c];g('sv-r').textContent=g('sv-d').value=='1'?(a+' '+N[c]+' = '+(a*r).toFixed(2)+' جنيه'):(a+' جنيه = '+(a/r).toFixed(3)+' '+N[c])}}['sv-a','sv-c','sv-d'].forEach(function(i){{g(i).oninput=f;g(i).onchange=f}});window.__onlive=f;f();}})();</script>
{LIVE_JS}
<h2>أسعار العملات مقابل الجنيه المصري اليوم</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>العملة</th><th>بالجنيه</th><th>الجنيه يساوي</th><th>التغيير من امبارح</th></tr></thead><tbody>{tr}</tbody></table></div>
<p class="sv-note">الأسعار دي متوسط سعر الصرف العالمي، وأسعار البيع والشراء في البنوك وشركات الصرافة بتختلف عنها شوية حسب كل بنك.</p>
<h2>إيه اللي بيأثر على سعر الدولار في مصر؟</h2>
<p>سعر الصرف بيتأثر بحجم الطلب على الدولار في الاستيراد، وتحويلات المصريين في الخارج، وإيرادات السياحة وقناة السويس، وقرارات البنك المركزي في الفايدة. ولو بتحوّل فلوس أو بتشتري من برا، قارن سعر أكتر من بنك قبل ما تحوّل.</p>
<h2>تحويلات شائعة</h2><div class="sv-links">{"".join(f'<a href="{SITE}/p/{c2.lower()}-{a2}-to-egp.html">{a2:,} {CUR_SHORT[c2]} كام جنيه</a>' for c2, a2 in CONV)}</div>
{faq([("سعر الدولار النهارده كام في مصر؟", f"متوسط سعر الدولار النهارده {fmt(usd)} جنيه (آخر تحديث {stamp(now)})."),
      ("سعر الريال السعودي النهارده كام؟", f"الريال السعودي النهارده حوالي {fmt(rates.get('SAR', 0))} جنيه."),
      ("الأسعار بتتحدث إمتى؟", "الصفحة بتتحدث لوحدها كذا مرة في اليوم.")])}
{links("currency")}</div>"""
    return body


# ---------------------------------------------------------------- gold
def xau():
    d = get("https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD")
    p = d[0]["spreadProfilePrices"][0]
    return (p["bid"] + p["ask"]) / 2


LIVE = "https://raw.githubusercontent.com/mohsenxpca/matches-data/live/live.json"
LIVE_JS = """<script>(function(){var L='""" + LIVE + """';function upd(){Promise.all([fetch(L+'?t='+Math.floor(Date.now()/60000)).then(function(r){return r.json()}),fetch('https://api.gold-api.com/price/XAU').then(function(r){return r.json()}).catch(function(){return null})]).then(function(a){var d=a[0],x=a[1],k=(x&&x.price&&d.xau)?x.price/d.xau:1;window.__G=d;window.__K=k;[].forEach.call(document.querySelectorAll('[data-g]'),function(el){var p=el.getAttribute('data-g').split('.'),v=d.gold[p[0]]&&d.gold[p[0]][p[1]];if(v)el.textContent=Math.round(v*k).toLocaleString('en-US')});[].forEach.call(document.querySelectorAll('[data-fx]'),function(el){var c=el.getAttribute('data-fx'),v=d.fx&&d.fx[c];if(v)el.textContent=v.toFixed(el.getAttribute('data-n')?+el.getAttribute('data-n'):2)});var u=document.getElementById('sv-upd');if(u)u.textContent=new Date().toLocaleTimeString('ar-EG-u-nu-latn',{hour:'2-digit',minute:'2-digit',timeZone:'Africa/Cairo'});if(window.__onlive)window.__onlive()}).catch(function(){})}upd();setInterval(upd,60000);})();</script>"""


def gold(now, oz_usd, usd, prev):
    from goldlive import market
    m = market()
    K = [("24", "عيار 24"), ("22", "عيار 22"), ("21", "عيار 21"), ("18", "عيار 18"), ("14", "عيار 14"), ("12", "عيار 12")]
    K = [(k, n) for k, n in K if k in m]
    pound = m.get("pound")
    cards = "".join(f'<div class="sv-card"><div class="k">جرام {n}</div><div class="v" data-g="{k}.sell">{fmt(m[k]["sell"], 0)}</div>'
                    f'<div class="k">شراء منك: <span data-g="{k}.buy">{fmt(m[k]["buy"], 0)}</span></div></div>' for k, n in K if k in ("24", "21", "18"))
    if pound:
        cards += (f'<div class="sv-card"><div class="k">الجنيه الذهب</div><div class="v" data-g="pound.sell">{fmt(pound["sell"], 0)}</div>'
                  f'<div class="k">شراء منك: <span data-g="pound.buy">{fmt(pound["buy"], 0)}</span></div></div>')
    p21 = prev.get("g21") if prev else None
    trend = ""
    if p21:
        d = m["21"]["sell"] - p21
        trend = f"، {'زيادة' if d > 0 else 'انخفاض'} {fmt(abs(d), 0)} جنيه عن امبارح" if abs(d) >= 1 else "، تقريبًا نفس سعر امبارح"
    tr = "".join(f'<tr><td><b>{n}</b></td><td data-g="{k}.sell">{fmt(m[k]["sell"], 0)}</td><td data-g="{k}.buy">{fmt(m[k]["buy"], 0)}</td></tr>' for k, n in K)
    if pound:
        tr += f'<tr><td><b>الجنيه الذهب (8 جرام عيار 21)</b></td><td data-g="pound.sell">{fmt(pound["sell"], 0)}</td><td data-g="pound.buy">{fmt(pound["buy"], 0)}</td></tr>'
    tr += f'<tr><td><b>الأونصة عالميًا</b></td><td colspan="2">{fmt(oz_usd, 0)} دولار = {fmt(oz_usd * usd, 0)} جنيه</td></tr>'
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">سعر جرام الذهب عيار 21 في مصر اليوم <b><span data-g="21.sell">{fmt(m["21"]["sell"], 0)}</span> جنيه</b>{trend}<br><small>أسعار سوق الصاغة في مصر (بيع وشراء من غير مصنعية) · بتتحدث كل دقيقة · آخر تحديث <span id="sv-upd">{now:%H:%M}</span></small></div>
<div class="sv-grid">{cards}</div>
<div class="sv-tool"><b>احسب تمن الذهب اللي معاك:</b><br><input id="sv-w" type="number" value="10" min="0" step="0.1"> جرام
<select id="sv-k">{"".join(f'<option value="{k}"{" selected" if k == "21" else ""}>{n}</option>' for k, n in K)}</select>
<select id="sv-s"><option value="buy">لو هتبيع (سعر الشراء منك)</option><option value="sell">لو هتشتري (سعر البيع)</option></select>
<div class="out" id="sv-g"></div><div class="sv-note">من غير المصنعية والدمغة.</div></div>
<script>(function(){{var B={json.dumps({k: m[k] for k, _ in K})};function g(i){{return document.getElementById(i)}}function f(){{var d=(window.__G&&window.__G.gold)||B,kk=window.__K||1,w=parseFloat(g('sv-w').value)||0,k=g('sv-k').value,s=g('sv-s').value;g('sv-g').textContent=Math.round(w*d[k][s]*kk).toLocaleString('en-US')+' جنيه'}}['sv-w','sv-k','sv-s'].forEach(function(i){{g(i).oninput=f;g(i).onchange=f}});window.__onlive=f;f();}})();</script>
{LIVE_JS}
<h2>أسعار الذهب في مصر اليوم بالجنيه</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>العيار</th><th>سعر البيع</th><th>سعر الشراء منك</th></tr></thead><tbody>{tr}</tbody></table></div>
<p class="sv-note">الأسعار دي أسعار سوق الذهب في مصر للجرام من غير مصنعية، وبتتحرك كل دقيقة مع سعر الأونصة العالمي. المصنعية والدمغة بتختلف من محل للتاني.</p>
<h2>الفرق بين عيار 24 و21 و18</h2>
<p>العيار بيقول نسبة الذهب الصافي في القطعة: عيار 24 ذهب صافي تقريبًا، وعيار 21 فيه 87.5% ذهب وده الأكتر انتشارًا في مصر، وعيار 18 فيه 75% ذهب وبيستخدم في الحلي الخفيفة. والجنيه الذهب وزنه 8 جرام عيار 21.</p>
<h2>إيه الفرق بين سعر البيع وسعر الشراء؟</h2>
<p>سعر البيع هو اللي بتشتري بيه الذهب من المحل، وسعر الشراء هو اللي المحل بيشتري بيه منك لو بعت. الفرق بينهم هو هامش التاجر، وفوق سعر البيع بتتحسب المصنعية حسب نوع القطعة.</p>
{faq([("سعر جرام الذهب عيار 21 النهارده كام؟", f"جرام عيار 21 النهارده بيتباع بحوالي {fmt(m['21']['sell'], 0)} جنيه ويتشري بحوالي {fmt(m['21']['buy'], 0)} جنيه من غير مصنعية."),
      ("سعر الجنيه الذهب النهارده كام؟", f"الجنيه الذهب حوالي {fmt(pound['sell'], 0) if pound else '-'} جنيه من غير مصنعية."),
      ("الأسعار بتتحدث كل قد إيه؟", "كل دقيقة وانت فاتح الصفحة.")])}
{links("gold")}</div>"""
    return body, {"g24": m["24"]["sell"], "g21": m["21"]["sell"], "oz_usd": round(oz_usd, 2)}

# ---------------------------------------------------------------- weather
def weather(now):
    lat = ",".join(str(c[2]) for c in CITIES)
    lon = ",".join(str(c[3]) for c in CITIES)
    data = get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min", "timezone": "Africa/Cairo", "forecast_days": 7})
    if isinstance(data, dict):
        data = [data]
    cards, tr = "", ""
    for (en, ar, *_), d in zip(CITIES, data):
        cur = d["current"]
        ic, tx = WCODE.get(cur["weather_code"], ("🌡️", ""))
        cards += f'<div class="sv-card"><div class="k">{ar}</div><div class="v">{ic} {round(cur["temperature_2m"])}°</div><div class="k">{tx}</div></div>'
        dd = d["daily"]
        tr += f"<tr><td><b>{ar}</b></td>" + "".join(
            f"<td>{WCODE.get(dd['weather_code'][i], ('🌡️',))[0]} {round(dd['temperature_2m_max'][i])}°/{round(dd['temperature_2m_min'][i])}°</td>" for i in range(7)) + "</tr>"
    days = "".join(f"<th>{AR_DAYS[(now + datetime.timedelta(days=i)).weekday()]}</th>" for i in range(7))
    c0 = data[0]["current"]
    ic, tx = WCODE.get(c0["weather_code"], ("🌡️", ""))
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">الطقس في القاهرة دلوقتي <b>{ic} {round(c0["temperature_2m"])}°</b> {tx} · الرطوبة {c0["relative_humidity_2m"]}% · الرياح {round(c0["wind_speed_10m"])} كم/س<br><small>آخر تحديث: {stamp(now)}</small></div>
<div class="sv-grid">{cards}</div>
<h2>توقعات الطقس في مصر لمدة 7 أيام</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>المحافظة</th>{days}</tr></thead><tbody>{tr}</tbody></table></div>
<p class="sv-note">العظمى/الصغرى بالدرجة المئوية. التوقعات بتتحدث لوحدها كل كام ساعة.</p>
<div class="sv-tool"><b>هل الجو محتاج جاكيت؟</b> <select id="sv-wc">{"".join(f'<option value="{round(d["current"]["temperature_2m"])}">{c[1]}</option>' for c, d in zip(CITIES, data))}</select><div class="out" id="sv-wo"></div></div>
<script>(function(){{var s=document.getElementById('sv-wc'),o=document.getElementById('sv-wo');function f(){{var t=+s.value;o.textContent=t>=30?'الجو حر، لبس خفيف واشرب مية كتير':t>=22?'الجو لطيف، لبس عادي':t>=16?'خد جاكيت خفيف معاك':'الجو برد، البس تقيل'}}s.onchange=f;f();}})();</script>
{faq([("درجة الحرارة في القاهرة النهارده كام؟", f"درجة الحرارة في القاهرة دلوقتي {round(c0['temperature_2m'])}° ({tx})."),
      ("التوقعات دي بتتحدث إمتى؟", "الصفحة بتتحدث لوحدها كل كام ساعة من بيانات الأرصاد العالمية.")])}
{links("weather")}</div>"""
    return body


# ---------------------------------------------------------------- publish
def token():
    def sec(n):
        return os.environ.get(n, "").strip().strip('"')
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": sec("BLOGGER_CLIENT_ID"), "client_secret": sec("BLOGGER_CLIENT_SECRET"),
        "refresh_token": sec("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google login failed ({r.status_code}): {r.text[:150]}")
    return r.json()["access_token"]


# ---------------------------------------------------------------- conversion pages ("100 دولار كام جنيه")
CONV = [("USD", 100), ("USD", 1000), ("SAR", 100), ("SAR", 1000), ("EUR", 100), ("AED", 100), ("AED", 1000), ("KWD", 100), ("GBP", 100)]
CUR_NAME = {c: n for c, n, _ in CURR}
CUR_SHORT = {"USD": "دولار", "SAR": "ريال سعودي", "EUR": "يورو", "AED": "درهم إماراتي", "KWD": "دينار كويتي", "GBP": "جنيه إسترليني"}


def conv_key(c, a):
    return f"{c}-{a}"


def convert(now, rates, c, amount):
    r = rates[c]
    short = CUR_SHORT[c]
    mult = [1, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
    t1 = "".join(f"<tr{' class=on' if m == amount else ''}><td>{m:,} {short}</td><td data-cx='{m}'>{fmt(m * r)} جنيه</td></tr>" for m in mult)
    egp = [100, 500, 1000, 5000, 10000, 50000, 100000]
    t2 = "".join(f"<tr><td>{m:,} جنيه</td><td data-cr='{m}'>{fmt(m / r)} {short}</td></tr>" for m in egp)
    others = "".join(f'<a href="{SITE}/p/{c2.lower()}-{a2}-to-egp.html">{a2:,} {CUR_SHORT[c2]}</a>' for c2, a2 in CONV if (c2, a2) != (c, amount))
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">{amount:,} {short} كام جنيه مصري النهارده؟<br><b style="font-size:28px"><span data-cx="{amount}">{fmt(amount * r)} جنيه</span></b><br><small>سعر {E(CUR_NAME[c])} = <span data-fx="{c}" data-n="4">{r:.4f}</span> جنيه · السعر الرسمي · بيتحدث كل دقيقة · آخر تحديث <span id="sv-upd">{now:%H:%M}</span></small></div>
<div class="sv-tool"><b>حوّل أي مبلغ:</b><br><input id="sv-a" type="number" value="{amount}" min="0"> {short} = <span class="out" id="sv-r"></span></div>
<script>(function(){{var C='{c}',R0={r:.6f};function rate(){{return (window.__G&&window.__G.fx&&window.__G.fx[C])||R0}}function g(i){{return document.getElementById(i)}}function f(){{var r=rate(),a=parseFloat(g('sv-a').value)||0;g('sv-r').textContent=(a*r).toLocaleString('en-US',{{maximumFractionDigits:2}})+' جنيه';[].forEach.call(document.querySelectorAll('[data-cx]'),function(e){{e.textContent=(+e.getAttribute('data-cx')*r).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})+' جنيه'}});[].forEach.call(document.querySelectorAll('[data-cr]'),function(e){{e.textContent=(+e.getAttribute('data-cr')/r).toLocaleString('en-US',{{maximumFractionDigits:2}})+' {short}'}})}}g('sv-a').oninput=f;window.__onlive=f;f();}})();</script>
{LIVE_JS}
<h2>جدول تحويل {E(CUR_NAME[c])} للجنيه المصري</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>المبلغ</th><th>بالجنيه المصري</th></tr></thead><tbody>{t1}</tbody></table></div>
<h2>الجنيه المصري كام {short}؟</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>بالجنيه</th><th>يساوي</th></tr></thead><tbody>{t2}</tbody></table></div>
<p class="sv-note">الأسعار دي سعر الصرف الرسمي، وأسعار البنوك وشركات الصرافة ممكن تزيد أو تقل شوية حسب كل بنك.</p>
<h2>تحويلات تانية</h2><div class="sv-links">{others}</div>
{faq([(f"{amount:,} {short} كام جنيه مصري؟", f"{amount:,} {short} يساوي حوالي {fmt(amount * r)} جنيه مصري بسعر الصرف الرسمي النهارده."),
      (f"سعر {CUR_NAME[c]} النهارده كام؟", f"{CUR_NAME[c]} النهارده حوالي {r:.2f} جنيه."),
      ("السعر بيتحدث كل قد إيه؟", "الصفحة بتشيّك على السعر كل دقيقة وانت فاتحها.")])}
{links("currency")}</div>"""
    return body


def build(keys):
    now = datetime.datetime.now(CAIRO)
    hist = json.load(open("services_history.json", encoding="utf-8")) if os.path.exists("services_history.json") else []
    yday = next((h for h in reversed(hist) if h["date"] < now.date().isoformat()), {})
    out, snap = {}, {"date": now.date().isoformat()}
    rates = None
    if "currency" in keys or "gold" in keys or "convert" in keys:
        rates, _ = fx()
        snap["fx"] = {c: round(v, 4) for c, v in rates.items()}
    if "prayer" in keys:
        out["prayer"], p = prayer(now)
        snap.update(p)
    if "currency" in keys:
        out["currency"] = currency(now, rates, yday.get("fx"))
    if "gold" in keys:
        out["gold"], g = gold(now, xau(), rates["USD"], yday)
        snap.update(g)
    if "weather" in keys:
        out["weather"] = weather(now)
    if "convert" in keys:
        for c, a in CONV:
            out[conv_key(c, a)] = convert(now, rates, c, a)
    hist = [h for h in hist if h["date"] != snap["date"]] + [{**next((h for h in hist if h["date"] == snap["date"]), {}), **snap}]
    json.dump(hist[-400:], open("services_history.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return out


def main():
    keys = ["prayer", "currency", "gold", "weather", "convert"]
    if "--only" in sys.argv:
        keys = sys.argv[sys.argv.index("--only") + 1].split(",")
    if "--html" in sys.argv:
        k = sys.argv[sys.argv.index("--html") + 1]
        print(build([k])[k])
        return
    pages = build(keys)
    tok = token()
    for k, body in pages.items():
        pid = (PAGES.get(k) or PAGES.get("conv", {}).get(k) or {}).get("id")
        if not pid:
            print("no page id for", k)
            continue
        r = requests.patch(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/pages/{pid}",
                           headers={"Authorization": "Bearer " + tok}, json={"content": body}, timeout=60)
        print(k, r.status_code if r.status_code >= 400 else "updated")
        time.sleep(3)


if __name__ == "__main__":
    main()
