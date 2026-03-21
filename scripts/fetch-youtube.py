import requests
import json
import os
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ── Deutsche KI-Kanäle ────────────────────────────────────────────────────────
# Channel-IDs direkt von YouTube
KANAELE = [
    {"name": "Everlast AI",              "id": "UCbmNph6atAoGfqLoCL_duAg"},
    {"name": "Christoph Magnussen",      "id": "UCsT0YIqwnpJCM-mx7-gSA4Q"},
    {"name": "Jonas Keil",               "id": "UC7T9E5vMDc5brqQ5i7EVAuQ"},
    {"name": "Sascha Hoffmann",          "id": "UCOzmF7UbTQ-pzkUWUEiDpHw"},
    {"name": "Neuland Pro",              "id": "UCddiUEpeqJcYeBxX1IVBKvQ"},
    {"name": "Leon Rennenkampff",        "id": "UCSXiGRIfMSH4G1Ev9N3BWEQ"},
    {"name": "Von ChatGPT bis n8n",      "id": "UCqK5XFEoAlqQfOBSGKPcKLQ"},
    {"name": "Marius Rothmann",          "id": "UCYpRDnFk4ggQ4LB6SdKJpWQ"},
    {"name": "KI Praxis",                "id": "UCGy2gdFAzMDKwDONwrqeQvg"},
    {"name": "SimpliAI",                 "id": "UCmTkEMBFnv_2IDuX_5_TlxQ"},
]

RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id="
NS = {
    'atom':  'http://www.w3.org/2005/Atom',
    'yt':    'http://www.youtube.com/xml/schemas/2015',
    'media': 'http://search.yahoo.com/mrss/'
}

cutoff = datetime.now(timezone.utc) - timedelta(days=7)
alle_videos = []

for kanal in KANAELE:
    url = RSS_BASE + kanal["id"]
    print(f"Fetching: {kanal['name']}...")
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)

        for entry in root.findall('atom:entry', NS):
            published_el = entry.find('atom:published', NS)
            if published_el is None:
                continue
            try:
                pub_dt = datetime.fromisoformat(published_el.text.replace('Z', '+00:00'))
            except:
                continue

            if pub_dt < cutoff:
                continue

            title_el    = entry.find('atom:title', NS)
            link_el     = entry.find('atom:link', NS)
            video_id_el = entry.find('yt:videoId', NS)
            thumb_el    = entry.find('.//media:thumbnail', NS)

            video_id = video_id_el.text if video_id_el is not None else ''
            thumb    = thumb_el.get('url') if thumb_el is not None else f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

            alle_videos.append({
                "kanal":     kanal["name"],
                "titel":     title_el.text if title_el is not None else '',
                "link":      link_el.get('href') if link_el is not None else '',
                "video_id":  video_id,
                "thumbnail": thumb,
                "datum":     published_el.text,
                "datum_de":  pub_dt.strftime("%d.%m.%Y"),
            })
            print(f"  ✓ {(title_el.text or '')[:60]}")

    except Exception as e:
        print(f"  FEHLER ({kanal['name']}): {e}")

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
