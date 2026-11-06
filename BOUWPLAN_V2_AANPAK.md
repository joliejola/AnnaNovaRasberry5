# Bouwplan v2 — aanpak voor Anna Nova (praatcel met bon)

*6 november 2026 15:00 · derde herziening na nieuwste bronplan*

**Status**: Jolanda heeft het bronplan aangescherpt (zie `docs/BOUWPLAN_BRON.md` sync 6 nov 14:50). Dit document vertaalt dat naar wat we vandaag bouwen, wat in branch `bouwplan-v2` al werkt, wat weg moet of veranderd, en welke tracks parallel kunnen.

**Wat is Anna Nova nu**: praatcel die slaapt tot *"Hoi Anna Nova"*. Dan **vast script**: opening + 5 vaste vragen (begin met "Wil je mijn vriendin worden?") + afrekening. Alleen de **één-zin reactie tussen vragen** is live van Mistral. De bon print een quote + wereld-AI-bedrag + datum, geen "jouw aandeel %" meer. Achter de cel: bezoeker vaag zichtbaar als stippen en lijnen (pose). Bezoeker vergeten na elk gesprek.

---

## Wat is er VERANDERD in het bronplan (sinds eerdere versie)

| Thema | Vorige versie (wat ik bouwde) | Nieuwste bron |
|---|---|---|
| Vragen | 4 getrokken uit 10 met halte-regel | **5 vaste vragen in `reeks`**, exacte volgorde |
| Haltes bekeken/bewaard/wrijving | Elke vraag had `halte` + `licht` | **Weg**. Geen haltes meer, geen trekking |
| Brain-reactie | Max 18 woorden, mag vraag stellen | **Max 15 woorden, geen vraagteken aan einde**, Anna stelt zelf GEEN vragen |
| Brain-soorten | antwoord\|pas\|zijweg\|provocatie\|verdriet\|ja\|nee | **Extra `twijfel`** voor vraag 1 + rekening |
| Wake | Voxtral/Mistral cloud ASR + wake_match | **Offline Vosk** (`vosk-model-small-nl`). Tot wake geen geluid naar internet |
| Stiltes | 2× stilte → door naar volgende vraag | **2× stilte → LOSLATEN zonder bon** (*"Weg is ook een antwoord"*) |
| Quote-schema | id, tekst, prijs_eur (float), halte | **id, tekst, prijs (string "€ 0,99"), zacht:bool** |
| Bon | logo + quote + wereld + **percentage** + datum | **Zonder "Jouw aandeel %" regel** (al gedaan in commit 44220fa) |
| Scherm-states | 7 (incl knopmodus) | **6: rust, luistert, denkt, spreekt, afrekenen, print** (knopmodus weg) |
| Camera in beeld | Alleen vaag backdrop | **Stippen (64×48 grijsraster) + pose-lijnen** via achtergrond.js canvas |
| Map-structuur | `web/face.html` | **`face/index.html` + `face/achtergrond.js`** |
| TTS | Voxtral TTS (bestaat niet) → Piper | **Piper nl_BE-nathalie-medium** — bron spreekt zich tegen, Piper is de werkelijke optie |

---

## Wat BLIJFT werken (al op branch, geen wijziging nodig)

- `anna/hear.py` wake_match + sleep_match met ASR-mishoor-varianten — hergebruikt in `wake.py` (fuzzy match na Vosk-transcriptie) én in live `hear.py`
- `anna/hear.py` droogloop stdin-loop — prima voor bouwdag
- `anna/speak.py` droogloop print-simulatie
- `anna/printer.py` cascade mini → ESC/POS → PNG-fallback
- `anna/face.py` HTTP-server + /tick + push_state (mapping bijstellen voor 6 states)
- `web/face.html` 6 van 7 states (knopmodus weg, de overige blijven). Mogelijk verplaatsen naar `face/index.html`.
- `anna/bon.py` grote structuur (logo, Pillow-render, cascade). Alleen quote-selectie + schema aanpassen.
- commit 44220fa: logo + "jouw aandeel %" weggehaald. Blijft.

## Wat MOET VERANDEREN

1. **`content/inhoud.json`** — nieuwe schema (reeks met reacties-per-vraag, situaties als dict, quotes zonder halte, lokzinnen uitbreiden)
2. **`anna/flow.py`** — 5-vragen-vaste-reeks ipv trekking, vraag 1 ja/nee/twijfel routing, geen halte-log, 2 stiltes → LOSLATEN
3. **`anna/brain.py`** — nieuwe soorten (incl `twijfel`), max 15 woorden, vraagteken-controle, geen zelf-vraag, voorbeeldreactie-fallback uit `reeks`
4. **`anna/bon.py`** — quote-selectie: geen halte, `zacht:true/false`, prijs is string (€ 4,10 of € 9,99 p/m)
5. **Nieuw `anna/wake.py`** — offline Vosk-wake, hergebruikt `wake_match` voor fuzzy varianten op Vosk-output
6. **Nieuw `face/achtergrond.js`** + `anna/see.py` uitbreiden — Hailo pose + 64×48 grijsraster → websocket → canvas
7. **Verplaats `web/face.html` → `face/index.html`** (+ `face/achtergrond.js`)

---

## Wat KAN TEGELIJK (parallel-tracks)

Zes tracks, drie kunnen vandaag parallel draaien, drie zijn Pi-only (later vandaag).

### 🅰️ **Content + flow + bon refactor** (ik, lokaal) — 2–3u
Grootste blok: nieuw inhoud.json-schema, flow.py herbouwen (5 vaste vragen, routing vraag 1), bon.py quote-selectie aanpassen, brain.py herzien, droogloop-sim hertesten. Geen externe dependencies.

