import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ── Deutsche KI-Kanäle ───────────────────────────────────────────────────────
KANAELE = [
    {"name": "Everlast AI",          "handle": "everlastai"},
    {"name": "Christoph Magnussen",  "handle": "christophmagnussen"},
    {"name": "Jonas Keil",           "handle": "JonasKeil"},
    {"name": "Neuland Pro",          "handle": "neulandpro"},
    {"name": "Leon Rennenkampff",    "handle": "leonrennenkampff"},
    {"name": "Marius Rothmann",      "handle": "mariusrothmann"},
    {"name": "Florian Dalwigk",      "handle": "FlorianDalwigk"},
    {"name": "KI Tutorials",         "handle": "KITutorialsDeutsch"},
    {"name": "Sascha Hoffmann",      "handle": "saschahoffmann"},
    {"name": "AI Revolution DE",     "handle": "airevolutionde"},
]

RSS_BASE   = "https://www.youtube.com/feeds/videos.xml?channel_id="
HANDLE_URL = "https://www.youtube.com/@"
HEADERS    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
NS         = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015', 'media': 'http://search.yahoo.com/mrss/'}

cutoff = datetime.now(timezone.utc) - timedelta(days=7)

def get_channel_id(handle):
    try:
        r = requests.get(f"{HANDLE_URL}{handle}", timeout=10, headers=HEADERS)
        for pattern in [
            r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"browseId":"(UC[a-zA-Z0-9_-]{22})"',
            r'channel/(UC[a-zA-Z0-9_-]{22})',
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
        ]:
            m = re.search(pattern, r.text)
            if m:
                return m.group(1)
    except Exception as e:
        print(f"  Fehler: {e}")
    return None

alle_videos = []

for kanal in KANAELE:
    print(f"\nFetching: {kanal['name']} (@{kanal['handle']})...")
    cid = get_channel_id(kanal['handle'])
    if not cid:
        print(f"  SKIP: Channel-ID nicht gefunden")
        continue
    print(f"  ID: {cid}")
    try:
        r = requests.get(RSS_BASE + cid, timeout=10, headers=HEADERS)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        count = 0
        for entry in root.findall('atom:entry', NS):
            pub_el = entry.find('atom:published', NS)
            if pub_el is None: continue
            try:
                pub_dt = datetime.fromisoformat(pub_el.text.replace('Z', '+00:00'))
            except: continue
            if pub_dt < cutoff: continue

            vid_el   = entry.find('yt:videoId', NS)
            title_el = entry.find('atom:title', NS)
            link_el  = entry.find('atom:link', NS)
            video_id = vid_el.text if vid_el is not None else ''

            alle_videos.append({
                "kanal":     kanal["name"],
                "titel":     title_el.text if title_el is not None else '',
                "link":      link_el.get('href') if link_el is not None else '',
                "video_id":  video_id,
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "datum":     pub_el.text,
                "datum_de":  pub_dt.strftime("%d.%m.%Y"),
            })
            count += 1
            print(f"  ✓ {(title_el.text or '')[:60]}")
        if count == 0:
            print(f"  Keine Videos in den letzten 7 Tagen")
    except Exception as e:
        print(f"  RSS Fehler: {e}")

alle_videos.sort(key=lambda v: v["datum"], reverse=True)

output = {
    "aktualisiert": datetime.now(timezone.utc).isoformat(),
    "zeitraum_tage": 7,
    "videos": alle_videos
}

os.makedirs("data", exist_ok=True)
with open("data/youtube.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nFertig! {len(alle_videos)} Videos gespeichert.")
