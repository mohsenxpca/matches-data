"""Zeda Shop <- Carry1st Egypt stock watcher (mohsen 2026-11-03). Hourly from zeda_watch.yml.

For every game in zeda_watch.json (built on mohsen's PC by blogger-pipeline/zeda/make_watch_config.py; PUBG, Free Fire
and the Codashop-priced Mobile Legends are not in it) read shop.carry1st.com/ar/EG/product/<slug>/direct-topup:
- page gone, product not ACTIVE / not inStock, or no Egyptian payment (Vodafone Cash / Fawry) on it -> every package off
- a package missing / not ACTIVE / not inStock -> that package off
"Off" = the package on the live Zeda post gets "off":1 in the picker data (greyed, "غير متوفر", can't be ordered) and
"غير متوفر حاليًا" in the price table. When Carry1st has it again it's switched back on. Packages switched off by hand
(stock 0 in zeda/prices.csv) are never switched on here: only names this script switched off (zeda_stock.json) are.

python zeda_watch.py [--dry-run]
"""
import html, json, os, re, sys, time, urllib.parse
import requests

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "zeda_watch.json")
STATE = os.path.join(HERE, "zeda_stock.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
EG_PAY = re.compile(r"Vodafone Cash|فودافون كاش|Fawry|فوري", re.I)
API = "https://www.googleapis.com/blogger/v3"


def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["BLOGGER_CLIENT_ID"], "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google login failed ({r.status_code}): {r.text[:200]}")
    return r.json()["access_token"]


def carry1st(slug):
    """-> (product or None, bundles, page text); product None = the page is gone."""
    u = "https://shop.carry1st.com/ar/EG/product/" + urllib.parse.quote(slug, safe="") + "/direct-topup"
    r = requests.get(u, headers={"User-Agent": UA, "Accept-Language": "ar"}, timeout=40)
    if r.status_code == 404:
        return None, [], ""
    r.raise_for_status()
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', r.text, re.S)
    txt = "".join(json.loads('"' + c + '"') for c in chunks)
    i = txt.find('"productBundles":')
    if i < 0:
        if not txt:
            raise RuntimeError("no page data (blocked?)")
        return None, [], txt
    arr, _ = json.JSONDecoder().raw_decode(txt[i + len('"productBundles":'):])
    return (arr[0]["product"] if arr else None), arr, txt


def nums(s):
    return tuple(int(x) for x in re.findall(r"\d+", s.replace(",", "").replace("٬", "")))


def price(b):
    return b.get("discountPrice") or b.get("localPrice") or 0


def match(items, bundles):
    """items = [[carry1st name, price when the page was built, name on Zeda]] -> {zeda name: bundle or None}"""
    out, used = {}, set()
    for raw, p, name in items:
        n = nums(raw)
        cand = [b for b in bundles if id(b) not in used and n and nums(b["name"]) == n]
        cand.sort(key=lambda b: abs(price(b) - p))
        if not cand:  # passes etc. without numbers: same price (±3%) as when the page was built
            cand = [b for b in bundles if id(b) not in used and abs(price(b) - p) <= max(1, p * .03)]
        b = cand[0] if cand else None
        if b:
            used.add(id(b))
        out[name] = b
    return out


def wanted_off(game):
    prod, bundles, txt = carry1st(game["c1"])
    whole = None
    if prod is None:
        whole = "اللعبة اتشالت من كاري فيرست"
    elif prod.get("status") != "ACTIVE" or not prod.get("inStock", True) or "WEB" not in (prod.get("platforms") or ["WEB"]):
        whole = f"اللعبة متوقفة على كاري فيرست ({prod.get('status')})"
    elif not EG_PAY.search(txt):
        whole = "وسائل الدفع المصرية اتشالت من صفحة اللعبة"
    if whole:
        return {name: whole for _, _, name in game["items"]}
    off = {}
    for name, b in match(game["items"], bundles).items():
        if b is None:
            off[name] = "الباقة اتشالت من كاري فيرست"
        elif b.get("status") != "ACTIVE" or not b.get("inStock", True) or b.get("displayInShop") is False:
            off[name] = "الباقة متوقفة على كاري فيرست"
    return off


