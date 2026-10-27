"""Gulf service pages on Egyptaway: gold, prayer times and currency prices for Saudi Arabia, the UAE and Kuwait.

Same look and helpers as services.py; written in simple Modern Standard Arabic for Gulf readers. Gold is computed from the
world ounce price (XAU/USD) and the dollar peg of each currency, and says so on the page. Updated with services.py
(services.yml); page ids live in services_pages.json under "gulf".
Usage: python gulf.py            update all pages
       python gulf.py --html gold-sa   print one page
"""
import datetime, json, sys, time
from zoneinfo import ZoneInfo
import requests
import services as S

E, fmt, CSS, SITE = S.E, S.fmt, S.CSS, S.SITE
OZ = 31.1035
COUNTRIES = {
    "sa": {"name": "السعودية", "cur": "SAR", "cur_ar": "ريال", "cur_full": "الريال السعودي", "country": "Saudi Arabia", "method": 4,
           "tz": "Asia/Riyadh", "cities": [("Riyadh", "الرياض"), ("Jeddah", "جدة"), ("Makkah", "مكة المكرمة"), ("Madinah", "المدينة المنورة"),
                                           ("Dammam", "الدمام"), ("Taif", "الطائف"), ("Tabuk", "تبوك"), ("Abha", "أبها")]},
    "ae": {"name": "الإمارات", "cur": "AED", "cur_ar": "درهم", "cur_full": "الدرهم الإماراتي", "country": "United Arab Emirates", "method": 16,
           "tz": "Asia/Dubai", "cities": [("Dubai", "دبي"), ("Abu Dhabi", "أبوظبي"), ("Sharjah", "الشارقة"), ("Ajman", "عجمان"),
                                          ("Al Ain", "العين"), ("Ras Al Khaimah", "رأس الخيمة"), ("Fujairah", "الفجيرة")]},
    "kw": {"name": "الكويت", "cur": "KWD", "cur_ar": "دينار", "cur_full": "الدينار الكويتي", "country": "Kuwait", "method": 9,
           "tz": "Asia/Kuwait", "cities": [("Kuwait City", "مدينة الكويت"), ("Al Ahmadi", "الأحمدي"), ("Hawalli", "حولي"), ("Al Jahra", "الجهراء")]},
}
KARATS = [("24", 1.0), ("22", 22 / 24), ("21", 21 / 24), ("18", 18 / 24)]
FX_LIST = ["USD", "EUR", "GBP", "EGP", "SAR", "AED", "KWD", "QAR", "OMR", "BHD", "JOD", "TRY", "CNY", "INR", "PKR", "PHP"]
FX_AR = {"USD": "الدولار الأمريكي", "EUR": "اليورو", "GBP": "الجنيه الإسترليني", "EGP": "الجنيه المصري", "SAR": "الريال السعودي",
         "AED": "الدرهم الإماراتي", "KWD": "الدينار الكويتي", "QAR": "الريال القطري", "OMR": "الريال العماني", "BHD": "الدينار البحريني",
         "JOD": "الدينار الأردني", "TRY": "الليرة التركية", "CNY": "اليوان الصيني", "INR": "الروبية الهندية", "PKR": "الروبية الباكستانية",
         "PHP": "البيزو الفلبيني"}


def gulf_links(skip):
    L = []
    for cc, c in COUNTRIES.items():
        L += [(f"gold-{cc}", f"الذهب في {c['name']}"), (f"prayer-{cc}", f"الصلاة في {c['name']}"), (f"currency-{cc}", f"العملات في {c['name']}")]
    return '<h2>صفحات الخليج</h2><div class="sv-links">' + "".join(
        f'<a href="{SITE}/p/{k}.html">{t}</a>' for k, t in L if k != skip) + f'<a href="{SITE}/p/gold-prices-egypt.html">الذهب في مصر</a></div>'


def usd_rates():
    d = S.get("https://open.er-api.com/v6/latest/USD")
    return d["rates"]


def stamp(now):
    return f"{S.AR_DAYS[now.weekday()]} {now.day} {S.AR_MONTHS[now.month - 1]} {now.year}"


