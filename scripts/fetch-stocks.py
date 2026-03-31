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
        print(f"    News-Fehler: {e}")
    return items

def uebersetze(name, news):
    if not GEMINI_API_KEY or not news:
        return [{'titel': n['titel'], 'einordnung': '', 'url': n['url'], 'quelle': n['quelle'], 'datum': n['datum']} for n in news]

    titeln = "\n".join(f"{i+1}. {n['titel']}" for i, n in enumerate(news))
    prompt = (
        f"Uebersetzungsaufgabe fuer Aktionare von {name}.\n"
        f"Uebersetze {len(news)} englische Finanznachrichten-Titel auf Deutsch.\n"
        f"Antworte NUR mit diesem JSON-Array (keine anderen Texte):\n"
        f'[{{"titel":"DE-Titel","einordnung":"1 Satz Einordnung fuer Aktionaere"}}]\n\n'
        f"Titel:\n{titeln}"
    )

    try:
        resp = requests.post(GEMINI_URL, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800}
        }, timeout=30)

        print(f"    Gemini HTTP: {resp.status_code}")
        body = resp.json()

        if 'error' in body:
            print(f"    Gemini API-Fehler: {body['error'].get('message','')[:100]}")
            raise Exception("API error")

        text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"    Gemini Antwort: {text[:100]}")

        # JSON extrahieren
        if not text.startswith('['):
            m = re.search(r'\[.*\]', text, re.DOTALL)
            text = m.group(0) if m else '[]'

        ue = json.loads(text)
        result = []
        for i, orig in enumerate(news):
            u = ue[i] if i < len(ue) else {}
            result.append({
                'titel':      u.get('titel', orig['titel']),
                'einordnung': u.get('einordnung', ''),
                'url':        orig['url'],
                'quelle':     orig['quelle'],
                'datum':      orig['datum'],
            })
        return result

    except Exception as e:
        print(f"    Gemini-Fehler: {e}")
        return [{'titel': n['titel'], 'einordnung': '', 'url': n['url'], 'quelle': n['quelle'], 'datum': n['datum']} for n in news]

results = []
rates = {}

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
        print(f"  {len(raw_news)} News")
        news_de = uebersetze(s['name'], raw_news) if raw_news else []
        if raw_news: time.sleep(4)

        chg = f"{d1:+.2f}%" if d1 is not None else "–"
        print(f"  OK: €{pe} ({chg}) | {len(news_de)} News übersetzt")

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
            "news": news_de, "fehler": None
        })

    except Exception as e:
        print(f"  FEHLER: {e}")
        results.append({"wkn": s["wkn"], "name": s["name"], "ticker": s["ticker"], "fehler": str(e)})

os.makedirs("data", exist_ok=True)
with open("data/stocks.json", "w", encoding="utf-8") as f:
    json.dump({"aktualisiert": datetime.now(timezone.utc).isoformat(), "aktien": results}, f, ensure_ascii=False, indent=2)

print(f"\nFertig! {len(results)} Aktien.")