def row_html(d):
    cells = '<td colspan="2">غير متوفر حاليًا</td>' if d.get("off") else f"<td><b>{d['price']:,} ج.م</b></td><td><s>{d['old']:,} ج.م</s></td>"
    return f"<tr><td>{html.escape((d['tab'] + ' — ' if d['tab'] else '') + d['name'])}</td>{cells}</tr>"


def apply(content, off, mine):
    """-> (new content, [(name, 'OFF'|'BACK')]). off = names Carry1st lacks; mine = names this script switched off before."""
    m = re.search(r"var D=(\[.*?\]),G=", content, re.S)
    if not m:
        raise RuntimeError("picker data not found in the post")
    D = json.loads(m.group(1))
    norm = lambda s: html.unescape(s).strip()
    off_n, mine_n = {norm(k) for k in off}, {norm(k) for k in mine}
    changes = []
    for d in D:
        n = norm(d["name"])
        if n in off_n and not d.get("off"):
            d["off"] = 1
            changes.append((d, "OFF"))
        elif n not in off_n and n in mine_n and d.get("off"):
            d.pop("off")
            changes.append((d, "BACK"))
    if not changes:
        return content, []
    if 'class="na"' not in content:
        raise RuntimeError("post was built before the out-of-stock feature; rebuild + upload it first")
    new = content[:m.start(1)] + json.dumps(D, ensure_ascii=False) + content[m.end(1):]
    for d, _ in changes:  # the price table row
        label = re.escape(html.escape((d["tab"] + " — " if d["tab"] else "") + d["name"]))
        new = re.sub(r"<tr><td>" + label + r"</td>.*?</tr>", lambda _m: row_html(d), new, count=1, flags=re.S)
    return new, [(d["name"], k) for d, k in changes]


def telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_ADMIN_CHAT")
    if tok and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": text[:3900]}, timeout=20)
        except Exception as e:
            print("telegram failed", e)


def main():
    dry = "--dry-run" in sys.argv
    cfg = json.load(open(CFG, encoding="utf-8"))
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    tok = None if dry else token()
    report = []
    for game in cfg["games"]:
        key = game["key"]
        try:
            off = wanted_off(game)
        except Exception as e:  # Carry1st down / blocked: change nothing for this game
            print(f"{key}: Carry1st check failed ({str(e)[:100]}), left as is")
            continue
        mine = state.get(key, {})
        print(f"{key}: {len(off)} off on Carry1st" + (" " + str(sorted(off)) if off else ""))
        if dry:
            state[key] = off
            continue
        url = f"{API}/blogs/{cfg['blog']}/posts/{game['post_id']}"
        h = {"Authorization": f"Bearer {tok}"}
        post = requests.get(url, headers=h, params={"fields": "content,url"}, timeout=40)
        post.raise_for_status()
        post = post.json()
        try:
            new, changes = apply(post["content"], off, mine)
        except RuntimeError as e:
            print(f"{key}: {e}")
            report.append(f"⚠️ {key}: {e}")
            continue
        if changes:
            r = requests.patch(url, headers=h, json={"content": new}, timeout=60)
            r.raise_for_status()
            for name, k in changes:
                line = f"{'⛔ غير متوفر' if k == 'OFF' else '✅ رجعت'} | {key} | {name}" + (f" — {off[name]}" if k == "OFF" and name in off else "")
                print(line)
                report.append(line)
            report.append(post["url"])
        state[key] = off
        time.sleep(1.5)
    if not dry:
        json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if report:
        telegram("زيدا شوب ← كاري فيرست:\n" + "\n".join(report))
    print("done", "(dry run)" if dry else "")


if __name__ == "__main__":
    main()
