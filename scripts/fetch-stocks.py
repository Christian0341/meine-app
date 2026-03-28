import yfinance as yf
import json
import os
import re
import time
import requests
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL     = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

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
    {"wkn": "A3C99G", "name": "Shell",                  "ticker": "SHELL.AS"},
    {"wkn": "723133", "name": "Sixt",                   "ticker": "SIX2.DE"},
    {"wkn": "852654", "name": "Texas Instruments",      "ticker": "TXN"},
    {"wkn": "869561", "name": "UnitedHealth",           "ticker": "UNH"},
]

def fmt(val, decimals=2):
    if val is None: return None
    try: return round(float(val), decimals)
    except: return None

def get_eur_rate(currency):
    if currency == 'EUR': return 1.0
    try:
        t = yf.Ticker(f"{currency}EUR=X")
        rate = t.info.get('regularMarketPrice') or t.fast_info.get('lastPrice')
        if rate: return float(rate)
    except: pass
    fallback = {'USD': 0.92, 'GBP': 1.17, 'JPY': 0.0061, 'CAD': 0.68, 'AUD': 0.60}
    return fallback.get(currency, 1.0)

def hole_news(ticker_obj):
    raw = []
    try:
        news = ticker_obj.news
        if not news: return []
        for item in news[:4]:
            titel = ''
            url   = ''
            quelle = ''
            datum  = ''
            if isinstance(item, dict):
                content = item.get('content', {})
                if content and isinstance(content, dict):
                    titel  = content.get('title', '')
                    quelle = content.get('provider', {}).get('displayName', '')
                    url    = (content.get('canonicalUrl', {}).get('url', '') or
                              content.get('clickThroughUrl', {}).get('url', ''))
                    pub    = content.get('pubDate', '')
                    if pub:
                        try:
                            dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                            datum = dt.strftime("%d.%m.%Y")
                        except: datum = pub[:10]
                if not titel:
                    titel  = item.get('title', '')
                    quelle = item.get('publisher', '')
                    url    = item.get('link', item.get('url', ''))
                    ts     = item.get('providerPublishTime', 0)
                    if ts:
                        try:
                            datum = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%d.%m.%Y")
                        except: pass
            if titel:
                raw.append({'titel': titel, 'url': url, 'quelle': quelle, 'datum': datum})
    except Exception as e:
        print(f"    News-Fehler: {e}")
    return raw

def parse_json_from_text(text):
    """Extrahiert JSON-Array aus beliebigem Text"""
    text = text.strip()
    # Direkt JSON?
    if text.startswith('['):
        return json.loads(text)
    # In Backticks?
    m = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Array irgendwo im Text?
    m = re.search(r'(\[.*\])', text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    raise ValueError(f"Kein JSON-Array gefunden: {text[:200]}")

def gemini_uebersetze(firmenname, news_liste):
    if not GEMINI_API_KEY or not news_liste:
        return [{
            "titel": n['titel'], "einordnung": "",
            "url": n.get('url',''), "quelle": n.get('quelle',''), "datum": n.get('datum','')
        } for n in news_liste]

    titelliste = "\n".join([f"{i+1}. {n['titel']}" for i, n in enumerate(news_liste)])

    prompt = f"""Übersetze diese {len(news_liste)} englischen Finanznachrichtentitel über {firmenname} ins Deutsche.
Füge jeweils eine kurze Einordnung hinzu (1 Satz auf Deutsch, was das für Aktionäre bedeutet).

Antworte NUR mit einem JSON-Array in diesem Format:
[
  {{"titel": "Deutscher Titel", "einordnung": "Kurze Einordnung"}},
  {{"titel": "Deutscher Titel 2", "einordnung": "Kurze Einordnung 2"}}
]

Originaltitel:
{titelliste}"""

    try:
        r = requests.post(GEMINI_URL, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000}
        }, timeout=30)
        r.raise_for_status()

        raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"    Gemini OK: {raw_text[:80]}...")

        uebersetzt = parse_json_from_text(raw_text)

        result = []
        for i, orig in enumerate(news_liste):
            ue = uebersetzt[i] if i < len(uebersetzt) else {}
            result.append({
                "titel":      ue.get("titel", orig['titel']),
                "einordnung": ue.get("einordnung", ""),
                "url":        orig.get('url', ''),
                "quelle":     orig.get('quelle', ''),
                "datum":      orig.get('datum', ''),
            })
        return result

    except Exception as e:
        print(f"    Gemini-Fehler: {e}")
        return [{
            "titel": n['titel'], "einordnung": "",
            "url": n.get('url',''), "quelle": n.get('quelle',''), "datum": n.get('datum','')
        } for n in news_liste]

