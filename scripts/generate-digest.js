// generate-digest.js
// Holt echte KI-Artikel aus Google News RSS, dann generiert Gemini den Digest

import fs from 'fs';
import path from 'path';
import { parseStringPromise } from 'xml2js';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_MODEL   = 'gemini-2.5-flash';
const OUTPUT_PATH    = path.join(__dirname, '..', 'data', 'digest.json');

if (!GEMINI_API_KEY) {
  console.error('❌ GEMINI_API_KEY nicht gesetzt.');
  process.exit(1);
}

// ── Datum ────────────────────────────────────────────────────────────────────
const heute    = new Date();
const datumISO = heute.toISOString().slice(0, 10);
const wochentage = ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'];
const monate     = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
const datumLang  = `${wochentage[heute.getDay()]}, ${heute.getDate()}. ${monate[heute.getMonth()]} ${heute.getFullYear()}`;

// ── Google News RSS Suchbegriffe ──────────────────────────────────────────────
const SUCHBEGRIFFE = [
  'künstliche Intelligenz',
  'OpenAI ChatGPT',
  'Anthropic Claude',
  'Google Gemini KI',
  'KI Regulierung EU',
  'Large Language Model',
  'KI Forschung',
  'KI Unternehmen Investition',
];

// ── Podcast Konfiguration ────────────────────────────────────────────────────
const PODCASTS = [
  {
    name: 'Heise KI-Update',
    desc: 'Mo, Mi, Fr · mit The Decoder',
    rss: 'https://kiupdate.podigee.io/feed/mp3',
    spotify: 'https://open.spotify.com/show/1rm6gMybQWnHePvY2eCpzp',
    itunesId: '1691536182'
  },
  {
    name: 'Doppelgänger Tech Talk',
    desc: 'Glöckler & Klöckner · 2x pro Woche',
    rss: 'https://feeds.megaphone.fm/LINDALA4208458418',
    spotify: 'https://open.spotify.com/show/3vBAacJIGDEb7hBHgdYlw3',
    itunesId: '1533580842'
  },
  {
    name: 'OMR Podcast',
    desc: 'Philipp Westermeyer · Tech & Business',
    rss: 'https://omr.podigee.io/feed/aac',
    spotify: 'https://open.spotify.com/show/4rION5Qm2nPvDbzIB1wUiH',
    itunesId: '1072188364'
  },
  {
    name: 'Der KI-Podcast · ARD',
    desc: 'Dienstags · Gregor Schmalzried & Team',
    rss: 'https://feeds.megaphone.fm/ADL9840502364',
    spotify: 'https://open.spotify.com/show/7IYjMXCK7KUrNJyVCLUEjk',
    itunesId: '1490402609'
  },
  {
    name: 'KI verstehen · Deutschlandfunk',
    desc: 'Wöchentlich · verständlich erklärt',
    rss: 'https://www.deutschlandfunk.de/ki-verstehen-102.xml',
    spotify: 'https://open.spotify.com/show/0rktSeF3DOjOyk2f0VPFwO',
    itunesId: '1535497738'
  },
  {
    name: 'Deep Minds · KI & Wissenschaft',
    desc: 'Experten-Interviews · tiefgründig',
    rss: 'https://deep-minds.podigee.io/feed/mp3',
    spotify: 'https://open.spotify.com/show/6rmXt98jRHNziyG1ev3sAT',
    itunesId: '1456243923'
  },
  {
    name: 'F.A.Z. Künstliche Intelligenz',
    desc: 'KI in Wirtschaft & Unternehmen',
    rss: 'https://kuenstlicheintelligenz.podigee.io/feed/mp3',
    spotify: 'https://open.spotify.com/show/2e0ib9yPTdELNdzzKojhKO',
    itunesId: '1523132877'
  }
];

