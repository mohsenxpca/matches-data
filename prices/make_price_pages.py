"""Egyptaway phone price pages (/p/<slug>.html) + hub page (/p/mobile-prices-egypt.html), built from prices/phones.json.
Includes Egypt (EGP), Saudi Arabia (SAR), and UAE (AED) published prices.

python prices/make_price_pages.py            -> write HTML to prices/pages/ only
python prices/make_price_pages.py --upload   -> create missing pages as drafts (English slug title) or update existing ones
python prices/make_price_pages.py --publish  -> publish drafts, then set the Arabic titles
To refresh prices: edit phones.json ("updated" + variants) and run --upload --refresh again.
"""
import html, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'outage'))
from make_pages import call  # 429 backoff wrapper

BID = '8325646053257070334'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'pages')
STATE = os.path.join(HERE, 'pages.json')
DATA = json.load(open(os.path.join(HERE, 'phones.json'), encoding='utf-8'))
MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
HUB = 'https://www.egyptaway.com/p/mobile-prices-egypt.html'
E = html.escape

STYLE = '''<style>
.pp{color:#1a1a1a;background:#fff;line-height:1.9;font-size:17px}
.pp h2{color:#1a1a1a;margin-top:1.5em}
.pp-box{background:#f5f8ff;border:1px solid #c9d6f5;border-radius:12px;padding:14px 16px;margin:16px 0}
.pp-grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:10px 0}
.pp-card{background:#fff;border:1px solid #dbe4ff;border-radius:10px;padding:10px 14px;text-align:center}
.pp-card span{display:block;font-size:14px;color:#555;font-weight:700}
.pp-big{font-size:23px;font-weight:800;color:#0d47a1;margin-top:2px}
.pp-scroll{overflow-x:auto}
.pp-t{border-collapse:collapse;width:100%;background:#fff;color:#1a1a1a;margin:10px 0}
.pp-t th,.pp-t td{border:1px solid #ccc;padding:8px 10px;text-align:right}
.pp-t th{background:#f0f4ff;font-weight:800}
.pp-pros{background:#f1fbf3;border-right:4px solid #2e7d32;padding:10px 14px;margin:12px 0;border-radius:6px}
.pp-cons{background:#fff4f4;border-right:4px solid #c62828;padding:10px 14px;margin:12px 0;border-radius:6px}
.pp-tool{background:#f7f9fc;border:1px solid #cbd5e1;border-radius:10px;padding:14px}
.pp-tool input,.pp-tool select,.pp-tool button{font-size:16px;padding:7px 10px;max-width:100%;border-radius:6px;border:1px solid #ccc}
.pp-tool button{background:#0d47a1;color:#fff;font-weight:700;border:0;cursor:pointer;padding:8px 18px}
.pp details{border:1px solid #ccc;border-radius:6px;padding:8px 12px;margin:8px 0;background:#fff}
.pp summary{font-weight:700;cursor:pointer}
.pp-note{font-size:14px;color:#555}
</style>'''


def ar_date(d):
    y, m, dd = d.split('-')
    return f'{int(dd)} {MONTHS[int(m) - 1]} {y}'


def money(n):
    return f'{n:,}'


