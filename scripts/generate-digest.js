// generate-digest.js
// Ruft die Gemini API auf, generiert einen strukturierten KI-News Digest
// und speichert ihn als data/digest.json im Repository.

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── Konfiguration ────────────────────────────────────────────────────────────
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_MODEL   = 'gemini-2.5-flash';
const OUTPUT_PATH    = path.join(__dirname, '..', 'data', 'digest.json');

if (!GEMINI_API_KEY) {
  console.error('❌ GEMINI_API_KEY nicht gesetzt. Abbruch.');
  process.exit(1);
}

// ── Datum ────────────────────────────────────────────────────────────────────
const heute = new Date();
const datumISO = heute.toISOString().slice(0, 10); // "2026-03-11"
const wochentage = ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'];
const monate     = ['Januar','Februar','März','April','Mai','Juni',
                    'Juli','August','September','Oktober','November','Dezember'];
const datumLang  = `${wochentage[heute.getDay()]}, ${heute.getDate()}. ${monate[heute.getMonth()]} ${heute.getFullYear()}`;

// ── Prompt ───────────────────────────────────────────────────────────────────
const PROMPT = `Du bist ein KI-Nachrichtenredakteur. Erstelle einen kompakten aber inhaltlich
reichen deutschsprachigen KI-News Digest für ${datumLang}.

Recherchiere die wichtigsten KI-Nachrichten der letzten 24 Stunden aus folgenden Bereichen:
- Neue Modelle & Releases (OpenAI, Anthropic, Google, Meta, Mistral, xAI usw.)
- Forschung & Wissenschaft (arxiv, bedeutende Studien)
- Unternehmen & Markt (Finanzierungen, Akquisitionen)
- Politik & Regulierung (EU AI Act, Behörden, Gesetze)
- Tools & Anwendungen (Open Source, neue Produkte)

Gib deine Antwort AUSSCHLIESSLICH als valides JSON zurück — kein Markdown, keine Erklärungen,
keine Backticks davor oder danach. Das JSON muss exakt dieser Struktur folgen:

{
  "datum": "${datumLang}",
  "datumISO": "${datumISO}",
  "tagesthema": "Ein prägnanter Satz der den Kern des Tages trifft",
  "kategorien": [
    {
      "emoji": "🚀",
      "titel": "Neue Modelle & Releases",
      "artikel": [
        {
          "titel": "Artikeltitel",
          "zusammenfassung": "2-3 Sätze: Wer hat was getan und warum ist es wichtig.",
          "einordnung": "1 Satz: Was das für KI-Interessierte bedeutet.",
          "quelle": "Quellenname (z.B. TechCrunch, OpenAI Blog)",
          "url": "https://...",
          "sterne": "⭐⭐⭐"
        }
      ]
    }
  ],
  "generiert_um": "${new Date().toISOString()}"
}

Regeln:
- Mindestens 3, maximal 5 Kategorien
- Pro Kategorie 2-4 Artikel
- Nur Kategorien mit echten Nachrichten aus den letzten 24-48h
- Sterne: ⭐⭐⭐ = bahnbrechend, ⭐⭐ = bedeutend, ⭐ = interessant
- Alle Texte auf Deutsch
- URLs müssen real und direkt abrufbar sein
- Keine erfundenen Nachrichten — lieber weniger aber korrekte Artikel`;

// ── Gemini API aufrufen ──────────────────────────────────────────────────────
async function generiereDigest() {
  console.log(`🔍 Generiere KI-News Digest für ${datumLang}...`);

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: PROMPT }] }],
    generationConfig: {
        temperature: 0.4,
       maxOutputTokens: 8192
      }
    })
  });

  if (!response.ok) {
    const fehler = await response.text();
    throw new Error(`Gemini API Fehler ${response.status}: ${fehler}`);
  }

  const data = await response.json();

  // Antwort extrahieren
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    console.error('Gemini Antwort:', JSON.stringify(data, null, 2));
    throw new Error('Keine Textantwort von Gemini erhalten.');
  }

  // JSON parsen (Backticks entfernen falls vorhanden)
  const bereinigt = text.replace(/```json\n?|\n?```/g, '').trim();
  let digest;
  try {
    digest = JSON.parse(bereinigt);
  } catch (e) {
    console.error('Rohantwort:', bereinigt.slice(0, 500));
    throw new Error(`JSON-Parsing fehlgeschlagen: ${e.message}`);
  }

  // Validierung
  if (!digest.kategorien || !Array.isArray(digest.kategorien)) {
    throw new Error('Digest hat keine gültige "kategorien"-Struktur.');
  }

  console.log(`✅ ${digest.kategorien.length} Kategorien, Tagesthema: "${digest.tagesthema}"`);
  return digest;
}

// ── Datei speichern ──────────────────────────────────────────────────────────
async function main() {
  try {
    const digest = await generiereDigest();

    // Sicherstellen dass data/ existiert
    const dataDir = path.dirname(OUTPUT_PATH);
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(digest, null, 2), 'utf-8');
    console.log(`💾 Digest gespeichert: ${OUTPUT_PATH}`);

    // Artikel-Statistik ausgeben
    let gesamtArtikel = 0;
    for (const kat of digest.kategorien) {
      gesamtArtikel += kat.artikel?.length || 0;
      console.log(`   ${kat.emoji} ${kat.titel}: ${kat.artikel?.length || 0} Artikel`);
    }
    console.log(`📊 Gesamt: ${gesamtArtikel} Artikel`);

  } catch (err) {
    console.error('❌ Fehler:', err.message);
    process.exit(1);
  }
}

main();