def gold(cc, now, oz_usd, R):
    c = COUNTRIES[cc]
    per_usd = R[c["cur"]]  # local units per 1 USD
    g = {k: oz_usd / OZ * p * per_usd for k, p in KARATS}
    dec = 3 if c["cur"] == "KWD" else 2
    cards = "".join(f'<div class="sv-card"><div class="k">جرام عيار {k}</div><div class="v" data-k="{p}">{fmt(g[k], dec)}</div><div class="k">{c["cur_ar"]}</div></div>'
                    for k, p in KARATS)
    tr = "".join(f'<tr><td><b>عيار {k}</b></td><td data-k="{p}">{fmt(g[k], dec)}</td><td data-k="{p * 8}">{fmt(g[k] * 8, dec)}</td><td data-k="{p * OZ}">{fmt(g[k] * OZ, dec)}</td></tr>'
                 for k, p in KARATS)
    js = (f"<script>(function(){{var B={oz_usd:.2f},U={per_usd:.6f},O={OZ},D={dec};function g(i){{return document.getElementById(i)}}"
          f"function put(x){{[].forEach.call(document.querySelectorAll('[data-k]'),function(e){{e.textContent=(x/O*U*+e.getAttribute('data-k')).toLocaleString('en-US',{{minimumFractionDigits:D,maximumFractionDigits:D}})}});"
          f"var w=parseFloat(g('sv-w').value)||0,k=+g('sv-k').value;g('sv-g').textContent=(w*x/O*U*k).toLocaleString('en-US',{{maximumFractionDigits:D}})+' {c['cur_ar']}';window.__X=x}}"
          f"function upd(){{fetch('https://api.gold-api.com/price/XAU').then(function(r){{return r.json()}}).then(function(d){{if(d&&d.price){{put(d.price);var u=g('sv-upd');if(u)u.textContent=new Date().toLocaleTimeString('ar-EG-u-nu-latn',{{hour:'2-digit',minute:'2-digit',timeZone:'{c['tz']}'}})}}}}).catch(function(){{}})}}"
          f"['sv-w','sv-k'].forEach(function(i){{g(i).oninput=function(){{put(window.__X||B)}};g(i).onchange=g(i).oninput}});put(B);upd();setInterval(upd,60000);}})();</script>")
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">سعر جرام الذهب عيار 21 في {c['name']} اليوم <b><span data-k="{21 / 24}">{fmt(g['21'], dec)}</span> {c['cur_ar']}</b> · عيار 24 <b><span data-k="1">{fmt(g['24'], dec)}</span> {c['cur_ar']}</b><br><small>{stamp(now)} · محسوب من سعر الأونصة العالمي ويتحدث كل دقيقة · آخر تحديث <span id="sv-upd">{now:%H:%M}</span></small></div>
<div class="sv-grid">{cards}</div>
<div class="sv-tool"><b>احسب قيمة الذهب الذي تملكه:</b><br><input id="sv-w" type="number" value="10" min="0" step="0.1"> جرام
<select id="sv-k">{"".join(f'<option value="{p}"{" selected" if k == "21" else ""}>عيار {k}</option>' for k, p in KARATS)}</select>
<div class="out" id="sv-g"></div><div class="sv-note">بدون المصنعية وضريبة القيمة المضافة.</div></div>
{js}
<h2>أسعار الذهب في {c['name']} اليوم بال{c['cur_ar']}</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>العيار</th><th>الجرام</th><th>8 جرام</th><th>الأونصة</th></tr></thead><tbody>{tr}</tbody></table></div>
<p class="sv-note">الأسعار محسوبة من سعر أونصة الذهب في البورصة العالمية ({fmt(oz_usd, 0)} دولار وقت التحديث) وسعر صرف {E(c['cur_full'])} مقابل الدولار، وهي أقرب لسعر الذهب الخام. أسعار محلات الذهب تضيف المصنعية وضريبة القيمة المضافة وتختلف من محل لآخر.</p>
<h2>كيف يُحسب سعر جرام الذهب؟</h2>
<p>سعر الجرام = سعر الأونصة بالدولار ÷ 31.1 جرام × نسبة نقاء العيار × سعر الدولار بال{c['cur_ar']}. عيار 24 ذهب خالص تقريبًا، وعيار 22 نسبته 91.7%، وعيار 21 نسبته 87.5%، وعيار 18 نسبته 75% وهو الأكثر استخدامًا في المجوهرات الحديثة.</p>
{S.faq([(f"كم سعر جرام الذهب عيار 21 في {c['name']} اليوم؟", f"حوالي {fmt(g['21'], dec)} {c['cur_ar']} للجرام بدون مصنعية حسب سعر الأونصة العالمي وقت التحديث."),
        (f"كم سعر جرام الذهب عيار 24 في {c['name']}؟", f"حوالي {fmt(g['24'], dec)} {c['cur_ar']} للجرام بدون مصنعية."),
        ("هل السعر يشمل المصنعية؟", "لا، السعر هنا لسعر الذهب نفسه، والمصنعية والضريبة تضاف في المحل.")])}
{gulf_links(f"gold-{cc}")}</div>"""
    return body


def prayer(cc, now):
    c = COUNTRIES[cc]
    rows, hijri = [], ""
    for en, ar in c["cities"]:
        d = S.get("https://api.aladhan.com/v1/timingsByCity", params={"city": en, "country": c["country"], "method": c["method"]})["data"]
        rows.append((ar, {k: d["timings"][k][:5] for k, _ in S.PRAYERS}))
        if not hijri:
            h = d["date"]["hijri"]
            hijri = f'{h["day"]} {h["month"]["ar"]} {h["year"]} هـ'
        time.sleep(0.5)
    cap, first = rows[0]
    cards = "".join(f'<div class="sv-card"><div class="k">{ar}</div><div class="v">{first[k]}</div></div>' for k, ar in S.PRAYERS)
    head = "".join(f"<th>{ar}</th>" for _, ar in S.PRAYERS)
    tr = "".join(f"<tr><td><b>{E(n)}</b></td>" + "".join(f"<td>{t[k]}</td>" for k, _ in S.PRAYERS) + "</tr>" for n, t in rows)
    opts = "".join(f'<option value="{i}">{E(n)}</option>' for i, (n, _) in enumerate(rows))
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">مواقيت الصلاة في {cap} اليوم <b>{stamp(now)}</b> الموافق <b>{hijri}</b><br>الصلاة القادمة: <b id="sv-next">-</b><br><small>بتوقيت {c['name']} المحلي · يتم التحديث يوميًا</small></div>
<div class="sv-grid">{cards}</div>
<script>(function(){{var T={json.dumps(first)},N={json.dumps(dict(S.PRAYERS))},n=new Date(new Date().toLocaleString("en-US",{{timeZone:"{c['tz']}"}})),h=("0"+n.getHours()).slice(-2)+":"+("0"+n.getMinutes()).slice(-2),k=["Fajr","Dhuhr","Asr","Maghrib","Isha"].find(function(x){{return T[x]>h}})||"Fajr";document.getElementById("sv-next").textContent=N[k]+" "+T[k];}})();</script>
<div class="sv-tool"><b>مواقيت الصلاة في مدينتك:</b> <select id="sv-city">{opts}</select><div class="out" id="sv-out"></div></div>
<script>(function(){{var D={json.dumps([t for _, t in rows])},N={json.dumps([ar for _, ar in S.PRAYERS])},K={json.dumps([k for k, _ in S.PRAYERS])},s=document.getElementById('sv-city'),o=document.getElementById('sv-out');function f(){{var t=D[s.value];o.innerHTML=K.map(function(k,i){{return N[i]+' '+t[k]}}).join(' · ')}}s.onchange=f;f();}})();</script>
<h2>مواقيت الصلاة اليوم في مدن {c['name']}</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>المدينة</th>{head}</tr></thead><tbody>{tr}</tbody></table></div>
<p class="sv-note">المواقيت محسوبة حسب طريقة الحساب المعتمدة في {c['name']}، وقد تختلف دقيقة أو دقيقتين عن تقويم المسجد القريب منك.</p>
{S.faq([(f"متى أذان الفجر اليوم في {cap}؟", f"أذان الفجر اليوم في {cap} الساعة {first['Fajr']} والشروق {first['Sunrise']}."),
        (f"متى أذان المغرب اليوم في {cap}؟", f"أذان المغرب اليوم في {cap} الساعة {first['Maghrib']}."),
        ("متى يتم تحديث المواقيت؟", "تتحدث الصفحة تلقائيًا كل يوم.")])}
{gulf_links(f"prayer-{cc}")}</div>"""
    return body


