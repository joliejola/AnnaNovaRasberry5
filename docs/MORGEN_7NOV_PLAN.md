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

## 11:00 — Bouwstap stem: A/B tussen 3 opties

Ik render 1 gekozen zin ("Snel. Dat zeggen ze allemaal.") met:

- **A**: ElevenLabs — Charlotte / Rachel / Lily
- **B**: Azure Neural — Fenna / Colette
- **C**: Piper `nl_NL-mls-medium` (lokaal, andere stem dan nu)

Jolanda luistert ze naast elkaar, kiest. Dan:
- [ ] Credentials in `.env` (`ELEVENLABS_API_KEY=` of `AZURE_TTS_KEY=`)
- [ ] `anna/speak.py` → `_say_live()` wrappen rond gekozen provider
- [ ] Pre-renderen van alle vaste zinnen (openingen, lokzinnen, wachtzinnen, situaties, afsluiting, slotzinnen) naar `audio/*.wav` zodat latency 0 is
- [ ] Live-TTS alleen voor `brain`-gegenereerde antwoorden

**Fallback** als cloud niet werkt: Piper `nl_NL-mls-medium` lokaal.

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

## Stem-opties (korte referentie)

Keuze morgen 11:00:

| # | Stem | Prijs | Latency | NL-kwaliteit |
|---|---|---|---|---|
| 1 | ElevenLabs Charlotte/Rachel/Lily | ~$5/mnd | 400 ms | ★★★★★ |
| 2 | Azure `nl-NL-FennaNeural` / `ColetteNeural` | €15 / 1M chars | 500 ms | ★★★★★ |
| 3 | OpenAI `tts-1-hd` nova / shimmer / coral | $0.015 / 1k | 700 ms | ★★★★ |
| 4 | Piper `nl_NL-mls-medium` (offline) | gratis | 200 ms | ★★★ |
| 5 | Coqui XTTS v2 voice cloning (offline) | gratis | 1–2 s | ★★★★ |

Pre-renderen van vaste zinnen = 0 ms latency voor 95% van wat Anna zegt — dus cloud is zonder zorg.

---

## Open punten voor Jolanda vóór morgen

1. Werk `content/inhoud.json` uit — vooral `goedgekeurd: true` zetten bij quotes
2. Keuze: wil je dat Jolanda-stem gekloond wordt (optie 5) of liever een studio-stem (1 of 2)?
3. Thuisgebruik: zet alvast ELEVENLABS/AZURE account aan als dat eenvoudig kan