// ── Cover-Bild per iTunes API holen ──────────────────────────────────────────
async function holeCoverBild(itunesId) {
  try {
    const resp = await fetch(
      `https://itunes.apple.com/lookup?id=${itunesId}&entity=podcast`,
      { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; myHUB/1.0)' } }
    );
    if (!resp.ok) {
      console.error(`  iTunes Fehler (${itunesId}): HTTP ${resp.status}`);
      return '';
    }
    const data = await resp.json();
    const url = data?.results?.[0]?.artworkUrl600 || data?.results?.[0]?.artworkUrl100 || '';
    if (url) {
      console.log(`  Cover OK (${itunesId}): ${url.slice(0,60)}`);
    } else {
      console.error(`  Cover leer (${itunesId}): ${JSON.stringify(data).slice(0,100)}`);
    }
    return url;
  } catch(e) {
    console.error(`  iTunes Ausnahme (${itunesId}): ${e.message}`);
    return '';
  }
}

// ── Letzte Podcast-Episode holen ─────────────────────────────────────────────
async function holePodcastEpisode(podcast) {
  try {
    const resp = await fetch(podcast.rss, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; myHUB/1.0)' }
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const xml  = await resp.text();
    const data = await parseStringPromise(xml, { explicitArray: false });
    const items = data?.rss?.channel?.item || data?.feed?.entry || [];
    const arr   = Array.isArray(items) ? items : [items];
    const item  = arr[0];
    if (!item) throw new Error('Keine Episoden');

    // Dauer aus RSS holen
    const dauer = item['itunes:duration'] || item.duration || '';
    let dauerStr = '';
    if (dauer) {
      const sek = dauer.includes(':')
        ? dauer.split(':').reduce((acc, t) => 60 * acc + parseInt(t), 0)
        : parseInt(dauer);
      if (!isNaN(sek) && sek > 0) dauerStr = `${Math.round(sek/60)} Min.`;
    }

    // Cover-Bild holen
    const cover = await holeCoverBild(podcast.itunesId);

    return {
      name:    podcast.name,
      desc:    podcast.desc,
      episode: item.title || '',
      datum:   item.pubDate ? new Date(item.pubDate).toLocaleDateString('de-DE') : '',
      dauer:   dauerStr,
      cover:   cover,
      spotify: podcast.spotify,
    };
  } catch(e) {
    console.error(`  Podcast RSS Fehler (${podcast.name}): ${e.message}`);
    const cover = await holeCoverBild(podcast.itunesId);
    return { name: podcast.name, desc: podcast.desc, episode: '', datum: '', dauer: '', cover, spotify: podcast.spotify };
  }
}

// ── Google News RSS abrufen ───────────────────────────────────────────────────
async function holeGoogleNews(suchbegriff) {
  const query = encodeURIComponent(suchbegriff);
  const url   = `https://news.google.com/rss/search?q=${query}&hl=de&gl=DE&ceid=DE:de`;
  try {
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; myHUB/1.0)' }
    });
    if (!resp.ok) return [];
    const xml  = await resp.text();
    const data = await parseStringPromise(xml, { explicitArray: false });
    const items = data?.rss?.channel?.item || [];
    const arr   = Array.isArray(items) ? items : [items];

    return arr.slice(0, 3).map(item => ({
      titel:  item.title   || '',
      url:    item.link    || '',
      quelle: item.source?._ || item.source || '',
      datum:  item.pubDate ? new Date(item.pubDate).toLocaleDateString('de-DE') : '',
    })).filter(a => a.titel && a.url);
  } catch (e) {
    console.error(`  RSS Fehler für "${suchbegriff}": ${e.message}`);
    return [];
  }
}

// ── Alle Artikel sammeln ──────────────────────────────────────────────────────
async function sammleArtikel() {
  console.log('📰 Sammle echte Artikel aus Google News...');
  const alle = [];
  const geseheneUrls = new Set();

  for (const begriff of SUCHBEGRIFFE) {
    const artikel = await holeGoogleNews(begriff);
    for (const a of artikel) {
      if (!geseheneUrls.has(a.url)) {
        geseheneUrls.add(a.url);
        alle.push(a);
      }
    }
    await new Promise(r => setTimeout(r, 500)); // kurze Pause
  }

  console.log(`  ${alle.length} Artikel gesammelt`);
  return alle;
}

