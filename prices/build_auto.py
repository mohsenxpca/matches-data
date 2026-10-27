"""Turn prices/auto_phones.json (phones7 facts) into page entries in phones.json, with our own pros/cons/FAQ wording.
python prices/build_auto.py
"""
import json, os, re, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, 'phones.json')
data = json.load(open(P, encoding='utf-8'))
auto = json.load(open(os.path.join(HERE, 'auto_phones.json'), encoding='utf-8'))
EG = 'https://www.egyptaway.com/2026/10/'
LINKS = {
    'سامسونج': [('المجلد الآمن في سامسونج خطوة بخطوة', EG + 'samsung-secure-folder-guide.html'), ('امسح مساحة موبايل سامسونج بأمان', EG + 'free-up-samsung-storage-safely.html')],
    'أبل': [('نقل بياناتك من الموبايل القديم للجديد', EG + 'transfer-data-old-phone-to-new.html'), ('حماية الواي فاي من سرقة النت', EG + 'protect-home-wifi-router-password.html')],
}
DEFAULT = [('نقل بياناتك من الموبايل القديم للجديد', EG + 'transfer-data-old-phone-to-new.html'), ('أفضل ألعاب أندرويد بدون إنترنت', EG + 'best-offline-android-games-by-genre.html')]


def short(s, n=110):
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.split(r'(?<=\.)\s', s)[0].rstrip('. ')
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'


def num(pat, s, default=0):
    m = re.search(pat, s or '')
    return int(m.group(1)) if m else default


def entry(d):
    r = d['rows']
    g = lambda k: r.get(k, '')
    slug = d['url'].rstrip('/').split('/')[-1]
    slug = re.sub(r'^(samsung-|xiaomi-(?=redmi)|apple-)', '', slug) + '-price-egypt'  # keep "xiaomi-" for Xiaomi 15T/17...
    s1 = lambda k, n=90: short(re.sub(r'\([^)]*\)', '', g(k)), n)
    join = lambda *xs: '، '.join(x for x in xs if x)
    specs = []
    if g('النوع') or g('الحجم'):
        hzs = re.search(r'\d{2,3}\s*هرتز', g('النوع'))
        specs.append(['الشاشة', join(s1('النوع', 40), g('الحجم').strip(' .'), ('تحديث ' + hzs.group(0)) if hzs else '')])
    if g('شريحة'):
        specs.append(['المعالج', s1('شريحة', 90)])
    if g('الرامات'):
        specs.append(['الرامات والتخزين', join('رام ' + s1('الرامات', 40), 'تخزين ' + s1('الداخلية', 40) if g('الداخلية') else '')])
    if g('الخلفية'):
        specs.append(['الكاميرا الخلفية', s1('الخلفية', 110)])
    if g('الامامية'):
        specs.append(['الكاميرا الأمامية', s1('الامامية', 80)])
    if g('السعة'):
        specs.append(['البطارية والشحن', join(s1('السعة', 40), s1('الشحن', 60))])
    if g('النظام'):
        specs.append(['النظام', s1('النظام', 100)])
    if g('الوزن') or g('المقاومة'):
        specs.append(['الوزن والمقاومة', join(s1('الوزن', 30), s1('المقاومة', 70))])
    bat = num(r'(\d{4,5})\s*ميل', g('السعة'))
    watt = num(r'(\d{2,3})\s*واط', g('الشحن'))
    hz = num(r'(\d{2,3})\s*هرتز', g('النوع'))
    amoled = 'اموليد' in g('النوع') or 'OLED' in g('النوع').upper()
    ip = re.search(r'IP6\d', g('المقاومة') or '')
    sd = 'يدعم' in g('SD')
    five = '5G' in g('الشبكة') or '5G' in d['name']
    pros, cons = [], []
    if bat >= 6000: pros.append(f'بطارية كبيرة {bat} مللي أمبير')
    if watt >= 45: pros.append(f'شحن سريع {watt} واط')
    if hz >= 120: pros.append(f'شاشة بتحديث {hz} هرتز')
    if amoled: pros.append('شاشة AMOLED بألوان وتباين أفضل')
    if ip and ip.group(0) in ('IP68', 'IP69'): pros.append(f'مقاومة للماء والغبار {ip.group(0)}')
    if sd: pros.append('بيدعم كارت ذاكرة')
    if five: pros.append('بيدعم شبكات 5G')
    if 'OIS' in g('الخلفية') or 'مثبت بصري' in g('الخلفية'): pros.append('كاميرا رئيسية بمثبت بصري')
    if bat and bat < 5000: cons.append(f'بطارية {bat} مللي أمبير أصغر من المنافسين')
    if watt and watt <= 25: cons.append(f'شحن {watt} واط بطيء')
    if hz and hz <= 90: cons.append(f'شاشة {hz} هرتز بس')
    if not amoled and g('النوع'): cons.append('شاشة LCD مش AMOLED')
    if not five: cons.append('ما بيدعمش 5G')
    if not ip or ip.group(0) in ('IP52', 'IP53', 'IP54', 'IP64'): cons.append('مقاومة محدودة للماء')
    if not sd and g('SD'): cons.append('مفيش كارت ذاكرة')
    pros = (pros or ['سعر مناسب لفئته'])[:4]
    cons = (cons or ['السعر أعلى من منافسين بنفس المواصفات تقريبًا'])[:4]
    price = d['eg'] or d['cat_price']
    variant = d['variant'] or 'أرخص نسخة'
    img = 'https://wsrv.nl/?url=' + urllib.parse.quote(d['img'], safe='') + '&w=400&h=330&fit=cover&a=top&output=webp&q=80' if d['img'] else ''  # crop off the phones7 footer watermark
    name = d['name'] if d['brand'] != 'أبل' else d['name']
    faq = [[f'سعر {name} في مصر كام؟', f'متوسط سعره في السوق المصري حوالي {price:,} جنيه لنسخة {variant}، حسب Phones7 بتاريخ {d["date"]}.'],
           [f'هل {name} بيدعم 5G؟', 'أيوه، بيدعم شبكات الجيل الخامس.' if five else 'لأ، النسخة دي بتدعم شبكات 4G.'],
           [f'سرعة شحن {name} كام؟', f'بيدعم شحن سلكي {watt} واط.' if watt else 'راجع ورقة المواصفات الرسمية للشحن.']]
    return {
        'slug': slug, 'en': slug.replace('-price-egypt', '').replace('-', ' ') + ' price egypt',
        'name': name, 'ar': (d['brand'] if d['brand'] != 'أبل' else 'آيفون') + ' ' + name.replace('iPhone ', ''), 'brand': d['brand'], 'img': img,
        'img_alt': f'صورة موبايل {name}', 'auto': True,
        'src': [f'Phones7: سعر {name} في مصر', d['url']],
        'variants': [[variant, price, 0, 'متوسط السوق']], 'specs': specs, 'pros': pros, 'cons': cons,
        'review': '', 'links': LINKS.get(d['brand'], DEFAULT), 'faq': faq,
    }


have = {p['slug'] for p in data['phones']}
new = 0
by_name = {}
for n, d in auto.items():
    if not d['img'] or not d['rows']:
        print('skip', n); continue
    e = entry(d)
    by_name[n] = e['slug']
    if e['slug'] in have:
        data['phones'] = [e if p['slug'] == e['slug'] else p for p in data['phones']]
    else:
        data['phones'].append(e); new += 1
for c in data['catalog']:
    if not c['page'] and c['n'] in by_name:
        c['page'] = by_name[c['n']]
json.dump(data, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('new', new, 'total', len(data['phones']))