def page_html(p, updated):
    low = min(v[1] for v in p['variants'])
    sa = p.get('sa', 0)
    ae = p.get('ae', 0)
    sa_txt = p.get('sa_txt') or (money(sa) if sa else '—')
    ae_txt = p.get('ae_txt') or (money(ae) if ae else '—')
    auto = p.get('auto')
    lowtxt = 'متوسط سعره في السوق المصري' if auto else 'أقل سعر لقيناه في المتاجر المصرية'
    boxtxt = 'متوسط السعر في مصر النهارده' if auto else 'أقل سعر في مصر النهارده'
    rows = ''.join(
        f'<tr><td>{E(v[0])}</td><td><b>{money(v[1])} جنيه</b></td><td>{money(v[2]) + " جنيه" if v[2] else "—"}</td><td>{E(v[3])}</td></tr>'
        for v in p['variants'])
    specs = ''.join(f'<tr><td>{E(k)}</td><td>{E(v)}</td></tr>' for k, v in p['specs'])
    pros = ''.join(f'<li>{E(x)}</li>' for x in p['pros'])
    cons = ''.join(f'<li>{E(x)}</li>' for x in p['cons'])

    faq_list = list(p['faq'])
    if sa and ae and not any('السعودية' in q for q, _ in faq_list):
        faq_list.insert(1, [
            f'كم سعر {p["name"]} في السعودية والإمارات؟',
            f'سعر {p["name"]} ({p["ar"]}) في السعودية يبدأ من {sa_txt} ريال سعودي تقريبًا، وفي الإمارات {ae_txt} درهم إماراتي، وفي مصر {money(low)} جنيه مصري (تحديث {ar_date(updated)} حسب Phones7).'
        ])
    faq = ''.join(f'<details><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq_list)
    l1, l2 = p['links']
    review = (f'<p>عايز رأينا بالتفصيل في الشاشة والكاميرا والبطارية؟ اقرأ <a href="{p["review"]}">مراجعة {E(p["name"])} الكاملة على موقع رفيو</a>.</p>'
              if p['review'] else '')

    opts = ''.join(f'<option value="{v[1]}|جنيه">{E(v[0])} — مصر ({money(v[1])} جنيه)</option>' for v in p['variants'])
    if sa:
        opts += f'<option value="{sa}|ريال سعودي">نسخة السوق السعودي ({money(sa)} ريال سعودي)</option>'
    if ae:
        opts += f'<option value="{ae}|درهم إماراتي">نسخة السوق الإماراتي ({money(ae)} درهم إماراتي)</option>'

    gulf_cards = ''
    gulf_table = ''
    if sa or ae:
        gulf_cards = f'''<div class="pp-grid3">
<div class="pp-card"><span>🇪🇬 {boxtxt}</span><div class="pp-big">{money(low)} جنيه</div></div>
<div class="pp-card"><span>🇸🇦 السعر في السعودية</span><div class="pp-big">{E(sa_txt)} ر.س</div></div>
<div class="pp-card"><span>🇦🇪 السعر في الإمارات</span><div class="pp-big">{E(ae_txt)} د.إ</div></div>
</div>'''
        gulf_table = f'''<h2>سعر {E(p["name"])} في مصر والسعودية والإمارات</h2>
<div class="pp-scroll"><table class="pp-t">
<thead><tr><th>الدولة</th><th>السعر في السوق</th><th>العملة</th><th>حالة التوفر</th></tr></thead>
<tbody>
<tr><td><b>🇪🇬 مصر</b></td><td><b>{money(low)} جنيه مصري</b></td><td>جنيه مصري (EGP)</td><td>متوفر في المتاجر المصرية</td></tr>
<tr><td><b>🇸🇦 السعودية (جرير / نون / أمازون)</b></td><td><b>{E(sa_txt)} ريال سعودي</b></td><td>ريال سعودي (SAR)</td><td>متوفر في السوق السعودي</td></tr>
<tr><td><b>🇦🇪 الإمارات (دبي / أبوظبي)</b></td><td><b>{E(ae_txt)} درهم إماراتي</b></td><td>درهم إماراتي (AED)</td><td>متوفر في السوق الإماراتي</td></tr>
</tbody></table></div>'''

    schema = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Product",
                "name": f"{p['name']} ({p['ar']})",
                "image": p["img"],
                "brand": {"@type": "Brand", "name": p["brand"]},
                "description": f"سعر ومواصفات {p['name']} ({p['ar']}) في مصر والسعودية والإمارات مع جدول النسخ وحاسبة التقسيط.",
                "offers": [
                    {"@type": "Offer", "priceCurrency": "EGP", "price": str(low), "availability": "https://schema.org/InStock", "areaServed": "EG"},
                    *( [{"@type": "Offer", "priceCurrency": "SAR", "price": str(sa), "availability": "https://schema.org/InStock", "areaServed": "SA"}] if sa else [] ),
                    *( [{"@type": "Offer", "priceCurrency": "AED", "price": str(ae), "availability": "https://schema.org/InStock", "areaServed": "AE"}] if ae else [] ),
                ]
            },
            {
                "@type": "FAQPage",
                "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq_list]
            }
        ]
    }, ensure_ascii=False)

    return f'''<div dir="rtl" class="pp">
<p>سعر {E(p["ar"])} ({E(p["name"])}) في مصر والسعودية والإمارات النهارده: {lowtxt} <strong>{money(low)} جنيه مصري</strong>، وفي السعودية <strong>{E(sa_txt)} ريال سعودي</strong>، وفي الإمارات <strong>{E(ae_txt)} درهم إماراتي</strong>، بتاريخ {ar_date(updated)}. هنا هتلاقي سعر كل نسخة وأقل وأعلى سعر، والتقسيط الشهري، والمواصفات المهمة، والمميزات والعيوب قبل ما تشتري.</p>
<figure style="text-align:center;margin:16px 0"><img src="{p["img"]}" alt="{E(p["img_alt"])}" width="600" height="600" style="max-width:100%;height:auto"/></figure>
<div class="pp-box">{gulf_cards}<div class="pp-note">آخر تحديث للأسعار: {ar_date(updated)} · المصدر: <a href="{p["src"][1]}" rel="nofollow noopener" target="_blank">{E(p["src"][0])}</a></div></div>
{gulf_table}
<h2>سعر {E(p["name"])} في مصر لكل نسخة</h2>
<div class="pp-scroll"><table class="pp-t"><thead><tr><th>النسخة</th><th>{'السعر' if auto else 'أقل سعر'}</th><th>أعلى سعر</th><th>{'المصدر' if auto else 'أقل سعر عند'}</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="pp-note">الأسعار بتتغير كل يوم حسب المتجر واللون والعروض في مصر والسعودية والإمارات، فراجع السعر في المتجر قبل الشراء، واتأكد إن الضمان محلي من الوكيل.</p>
<h2>احسب قسط {E(p["name"])} الشهري (مصر / السعودية / الإمارات)</h2>
<div class="pp-tool">
<p><label>النسخة والدولة: <select id="pp-v">{opts}</select></label></p>
<p><label>الدفعة المقدمة: <input id="pp-d" type="number" value="0" min="0" step="100"/></label></p>
<p><label>مدة التقسيط: <select id="pp-m"><option value="4">4 شهور (تمارا / تابي الخليج)</option><option>6</option><option selected>12</option><option>18</option><option>24</option><option>36</option></select> شهر</label></p>
<p><label>نسبة الفايدة أو المصاريف الكلية %: <input id="pp-r" type="number" value="0" min="0" step="0.5"/></label></p>
<p><button id="pp-go" type="button">احسب القسط الشهري</button></p>
<div id="pp-out"></div>
<p class="pp-note">لو العرض "بدون فوايد" (أو تقسيط تابي وتمارا في السعودية والإمارات على 4 دفعات) سيب النسبة صفر. الحساب تقريبي حسب البنك أو شركة التقسيط.</p>
</div>
<h2>مواصفات {E(p["name"])} المهمة</h2>
<div class="pp-scroll"><table class="pp-t"><tbody>{specs}</tbody></table></div>
{review}
<h2>المميزات والعيوب</h2>
<div class="pp-pros"><strong>المميزات</strong><ul>{pros}</ul></div>
<div class="pp-cons"><strong>العيوب</strong><ul>{cons}</ul></div>
<h2>اقرأ كمان</h2>
<ul><li><a href="{l1[1]}">{E(l1[0])}</a></li><li><a href="{l2[1]}">{E(l2[0])}</a></li><li><a href="{HUB}">أسعار الموبايلات في مصر والسعودية والإمارات اليوم</a></li></ul>
<h2>أسئلة شائعة</h2>
{faq}
<p class="pp-note">بنحدّث الأسعار في الصفحة دي بشكل دوري من المتاجر الكبيرة في مصر والخليج. ايجبتاوى مش بيبيع الموبايلات ومش تابع لأي متجر.</p>
</div>
<script>
(function(){{var b=document.getElementById('pp-go');if(!b)return;
function f(n){{return Math.round(n).toLocaleString('en-US');}}
b.addEventListener('click',function(){{var raw=document.getElementById('pp-v').value.split('|'),p=+raw[0],cur=raw[1]||'جنيه',d=+document.getElementById('pp-d').value||0,m=+document.getElementById('pp-m').value,r=+document.getElementById('pp-r').value||0;
var rest=Math.max(0,p-d),total=rest*(1+r/100),mo=total/m;
document.getElementById('pp-out').innerHTML='<p>القسط الشهري تقريبًا: <strong>'+f(mo)+' '+cur+'</strong> لمدة '+m+' شهر</p><p>إجمالي اللي هتدفعه: '+f(total+d)+' '+cur+'</p>';}});}})();
</script>
<script type="application/ld+json">{schema}</script>
{STYLE}'''


