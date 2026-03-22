import yfinance as yf
import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.5-flash"
GEMINI_URL     = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

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
    {"wkn": "A3C99G", "name": "Shell", "ticker": "SHEL.AS"},
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

def gemini_uebersetze_news(news_liste, unternehmensname):
    """Übersetzt News-Artikel mit Gemini ins Deutsche"""
    if not GEMINI_API_KEY or not news_liste:
        return news_liste

    # News als JSON-String für den Prompt vorbereiten
    news_json = json.dumps([{"titel": n.get("titel",""), "zusammenfassung": n.get("zusammenfassung","")} for n in news_liste], ensure_ascii=False)

    prompt = f"""Übersetze folgende Finanznachrichten über {unternehmensname} ins Deutsche.
Gib NUR valides JSON zurück, keine Erklärungen, keine Backticks.
Format: [{{"titel": "...", "zusammenfassung": "..."}}]

Originaltext:
{news_json}

Regeln:
- Titel: präzise, max 80 Zeichen
- Zusammenfassung: 1-2 Sätze, verständlich für Privatanleger
- Fachbegriffe dürfen auf Englisch bleiben (z.B. Q1, EPS, CEO)
- Nur JSON zurückgeben"""

    try:
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}
        }).encode('utf-8')

        req = urllib.request.Request(
            GEMINI_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = text.replace("```json", "").replace("```", "").strip()
        uebersetzt = json.loads(text)

        # Originaldaten mit Übersetzungen zusammenführen
        for i, n in enumerate(news_liste):
            if i < len(uebersetzt):
                n["titel_de"]         = uebersetzt[i].get("titel", n.get("titel",""))
                n["zusammenfassung_de"] = uebersetzt[i].get("zusammenfassung", "")
        return news_liste

    except Exception as e:
        print(f"    Übersetzungsfehler: {e}")
        return news_liste

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

        # Performance
        change_1d_pct = None
        if price_orig and prev_close and prev_close > 0:
            change_1d_pct = fmt((price_orig - prev_close) / prev_close * 100)

        change_1w_pct = None
        if len(hist) >= 6:
            p = hist["Close"].iloc[-6]
            if p > 0: change_1w_pct = fmt((hist["Close"].iloc[-1] - p) / p * 100)

        change_1m_pct = None
        if len(hist) >= 22:
            p = hist["Close"].iloc[-22]
            if p > 0: change_1m_pct = fmt((hist["Close"].iloc[-1] - p) / p * 100)

        change_1y_pct = None
        if len(hist) >= 2:
            p = hist["Close"].iloc[0]
            if p > 0: change_1y_pct = fmt((hist["Close"].iloc[-1] - p) / p * 100)

        # 52W Range in EUR
        w52_high = fmt(info.get("fiftyTwoWeekHigh"))
        w52_low  = fmt(info.get("fiftyTwoWeekLow"))
        w52_high_eur = fmt(w52_high * eur_rate) if w52_high else None
        w52_low_eur  = fmt(w52_low  * eur_rate) if w52_low  else None

        # Dividende
        div_rate  = fmt(info.get("dividendRate"))
        div_yield = None
        dy = info.get("dividendYield")
        if dy: div_yield = fmt(float(dy) * 100)
        div_rate_eur = fmt(div_rate * eur_rate) if div_rate else None

        # Analysten
        target_price   = fmt(info.get("targetMeanPrice"))
        target_eur     = fmt(target_price * eur_rate) if target_price else None
        recommendation = info.get("recommendationKey", "")
        analyst_count  = info.get("numberOfAnalystOpinions")

        rec_map = {
            "strong_buy": "Starker Kauf",
            "buy":        "Kaufen",
            "hold":       "Halten",
            "sell":       "Verkaufen",
            "strong_sell":"Starker Verkauf"
        }
        recommendation_de = rec_map.get(recommendation, recommendation)

        # Marktkapitalisierung
        mc = info.get("marketCap")
        if mc:
            if mc >= 1e12: mc_str = f"{mc/1e12:.2f}T"
            elif mc >= 1e9: mc_str = f"{mc/1e9:.1f}B"
            else: mc_str = f"{mc/1e6:.0f}M"
        else: mc_str = None

        # Sparkline in EUR
        sparkline = []
        if len(hist) >= 2:
            last30 = hist["Close"].tail(30)
            sparkline = [fmt(v * eur_rate, 4) for v in last30.tolist()]

        # ── News abrufen ──────────────────────────────────────
        news_liste = []
        try:
            raw_news = t.news
            if raw_news:
                for n in raw_news[:4]:  # Max 4 News
                    content = n.get("content", {})
                    title   = content.get("title", "") or n.get("title", "")
                    summary = content.get("summary", "") or ""
                    url     = ""
                    # URL aus verschiedenen Strukturen extrahieren
                    cp = content.get("canonicalUrl", {})
                    if isinstance(cp, dict):
                        url = cp.get("url", "")
                    if not url:
                        url = n.get("link", "") or n.get("url", "")

                    # Zeitstempel
                    pub_time = n.get("providerPublishTime") or content.get("pubDate", "")
                    datum_de = ""
                    if pub_time:
                        try:
                            if isinstance(pub_time, (int, float)):
                                dt = datetime.fromtimestamp(pub_time, tz=timezone.utc)
                            else:
                                dt = datetime.fromisoformat(str(pub_time).replace('Z','+00:00'))
                            datum_de = dt.strftime("%d.%m.%Y")
                        except: pass

                    quelle = content.get("provider", {})
                    if isinstance(quelle, dict):
                        quelle = quelle.get("displayName", "")
                    if not quelle:
                        quelle = n.get("publisher", "")

                    if title:
                        news_liste.append({
                            "titel":         title,
                            "zusammenfassung": summary[:200] if summary else "",
                            "url":           url,
                            "datum_de":      datum_de,
                            "quelle":        quelle,
                        })

            print(f"  {len(news_liste)} News gefunden")

            # Mit Gemini übersetzen
            if news_liste and GEMINI_API_KEY:
                print(f"  Übersetze mit Gemini...")
                news_liste = gemini_uebersetze_news(news_liste, s["name"])
                time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"  News-Fehler: {e}")

        chg = f"{change_1d_pct:+.2f}%" if change_1d_pct is not None else "–"
        print(f"  OK: €{price_eur} ({chg})")

        results.append({
            "wkn":             s["wkn"],
            "name":            s["name"],
            "ticker":          ticker,
            "currency_orig":   currency,
            "currency":        "EUR",
            "price":           price_eur,
            "price_orig":      price_orig,
            "eur_rate":        fmt(eur_rate, 6),
            "change_1d_pct":   change_1d_pct,
            "change_1w_pct":   change_1w_pct,
            "change_1m_pct":   change_1m_pct,
            "change_1y_pct":   change_1y_pct,
            "week52_high":     w52_high_eur,
            "week52_low":      w52_low_eur,
            "div_yield":       div_yield,
            "div_rate":        div_rate_eur,
            "market_cap":      mc_str,
            "pe_ratio":        fmt(info.get("trailingPE")),
            "target_price":    target_eur,
            "recommendation":  recommendation_de,
            "analyst_count":   analyst_count,
            "sparkline":       sparkline,
            "news":            news_liste,
            "fehler":          None
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
