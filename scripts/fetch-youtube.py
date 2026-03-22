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
    "KI Tutorial deutsch 2026",
    "ChatGPT deutsch anleitung",
    "Claude Anthropic deutsch",
    "KI Automatisierung deutsch tutorial",
    "künstliche Intelligenz deutsch neu",
    "AI Werkzeuge deutsch",
    "Gemini Google KI deutsch",
    "KI Agent bauen deutsch",
    "n8n deutsch tutorial",
    "KI News deutsch woche",
]

# ── KI-relevante Schlüsselwörter ──────────────────────────────────────────────
KI_KEYWORDS = [
    "ki ", " ki,", " ki.", "k.i.", " ai ", "a.i.", "künstliche intelligenz",
    "chatgpt", "claude", "gemini", "llm", "gpt", "copilot", "openai",
    "midjourney", "stable diffusion", "ollama", "llama", "mistral",
    "machine learning", "deep learning", "neural", "automatisierung",
    "n8n", "make.com", "agent", "prompt", "rag", "anthropic",
    "sprachmodell", "bildgenerierung", "ki-tool", "ki tool", "ki-news",
    "sora", "runway", "elevenlabs", "perplexity", "notebooklm",
    "cowork", "cursor", "windsurf", "replit", "bolt.new",
]

# ── Blacklist ──────────────────────────────────────────────────────────────────
BLACKLIST = [
    "betrügt", "betrogen", "rap", "hiphop", "musik", "song", "rocksong",
    "politik", "trump", "krieg", "sport", "fußball", "rezept",
    "fitness", "meditation", "reise", "urlaub", "kochen", "backen",
    "prypjat", "centralia", "uwe boll",
]

# ── Eindeutig englische Wörter (wenn 2+ davon vorkommen = englisch) ───────────
ENGLISH_WORDS = [
    " the ", " this ", " that ", " with ", " your ", " you ",
    " how ", " best ", " new ", " use ", " using ", " build ",
    " make ", " create ", " learn ", " from ", " into ", " just ",
    "i gave", "i built", "i tried", "i made", "i tested",
    " is ", " are ", " was ", " will ", " can ", " vs ",
    " full ", " access ", " agent ", " update ", " tool ",
    "which ai", "what ai", "why ai",
]

RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id="
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NS       = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}

cutoff     = datetime.now(timezone.utc) - timedelta(days=7)
cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

alle_videos = []
bekannte_ids = set()

def ist_englisch(titel):
    t = " " + titel.lower() + " "
    treffer = sum(1 for w in ENGLISH_WORDS if w in t)
    return treffer >= 2

def ist_ki_relevant(titel):
    t = " " + titel.lower() + " "
    for word in BLACKLIST:
        if word in t:
            return False
    for kw in KI_KEYWORDS:
        if kw in t:
            return True
    return False

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
            print("  Keine Videos in den letzten 7 Tagen")
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
                "videoDuration":     "medium",
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

kanal_count = sum(1 for v in alle_videos if v.get('quelle') == 'kanal')
suche_count = sum(1 for v in alle_videos if v.get('quelle') == 'suche')
print(f"\nFertig! {len(alle_videos)} Videos ({kanal_count} Kanal, {suche_count} Suche).")