def currency(cc, now, R):
    c = COUNTRIES[cc]
    base = R[c["cur"]]  # local per USD
    rate = {x: base / R[x] for x in FX_LIST if x in R and x != c["cur"]}  # local units per 1 unit of x
    dec = 3 if c["cur"] == "KWD" else 2
    cards = "".join(f'<div class="sv-card"><div class="k">{E(FX_AR[x])}</div><div class="v">{fmt(rate[x], 4 if rate[x] < 1 else dec)}</div><div class="k">{c["cur_ar"]}</div></div>'
                    for x in ["USD", "EUR", "GBP", "EGP"] if x in rate)
    tr = "".join(f"<tr><td><b>{E(FX_AR[x])}</b></td><td>{fmt(rate[x], 4)}</td><td>{fmt(1 / rate[x], 4)}</td></tr>" for x in rate)
    opts = "".join(f'<option value="{x}">{E(FX_AR[x])}</option>' for x in rate)
    body = f"""{CSS}<div class="sv">
<div class="sv-hero">سعر الدولار في {c['name']} اليوم <b>{fmt(rate['USD'], 4)} {c['cur_ar']}</b> · الجنيه المصري <b>{fmt(rate['EGP'], 4)} {c['cur_ar']}</b><br><small>{stamp(now)} · أسعار الصرف المرجعية · آخر تحديث {now:%H:%M}</small></div>
<div class="sv-grid">{cards}</div>
<div class="sv-tool"><b>حوّل بين العملات و{E(c['cur_full'])}:</b><br><input id="sv-a" type="number" value="100" min="0"> <select id="sv-c">{opts}</select>
<select id="sv-d"><option value="1">إلى {c['cur_ar']}</option><option value="0">من {c['cur_ar']}</option></select><div class="out" id="sv-r"></div></div>
<script>(function(){{var R={json.dumps({x: round(v, 6) for x, v in rate.items()})},N={json.dumps(FX_AR, ensure_ascii=False)};function g(i){{return document.getElementById(i)}}function f(){{var a=parseFloat(g('sv-a').value)||0,x=g('sv-c').value,r=R[x];g('sv-r').textContent=g('sv-d').value=='1'?(a+' '+N[x]+' = '+(a*r).toFixed({dec})+' {c['cur_ar']}'):(a+' {c['cur_ar']} = '+(a/r).toFixed(3)+' '+N[x])}}['sv-a','sv-c','sv-d'].forEach(function(i){{g(i).oninput=f;g(i).onchange=f}});f();}})();</script>
<h2>أسعار العملات مقابل {E(c['cur_full'])} اليوم</h2>
<div class="sv-wrap"><table class="sv-t"><thead><tr><th>العملة</th><th>بال{c['cur_ar']}</th><th>ال{c['cur_ar']} يساوي</th></tr></thead><tbody>{tr}</tbody></table></div>
<p class="sv-note">هذه أسعار صرف مرجعية، وأسعار البنوك وشركات الصرافة والتحويل تختلف قليلًا حسب كل جهة ورسوم التحويل.</p>
<h2>تحويل الأموال إلى مصر</h2>
<p>إذا كنت تحوّل إلى مصر، قارن سعر الصرف والرسوم بين أكثر من شركة تحويل قبل الإرسال، فالفرق في سعر الصرف قد يكون أكبر من الرسوم نفسها. ويمكنك معرفة قيمة المبلغ بالجنيه من صفحات التحويل بالأسفل.</p>
<div class="sv-links"><a href="{SITE}/p/sar-100-to-egp.html">100 ريال سعودي كم جنيه</a><a href="{SITE}/p/aed-100-to-egp.html">100 درهم كم جنيه</a><a href="{SITE}/p/kwd-100-to-egp.html">100 دينار كويتي كم جنيه</a><a href="{SITE}/p/currency-prices-egypt.html">أسعار العملات في مصر</a></div>
{S.faq([(f"كم سعر الدولار في {c['name']} اليوم؟", f"الدولار يساوي حوالي {fmt(rate['USD'], 4)} {c['cur_ar']}."),
        (f"كم يساوي الجنيه المصري بال{c['cur_ar']}؟", f"الجنيه المصري يساوي حوالي {fmt(rate['EGP'], 4)} {c['cur_ar']}، أي أن ال{c['cur_ar']} يساوي {fmt(1 / rate['EGP'], 2)} جنيه."),
        ("متى تتحدث الأسعار؟", "تتحدث الصفحة تلقائيًا عدة مرات في اليوم.")])}
{gulf_links(f"currency-{cc}")}</div>"""
    return body


def build(only=None):
    R = usd_rates()
    oz = S.xau()
    out = {}
    for cc in COUNTRIES:
        now = datetime.datetime.now(ZoneInfo(COUNTRIES[cc]["tz"]))
        for kind in ("gold", "prayer", "currency"):
            k = f"{kind}-{cc}"
            if only and k not in only:
                continue
            if kind == "gold":
                out[k] = gold(cc, now, oz, R)
            elif kind == "prayer":
                out[k] = prayer(cc, now)
            else:
                out[k] = currency(cc, now, R)
    return out


def main():
    if "--html" in sys.argv:
        k = sys.argv[sys.argv.index("--html") + 1]
        print(build([k])[k])
        return
    ids = S.PAGES.get("gulf", {})
    pages = build()
    tok = S.token()
    for k, body in pages.items():
        pid = (ids.get(k) or {}).get("id")
        if not pid:
            print("no page id for", k)
            continue
        r = requests.patch(f"https://www.googleapis.com/blogger/v3/blogs/{S.BLOG}/pages/{pid}",
                           headers={"Authorization": "Bearer " + tok}, json={"content": body}, timeout=60)
        print(k, r.status_code if r.status_code >= 400 else "updated")
        time.sleep(3)


if __name__ == "__main__":
    main()