# hub cover made by prices/make_hub_cover.py, hosted on Blogger (draft 7483753207242699202 "image host (do not publish)")
HUB_IMG = 'https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgxEZ00PHNaY24NcO0T9LT7iGnMZkKfx7eSAVoMKHAht8NKH0Y3-jA5QYpQscVmStyVgmgHgtrjWQfxSl4ukyDg_A3pP5EBvQ9tqCHv6W4Qfs9nC6pKBeIe5XbwVvNXEYRPfHR_QK9SZ2IlcFgRMei6D5BZl2S1TVea9Yr5lfMKwdf4608I2PZeT5jijLtR/s1200/hub_cover.jpg'


def hub_html(phones, updated):
    by_slug = {p['slug']: p for p in phones}
    data = []
    for c in DATA.get('catalog', []):
        pg = by_slug.get(c.get('page', ''))
        sa = c.get('sa') or (pg.get('sa', 0) if pg else 0)
        ae = c.get('ae') or (pg.get('ae', 0) if pg else 0)
        data.append({'n': c['n'], 'b': c['b'], 'p': c['p'], 'sa': sa, 'ae': ae, 'u': f'/p/{c["page"]}.html' if c['page'] else ''})
    brands = sorted({c['b'] for c in DATA.get('catalog', [])})
    srcs = sorted({(c['b'], c['src']) for c in DATA.get('catalog', [])})
    src_html = ' · '.join(f'<a href="{u}" rel="nofollow noopener" target="_blank">{E(b)}</a>' for b, u in srcs)
    bopts = ''.join(f'<option>{E(b)}</option>' for b in brands)
    return f'''<div dir="rtl" class="pp">
<p>أسعار الموبايلات في <strong>مصر والسعودية والإمارات</strong> النهارده من المتاجر الكبيرة، محدثة بتاريخ {ar_date(updated)}. اختار الماركة والعملة والميزانية، وادخل على صفحة أي موبايل تشوف سعر كل نسخة بالجنيه والريال والدرهم والتقسيط الشهري والمواصفات.</p>
<figure style="text-align:center;margin:16px 0"><img src="{HUB_IMG}" alt="أسعار الموبايلات في مصر والسعودية والإمارات اليوم محدثة يوميًا" width="1200" height="675" style="max-width:100%;height:auto"/></figure>
<div class="pp-tool">
<p><label>ابحث: <input id="hb-q" type="search" placeholder="مثلًا A57 أو ريدمي أو iPhone"/></label></p>
<p><label>الماركة: <select id="hb-b"><option value="">كل الماركات</option>{bopts}</select></label>
<label>العملة: <select id="hb-cur"><option value="p">🇪🇬 جنيه مصري</option><option value="sa">🇸🇦 ريال سعودي</option><option value="ae">🇦🇪 درهم إماراتي</option></select></label>
<label>ميزانيتك لحد: <input id="hb-p" type="number" placeholder="مثلًا 25000 أو 1500" min="0" step="100"/></label>
<label>الترتيب: <select id="hb-s"><option value="a">الأرخص الأول</option><option value="d">الأغلى الأول</option></select></label></p>
<div class="pp-scroll"><table class="pp-t"><thead><tr><th>الموبايل</th><th>الماركة</th><th>🇪🇬 مصر (جنيه)</th><th>🇸🇦 السعودية (ريال)</th><th>🇦🇪 الإمارات (درهم)</th></tr></thead><tbody id="hb-t"></tbody></table></div>
<p class="pp-note" id="hb-c"></p>
<p class="pp-note">الأسعار "يبدأ من" لأرخص نسخة في المتاجر لشهر أكتوبر 2026، حسب قوائم Phones7: {src_html}. الموبايلات اللي عليها رابط ليها صفحة كاملة عندنا بسعر كل نسخة في مصر والسعودية والإمارات والتقسيط.</p>
</div>
<h2>إزاي تستخدم صفحة أسعار الموبايلات في مصر والخليج؟</h2>
<p>كل موبايل له صفحة مستقلة فيها متوسط وأقل سعر في مصر بالجنيه المصري، والسعر في السعودية بالريال السعودي، والسعر في الإمارات بالدرهم الإماراتي، مع حاسبة تقسيط شهري (تشمل تقسيط البنوك في مصر أو تابي وتمارا في السعودية والإمارات)، ومواصفات ومميزات وعيوب الهاتف.</p>
<h2>نصايح قبل ما تشتري</h2>
<ul><li>اشتري بضمان الوكيل المحلي في بلدك (مصر أو السعودية أو الإمارات)، واتأكد من دعم ترددات الجيل الخامس 5G.</li><li>قارن سعر نفس النسخة (الرام والتخزين) مش اسم الموبايل بس.</li><li>عروض التقسيط بدون فوايد (أو على 4 دفعات في الخليج) ممكن توفر سيولة ممتازة بدون أي زيادة على السعر الكاش.</li></ul>
<p class="pp-note">ايجبتاوى مش بيبيع الموبايلات ومش تابع لأي متجر، والأسعار بتتغير بسرعة فراجعها في المتجر قبل الشراء. وتابع كمان <a href="https://www.egyptaway.com/p/is-it-down-egypt.html">رصد الأعطال في مصر</a> و<a href="https://www.egyptaway.com/p/make-money-online-egypt.html">دليل طرق الربح من الإنترنت والموبايل</a>.</p>
</div>
<script>
(function(){{var D={json.dumps(data, ensure_ascii=False)};var t=document.getElementById('hb-t');if(!t)return;
function f(n){{return n?n.toLocaleString('en-US'):'—';}}
function draw(){{var b=document.getElementById('hb-b').value,cur=document.getElementById('hb-cur').value,p=+document.getElementById('hb-p').value||0,q=document.getElementById('hb-q').value.trim().toLowerCase(),s=document.getElementById('hb-s').value;
var r=D.filter(function(x){{var val=x[cur]||x.p;return(!b||x.b===b)&&(!p||(val&&val<=p))&&(!q||(x.n+' '+x.b).toLowerCase().indexOf(q)>=0);}}).sort(function(x,y){{var vx=x[cur]||x.p,vy=y[cur]||y.p;return s==='d'?vy-vx:vx-vy;}});
t.innerHTML=r.map(function(x){{return '<tr><td>'+(x.u?'<a href="'+x.u+'"><strong>'+x.n+'</strong></a> <small style="color:#0b6e4f">(صفحة كاملة)</small>':x.n)+'</td><td>'+x.b+'</td><td><b>'+f(x.p)+' ج.م</b></td><td>'+(x.sa?f(x.sa)+' ر.س':'—')+'</td><td>'+(x.ae?f(x.ae)+' د.إ':'—')+'</td></tr>';}}).join('')||'<tr><td colspan="5">مفيش موبايل بالشروط دي حاليًا.</td></tr>';
document.getElementById('hb-c').textContent=r.length+' موبايل';}}
['hb-b','hb-cur','hb-s'].forEach(function(i){{document.getElementById(i).onchange=draw;}});['hb-p','hb-q'].forEach(function(i){{document.getElementById(i).oninput=draw;}});draw();}})();
</script>
{STYLE}'''


