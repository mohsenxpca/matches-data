"""Egyptian market gold prices (buy/sell per karat, gold pound) + world spot + USD/EGP -> live.json.

Runs every 5 minutes on GitHub Actions (.github/workflows/goldlive.yml) and is pushed to the 'live' branch
(force-pushed, so the main history doesn't grow). The gold/currency pages read it every minute and move the
prices with the world spot price (api.gold-api.com) between two snapshots.
"""
import datetime, json, re, sys, time
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
KARATS = {"عيار 24": "24", "عيار 22": "22", "عيار 21": "21", "عيار 18": "18", "عيار 14": "14", "عيار 12": "12", "جنيه ذهب": "pound"}


LIVE = "https://raw.githubusercontent.com/mohsenxpca/matches-data/live/live.json"


def get(url, timeout=20):
    """GET with 3 tries: runner DNS/network hiccups are common and shouldn't fail the whole job."""
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            if i == 2:
                raise
            print("  retry", url.split("/")[2], e.__class__.__name__)
            time.sleep(5 * (i + 1))


def market():
    s = BeautifulSoup(get("https://isagha.com/", 30).text, "html.parser")
    t = re.sub(r"\s+", " ", s.get_text(" ", strip=True))
    out = {}
    for label, key in KARATS.items():
        m = re.search(re.escape(label) + r" ([\d,.]+) ([\d,.]+)", t)
        if m:
            buy, sell = (float(x.replace(",", "")) for x in m.groups())
            if 0 < buy <= sell:
                out[key] = {"buy": buy, "sell": sell}
    if "21" not in out or "24" not in out:
        raise SystemExit("market prices not found - page layout changed?")
    return out


def main():
    try:
        prev = requests.get(LIVE, headers=UA, timeout=20).json()
    except Exception:
        prev = {}
    gold, xau, fx = prev.get("gold"), prev.get("xau"), prev.get("fx")
    fresh = 0
    try:
        gold, fresh = market(), fresh + 1
    except BaseException as e:  # market() raises SystemExit on layout changes
        print("market failed, keeping last prices:", e)
    try:
        xau, fresh = get("https://api.gold-api.com/price/XAU").json()["price"], fresh + 1
    except Exception as e:
        print("xau failed, keeping last:", e)
    try:
        usd = get("https://open.er-api.com/v6/latest/USD").json()["rates"]
        fx = {c: round(usd["EGP"] / usd[c], 4) for c in ("USD", "EUR", "SAR", "AED", "KWD", "GBP", "QAR", "JOD", "OMR", "BHD", "CNY", "TRY") if c in usd}
        fresh += 1
    except Exception as e:
        print("fx failed, keeping last:", e)
    if not fresh or not (gold and xau and fx):
        print("no source reachable this time; keeping the last live.json")
        if prev:
            json.dump(prev, open("live.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        return
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump({"updated": now, "xau": xau, "gold": gold, "fx": fx}, open("live.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(now, "21k", gold["21"], "xau", xau, "usd", fx["USD"])


if __name__ == "__main__":
    main()