// ── Gemini Digest generieren ──────────────────────────────────────────────────
async function generiereDigest(artikel) {
  const artikelText = artikel.map((a, i) =>
    `${i+1}. Titel: ${a.titel}\n   URL: ${a.url}\n   Quelle: ${a.quelle}\n   Datum: ${a.datum}`
  ).join('\n\n');

  const prompt = `Du bist ein KI-Nachrichtenredakteur. Erstelle einen strukturierten KI-News Digest für ${datumLang}.

Hier sind echte Artikel die heute verfügbar sind:

${artikelText}

Gruppiere diese Artikel in 4-6 thematische Kategorien (z.B. Neue Modelle, Forschung, Unternehmen, Regulierung).
Schreibe für jeden Artikel eine kurze Zusammenfassung (2-3 Sätze) und eine Einordnung (1 Satz).
Verwende NUR die URLs aus der obigen Liste — erfinde keine neuen URLs.

Antworte AUSSCHLIESSLICH als valides JSON ohne Markdown-Backticks:

{
  "datum": "${datumLang}",
  "datumISO": "${datumISO}",
  "tagesthema": "Ein prägnanter Satz der den Kern des Tages trifft",
  "kategorien": [
    {
      "emoji": "🚀",
      "titel": "Kategoriename",
      "artikel": [
        {
          "titel": "Artikeltitel auf Deutsch",
          "zusammenfassung": "2-3 Sätze Zusammenfassung",
          "einordnung": "1 Satz Einordnung für KI-Interessierte",
          "quelle": "Quellenname",
          "url": "https://... (aus der obigen Liste)",
          "sterne": "⭐⭐⭐"
        }
      ]
    }
  ],
  "generiert_um": "${new Date().toISOString()}"
}

Regeln:
- Nur Artikel aus der obigen Liste verwenden
- 4-6 Kategorien, pro Kategorie 2-5 Artikel
- Alle Texte auf Deutsch
- Sterne: ⭐⭐⭐ = bahnbrechend, ⭐⭐ = bedeutend, ⭐ = interessant`;

  const url  = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;
  const resp = await fetch(url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.4, maxOutputTokens: 16000 }
    })
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Gemini Fehler ${resp.status}: ${err}`);
  }

  const data = await resp.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error('Keine Antwort von Gemini');

  const bereinigt = text.replace(/```json\n?|\n?```/g, '').trim();
  const digest    = JSON.parse(bereinigt);

  if (!digest.kategorien?.length) throw new Error('Keine Kategorien im Digest');
  return digest;
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  try {
    const artikel = await sammleArtikel();

    if (artikel.length < 5) {
      throw new Error(`Zu wenige Artikel gesammelt: ${artikel.length}`);
    }

    console.log('\n🎙️ Lade Podcast-Episoden...');
    const podcasts = await Promise.all(PODCASTS.map(holePodcastEpisode));
    const podcastsGueltig = podcasts.filter(Boolean);
    console.log(`  ${podcastsGueltig.length} Podcasts geladen`);

    console.log(`\n🤖 Generiere Digest mit Gemini (${artikel.length} Artikel)...`);
    const digest = await generiereDigest(artikel);
    digest.podcasts = podcastsGueltig;

    const dataDir = path.dirname(OUTPUT_PATH);
    if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(digest, null, 2), 'utf-8');

    console.log(`✅ Digest gespeichert: ${digest.kategorien.length} Kategorien`);
    let gesamt = 0;
    for (const kat of digest.kategorien) {
      gesamt += kat.artikel?.length || 0;
      console.log(`   ${kat.emoji} ${kat.titel}: ${kat.artikel?.length || 0} Artikel`);
    }
    console.log(`📊 Gesamt: ${gesamt} Artikel`);

  } catch (err) {
    console.error('❌ Fehler:', err.message);
    process.exit(1);
  }
}

main();