def build():
    os.makedirs(OUT, exist_ok=True)
    up = DATA['updated']
    pages = {'mobile-prices-egypt': ('mobile prices egypt', 'أسعار الموبايلات في مصر والسعودية والإمارات اليوم: سامسونج وآيفون وشاومي وأوبو', hub_html(DATA['phones'], up))}
    for p in DATA['phones']:
        t = f'سعر {p["name"]} في مصر والسعودية والإمارات اليوم: النسخ والتقسيط'
        if len(t) > 70:
            t = f'سعر {p["name"]} في مصر والسعودية والإمارات اليوم'
        pages[p['slug']] = (p['en'], t, page_html(p, up))
    for slug, (_, _, h) in pages.items():
        open(os.path.join(OUT, slug + '.html'), 'w', encoding='utf-8').write(h)
    return pages


def main():
    pages = build()
    print('built', len(pages))
    state = json.load(open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
    if '--upload' in sys.argv:
        start_from = sys.argv[sys.argv.index('--from') + 1] if '--from' in sys.argv else None
        started = not start_from
        for slug, (slug_title, title, h) in pages.items():
            if not started:
                if slug == start_from:
                    started = True
                else:
                    continue
            if slug in state:
                if '--refresh' not in sys.argv and slug != 'mobile-prices-egypt':
                    continue  # existing page: only rewritten with --refresh (weekly price update)
                body = {'content': h}
                if state[slug].get('published'):
                    body['title'] = title
                for t in range(4):
                    try:
                        call('PATCH', f'/blogs/{BID}/pages/{state[slug]["id"]}', None, body)
                        print('updated', slug)
                        break
                    except Exception as e:
                        import time
                        print('retry', slug, str(e)[:40])
                        time.sleep(5 * (t + 1))
                continue
            p = call('POST', f'/blogs/{BID}/pages', {'isDraft': 'true'}, {'title': slug_title, 'content': h})
            state[slug] = {'id': p['id'], 'url': p.get('url'), 'title': title}
            print('created', slug)
            json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if '--publish' in sys.argv:
        for slug, v in state.items():
            if v.get('published'):
                continue
            p = call('POST', f'/blogs/{BID}/pages/{v["id"]}/publish', None, None)
            call('PATCH', f'/blogs/{BID}/pages/{v["id"]}', None, {'title': pages[slug][1]})
            v['url'] = p.get('url'); v['published'] = True
            print('published', slug, p.get('url'))
        json.dump(state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