results = []
eur_rates = {}

for s in STOCKS:
    ticker = s["ticker"]
    print(f"\nFetching {s['name']} ({ticker})...")
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="1y")

        currency = info.get("currency", "USD")
        if currency not in eur_rates:
            eur_rates[currency] = get_eur_rate(currency)
        eur_rate = eur_rates[currency]

        price_orig = fmt(info.get("currentPrice") or info.get("regularMarketPrice"))
        prev_close = fmt(info.get("previousClose"))
        price_eur  = fmt(price_orig * eur_rate) if price_orig else None

        change_1d_pct = None
        if price_orig and prev_close and prev_close > 0:
            change_1d_pct = fmt((price_orig - prev_close) / prev_close * 100)

        change_1w_pct = None
        if len(hist) >= 6:
            p1w = hist["Close"].iloc[-6]
            if p1w > 0: change_1w_pct = fmt((hist["Close"].iloc[-1] - p1w) / p1w * 100)

        change_1m_pct = None
        if len(hist) >= 22:
            p1m = hist["Close"].iloc[-22]
            if p1m > 0: change_1m_pct = fmt((hist["Close"].iloc[-1] - p1m) / p1m * 100)

        change_1y_pct = None
        if len(hist) >= 2:
            p1y = hist["Close"].iloc[0]
            if p1y > 0: change_1y_pct = fmt((hist["Close"].iloc[-1] - p1y) / p1y * 100)

        w52_high_eur = fmt(info.get("fiftyTwoWeekHigh", 0) * eur_rate) if info.get("fiftyTwoWeekHigh") else None
        w52_low_eur  = fmt(info.get("fiftyTwoWeekLow",  0) * eur_rate) if info.get("fiftyTwoWeekLow") else None

        div_rate     = fmt(info.get("dividendRate"))
        div_rate_eur = fmt(div_rate * eur_rate) if div_rate else None

        div_yield = None
        dy = info.get("dividendYield")
        if dy:
            dy_pct = float(dy) * 100
            if 0 < dy_pct < 25:
                div_yield = fmt(dy_pct)
        elif div_rate and price_orig and price_orig > 0:
            dy_calc = (div_rate / price_orig) * 100
            if 0 < dy_calc < 25:
                div_yield = fmt(dy_calc)

        mc = info.get("marketCap")
        mc_str = None
        if mc:
            if mc >= 1e12: mc_str = f"{mc/1e12:.2f}T"
            elif mc >= 1e9: mc_str = f"{mc/1e9:.1f}B"
            else: mc_str = f"{mc/1e6:.0f}M"

        sparkline = []
        if len(hist) >= 2:
            sparkline = [fmt(v * eur_rate, 4) for v in hist["Close"].tail(30).tolist()]

        analyst_rating = info.get("recommendationKey", "")
        analyst_target = fmt(info.get("targetMeanPrice", 0) * eur_rate) if info.get("targetMeanPrice") else None
        analyst_count  = info.get("numberOfAnalystOpinions")
        rating_map = {"strong_buy":"Starker Kauf","buy":"Kaufen","hold":"Halten","sell":"Verkaufen","strong_sell":"Starker Verkauf"}
        analyst_rating_de = rating_map.get(analyst_rating, analyst_rating)

        raw_news = hole_news(t)
        print(f"  {len(raw_news)} News gefunden")

        news_de = []
        if raw_news:
            news_de = gemini_uebersetze(s["name"], raw_news)
            time.sleep(2)

        chg = f"{change_1d_pct:+.2f}%" if change_1d_pct is not None else "–"
        print(f"  OK: €{price_eur} ({chg}) | {len(news_de)} News übersetzt")

        results.append({
            "wkn":            s["wkn"],
            "name":           s["name"],
            "ticker":         ticker,
            "currency":       "EUR",
            "price":          price_eur,
            "change_1d_pct":  change_1d_pct,
            "change_1w_pct":  change_1w_pct,
            "change_1m_pct":  change_1m_pct,
            "change_1y_pct":  change_1y_pct,
            "week52_high":    w52_high_eur,
            "week52_low":     w52_low_eur,
            "div_yield":      div_yield,
            "div_rate":       div_rate_eur,
            "market_cap":     mc_str,
            "pe_ratio":       fmt(info.get("trailingPE")),
            "sparkline":      sparkline,
            "analyst_rating": analyst_rating_de,
            "analyst_target": analyst_target,
            "analyst_count":  analyst_count,
            "news":           news_de,
            "fehler":         None
        })

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

print(f"\nFertig! {len(results)} Aktien gespeichert.")
