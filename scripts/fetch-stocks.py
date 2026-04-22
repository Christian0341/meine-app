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

# ── Gemini API mit Retry-Mechanismus ─────────────────────────────────────────
def gemini_mit_retry(payload, max_versuche=4):
    """Schickt einen Request an Gemini mit exponential backoff bei 429/503."""
    wartezeiten = [20, 60, 120]  # Sekunden — erhöht wegen anhaltender 503-Fehler

    for versuch in range(1, max_versuche + 1):
        try:
            print(f"  Gemini Versuch {versuch}/{max_versuche}...")
            resp = requests.post(GEMINI_URL, json=payload, timeout=90)
            print(f"  Gemini HTTP: {resp.status_code}")

            if resp.status_code == 200:
                return resp

            # Bei 429 (Rate Limit) oder 503 (Überlastet) → Retry
            if resp.status_code in (429, 503) and versuch < max_versuche:
                warte = wartezeiten[versuch - 1]
                print(f"  ⚠️ Gemini {resp.status_code} — warte {warte}s vor Versuch {versuch+1}...")
                time.sleep(warte)
                continue

            # Anderen Fehler loggen und None zurückgeben
            print(f"  ❌ Gemini Fehler {resp.status_code}: {resp.text[:200]}")
            return None

        except Exception as e:
            if versuch < max_versuche:
                warte = wartezeiten[versuch - 1]
                print(f"  ⚠️ Netzwerkfehler (Versuch {versuch}): {e} — warte {warte}s...")
                time.sleep(warte)
            else:
                print(f"  ❌ Netzwerkfehler nach {max_versuche} Versuchen: {e}")
                return None

    return None

# ── Einen Batch übersetzen ────────────────────────────────────────────────────
def uebersetze_batch(eintraege):
    """
    Übersetzt einen Batch von News-Titeln via Gemini.
    eintraege: [(firmenname, index, news_dict), ...]
    Gibt zurück: [{titel, einordnung}, ...] in gleicher Reihenfolge, oder [] bei Fehler
    """
    if not eintraege:
        return []

    titelliste = "\n".join(
        f"{idx+1}. [{firma}] {n['titel']}"
        for idx, (firma, i, n) in enumerate(eintraege)
    )

    prompt = (
        f"Uebersetze {len(eintraege)} englische Finanznachrichten-Titel ins Deutsche.\n"
        f"Schreibe fuer jeden Titel eine kurze Einordnung (1 Satz) fuer Aktionaere.\n"
        f"Antworte NUR mit einem JSON-Array (kein Markdown, keine Erklaerungen):\n"
        f'[{{"titel":"DE-Titel","einordnung":"Einordnung"}}]\n\n'
        f"Titel:\n{titelliste}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # FIX: 8000 Tokens — 40 Titel × ~15 Wörter JSON brauchen ~3000, Puffer für Sonderzeichen
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8000}
    }

    resp = gemini_mit_retry(payload)
    if resp is None:
        return []

    try:
        body = resp.json()

        if 'error' in body:
            print(f"  ❌ Gemini API-Fehler: {body['error'].get('message','')[:200]}")
            return []

        text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"  Gemini Antwort: {len(text)} Zeichen")

        # JSON aus Antwort extrahieren (entfernt Markdown-Backticks falls vorhanden)
        text = re.sub(r'```json\s*|\s*```', '', text).strip()
        if not text.startswith('['):
            m = re.search(r'\[.*\]', text, re.DOTALL)
            text = m.group(0) if m else '[]'

        ue_liste = json.loads(text)
        print(f"  ✅ {len(ue_liste)}/{len(eintraege)} Übersetzungen erhalten")
        return ue_liste

    except Exception as e:
        print(f"  ❌ Parse-Fehler: {e}")
        return []

