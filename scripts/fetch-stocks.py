import yfinance as yf
import json, os, re, time, requests
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

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

def fmt(v, d=2):
    if v is None: return None
    try: return round(float(v), d)
    except: return None

def eur_rate(cur):
    if cur == 'EUR': return 1.0
    try:
        r = yf.Ticker(f"{cur}EUR=X").info.get('regularMarketPrice')
        if r: return float(r)
    except: pass
    return {'USD':0.92,'GBP':1.17,'JPY':0.0061,'CAD':0.68,'AUD':0.60}.get(cur, 1.0)

def hole_news(t):
    items = []
    try:
        for n in (t.news or [])[:4]:
            c = n.get('content', {}) if isinstance(n, dict) else {}
            titel  = c.get('title') or n.get('title', '')
            quelle = c.get('provider', {}).get('displayName') or n.get('publisher', '')
            url    = (c.get('canonicalUrl', {}).get('url') or
                      c.get('clickThroughUrl', {}).get('url') or
                      n.get('link') or n.get('url', ''))
            pub    = c.get('pubDate', '')
            if pub:
                try: datum = datetime.fromisoformat(pub.replace('Z','+00:00')).strftime("%d.%m.%Y")
                except: datum = pub[:10]
            else:
                ts = n.get('providerPublishTime', 0)
                try: datum = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%d.%m.%Y") if ts else ''
                except: datum = ''
            if titel:
                items.append({'titel': titel, 'url': url, 'quelle': quelle, 'datum': datum})
    except Exception as e:
        print(f"  News-Fehler: {e}")
    return items

def uebersetze_alle(alle_news_dict):
    """
    Übersetzt ALLE News in einer einzigen Gemini-Anfrage.
    alle_news_dict: {"AbbVie": [news1, news2...], "Allianz": [...], ...}
    Gibt zurück: {"AbbVie": [ue1, ue2...], ...}
    """
    if not GEMINI_API_KEY:
        return {}

    # Alle Titel nummeriert auflisten
    alle_eintraege = []  # [(firmenname, index, news)]
    for firma, news_liste in alle_news_dict.items():
        for i, n in enumerate(news_liste):
            alle_eintraege.append((firma, i, n))

    if not alle_eintraege:
        return {}

    titelliste = "\n".join(
        f"{idx+1}. [{firma}] {n['titel']}"
        for idx, (firma, i, n) in enumerate(alle_eintraege)
    )

    prompt = (
        f"Uebersetze {len(alle_eintraege)} englische Finanznachrichten-Titel ins Deutsche.\n"
        f"Schreibe fuer jeden Titel eine kurze Einordnung (1 Satz) fuer Aktionaere.\n"
        f"Antworte NUR mit einem JSON-Array:\n"
        f'[{{"titel":"DE-Titel","einordnung":"Einordnung"}}]\n\n'
        f"Titel:\n{titelliste}"
    )

    try:
        resp = requests.post(GEMINI_URL, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8000}
        }, timeout=60)

        print(f"Gemini HTTP: {resp.status_code}")
        body = resp.json()

        if 'error' in body:
            print(f"Gemini Fehler: {body['error'].get('message','')[:150]}")
            return {}

        text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"Gemini Antwort: {len(text)} Zeichen")

        # JSON extrahieren
        if not text.startswith('['):
            m = re.search(r'\[.*\]', text, re.DOTALL)
            text = m.group(0) if m else '[]'

        ue_liste = json.loads(text)
        print(f"Gemini: {len(ue_liste)} Übersetzungen erhalten")

        # Ergebnisse zurück den Firmen zuordnen
        result = {}
        for idx, (firma, i, orig) in enumerate(alle_eintraege):
            if firma not in result:
                result[firma] = []
            ue = ue_liste[idx] if idx < len(ue_liste) else {}
            result[firma].append({
                'titel':      ue.get('titel', orig['titel']),
                'einordnung': ue.get('einordnung', ''),
                'url':        orig['url'],
                'quelle':     orig['quelle'],
                'datum':      orig['datum'],
            })
        return result

    except Exception as e:
        print(f"Gemini Ausnahme: {e}")
        return {}

# ── Schritt 1: Alle Aktiendaten abrufen ──────────────────────────────────────
print("=== Aktiendaten abrufen ===")
results = []
rates = {}
alle_news_roh = {}  # Firma -> raw news

