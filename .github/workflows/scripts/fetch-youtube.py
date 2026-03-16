import requests
import json
import os
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ── Kanäle ───────────────────────────────────────────────────────────────────
# Channel-IDs von YouTube (für RSS-Feed benötigt)
KANAELE = [
    {"name": "Everlast AI",           "id": "UCbmNph6atAoGfqLoCL_duAg"},
    {"name": "Christoph Magnussen",   "id": "UCsT0YIqwnpJCM-mx7-gSA4Q"},
    {"name": "Jonas Keil",            "id": "UC7T9E5vMDc5brqQ5i7EVAuQ"},
    {"name": "The Ai Grid",           "id": "PLVlm0oiGSdkJ7JYkIHNnHQYGm_JLmKE"},
    {"name": "KI Praxis",             "id": "UCGy2gdFAzMDKwDONwrqeQvg"},
    {"name": "Marius Rothmann",       "id": "UCYpRDnFk4ggQ4LB6SdKJpWQ"},
    {"name": "SimpliAI",              "id": "UCmTkEMBFnv_2IDuX_5_TlxQ"},
    {"name": "Leon Rennenkampff",     "id": "UCsXiGRIfMSH4G1Ev9N3BWEQ"},
    {"name": "Digitale Leute",        "id": "UCDtH8RnBCtSPSM2GX15DKFA"},
    {"name": "KI Magazin",            "id": "UCwO8zNd5E5e8mJaK7EAANPQ"},
]

RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id="
NS = {'atom': 'http://www.w3.org/2005/Atom',
      'yt':   'http://www.youtube.com/xml/schemas/2015',
      'media':'http://search.yahoo.com/mrss/'}

cutoff = datetime.now(timezone.utc) - timedelta(days=7)

alle_videos = []

for kanal in KANAELE:
    url = RSS_BASE + kanal["id"]
    print(f"Fetching: {kanal['name']}...")
    try:
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)

        entries = root.findall('atom:entry', NS)
        for entry in entries:
            # Datum prüfen
            published_el = entry.find('atom:published', NS)
            if published_el is None:
                continue
            pub_str = published_el.text
            try:
                pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
            except:
                continue

            if pub_dt < cutoff:
                continue  # Älter als 7 Tage → überspringen

            # Daten extrahieren
            title_el    = entry.find('atom:title', NS)
            link_el     = entry.find('atom:link', NS)
            video_id_el = entry.find('yt:videoId', NS)
            thumb_el    = entry.find('.//media:thumbnail', NS)

            titel    = title_el.text if title_el is not None else ''
            link     = link_el.get('href') if link_el is not None else ''
            video_id = video_id_el.text if video_id_el is not None else ''
            thumb    = thumb_el.get('url') if thumb_el is not None else f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

            alle_videos.append({
                "kanal":     kanal["name"],
                "titel":     titel,
                "link":      link,
                "video_id":  video_id,
                "thumbnail": thumb,
                "datum":     pub_str,
                "datum_de":  pub_dt.strftime("%d.%m.%Y"),
            })
            print(f"  ✓ {titel[:60]}")

    except Exception as e:
        print(f"  FEHLER: {e}")

# Nach Datum sortieren (neueste zuerst)
alle_videos.sort(key=lambda v: v["datum"], reverse=True)

output = {
    "aktualisiert": datetime.now(timezone.utc).isoformat(),
    "zeitraum_tage": 7,
    "videos": alle_videos
}

os.makedirs("data", exist_ok=True)
with open("data/youtube.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nFertig! {len(alle_videos)} Videos der letzten 7 Tage gespeichert.")
