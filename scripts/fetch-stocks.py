import yfinance as yf
import json
import os
from datetime import datetime, timezone

STOCKS = [
    {"wkn": "A1J84E", "name": "AbbVie",              "ticker": "ABBV"},
    {"wkn": "A2ANT0", "name": "Ahold Delhaize",       "ticker": "AD.AS"},
    {"wkn": "840400", "name": "Allianz",               "ticker": "ALV.DE"},
    {"wkn": "850471", "name": "Boeing",                "ticker": "BA"},
    {"wkn": "850501", "name": "Bristol-Myers Squibb",  "ticker": "BMY"},
    {"wkn": "916018", "name": "Brit. American Tobacco","ticker": "BTI"},
    {"wkn": "878841", "name": "Cisco Systems",         "ticker": "CSCO"},
    {"wkn": "A0MW32", "name": "CME Group",             "ticker": "CME"},
    {"wkn": "547030", "name": "CTS Eventim",           "ticker": "EVD.DE"},
    {"wkn": "887891", "name": "Fastenal",              "ticker": "FAST"},
    {"wkn": "853260", "name": "Johnson & Johnson",     "ticker": "JNJ"},
    {"wkn": "A0RLRP", "name": "Koei Tecmo",           "ticker": "3635.T"},
    {"wkn": "856958", "name": "McDonald's",            "ticker": "MCD"},
    {"wkn": "710000", "name": "Mercedes-Benz",         "ticker": "MBG.DE"},
    {"wkn": "851995", "name": "PepsiCo",               "ticker": "PEP"},
    {"wkn": "899744", "name": "Realty Income",         "ticker": "O"},
    {"wkn": "852147", "name": "Rio Tinto",             "ticker": "RIO"},
    {"wkn": "A3C99G", "name": "Shell",                 "ticker": "SHEL.AS"},
    {"wkn": "723133", "name": "Sixt",                  "ticker": "SIX2.DE"},
    {"wkn": "852654", "name": "Texas Instruments",     "ticker": "TXN"},
    {"wkn": "869561", "name": "UnitedHealth",          "ticker": "UNH"},
]

def fmt(val, decimals=2):
    if val is None:
        return None
    try:
        return round(float(val), decimals)
    except:
        return None

def pct(val):
    if val is None:
        return None
    try:
        return round(float(val) * 100, 2)
    except:
        return None

results = []

for s in STOCKS:
    ticker = s["ticker"]
    print(f"Fetching {s['name']} ({ticker})...")
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="1y")

        price = fmt(info.get("currentPrice") or info.get("regularMarketPrice"))
        currency = info.get("currency", "")
        prev_close = fmt(info.get("previousClose"))

        # Tagesveränderung
        change_1d = None
        change_1d_pct = None
        if price and prev_close and prev_close > 0:
            change_1d = fmt(price - prev_close)
            change_1d_pct = fmt((price - prev_close) / prev_close * 100)

        # Wochenveränderung (5 Handelstage)
        change_1w_pct = None
        if len(hist) >= 6:
            price_1w = hist["Close"].iloc[-6]
            if price_1w > 0:
                change_1w_pct = fmt((hist["Close"].iloc[-1] - price_1w) / price_1w * 100)

        # Monatsveränderung (21 Handelstage)
        change_1m_pct = None
        if len(hist) >= 22:
            price_1m = hist["Close"].iloc[-22]
            if price_1m > 0:
                change_1m_pct = fmt((hist["Close"].iloc[-1] - price_1m) / price_1m * 100)

        # Jahresveränderung
        change_1y_pct = None
        if len(hist) >= 2:
            price_1y = hist["Close"].iloc[0]
            if price_1y > 0:
                change_1y_pct = fmt((hist["Close"].iloc[-1] - price_1y) / price_1y * 100)

        # 52-Wochen-Range
        week52_high = fmt(info.get("fiftyTwoWeekHigh"))
        week52_low  = fmt(info.get("fiftyTwoWeekLow"))

        # Dividende
        div_yield = pct(info.get("dividendYield"))
        div_rate  = fmt(info.get("dividendRate"))
        ex_div    = info.get("exDividendDate")
        if ex_div:
            try:
                ex_div = datetime.fromtimestamp(ex_div, tz=timezone.utc).strftime("%Y-%m-%d")
            except:
                ex_div = None

        # Kennzahlen
        market_cap = info.get("marketCap")
        if market_cap:
            if market_cap >= 1e12:
                market_cap_str = f"{market_cap/1e12:.2f}T"
            elif market_cap >= 1e9:
                market_cap_str = f"{market_cap/1e9:.1f}B"
            else:
                market_cap_str = f"{market_cap/1e6:.0f}M"
        else:
            market_cap_str = None

        # Sparkline (letzte 30 Tage Schlusskurse)
        sparkline = []
        if len(hist) >= 2:
            last30 = hist["Close"].tail(30)
            sparkline = [fmt(v, 4) for v in last30.tolist()]

        results.append({
            "wkn":           s["wkn"],
            "name":          s["name"],
            "ticker":        ticker,
            "currency":      currency,
            "price":         price,
            "change_1d":     change_1d,
            "change_1d_pct": change_1d_pct,
            "change_1w_pct": change_1w_pct,
            "change_1m_pct": change_1m_pct,
            "change_1y_pct": change_1y_pct,
            "week52_high":   week52_high,
            "week52_low":    week52_low,
            "div_yield":     div_yield,
            "div_rate":      div_rate,
            "ex_div":        ex_div,
            "market_cap":    market_cap_str,
            "pe_ratio":      fmt(info.get("trailingPE")),
            "sparkline":     sparkline,
            "fehler":        None
        })
        print(f"  OK: {price} {currency} ({change_1d_pct:+.2f}%)" if price and change_1d_pct else f"  OK: {price} {currency}")

    except Exception as e:
        print(f"  FEHLER: {e}")
        results.append({
            "wkn":    s["wkn"],
            "name":   s["name"],
            "ticker": ticker,
            "fehler": str(e)
        })

output = {
    "aktualisiert": datetime.now(timezone.utc).isoformat(),
    "aktien": results
}

os.makedirs("data", exist_ok=True)
with open("data/stocks.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nFertig! {len(results)} Aktien gespeichert.")
