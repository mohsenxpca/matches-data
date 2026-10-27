"""Egyptian market gold prices (buy/sell per karat, gold pound) + world spot + USD/EGP -> live.json.

Runs every 5 minutes on GitHub Actions (.github/workflows/goldlive.yml) and is pushed to the 'live' branch
(force-pushed, so the main history doesn't grow). The gold/currency pages read it every minute and move the
prices with the world spot price (api.gold-api.com) between two snapshots.
"""
import datetime, json, re, sys
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
KARATS = {"عيار 24": "24", "عيار 22": "22", "عيار 21": "21", "عيار 18": "18", "عيار 14": "14", "عيار 12": "12", "جنيه ذهب": "pound"}


def market():
    s = BeautifulSoup(requests.get("https://isagha.com/", headers=UA, timeout=30).text, "html.parser")
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
    gold = market()
    xau = requests.get("https://api.gold-api.com/price/XAU", headers=UA, timeout=20).json()["price"]
    usd = requests.get("https://open.er-api.com/v6/latest/USD", headers=UA, timeout=20).json()["rates"]
    fx = {c: round(usd["EGP"] / usd[c], 4) for c in ("USD", "EUR", "SAR", "AED", "KWD", "GBP", "QAR", "JOD", "OMR", "BHD", "CNY", "TRY") if c in usd}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump({"updated": now, "xau": xau, "gold": gold, "fx": fx}, open("live.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(now, "21k", gold["21"], "xau", xau, "usd", fx["USD"])


if __name__ == "__main__":
    main()
