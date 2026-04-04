import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

FESTE_KANAELE = [
    {"name": "Everlast AI",          "channel_id": "UC8T5gQ4U4GbI2h8kYCkEcvg"},
    {"name": "Christoph Magnussen",  "channel_id": "UCDx6L69jmKBJbNu5GnkCilg"},
    {"name": "Jonas Keil",           "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ"},
    {"name": "Neuland Pro",          "channel_id": "UCcQz40FwO1qaePDQ5RRzlcw"},
    {"name": "Sascha Hoffmann",      "channel_id": "UC7xxAtIMrlTcB1mKLziqEbA"},
    {"name": "Sascha Taschan",       "handle": "saschthetasch"},
    {"name": "KI-Campus",            "channel_id": "UCtimfZyjzmkpOeLI1s88hcQ"},
    {"name": "Morpheus Tutorials",   "handle": "TheMorpheusTutorials"},
    {"name": "Timo Specht",          "handle": "timo-specht-seo"},
    {"name": "KI-Lernzone",          "handle": "KI-Lernzone"},
    {"name": "Akademie4KI",          "handle": "akademie4ki"},
]

SUCHBEGRIFFE = [
    "ChatGPT Tutorial deutsch",
    "Claude AI Tutorial deutsch",
    "n8n Automatisierung deutsch",
    "KI Tools Tutorial deutsch",
    "Gemini Tutorial deutsch",
    "KI Agent Tutorial deutsch",
    "OpenAI deutsch Tutorial",
    "KI Workflow deutsch",
    "LLM Tutorial deutsch",
    "KI Anwendung Tutorial deutsch",
]

PFLICHT_KEYWORDS = [
    "chatgpt", "claude", "gemini", "gpt-", "openai", "anthropic",
    "llm", "llama", "mistral", "ollama", "perplexity", "midjourney",
    "stable diffusion", "n8n", "make.com", "notebooklm", "copilot",
    "ki-tool", "ki tool", "ki-agent", "ki agent", "ki-workflow",
    "ki-automatisierung", "ki automatisierung", "ki-tutorial",
    "ki tutorial", "ki-news", "ai-tool", "ai agent", "ai workflow",
    "sprachmodell", "bildgenerierung", "prompt engineering",
    "rag ", "fine-tuning", "cowork", "cursor ai", "windsurf",
    "replit", "bolt.new", "sora", "runway", "elevenlabs",
    "hugging face", "embedding", "ki lernzone", "ki-lernzone",
]

BLACKLIST_TITEL = [
    "offiziell", "official", "lyrics", "music video", "audio",
    "helene fischer", "schlager", "pop song", "album", "single",
    "betrügt", "betrogen", "rap", "hiphop",
    "krieg", "sport", "fußball", "rezept", "kochen", "backen",
    "reise", "urlaub", "fitness", "meditation",
    "verwaltungsmanager", "spanien", "skandal",
    "smci", "ermittlung", "nachrichten der woche", "news der woche",
    "consistent deutsch zu sprechen", "deutsch lernen", "sprache lernen",
    "#shorts", "shorts",
]

BLACKLIST_KANAL = [
    "skyline music", "music", "official", "records", "label",
    "vallejo law", "bug bounty",
]

MAX_VIDEOS    = 15
RSS_BASE      = "https://www.youtube.com/feeds/videos.xml?channel_id="
HEADERS       = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NS            = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}

cutoff        = datetime.now(timezone.utc) - timedelta(days=7)
cutoff_str    = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
alle_videos   = []
bekannte_ids  = set()

def get_channel_id(handle):
    try:
        r = requests.get(f"https://www.youtube.com/@{handle}", timeout=10, headers=HEADERS)
        for pattern in [
            r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"browseId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
        ]:
            m = re.search(pattern, r.text)
            if m:
                return m.group(1)
    except Exception as e:
        print(f"  Handle-Fehler: {e}")
    return None

def ist_short(titel, video_id):
    """Shorts erkennen: #shorts im Titel oder typische Short-Muster"""
    t = titel.lower()
    if "#shorts" in t or "#short" in t:
        return True
    return False

def ist_englisch(titel):
    t = " " + titel.lower() + " "
    english = [" the ", " this ", " that ", " your ", " you ", " how ",
               " best ", " use ", " using ", " build ", " make ",
               " create ", " learn ", " from ", " just ", " is ",
               " are ", " was ", " will ", " can ", " vs ",
               "i gave", "i built", "i tried", "i made", "i tested",
               "which ai", "what ai", "why ai", " full ", " access "]
    return sum(1 for w in english if w in t) >= 2

