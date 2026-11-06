# Morgen 7 nov — plan van aanpak

*Vast schema, jouw nieuwe dialoog laden + printer live + betere stem.*

---

## Vanavond (Jolanda thuis, zelf)

**Werk uit:** `content/inhoud.json` (bouwplan-v2 branch).

Pas aan naar wens:
- `openingen[]` — wat Anna zegt bij wake
- `reeks[]` — de 5 vragen + reacties per vraag (vraag 1 heeft ja/nee/twijfel/elk; rest alleen `elk`)
- `wachtzinnen[]` — wat Anna zegt tijdens denken
- `situaties{}` — pas / ruis / zijweg / provocatie / verdriet / verdwaald / tijd / weg / fout / geenprint
- `afsluiting`, `na_nee`, `slotzinnen[]`
- `quotes[]` — 20 stuks met prijs. Zet `goedgekeurd: true` bij de versies die je wil toelaten.

**Push als je klaar bent:**
```bash
cd ~/websiteAI/....   # waar je bouwplan-v2 clone staat
git add content/inhoud.json
git commit -m "dialoog v0.3 — Jolanda thuis"
git push origin bouwplan-v2
```

Als je het liever op de Mac via de editor doet is ook prima — zeg het, dan commit ik.

---

## Morgen 09:00 — start

- [ ] Beide sessies pullen: `git pull origin bouwplan-v2`
- [ ] Anna-service status check (Pi): `systemctl status anna-nova`
- [ ] Lezen: nieuwe `content/inhoud.json`, controleer dat alle `goedgekeurd: true` staan bij quotes je wil
- [ ] Render audio opnieuw (vaste zinnen): `.venv/bin/python tools/render_audio.py`
  *(duurt ~2 min — opent/lok/wacht/situaties/afsluiting, alles behalve brain-antwoorden)*

## 09:30 — Bouwstap 1: printer live (max 1 uur)

Volg `docs/voorbereiding/PRINTER_SETUP.md`. Checklist:

- [ ] Stap 1 — BlueZ actief (`systemctl is-active bluetooth` → `active`)
- [ ] Stap 2 — Printertje pairen via `bluetoothctl` → MAC in `.env` als `PRINTER_MAC=...`
- [ ] Stap 3 — TiMini-Print clone + venv
- [ ] Stap 4 — Testregel via `-m timini --bluetooth MAC --file /tmp/test.txt`
- [ ] Stap 5 — Lineaal-PNG printen → `PRINT_BREEDTE_PX=384` of `576` in `.env`
- [ ] Stap 6 — Een echte bon via `anna.bon.render_bon()` + `anna.printer.print_bon_png()`

**Timebox:** 1 uur. Als stap 2 (pairen) niet lukt → **stop**, bestel USB ESC/POS fallback.

## 11:00 — Bouwstap stem: ElevenLabs implementeren

**Keuze is gemaakt:** ElevenLabs. Jolanda kiest vanavond zelf welke stem (Charlotte / Rachel / Lily / anders) in haar ElevenLabs-dashboard.

Zij geeft morgen:
- Voice-ID (string, bv `EXAVITQu4vr4xnSDxMAC`)
- API key (`ELEVENLABS_API_KEY=sk_...`)

Dan ik:
- [ ] `.env` → `ELEVENLABS_API_KEY=...` + `ELEVENLABS_VOICE_ID=...`
- [ ] `anna/speak.py` → `_say_live()` wrappen rond ElevenLabs API (`eleven_multilingual_v2`, stability 0.5, similarity 0.75 default)
- [ ] `tools/render_audio.py` uitbreiden: pre-rendert alle vaste zinnen (openingen, lokzinnen, wachtzinnen, situaties, afsluiting, slotzinnen) naar `audio/*.wav` → latency 0 voor 95% van wat Anna zegt
- [ ] Live-TTS alleen voor `brain`-gegenereerde antwoorden + quotes (die wisselen per gesprek)
- [ ] Cache voor laatste 50 live-zinnen → als bezoeker 2x iets zelfde zegt geen nieuwe API-call

**Fallback** als ElevenLabs cloud wegvalt: Piper `nl_BE-nathalie-medium` (huidige, al op Pi). `.env` toggle `TTS_MODE=elevenlabs|piper`.

## 13:00 — Lunch + droogloop

- [ ] `DROOGLOOP=1 .venv/bin/python -m anna.main` — hele flow in tekst door console
- [ ] Check dat alle vragen, reacties, situaties, 1 quote per gesprek-pad werken
- [ ] Geen tekst missen — als Anna "???" zegt → inhoud.json bijwerken

