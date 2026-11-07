# Status 7 nov 13:00 — Anna Nova expositie-check

*Totaalplan: wat werkt, wat nog niet, wat er vóór publiek moet.*

---

## ✅ Werkt (bewezen)

| Onderdeel | Commit | Bewijs |
|---|---|---|
| **Printer** — Agodeo mini MXW01, MAC `48:0F:57:4B:E5:D4` | `8a46415` | Testregel + echte bon komen uit printertje (7s / 15s) |
| **Bon-layout** — logo alleen bovenaan, geen kop | `677699e` | 384×384 PNG met quote, prijs, datum, URL |
| **Wake** — "Hoi Anna Nova" + "Hoi Anna" via Vosk | — | Getest 6 nov door Jolanda |
| **ElevenLabs API** — stem `o4g7vs6IQ4oCQwuS7wi7` | `8257c85` | HTTP 200 + bytes; sample goedgekeurd door Jolanda |
| **ElevenLabs playback** — mpg123 → aplay pipe (PipeWire fix) | `3cf1fcc` | Pipe getest op Pi |
| **Mistral brein** — JSON out via `mistral-small-latest` | — | Key live in `.env` op Pi |
| **render_audio** — `--engine elevenlabs` support | `b05dbbc` | Dry-run laat 32 items zien |
| **Scherm-states** — sluimert/luistert/denkt/spreekt | — | demo `web/achtergrond-demo.html?demo=1` |
| **Printer-guide** | — | `docs/voorbereiding/PRINTER_SETUP.md` |

## 🔄 Nu in behandeling door peer-sessie

Spoor A+B uit [docs/MIDDAG_7NOV_STEM_DIALOOG.md](MIDDAG_7NOV_STEM_DIALOOG.md) (commit `6bc0274`):

**A. Stem live-verifiëren** (30 min timebox)
- [x] speak.py pipe-patch gecommit (`3cf1fcc`)
- [ ] `anna.main` hard-restart met nieuwe speak
- [ ] Jolanda zegt "Hoi Anna Nova" → ElevenLabs hoorbaar binnen ~3s
- [ ] **Pass**: niet Piper-stem maar ElevenLabs

**B. Dialoog v0.5 schema in flow+brain** (1 uur timebox)
- [x] `inhoud.json` v0.5-draft gepusht (`eae7257`) — nieuw schema: `anna.karakter`, `reactie_regels`, `v0` als opening-vraag, `reserve` ipv `reacties`, `aanloop`/`na_reactie`/`takken`/`standaard_takken` per vraag, aparte `zeker`-state
- [ ] `flow.py handle_opening`: direct naar `vraag_index=0` (v0)
- [ ] `flow.py handle_vraag`: speelt `aanloop.tekst` + `tekst`
- [ ] `flow.py handle_reageren`: `reserve` ipv `reacties`, speelt `na_reactie` als die bestaat
- [ ] `flow.py` gespreksboom (`takken` + `standaard_takken` + nieuwe `State.ZEKER`)
- [ ] `brain.py` SYSTEM_PROMPT: gebouwd uit `anna.karakter` + `anna.toon` + `reactie_regels` + per-vraag `sturing`
- [ ] `brain.py` `max_woorden` uit `reactie_regels.max_woorden[vrijheid]` (6/15/25)
- [ ] **Pass**: volledig gesprek v0 → v1-v5 → afsluiting → bon, zeker-check bij "nee"

## ❌ Nog niet opgelost — vóór publiek nodig

| Punt | Waarom | Wie / wanneer |
|---|---|---|
| **Camera** — `/frame.jpg` leeg, dequeue-timeout | CSI-lintkabel/sensor | Jolanda fysiek: power eraf → beide kabel-uiteinden stevig terug → reboot |
| **Quotes `goedgekeurd: true`** | Nu 0 van 20 goedgekeurd — `ALLE_QUOTES=1` werkt wel, maar voor publiek moet Jolanda bewust kiezen | Jolanda kiest welke 20 quotes mogen |
| **Pre-render vaste zinnen** | Nu alle 32 zinnen live via ElevenLabs = €-kosten + latency | Na dialoog-freeze: `python3 tools/render_audio.py --engine elevenlabs` (eenmalig ~2 min) |
| **Full flow-test** | Zodra Spoor B klaar is | 15 testen uit vorige versie van dit plan (hieronder herhaald) |
| **3 bezoekers droogloop** | Laatste check voor expositie | Na alles af |

---

## Testplan — 15 acceptatie-criteria

**A. Stem (ElevenLabs)**
- A1. `TTS_MODE=elevenlabs` + key gezet → stem niet Piper
- A2. Netwerk uit → Piper fallback, geen crash
- A3. Latency wake → eerste klank < 3 s

**B. Brein (Mistral)**
- B1. JSON-respons `{soort, reactie}` binnen 3 s
- B2. Key leeg → situatie `fout`

**C. Wake / slaap**
- C1. "Hoi Anna Nova" op 2 m → opening binnen 2 s
- C2. "Slaap lekker" → `state-sluimert` binnen 3 s
- C3. 10 s stilte → situatie `ruis`

**D. Vragen-reeks (v0.5 schema)**
- D1. v0 opening-vraag triggert
- D2. v1 "Ja/Nee/Twijfel" via `reserve` reageert
- D3. v2 `na_reactie` speelt na brain
- D4. Zijweg op v1-v5 → `standaard_takken` of per-vraag `takken` volgt
- D5. 5 vragen in gewoon tempo, klaar binnen 3 min

**E. Printer**
- E1. Afsluiting "Ja" → bon print binnen 15 s
- E2. Printer uit → situatie `geenprint`
- E3. Bon leesbaar, alle tekst zichtbaar

**F. Privacy**
- F1. Geen nieuwe files in `audio/` na 5 bezoekers (alleen vooraf gerenderd)
- F2. Geen gesprekstekst in `journalctl -u anna-nova`
- F3. WebSocket :8766 → alleen stippen + pose keypoints
- F4. `.env` niet in git, keys nergens anders

---

## Fallback-matrix

| Faalt | Fallback | Bezoeker merkt |
|---|---|---|
| Netwerk | Piper lokaal + brain uit (hardcoded) | Minder mooie stem, geen vraag-afwijking |
| Printer | Situatie `geenprint` | "Mijn printer is op. Je krijgt hem in gedachten." |
| Camera | Geen pose-overlay, alleen stippen | Scherm werkt nog |
| Mistral | Situatie `fout` | "Ik hapte even. Ik ben met de hand gemaakt." |

---

## Scherm-states tijdens flow

- `state-sluimert` — rood, trage puls — bij wachten
- `state-luistert` — mint, rustig — bij mic-opname
- `state-denkt` — goud, draaien — bij Mistral-call
- `state-spreekt` — oranje, snelle puls — bij TTS