# ── Alle News in Batches übersetzen ──────────────────────────────────────────
def uebersetze_alle(alle_news_dict, batch_groesse=20):
    """
    Übersetzt ALLE News in Batches (max. batch_groesse Titel pro Request).
    Verhindert 429-Fehler durch kleinere Batches + Pause zwischen Batches.
    """
    if not GEMINI_API_KEY:
        print("  ⚠️ GEMINI_API_KEY nicht gesetzt — überspringe Übersetzung")
        return {}

    # Alle Einträge flach auflisten
    alle_eintraege = []
    for firma, news_liste in alle_news_dict.items():
        for i, n in enumerate(news_liste):
            alle_eintraege.append((firma, i, n))

    if not alle_eintraege:
        return {}

    gesamt = len(alle_eintraege)
    print(f"  {gesamt} Titel in Batches à {batch_groesse}...")

    # In Batches aufteilen
    alle_ue = []
    for start in range(0, gesamt, batch_groesse):
        batch = alle_eintraege[start:start + batch_groesse]
        batch_nr = start // batch_groesse + 1
        batch_gesamt = (gesamt + batch_groesse - 1) // batch_groesse
        print(f"\n  Batch {batch_nr}/{batch_gesamt} ({len(batch)} Titel):")

        ue_batch = uebersetze_batch(batch)
        alle_ue.extend(ue_batch)

        # Pause zwischen Batches (außer nach dem letzten)
        if start + batch_groesse < gesamt:
            print("  Pause 15s zwischen Batches...")
            time.sleep(15)

    # Ergebnisse zurück den Firmen zuordnen
    result = {}
    for idx, (firma, i, orig) in enumerate(alle_eintraege):
        if firma not in result:
            result[firma] = []
        ue = alle_ue[idx] if idx < len(alle_ue) else {}
        result[firma].append({
            'titel':      ue.get('titel', orig['titel']),
            'einordnung': ue.get('einordnung', ''),
            'url':        orig['url'],
            'quelle':     orig['quelle'],
            'datum':      orig['datum'],
        })

    uebersetzt = sum(1 for idx, _ in enumerate(alle_eintraege) if idx < len(alle_ue) and alle_ue[idx].get('titel'))
    print(f"\n  Übersetzung abgeschlossen: {uebersetzt}/{gesamt} Titel übersetzt")
    return result

# ── Schritt 1: Alle Aktiendaten abrufen ──────────────────────────────────────
print("=== Aktiendaten abrufen ===")
results = []
rates = {}
alle_news_roh = {}

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
        if len(hist)>=6:
            v = fmt((hist["Close"].iloc[-1]-hist["Close"].iloc[-6])/hist["Close"].iloc[-6]*100)
            d1w = None if v != v else v  # NaN check
        if len(hist)>=22:
            v = fmt((hist["Close"].iloc[-1]-hist["Close"].iloc[-22])/hist["Close"].iloc[-22]*100)
            d1m = None if v != v else v
        if len(hist)>=2:
            v = fmt((hist["Close"].iloc[-1]-hist["Close"].iloc[0])/hist["Close"].iloc[0]*100)
            d1y = None if v != v else v

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
        sp  = [x if x is not None and x == x else None for x in [fmt(v*er,4) for v in hist["Close"].tail(30).tolist()]] if len(hist)>=2 else []

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
            "news": [],
            "fehler": None
        })

    except Exception as e:
        print(f"  FEHLER: {e}")
        results.append({"wkn": s["wkn"], "name": s["name"], "ticker": s["ticker"], "fehler": str(e)})

# ── Schritt 2: Alle News in Batches übersetzen ────────────────────────────────
gesamt_news = sum(len(v) for v in alle_news_roh.values())
print(f"\n=== Übersetze alle News ({gesamt_news} Titel) ===")
ue_alle = uebersetze_alle(alle_news_roh, batch_groesse=20)

# News den Ergebnissen zuordnen
uebersetzt_count = 0
englisch_count = 0
for r in results:
    if r.get('fehler'): continue
    name = r['name']
    if name in ue_alle and ue_alle[name] and ue_alle[name][0].get("titel"):
        r['news'] = ue_alle[name]
        uebersetzt_count += len(ue_alle[name])
    elif name in alle_news_roh:
        # Fallback: englische Originale (mit Log-Hinweis)
        print(f"  ⚠️ Fallback auf Englisch: {name}")
        englisch_count += len(alle_news_roh[name])
        r['news'] = [{'titel': n['titel'], 'einordnung': '', 'url': n['url'], 'quelle': n['quelle'], 'datum': n['datum']} for n in alle_news_roh[name]]

print(f"\n  📊 News-Statistik: {uebersetzt_count} übersetzt, {englisch_count} englisch (Fallback)")

# ── Speichern ─────────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
with open("data/stocks.json", "w", encoding="utf-8") as f:
    json.dump({"aktualisiert": datetime.now(timezone.utc).isoformat(), "aktien": results}, f, ensure_ascii=False, indent=2, allow_nan=False)

print(f"\n✅ Fertig! {len(results)} Aktien gespeichert.")