## 14:00 — Full stack test (echte hardware)

- [ ] `DROOGLOOP=0 .venv/bin/python -m anna.main`
- [ ] "Hoi Anna Nova" (wake via Vosk) → opening
- [ ] 5 vragen doorlopen met echte antwoorden (ja / nee / twijfel / pas)
- [ ] Testen: `pas`, `ruis` (gewoon stil blijven), `zijweg` (iets heel anders zeggen)
- [ ] Afsluiting → bon print → Anna slaapt

## 15:00 — Style-ronde

- [ ] Scherm-states: `sluimert` / `luistert` / `denkt` / `spreekt` kleuren check (zie `web/achtergrond-demo.html`)
- [ ] Hint-tekst in cel groter / kleiner?
- [ ] Logo op bon — nu assets/logo.png B&W
- [ ] Font-weight op scherm — Georgia italic ok?

## 16:00 — 3 echte bezoekers droogloop

Vraag 3 mensen (vriend/vriendin/toevallige) om 1x Anna te proberen zonder uitleg.
Observeer:
- [ ] Vinden ze het wake-woord?
- [ ] Antwoorden ze op de vragen of lopen ze weg?
- [ ] Wordt het bonnetje gelezen?
- [ ] Zouden ze opnieuw willen?

Noteer in eigen woorden wat er niet werkt → inhoud.json / flow aanpassen.

## 17:00 — Buffer / bugs / rust

Wat er overblijft:
- Camera-lintkabel nog aandrukken? (als `/frame.jpg` nog leeg is)
- Pose-overlay check (`web/achtergrond-demo.html?demo=1`)
- Nachtmodus / kiosk op juiste resolutie

---

## Testplan — acceptatie-criteria

Anna is "klaar" als dit allemaal werkt:

1. **Wake**: "Hoi Anna Nova" op 2 m afstand → binnen 2 s "Hoi, je staat op de plek…"
2. **Vraag 1 ja**: "Ja" → "Snel. Dat zeggen ze allemaal."
3. **Vraag 1 nee**: "Nee" → "Verstandig. Laten we toch kennismaken."
4. **Vraag 1 twijfel**: "Misschien" → "Twijfel is gezond. Ik heb het niet."
5. **Pas**: "Pas" in elke vraag → "Pas is ook een antwoord."
6. **Ruis**: Niets zeggen 5 s → "Ik hoorde ruis. Nog een keer, langzaam?"
7. **5 vragen volledig**: Met "elk"-reacties, geen vastloper
8. **Afsluiting + bon**: Anna vraagt "Dan nu de rekening. Wil je hem?" → "Ja" → bon print binnen 8 s met quote + prijs + URL + datum
9. **Bon fallback**: Printer uit → Anna zegt situatie `geenprint`
10. **Slaap**: "Slaap lekker" of 10 s stil → zacht naar `sluimert`

**Scherm-states zichtbaar:**
- `state-sluimert` (rood puls, langzaam)
- `state-luistert` (groen/mint, stil)
- `state-denkt` (goudtint, stippen draaien)
- `state-spreekt` (oranje, pulseert)

**Privacy-check:**
- [ ] Geen tekst / audio / beeld naar disk (ook niet in logs)
- [ ] Alleen keypoints over WebSocket, nooit beeld
- [ ] `MISTRAL_API_KEY` in `.env` (gitignored)

---

## Stem: ElevenLabs

**Gekozen:** ElevenLabs (optie 1). Jolanda kiest vanavond zelf welke stem uit haar dashboard.

- Prijs: ~$5/mnd Starter (30k chars) of $22/mnd Creator (100k chars)
- Model: `eleven_multilingual_v2` (NL-ondersteuning)
- Latency: 400 ms voor live-zinnen; 0 ms voor pre-gerenderde vaste zinnen

Overwogen-maar-niet:
- Azure Neural Fenna/Colette — iets minder expressief
- OpenAI nova/shimmer — meer accent
- Piper lokaal — blijft als fallback
- XTTS voice cloning — te zwaar op Pi 5

---

## Open punten voor Jolanda vóór morgen

1. Werk `content/inhoud.json` uit — vooral `goedgekeurd: true` zetten bij quotes
2. ElevenLabs stem kiezen (en test-zin "Snel. Dat zeggen ze allemaal." uitproberen in hun UI)
3. Noteer voor morgen: `ELEVENLABS_VOICE_ID=...` en `ELEVENLABS_API_KEY=sk_...`
4. Stability + similarity-waarden uit het dashboard overnemen (default 0.5 / 0.75 werkt meestal)
