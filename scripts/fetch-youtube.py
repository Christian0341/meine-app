import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# ── Feste Kanäle (verifizierte Channel-IDs) ──────────────────────────────────
FESTE_KANAELE = [
    {"name": "Everlast AI",         "channel_id": "UC8T5gQ4U4GbI2h8kYCkEcvg"},
    {"name": "Christoph Magnussen", "channel_id": "UCDx6L69jmKBJbNu5GnkCilg"},
    {"name": "Jonas Keil",          "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ"},
    {"name": "Neuland Pro",         "channel_id": "UCcQz40FwO1qaePDQ5RRzlcw"},
    {"name": "Sascha Hoffmann",     "channel_id": "UC7xxAtIMrlTcB1mKLziqEbA"},
]

# ── Suchbegriffe ──────────────────────────────────────────────────────────────
SUCHBEGRIFFE = [
    "ChatGPT Tutorial deutsch 2026",
    "Claude AI deutsch Tutorial",
    "KI Automatisierung n8n deutsch",
    "künstliche Intelligenz Anwendung deutsch",
    "AI Agent deutsch Tutorial",
    "Gemini KI deutsch",
    "LLM deutsch Tutorial",
]

# ── KI-relevante Schlüsselwörter (mind. 1 muss im Titel vorkommen) ────────────
KI_KEYWORDS = [
    "ki ", "k.i.", "ai ", "a.i.", "künstliche intelligenz",
    "chatgpt", "claude", "gemini", "llm", "gpt", "copilot",
    "midjourney", "stable diffusion", "ollama", "llama",
    "machine learning", "deep learning", "neural", "automatisierung",
    "n8n", "make.com", "zapier", "agent", "prompt", "rag",
    "openai", "anthropic", "mistral", "perplexity", "hugging face",
    "sprachmodell", "bildgenerierung", "ki-tool", "ki tool",
    "sora", "runway", "elevenlabs", "midjourney",
]

# ── Ausschluss-Wörter (sofortiger Ausschluss wenn im Titel) ──────────────────
BLACKLIST = [
    "betrügt", "betrogen", "rap", "hiphop", "musik", "song",
    "politik", "trump", "krieg", "sport", "fußball", "rezept",
    "fitness", "meditation", "reise", "urlaub", "kochen",
    "prypjat", "centralia", "uwe boll", "österreich #", "deutschland #",
]

RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id="
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NS       = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}

cutoff     = datetime.now(timezone.utc) - timedelta(days=7)
cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

alle_videos = []
bekannte_ids = set()

def ist_ki_relevant(titel):
    """Prüft ob ein Video KI-relevant ist"""
    titel_lower = titel.lower()
    # Blacklist prüfen
    for word in BLACKLIST:
        if word in titel_lower:
            return False
    # Mind. ein KI-Keyword muss vorkommen
    for kw in KI_KEYWORDS:
        if kw in titel_lower:
            return True
    return False

def ist_englisch(titel):
    """Grobe Erkennung englischer Titel"""
    english_indicators = [
        " the ", "how to ", " is ", " are ", " was ", " will ",
        " can ", " your ", " you ", " this ", " that ", " with ",
        " for ", " from ", " best ", " new ", " vs ", "i tried",
        "i built", "i made", "we built",
    ]
    titel_lower = " " + titel.lower() + " "
    count = sum(1 for w in english_indicators if w in titel_lower)
    return count >= 2

# ── Teil 1: Feste Kanäle per RSS ─────────────────────────────────────────────
print("=== Feste Kanäle ===")
for kanal in FESTE_KANAELE:
    print(f"\nFetching: {kanal['name']}...")
    try:
        r = requests.get(RSS_BASE + kanal["channel_id"], timeout=10, headers=HEADERS)
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
            if video_id in bekannte_ids: continue
            bekannte_ids.add(video_id)

            titel = title_el.text if title_el is not None else ''
            alle_videos.append({
                "kanal":     kanal["name"],
                "titel":     titel,
                "link":      link_el.get('href') if link_el is not None else '',
                "video_id":  video_id,
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "datum":     pub_el.text,
                "datum_de":  pub_dt.strftime("%d.%m.%Y"),
                "quelle":    "kanal"
            })
            count += 1
            print(f"  ✓ {titel[:60]}")
        if count == 0:
            print(f"  Keine Videos in den letzten 7 Tagen")
    except Exception as e:
        print(f"  Fehler: {e}")

# ── Teil 2: YouTube API Suche ─────────────────────────────────────────────────
print("\n=== YouTube Suche ===")
if not YOUTUBE_API_KEY:
    print("SKIP: Kein YOUTUBE_API_KEY gesetzt")
else:
    for begriff in SUCHBEGRIFFE:
        print(f"\nSuche: '{begriff}'...")
        try:
            params = {
                "key":               YOUTUBE_API_KEY,
                "q":                 begriff,
                "type":              "video",
                "part":              "snippet",
                "maxResults":        8,
                "order":             "date",
                "publishedAfter":    cutoff_str,
                "relevanceLanguage": "de",
                "videoDuration":     "medium",  # 4-20 Minuten (keine Shorts)
            }
            r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            for item in data.get("items", []):
                video_id = item["id"].get("videoId", "")
                if not video_id or video_id in bekannte_ids:
                    continue

                snippet = item.get("snippet", {})
                titel   = snippet.get("title", "")
                kanal   = snippet.get("channelTitle", "")
                pub_str = snippet.get("publishedAt", "")

                # Filter anwenden
                if ist_englisch(titel):
                    print(f"  SKIP (englisch): {titel[:50]}")
                    continue
                if not ist_ki_relevant(titel):
                    print(f"  SKIP (nicht KI): {titel[:50]}")
                    continue

                try:
                    pub_dt   = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                    datum_de = pub_dt.strftime("%d.%m.%Y")
                except:
                    datum_de = ""

                bekannte_ids.add(video_id)
                alle_videos.append({
                    "kanal":     kanal,
                    "titel":     titel,
                    "link":      f"https://www.youtube.com/watch?v={video_id}",
                    "video_id":  video_id,
                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    "datum":     pub_str,
                    "datum_de":  datum_de,
                    "quelle":    "suche"
                })
                print(f"  ✓ [{kanal}] {titel[:50]}")

        except Exception as e:
            print(f"  API Fehler: {e}")

# ── Sortieren und speichern ───────────────────────────────────────────────────
alle_videos.sort(key=lambda v: v.get("datum", ""), reverse=True)

output = {
    "aktualisiert": datetime.now(timezone.utc).isoformat(),
    "zeitraum_tage": 7,
    "videos": alle_videos
}

os.makedirs("data", exist_ok=True)
with open("data/youtube.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

kanal_count  = sum(1 for v in alle_videos if v.get('quelle') == 'kanal')
suche_count  = sum(1 for v in alle_videos if v.get('quelle') == 'suche')
print(f"\nFertig! {len(alle_videos)} Videos ({kanal_count} Kanal, {suche_count} Suche).")