for s in STOCKS:
    print(f"\n{s['name']} ({s['ticker']})...")
    try:
        t    = yf.Ticker(s['ticker'])
        info = t.info
        hist = t.history(period="1y")
        cur  = info.get('currency', 'USD')
        if cur not in rates: rates[cur] = eur_rate(cur)
        er   = rates[cur]

        po   = fmt(info.get('currentPrice') or info.get('regularMarketPrice'))
        pc   = fmt(info.get('previousClose'))
        pe   = fmt(po * er) if po else None

        d1 = fmt((po-pc)/pc*100) if po and pc and pc>0 else None
        d1w = d1m = d1y = None
        if len(hist)>=6:  d1w = fmt((hist["Close"].iloc[-1]-hist["Close"].iloc[-6])/hist["Close"].iloc[-6]*100)
        if len(hist)>=22: d1m = fmt((hist["Close"].iloc[-1]-hist["Close"].iloc[-22])/hist["Close"].iloc[-22]*100)
        if len(hist)>=2:  d1y = fmt((hist["Close"].iloc[-1]-hist["Close"].iloc[0])/hist["Close"].iloc[0]*100)

        h52 = fmt(info.get('fiftyTwoWeekHigh',0)*er) if info.get('fiftyTwoWeekHigh') else None
        l52 = fmt(info.get('fiftyTwoWeekLow',0)*er)  if info.get('fiftyTwoWeekLow')  else None
        dr  = fmt(info.get('dividendRate'))
        dre = fmt(dr*er) if dr else None

        dy = None
        raw_dy = info.get('dividendYield')
        if raw_dy:
            p = float(raw_dy)*100
            if 0 < p < 25: dy = fmt(p)
        elif dr and po and po > 0:
            p = dr/po*100
            if 0 < p < 25: dy = fmt(p)

        mc = info.get('marketCap')
        mcs = f"{mc/1e12:.2f}T" if mc and mc>=1e12 else f"{mc/1e9:.1f}B" if mc and mc>=1e9 else f"{mc/1e6:.0f}M" if mc else None
        sp  = [fmt(v*er,4) for v in hist["Close"].tail(30).tolist()] if len(hist)>=2 else []

        rm  = {"strong_buy":"Starker Kauf","buy":"Kaufen","hold":"Halten","sell":"Verkaufen","strong_sell":"Starker Verkauf"}
        ar  = rm.get(info.get('recommendationKey',''), info.get('recommendationKey',''))
        at  = fmt(info.get('targetMeanPrice',0)*er) if info.get('targetMeanPrice') else None
        ac  = info.get('numberOfAnalystOpinions')

        raw_news = hole_news(t)
        print(f"  {len(raw_news)} News gefunden")
        if raw_news:
            alle_news_roh[s['name']] = raw_news

        chg = f"{d1:+.2f}%" if d1 is not None else "–"
        print(f"  Kurs: €{pe} ({chg})")

        results.append({
            "wkn": s["wkn"], "name": s["name"], "ticker": s["ticker"],
            "currency": "EUR", "price": pe,
            "change_1d_pct": d1, "change_1w_pct": d1w,
            "change_1m_pct": d1m, "change_1y_pct": d1y,
            "week52_high": h52, "week52_low": l52,
            "div_yield": dy, "div_rate": dre,
            "market_cap": mcs, "pe_ratio": fmt(info.get('trailingPE')),
            "sparkline": sp,
            "analyst_rating": ar, "analyst_target": at, "analyst_count": ac,
            "news": [],  # wird später befüllt
            "fehler": None
        })

    except Exception as e:
        print(f"  FEHLER: {e}")
        results.append({"wkn": s["wkn"], "name": s["name"], "ticker": s["ticker"], "fehler": str(e)})

# ── Schritt 2: Alle News in einer Gemini-Anfrage übersetzen ───────────────────
print(f"\n=== Übersetze alle News ({sum(len(v) for v in alle_news_roh.values())} Titel) ===")
ue_alle = uebersetze_alle(alle_news_roh)

# News den Ergebnissen zuordnen
for r in results:
    if r.get('fehler'): continue
    name = r['name']
    if name in ue_alle:
        r['news'] = ue_alle[name]
    elif name in alle_news_roh:
        # Fallback: englische Originale
        r['news'] = [{'titel': n['titel'], 'einordnung': '', 'url': n['url'], 'quelle': n['quelle'], 'datum': n['datum']} for n in alle_news_roh[name]]

# ── Speichern ─────────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
with open("data/stocks.json", "w", encoding="utf-8") as f:
    json.dump({"aktualisiert": datetime.now(timezone.utc).isoformat(), "aktien": results}, f, ensure_ascii=False, indent=2)

print(f"\nFertig! {len(results)} Aktien gespeichert.")