def ist_relevant(titel, kanal_name=""):
    t = titel.lower()
    k = kanal_name.lower()
    for bk in BLACKLIST_KANAL:
        if bk in k:
            return False, "kanal-blacklist"
    for bt in BLACKLIST_TITEL:
        if bt in t:
            return False, f"blacklist"
    if ist_short(titel, ""):
        return False, "short"
    if ist_englisch(titel):
        return False, "englisch"
    for kw in PFLICHT_KEYWORDS:
        if kw in t:
            return True, "ok"
    return False, "kein KI-keyword"

# ── Teil 1: Feste Kanäle ─────────────────────────────────────────────────────
print("=== Feste Kanäle ===")
for kanal in FESTE_KANAELE:
    print(f"\n{kanal['name']}...")
    if "channel_id" in kanal:
        cid = kanal["channel_id"]
    else:
        cid = get_channel_id(kanal["handle"])
        if not cid:
            print(f"  SKIP: Channel-ID nicht gefunden")
            continue
        print(f"  ID: {cid}")
    try:
        r = requests.get(RSS_BASE + cid, timeout=10, headers=HEADERS)
        r.raise_for_status()
        root  = ET.fromstring(r.content)
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
            if video_id in bekannte_ids: continue
            titel = title_el.text if title_el is not None else ''
            if ist_short(titel, video_id):
                print(f"  SKIP (short): {titel[:45]}")
                continue
            bekannte_ids.add(video_id)
            alle_videos.append({
                "kanal": kanal["name"], "titel": titel,
                "link": link_el.get('href') if link_el is not None else '',
                "video_id": video_id,
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "datum": pub_el.text, "datum_de": pub_dt.strftime("%d.%m.%Y"),
                "quelle": "kanal"
            })
            count += 1
            print(f"  ✓ {titel[:60]}")
        if count == 0:
            print("  Keine neuen Videos diese Woche")
    except Exception as e:
        print(f"  Fehler: {e}")

# ── Teil 2: YouTube API Suche ─────────────────────────────────────────────────
print("\n=== YouTube Suche ===")
if not YOUTUBE_API_KEY:
    print("SKIP: Kein API Key")
else:
    for begriff in SUCHBEGRIFFE:
        print(f"\n'{begriff}'...")
        try:
            params = {
                "key": YOUTUBE_API_KEY, "q": begriff,
                "type": "video", "part": "snippet",
                "maxResults": 6, "order": "date",
                "publishedAfter": cutoff_str,
                "relevanceLanguage": "de",
                "videoDuration": "medium",
            }
            r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=10)
            r.raise_for_status()
            for item in r.json().get("items", []):
                video_id = item["id"].get("videoId", "")
                if not video_id or video_id in bekannte_ids: continue
                snippet  = item.get("snippet", {})
                titel    = snippet.get("title", "")
                kanal    = snippet.get("channelTitle", "")
                pub_str  = snippet.get("publishedAt", "")
                ok, grund = ist_relevant(titel, kanal)
                if not ok:
                    print(f"  SKIP ({grund}): {titel[:45]}")
                    continue
                try:
                    pub_dt   = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                    datum_de = pub_dt.strftime("%d.%m.%Y")
                except:
                    datum_de = ""
                bekannte_ids.add(video_id)
                alle_videos.append({
                    "kanal": kanal, "titel": titel,
                    "link": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    "datum": pub_str, "datum_de": datum_de,
                    "quelle": "suche"
                })
                print(f"  ✓ [{kanal}] {titel[:45]}")
        except Exception as e:
            print(f"  API Fehler: {e}")

# ── Sortieren + auf 15 begrenzen ──────────────────────────────────────────────
alle_videos.sort(key=lambda v: v.get("datum", ""), reverse=True)
alle_videos = alle_videos[:MAX_VIDEOS]
print(f"\n→ Nach Filter: {len(alle_videos)} Videos (max. {MAX_VIDEOS})")

# ── Speichern ─────────────────────────────────────────────────────────────────
output = {
    "aktualisiert": datetime.now(timezone.utc).isoformat(),
    "zeitraum_tage": 7,
    "videos": alle_videos
}
os.makedirs("data", exist_ok=True)
with open("data/youtube.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

k = sum(1 for v in alle_videos if v.get('quelle') == 'kanal')
s = sum(1 for v in alle_videos if v.get('quelle') == 'suche')
print(f"Fertig! {len(alle_videos)} Videos ({k} Kanal, {s} Suche).")
