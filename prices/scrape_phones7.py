"""Scrape phones7.com spec pages for every catalog phone without its own page -> prices/auto_phones.json.

Facts only (specs, average Egypt/KSA/UAE price, price date, variant); our own wording for pros/cons/FAQ.
python prices/scrape_phones7.py
"""
import html as H, json, os, re, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141 Safari/537.36'}
BRANDS = {'سامسونج': 'samsung', 'أوبو': 'oppo', 'شاومي': 'xiaomi', 'هونر': 'honor', 'إنفينكس': 'infinix', 'أبل': 'iphone'}
PREFIX = {'samsung': 'samsung-', 'oppo': 'oppo-', 'xiaomi': 'xiaomi-', 'honor': 'honor-', 'infinix': 'infinix-', 'iphone': 'apple-'}


def get(u):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode('utf-8', 'ignore')
        except Exception as e:
            err = e; time.sleep(3)
    raise err


cl = lambda s: re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower().replace('+', 'plus'))


def brand_links(key):
    h = get(f'https://phones7.com/eg/{key}-mobiles-prices-in-egypt/')
    return sorted(set(u for u in re.findall(r'href="(https://phones7\.com/[a-z0-9-]+/)"', h)
                      if not any(x in u for x in ('/eg/', '/brand/', '/sa/', '/ae/', 'mobiles-prices', '/category/', '/tag/'))))


def rows(h):
    out = {}
    for t in re.findall(r'<table.*?</table>', h, re.S):
        for r in re.findall(r'<tr.*?</tr>', t, re.S):
            c = [cl(x) for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)]
            if len(c) >= 2 and c[0] not in out:
                out[c[0]] = c[1]
    return out


def first(s, n=120):
    s = re.split(r'(?<=[.])\s', s)[0].rstrip('.')
    return s[:n]


def parse(url):
    h = get(url)
    r = rows(h)
    lines = [l.strip() for l in H.unescape(re.sub(r'<[^>]+>', '\n', re.sub(r'<script.*?</script>|<style.*?</style>', '', h, flags=re.S))).split('\n') if l.strip()]
    title = cl(re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S).group(1)) if re.search(r'<h1', h) else lines[0]
    ar = title.split(' - ')[0].strip()
    def after(label):
        for i, l in enumerate(lines):
            if l.startswith(label):
                for x in lines[i + 1:i + 4]:
                    m = re.match(r'^[\d,]+$', x)
                    if m:
                        return int(x.replace(',', ''))
        return 0
    eg = after('سعر') if False else 0
    for i, l in enumerate(lines):
        if l.startswith('سعر') and 'في مصر' in l and i + 1 < len(lines) and re.match(r'^[\d,]+$', lines[i + 1]):
            eg = int(lines[i + 1].replace(',', '')); break
    date = ''
    for i, l in enumerate(lines):
        if 'اخر تحديث لسعر' in l and i + 1 < len(lines):
            date = lines[i + 1]; break
    variant = ''
    for i, l in enumerate(lines):
        if 'الاسعار التالية هي اسعار النسخة' in l and i + 1 < len(lines):
            variant = re.sub(r'\d+ السعودية / ', '', lines[i + 1]).replace('باقي الدول ', '').strip(' .'); break
    img = ''
    for u in re.findall(r'https://phones7\.com/wp-content/uploads/[^"\' ]+\.(?:jpg|jpeg|png|webp)', h):
        if not re.search(r'-\d+x\d+\.', u) and 'logo' not in u:
            img = u; break
    return {'ar': ar, 'eg': eg, 'date': date, 'variant': variant, 'img': img, 'rows': r}


def main():
    data = json.load(open(os.path.join(HERE, 'phones.json'), encoding='utf-8'))
    out = {}
    links_cache = {}
    for c in data['catalog']:
        if c['page']:
            continue
        key = BRANDS[c['b']]
        if key not in links_cache:
            links_cache[key] = brand_links(key)
        target = norm(PREFIX[key] + c['n'].replace('Xiaomi ', '').replace('Oppo ', '').replace('Honor ', '').replace('Infinix ', '').replace('Galaxy ', 'galaxy ').replace('Redmi', 'redmi'))
        cand = [u for u in links_cache[key] if norm(u.rstrip('/').split('/')[-1]) == target]
        if not cand:
            cand = [u for u in links_cache[key] if norm(u.rstrip('/').split('/')[-1]).endswith(norm(c['n']))]
        if not cand:
            print('NO LINK', c['n']); continue
        try:
            d = parse(cand[0])
        except Exception as e:
            print('FAIL', c['n'], e); continue
        d.update({'name': c['n'], 'brand': c['b'], 'url': cand[0], 'cat_price': c['p']})
        out[c['n']] = d
        print('ok', c['n'], d['eg'], d['date'], d['variant'][:40], 'img' if d['img'] else 'NOIMG', len(d['rows']))
        time.sleep(1)
    json.dump(out, open(os.path.join(HERE, 'auto_phones.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('total', len(out))


if __name__ == '__main__':
    main()