### 🅱️ **Audio render** (parent of ik, lokaal) — 30 min + rendertijd
`tools/render_audio.py` die alle opgenomen zinnen uit nieuwe inhoud.json naar `audio/<id>.wav` rendert via Piper nl_BE-nathalie-medium. Piper install + nathalie-stem al op Pi — lokaal downloaden om te testen. **Jolanda hoort 1e sample bij BM3 (stem-keuze)**.

### 🅲️ **Hear.py live-skelet** (parent, lokaal) — 45 min
Pi-ready class met `sd.InputStream`, VAD-throttle 128ms, `transcribe_voxtral`-wrapper uit oude anna-nova.py. Alleen activeren hoeft, geen test-run lokaal zonder mic.

### 🅳 **Wake.py offline (Vosk)** — Pi-only
Download `vosk-model-small-nl` (~50MB) op Pi, pipeline: AudioListener → Vosk stream → match tegen WEKWOORDEN. Blokkeert hear.py niet want runt parallel-proces of in rust-mode.

### 🅴 **Camera stippen+lijnen** (Pi, ambitieus) — 2u
`see.py` picamera2 + Hailo pose 17-punt → 64×48 grijsraster + lichaamspunten → websocket. `face/achtergrond.js` canvas-renderer. Fallback: alleen stippen als Hailo te zwaar. Bron 2 stap 9, kan ook morgen voor-expositie als tijd dringt.

### 🅵 **Face states-mapping bijstellen** (ik, snel) — 15 min
knopmodus weg uit face.html (6 states ipv 7), eventueel verplaatsen naar `face/index.html`-pad. STATE_MAP in face.py bijstellen.

---

## Dagritme (bijgesteld om ±15:00)

| Tijd | 🅰️ Jolanda + ik (Pi/lokaal) | 🅱️🅲️ Parent / solo | 🅴 Camera |
|---|---|---|---|
| nu (±15:00) | **🅰️ ik: refactor inhoud+flow+bon+brain** | parent: 🅱️ render_audio + 🅲️ hear-skelet | |
| 16:00 | 🅰️ droogloop-hertest 5 gesprekken met nieuwe reeks → **🔔 BM3** (voelt het?) | 🅱️ nathalie-samples klaar → **🔔 BM3 stem?** | |
| 16:30 | **🅱️ wifi-dongel + printertje binnen** → bouwstap 1 (printer pairen) | | |
| 17:00 | bouwstap 3 echte bon | 🅲️ hear.py op Pi + wake Vosk | |
| 17:30 | hear/wake koppelen → **🔔 BM4 wake-ruimte-test** | | |
| 18:00 | scherm op Pi met 6 states → **🔔 BM5** | | 🅴 begin picamera2 + raster |
| 18:30 | groepstest 5 vrienden → **🔔 BM6** | | 🅴 stippen in achtergrond.js |
| 19:00 | expositie-klaar + eindsimulatie → **🔔 BM7** | | 🅴 pose-lijnen als tijd |

**Buffer tot 21:00**. Vandaag loopt uit — vroege start was 09:00, veel meer verzet dan oorspronkelijk gedacht. Als iets niet lukt in 🅴 (camera-stippen): Jolanda beslist of expositie zonder gaat of uitgesteld.

---

## Jolanda-beslismomenten (bijgesteld, 5 tijdens de bouwdag)

Veel minder dan vorige lijst van 9 — vaste reeks betekent minder keuzes.

- 🔔 **BM1 (nu)** — Dit nieuwe bouwplan OK? Vooral: akkoord met 5 vaste vragen (geen trekking)?
- 🔔 **BM2 (bon)** — gedaan, commit 44220fa (jij vond mooi)
- 🔔 **BM3** (~16:00) — droogloop 5 gesprekken met nieuwe reeks. Voelt het? + stem-sample van render_audio klinkt goed?
- 🔔 **BM4** (~17:30) — wake-test ruimte: 10× "Hoi Anna Nova" vs 10 min achtergrond-praten
- 🔔 **BM5** (~18:00) — 6 states op scherm
- 🔔 **BM6** (~18:30) — groepstest-drempels (vals-positief vs gemist)
- 🔔 **BM7** (~19:00) — expositie-go?

Totaal ~45 min van jouw tijd.

---

## Risico's

- **Vosk offline-wake**: nieuwe dependency, nog niet getest op Pi 5. Mitigatie: fallback naar oude Voxtral-wake (cloud) als Vosk te traag of model niet installeerbaar; wake_match is identiek.
- **Camera-stippen op Hailo pose**: compute-zwaar, kan tegelijk met Voxtral voor hear.py op CPU stuiteren. Mitigatie: lijnen uitzetten (`LIJNEN=0`), alleen stippen die goedkoop zijn.
- **Vaste 5-vragen voelt saai bij herhaling**: Jolanda zelf test bij BM3 — als het niet werkt kunnen we de reeks uitbreiden naar 8 vragen met lichte willekeur, maar bron 2 is duidelijk "altijd de vijf vragen in volgorde".
- **"Wil je mijn vriendin worden?" als vraag 1 is krachtig maar ongewoon** — bezoeker kan afhaken. Vraag 1 heeft ja/nee/twijfel-routing dus elk pad is voorbereid.
- **Branch heeft veel werk, mogelijk merge-conflicten met parent**: ik commit klein en vaak; parent doet 🅱️/🅲️ in andere files.

---

## Wat na vandaag

Tag `v2.0-expositie` bij BM7-go. SD-image van werkende Pi. Als 🅴 camera-stippen niet gelukt is: `face/index.html` draait zonder achtergrond, is een acceptabele versie-0.
