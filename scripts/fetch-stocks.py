import yfinance as yf
import json
import os
from datetime import datetime, timezone

STOCKS = [
    {"wkn": "A1J84E", "name": "AbbVie",               "ticker": "ABBV"},
    {"wkn": "A2ANT0", "name": "Ahold Delhaize",        "ticker": "AD.AS"},
    {"wkn": "840400", "name": "Allianz",                "ticker": "ALV.DE"},
    {"wkn": "850471", "name": "Boeing",                 "ticker": "BA"},
    {"wkn": "850501", "name": "Bristol-Myers Squibb",   "ticker": "BMY"},
    {"wkn": "916018", "name": "Brit. American Tobacco", "ticker": "BTI"},
    {"wkn": "878841", "name": "Cisco Systems",          "ticker": "CSCO"},
    {"wkn": "A0MW32", "name": "CME Group",              "ticker": "CME"},
    {"wkn": "547030", "name": "CTS Eventim",            "ticker": "EVD.DE"},
    {"wkn": "887891", "name": "Fastenal",               "ticker": "FAST"},
    {"wkn": "853260", "name": "Johnson & Johnson",      "ticker": "JNJ"},
    {"wkn": "A0RLRP", "name": "Koei Tecmo",            "ticker": "3635.T"},
    {"wkn": "856958", "name": "McDonald's",             "ticker": "MCD"},
    {"wkn": "710000", "name": "Mercedes-Benz",          "ticker": "MBG.DE"},
    {"wkn": "851995", "name": "PepsiCo",                "ticker": "PEP"},
    {"wkn": "899744", "name": "Realty Income",          "ticker": "O"},
    {"wkn": "852147", "name": "Rio Tinto",              "ticker": "RIO"},
   {"wkn": "A3C99G", "name": "Shell", "ticker": "SHEL.L"},
    {"wkn": "723133", "name": "Sixt",                   "ticker": "SIX2.DE"},
    {"wkn": "852654", "name": "Texas Instruments",      "ticker": "TXN"},
    {"wkn": "869561", "name": "UnitedHealth",           "ticker": "UNH"},
]

def fmt(val, decimals=2):
    if val is None: return None
    try: return round(float(val), decimals)
    except: return None

def get_eur_rate(currency):
    """Holt EUR-Umrechnungskurs für eine Währung"""
    if currency == 'EUR': return 1.0
    try:
        pair = f"{currency}EUR=X"
        t = yf.Ticker(pair)
        rate = t.info.get('regularMarketPrice') or t.fast_info.get('lastPrice')
        if rate: return float(rate)
    except: pass
    # Fallback-Kurse
    fallback = {'USD': 0.92, 'GBP': 1.17, 'JPY': 0.0061, 'CAD': 0.68, 'AUD': 0.60}
    return fallback.get(currency, 1.0)

results = []
eur_rates = {}

for s in STOCKS:
    ticker = s["ticker"]
    print(f"Fetching {s['name']} ({ticker})...")
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="1y")

        currency = info.get("currency", "USD")

        # EUR-Kurs holen (gecacht)
        if currency not in eur_rates:
            eur_rates[currency] = get_eur_rate(currency)
        eur_rate = eur_rates[currency]

        price_orig = fmt(info.get("currentPrice") or info.get("regularMarketPrice"))
        prev_close = fmt(info.get("previousClose"))

        # Alles in EUR umrechnen
        price_eur = fmt(price_orig * eur_rate) if price_orig else None

        # Tagesveränderung (%)
        change_1d_pct = None
        if price_orig and prev_close and prev_close > 0:
            change_1d_pct = fmt((price_orig - prev_close) / prev_close * 100)

        # Wochenveränderung (%)
        change_1w_pct = None
        if len(hist) >= 6:
            p1w = hist["Close"].iloc[-6]
            if p1w > 0:
                change_1w_pct = fmt((hist["Close"].iloc[-1] - p1w) / p1w * 100)

        # Monatsveränderung (%)
        change_1m_pct = None
        if len(hist) >= 22:
            p1m = hist["Close"].iloc[-22]
            if p1m > 0:
                change_1m_pct = fmt((hist["Close"].iloc[-1] - p1m) / p1m * 100)

        # Jahresveränderung (%)
        change_1y_pct = None
        if len(hist) >= 2:
            p1y = hist["Close"].iloc[0]
            if p1y > 0:
                change_1y_pct = fmt((hist["Close"].iloc[-1] - p1y) / p1y * 100)

        # 52W Range in EUR
        w52_high = fmt(info.get("fiftyTwoWeekHigh"))
        w52_low  = fmt(info.get("fiftyTwoWeekLow"))
        w52_high_eur = fmt(w52_high * eur_rate) if w52_high else None
        w52_low_eur  = fmt(w52_low  * eur_rate) if w52_low  else None

        # Dividende in EUR
        div_rate = fmt(info.get("dividendRate"))
        div_rate_eur = fmt(div_rate * eur_rate) if div_rate else None
        div_yield = None
        dy = info.get("dividendYield")
        if dy: div_yield = fmt(float(dy) * 100)

        # Marktkapitalisierung
        mc = info.get("marketCap")
        if mc:
            if mc >= 1e12: mc_str = f"{mc/1e12:.2f}T"
            elif mc >= 1e9: mc_str = f"{mc/1e9:.1f}B"
            else: mc_str = f"{mc/1e6:.0f}M"
        else: mc_str = None

        # Sparkline (letzte 30 Tage, in EUR)
        sparkline = []
        if len(hist) >= 2:
            last30 = hist["Close"].tail(30)
            sparkline = [fmt(v * eur_rate, 4) for v in last30.tolist()]

        results.append({
            "wkn":           s["wkn"],
            "name":          s["name"],
            "ticker":        ticker,
            "currency_orig": currency,
            "currency":      "EUR",
            "price":         price_eur,
            "price_orig":    price_orig,
            "eur_rate":      fmt(eur_rate, 6),
            "change_1d_pct": change_1d_pct,
            "change_1w_pct": change_1w_pct,
            "change_1m_pct": change_1m_pct,
            "change_1y_pct": change_1y_pct,
            "week52_high":   w52_high_eur,
            "week52_low":    w52_low_eur,
            "div_yield":     div_yield,
            "div_rate":      div_rate_eur,
            "market_cap":    mc_str,
            "pe_ratio":      fmt(info.get("trailingPE")),
            "sparkline":     sparkline,
            "fehler":        None
        })
        chg = f"{change_1d_pct:+.2f}%" if change_1d_pct is not None else "–"
        print(f"  OK: €{price_eur} ({chg})")

    except Exception as e:
        print(f"  FEHLER: {e}")
        results.append({"wkn": s["wkn"], "name": s["name"], "ticker": ticker, "fehler": str(e)})

output = {
    "aktualisiert": datetime.now(timezone.utc).isoformat(),
    "aktien": results
}

os.makedirs("data", exist_ok=True)
with open("data/stocks.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nFertig! {len(results)} Aktien gespeichert (alle in EUR).")
