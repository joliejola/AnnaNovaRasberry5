# Bouwplan v2 — aanpak voor Anna Nova (praatcel met bon)

*6 november 2026 · vervangt `MORGEN_AANPAK.md`, revisie na Jolanda's feedback 6 nov ochtend*

Jolanda schreef in de nacht van 5→6 november een nieuw bouwplan (zie `docs/BOUWPLAN_BRON.md`). Dat herdefinieert het kunstwerk wezenlijk: geen galerij, geen foto's — een gespreksmachine van ~3 minuten die eindigt met een bon uit een klein Bluetooth-printertje. Dit document is **onderhevig aan bron 2**. Waar iets botst: bron 2 wint, behalve waar Jolanda expliciet een afwijking vraagt (zie revisie-notitie onderaan).

Dit document is voor vandaag. Het zegt (1) wat uit het oude plan blijft, (2) wat weggaat, (3) wat bewust blijft bestaan maar niet gebruikt wordt, (4) hoe we de 10 bouwstappen uit bron 2 in parallelle tracks verdelen, en (5) waar Jolanda een beslissing maakt.

## Revisie 6 nov ochtend — door Jolanda

- **Wake-phrase blijft primaire trigger**. Reden: expositie met veel mensen → Anna mag niet zomaar aanslaan, moet eerst aangesproken worden ("Hoi Anna Nova" + alle fuzzy varianten).
- **SLEEP_PHRASES blijven** ("slaap lekker", "ga maar slapen", etc.). Reden: Jolanda moet Anna midden-expositie kunnen laten zwijgen zonder stekker eruit.
- **Foto-pijplijn**: niet slopen uit codebase. Laten staan in `vision.py` / `anna-sync.py` / `web/gallery.html`. Niet doorontwikkelen, niet opstarten in service, mogelijk later weer actief.
- **Printer + USB wifi-dongel komen pas vanmiddag**. Volgorde omgedraaid: offline- en Pi-werk eerst, hardware-integratie na lunch.

---

## Twee kernvragen — door Jolanda al beantwoord (6 nov ochtend)

1. **Repo**: bestaande `joliejola/AnnaNovaRasberry5` rewriten in branch `bouwplan-v2`. Geen nieuwe repo. ✅
2. **face.html**: hergebruik `web/face.html` (vignette-per-state + draaikolk werken al), pas aan voor nieuwe toestanden rust/luistert/denkt/spreekt/afrekenen/print/knopmodus. ✅

**Nieuw hardware-nieuws (6 nov ochtend)**: camera is aangesloten (Arducam OV5647 via CSI). `see.py` kan tegen echte libcamera-input gebouwd worden. Hailo-8L aanwezig; SCRFD HEF nog niet op Pi — `install.sh` downloadt die. Test: `ssh annanova 'rpicam-hello --list-cameras'`.

---

## Wat uit het oude plan BLIJFT (hergebruik zonder gêne)

Deze stukken zijn werkend fundament uit de afgelopen week. Niet weggooien — mappen naar de nieuwe structuur.

| Oud | Wordt | Waarom bewaren |
|---|---|---|
| Vignette-per-state in `web/face.html` (CSS gradients, state-specifieke kleuren, draaikolk bij denkt) | `face/index.html` — mapping: sluimert→**rust**, luistert→**luistert**, denkt→**denkt**, spreekt→**spreekt**. Nieuwe states: **afrekenen**, **print**, **knopmodus**. | Werkt al, Jolanda kent deze stijl, "denkt mag haperen" past bij de draaikolk |
| Voxtral ASR-wrapper (anna-nova.py, http-call met MISTRAL_API_KEY, upload-timeout 30s) | `anna/hear.py` — ASR-deel | Werkt al, Voxtral is sneller dan Whisper. Whisper als offline fallback kan blijven |
| Piper subprocess + nathalie-medium stem (`nl_BE-nathalie-medium.onnx`) | `anna/speak.py` — derde fallback na vooraf opgenomen en live TTS | Stem is Jolanda's keuze, al gedownload op Pi |
| Mistral http-client (EU endpoint, API-key, timeout-pattern) | `anna/brain.py` — basis | Werkt al; alleen de prompt + JSON-output zijn nieuw |
| ReSpeaker DoA (`respeaker_doa.py`) | `anna/see.py` of apart `anna/hear.py` — richtingsbepaling | Werkt al, is kern van spreekplek-detectie |
| VAD-throttle (silero_vad elke 128ms ipv 32ms) | `anna/hear.py` — stilte-detectie in LUISTEREN | CPU-fix 140%→20%, cruciaal voor Pi |
| `reset_session_window()` + forget-logica bij slaap/wake | `anna/flow.py` — LOSLATEN-toestand | Dezelfde logica, meerdere triggers (6s plek leeg, BON afgerond, of SLEEP_PHRASE) |
| **Wake-phrase ("Hoi Anna Nova" + fuzzy varianten)** | `anna/hear.py` — primaire RUST→OPENING trigger. Spreekplek-detectie blijft, maar als filter bij LUISTEREN (wie van de omstanders telt), niet om Anna wakker te maken | Veel mensen op expositie → Anna mag niet zomaar aanslaan. Behoudt variants uit huidige `.env` `WAKE_PHRASE` |
| **SLEEP_PHRASES** (`slaap lekker`, `ga maar slapen`, `welterusten`, etc.) | `anna/hear.py` — werkt in elke actieve toestand (OPENING/VRAAG/LUISTEREN/REAGEREN). Triggert direct LOSLATEN → RUST. Geen bon. | Jolanda-noodrem als Anna irritant wordt mid-expositie. Komma-lijst uit huidige `.env` wordt overgenomen |
| `WAKE_ACK`, `SLEEP_ACK` korte bevestigingen | Blijven, uit `inhoud.json.situaties` (nieuw: `wake_ack`, `sleep_ack`) | Hoorbare bevestiging dat Anna het commando hoorde |
| `install.sh` (systemd-unit template, model-downloads, dependencies) | Aangepaste `install.sh` — 1 service `anna-nova.service`, geen galerij-services | systemd-skelet bruikbaar, alleen inhoud wisselt |
| `config.sample.env` | Nieuwe, veel kortere `.env.sample` (zie bron 2). Behouden: `MISTRAL_API_KEY`, `MISTRAL_MODEL`, `PIPER_VOICE`, `AUDIO_INPUT_DEVICE`, `AUDIO_OUTPUT_DEVICE`, `SPEAK_ANGLE_CENTER`/`MARGIN`, `ASR_ENGINE`, `VOXTRAL_MODEL` | Hardware-config is hergebruikbaar |
| Hailo face-detection (`vision.py` SCRFD) | `anna/see.py` — alleen "hoeveel mensen op plek" nodig, geen mood/attr | Face-count is de nieuwe rol; mood kan eruit |
| `persona.md` — Anna's **stem** (zacht in vorm, droog in toon, max 1-2 zinnen, geen emoji, geen "Als AI...") | `anna/brain.py` system-prompt — maar véél korter, want brain geeft JSON en max 18 woorden | Het karakter is er; alleen de output-vorm wisselt |

---

## Wat uit het oude plan WEG GAAT (verwijderen in branch)

Bron 2: geen galerij draaiend, geen SSD, bezoekers niet onthouden. Daarmee verdwijnt:

- **Voice-recognition**: `anna-enroll.py`, resemblyzer, voiceprint-threshold, "Jolanda-herkenning" in persona
- **Nachtslaap / persona-arc**: `nachtslaap.py`, `persona_history` SQLite-tabel, dag-arc reflectie. Anna heeft geen dag-geheugen meer — elke bon is het enige exemplaar.
- **Ambient-mompelen in sluimer** (`AMBIENT_LINES`): vervangen door `lokzinnen` uit `inhoud.json` (vergelijkbaar effect, nieuwe content-plek)
- **Grace-farewell** (`GRACE_FAREWELL_*`): vervangen door `slotzinnen` en `na_nee` uit `inhoud.json`
- **Uitgebreide persona.md-secties 3-11** (reden van bestaan, backstory, meningen, wat Anna leuk vindt, grenzen): komt uit als "lore"-document; brain.py gebruikt alleen een korte system-prompt. De uitgebreide tekst blijft in de repo als `docs/persona-archief.md` — Jolanda kan er stukken uit halen voor interviews/perstekst.
- **SD-backup fase 13**: geen uitgebreid backup-ritueel. Wel: één `.img` dump aan het eind van de bouwdag, maar geen SSD.
- **Externe galerij HTTP-server-route `/gallery`**: wordt niet meer gestart (zie "Slapend laten" hieronder).
- **De 7 beslismomenten uit het oude plan**: vervangen door nieuwe beslismomenten (zie onder).

## Slapend laten bestaan (niet slopen, niet gebruiken)

Jolanda wil deze code behouden voor een mogelijke latere revival; we doen er nu niks mee, maar we gooien het ook niet weg.

| Bestand / stuk code | Status vandaag | Reden behouden |
|---|---|---|
| `vision.py` → `_photo_pipeline()`, `_apply_filter()`, foto-opslag | **Niet aangeroepen**. Code blijft staan, service-loop start geen foto-thread. | Mogelijk later terugkomen op foto-concept |
| `anna-sync.py` | **Niet gestart**. Blijft in repo. | Werkende SFTP/GitHub-Pages sync-code |
| `web/gallery.html` + CSS | **Niet geserveerd**. Blijft in repo. | Ontwerp bruikbaar voor ander kunstwerk |
| `PHOTO_*` env-vars in `config.sample.env` | **Verplaatst naar `config.sample.env` sectie "# SLAPEND — foto-pijplijn (niet actief)"** met expliciete markering | Duidelijk wat uit staat |
| Hailo face-attr (mood-detection) | **Niet aangeroepen**. HEF kan op Pi blijven. | Mogelijk later |

**Belangrijk**: in `anna/main.py` géén imports naar foto-code. De bestanden bestaan maar worden niet geladen, zodat `systemctl status anna-nova` geen foto-gerelateerde errors geeft.

---

## Volgorde vandaag — printer en dongel komen 's middags

Bron 2 nummert bouwstappen 1–10. Omdat de printer en USB wifi-dongel pas na de lunch binnen zijn, draaien we de volgorde om:

**Ochtend (zonder printer, zonder dongel)** — offline + Pi met huidige wifi:
- Bouwstap 2 (inhoud.json + bon.py + test_bon.py) — laptop
- Bouwstap 4 (flow.py droogloop) — laptop, inclusief wake-phrase + sleep-phrases
- Bouwstap 5 (brain.py + 10 testvoorbeelden) — laptop + Mistral
- Bouwstap 7 (hear + see + wake-detect + sleep-detect op Pi) — Pi, camera is net aangesloten
- Bouwstap 8-voorbereiding (face.html aanpassen voor 7 nieuwe states) — laptop
- Bouwstap 6a (render_audio draaien — kan lang duren, parallel) — laptop

**Middag (printer binnen + eventueel wifi-dongel)**:
- Bouwstap 1 (printer pairen) — Pi + printer
- Bouwstap 3 (printer.py integratie + echte bon) — Pi + printer
- Bouwstap 6b (speak.py op Pi testen) — Pi
- Bouwstap 8 (face.py + scherm) — Pi, Jolanda bekijkt
- Bouwstap 9 (groepstest met 5 vrienden) — atelier
- Bouwstap 10 (expositie-klaar) — Pi

Als de dongel niet komt: ochtend Voxtral/Mistral werkt mogelijk trager → fallback voor render_audio is Piper offline-render (consistent, iets minder natuurlijk). Flow.py kan volledig zonder dongel.

## De 10 bouwstappen van bron 2 — vertaald naar vandaag

Bron 2 geeft 10 bouwstappen, elk eindigend in een test. Hieronder per stap: wie doet wat, waar (Pi / lokaal), hoeveel tijd, wat Jolanda beslist. Volgorde van bron 2 behouden voor referentie; het dagritme (verderop) herverdeelt ze.

### Bouwstap 1 — Printertje aan de praat
**Wie**: Jolanda fysiek (printer uit doos, aanzetten, Bluetooth pairen met Pi) + ik in SSH. **Waar**: Pi. **Tijd**: 30–60 min (zoals bron 2 zegt: max 1u proberen).

Agodeo mini pairen via `bluetoothctl`, testregel printen via TiMini-Print of funprint CLI. Print-breedte (in pixels, bij 300 DPI typisch 576 of 384) meten door een lijn te printen en te turven. Invullen in `.env`: `PRINT_BREEDTE_PX=…`, `PRINTER=mini`.

🔔 **Beslismoment 1**: lukt niet binnen 1u → *doorschakelen naar USB ESC/POS reserve, of droogloop-only vandaag*?

**Test**: één regel "Hoi Anna" uit het printertje.

### Bouwstap 2 — `inhoud.json` + `bon.py` + `tools/test_bon.py`
**Wie**: ik autonoom lokaal (geen Pi nodig). **Waar**: laptop. **Tijd**: 60–90 min.

- `content/inhoud.json` eerste versie: 3 openingen, 10 vragen (verdeeld over bekeken/bewaard/wrijving, met `licht:true/false`), 4 brugzinnen, 3 wachtzinnen, 9 situatiezinnen, afsluiting, na_nee, 2 slotzinnen, 20 voorbeeld-quotes (half goedgekeurd:null — Jolanda keurt later).
- `anna/bon.py`: Pillow-render. Logo uit `assets/logo.png`, Courier Prime-font (free), quote-keuze volgens longest-halte-regel, percentage-berekening ($2.67T basis).
- `tools/test_bon.py`: rendert 5 PNG-bonnen met verschillende quotes + verschillende prijzen.

🔔 **Beslismoment 2**: na 5 PNG-bonnen: quote-selectie eerlijk? percentage-notatie (bijv. `0,0000000000015 %` voor €0,04) OK of te bang/te wiskundig? prijsjes op quotes OK?

**Test**: 5 PNG-bonnen op laptop openen.

### Bouwstap 3 — `anna/printer.py` (hardware + reserve-routes)
**Wie**: ik + Jolanda (Pi met printer aan). **Waar**: Pi. **Tijd**: 45 min.

Bellt in op bouwstap 1's print-CLI. Fallback-cascade: (1) mini via Bluetooth, (2) USB ESC/POS via python-escpos, (3) PNG-opslag + Anna zegt `situaties.geenprint`. Printer-health-check bij opstart.

**Test**: echte bon uit printer; printer uit → droogloop meldt `geenprint`.

### Bouwstap 4 — `anna/flow.py` droogloop (de machine zelf)
**Wie**: ik autonoom lokaal. **Waar**: laptop. **Tijd**: 2–3u (grootste werk).

Volledige state-machine volgens tabel in bron 2 — **aangepast** voor wake-phrase en sleep-phrases:

| Toestand | Trigger naar deze toestand | Wat Anna doet | Naar |
|---|---|---|---|
| RUST | start, LOSLATEN, SLEEP_PHRASE | Slaapt, roept lokzin als mensen in ruimte maar niet op plek | **wake-phrase detected** → WAKE_ACK → OPENING |
| OPENING | wake-phrase gehoord | Korte "Hm."/WAKE_ACK + speelt willekeurige opening | VRAAG |
| VRAAG | OPENING, REAGEREN | Stelt volgende vraag uit getrokken reeks | LUISTEREN |
| LUISTEREN | VRAAG | Wacht spraak van plek | REAGEREN, STIL na 8s, RUIS, of **sleep-phrase → LOSLATEN** |
| REAGEREN | LUISTEREN met spraak | Mistral-call, speelt reactie/brugzin | VRAAG, AFSLUITING of ZACHT |
| STIL, RUIS, DRUK, ZACHT | (zoals bron 2) | (zoals bron 2) | (zoals bron 2); sleep-phrase werkt ook hier |
| AFSLUITING | 4 vragen klaar / 5 min / 2 zijwegen / ZACHT | "Wil je de rekening?" | BON bij ja, LOSLATEN bij nee |
| BON | AFSLUITING met ja | Bouwt en print bon, speelt slotzin | LOSLATEN |
| LOSLATEN | BON / nee / 6s plek leeg / SLEEP_PHRASE | Wist gesprek | RUST |

**Nieuwe elementen t.o.v. bron 2**:
- Wake-phrase is primaire RUST→OPENING trigger. "Iemand op plek" alleen is niet genoeg.
- Sleep-phrase werkt in élke actieve toestand (vangt Anna in één keer stil).
- WAKE_ACK uit `inhoud.json.situaties.wake_ack` (bijv. "Hm.", "Hé.", "Ja?")
- SLEEP_ACK uit `inhoud.json.situaties.sleep_ack` (bijv. "Mmh. Welterusten.")

Droogloop-modus (`DROOGLOOP=1` in `.env`):
- hear.py → `input()` ipv mic
- speak.py → `print()` + sleep-om-duur-te-simuleren ipv audio
- printer.py → PNG opslaan ipv printen
- see.py → `[1 persoon op plek]` indicator in console; typ `#weg` om te simuleren weg

Debug-toetsen tijdens droogloop: Enter = stilte, `#ruis` = ruis-detectie, `#druk` = meerdere mensen, `#weg` = plek leeg. Normale tekst = gesproken zin. Begint met "hoi anna nova" (of variant) → wake-trigger. Bevat sleep-phrase (bijv. "slaap lekker") → direct LOSLATEN.

🔔 **Beslismoment 3**: Jolanda speelt 5 droogloop-gesprekken na — doet ze het nog een keer als het haar irriteert?
- Voelen brugzinnen natuurlijk?
- Zijn de 4 vragen de juiste?
- Mist er een zacht-situatie?
- Werkt de 2-zijwegen-regel?
- Wake-ack kort genoeg (niet irritant bij veel bezoekers)?

**Test**: 5 droogloop-gesprekken (zie `TESTPLAN_V2.md`), start steeds met wake-phrase, 1x met sleep-phrase midden in.

### Bouwstap 5 — `anna/brain.py` (Mistral JSON-call)
**Wie**: ik autonoom lokaal. **Waar**: laptop + Mistral-API. **Tijd**: 45 min.

System-prompt in Nederlands. Verwachte output: `{"soort":"antwoord|pas|zijweg|provocatie|verdriet|ja|nee","reactie":"…"}`. Max 18 woorden. Timeout 4s → brugzin + `soort=antwoord`. EU endpoint, `training=false`.

**Test**: 10 voorbeeld-prompts (zie `TESTPLAN_V2.md`). Internet uit → brugzin.

🔔 **Beslismoment 4**: brain-output bij 10 testvoorbeelden — voelt het als Anna's stem? Welke "soort"-detectie werkt niet goed?

### Bouwstap 6 — `tools/render_audio.py` + `anna/speak.py`
**Wie**: ik autonoom lokaal → naar Pi. **Waar**: laptop (render), Pi (speak-integratie). **Tijd**: 60 min + rendertijd.

- `tools/render_audio.py`: loopt `content/inhoud.json`, rendert elke zin met `id` naar `audio/<id>.wav` via Voxtral TTS (vereist tegoed, ongeveer $0.02/minuut audio). Hash-check: alleen hergenereren bij wijziging.
  - Als Voxtral-TTS niet beschikbaar is: Piper-fallback bij render-tijd (nathalie-medium) — niet live. Dan klinkt de vaste zinnen = Piper-stem, en live-TTS is ook Piper. Minder verschil, maar werkt.
- `anna/speak.py`: cascade (1) `audio/<id>.wav` als bestaat, (2) live Voxtral-TTS, (3) Piper offline.

🔔 **Beslismoment 5**: eerste opening klinkt binnen 0,5s na start? Voxtral-stem vs Piper-stem — voelt het één persoon?

**Test**: `OPENING` triggeren in droogloop → audio uit laptopspeaker.

### Bouwstap 7 — `anna/hear.py` + `anna/see.py` + wake/sleep aan flow koppelen
**Wie**: ik + Jolanda. **Waar**: Pi. **Tijd**: 75 min.

Drie subsystemen:

1. **Wake-phrase detectie in RUST**: hear.py luistert continu met VAD (lage drempel voor CPU). Elke spraak-blob gaat door Voxtral (mini-latest) → tekst matcht fuzzy tegen `WAKE_PHRASE_PATTERNS` (uit `.env`, komma-lijst, substring+edit-distance zoals huidige code). Match → `hear.wake_detected()` event naar flow. De spreker-richting hoeft niet op plek te zijn (iemand staat voor Anna, spreekt haar aan — dan loopt die de laatste meter).

2. **Sleep-phrase detectie in alle actieve toestanden**: zelfde VAD-pipeline, elke transcriptie ook getest tegen `SLEEP_PHRASES` (komma-lijst). Match → `hear.sleep_detected()` event → flow springt direct naar LOSLATEN. Werkt ongeacht wie het zegt (bezoeker zegt per ongeluk "ga slapen" = Anna slaapt, Jolanda haalt haar weer wakker met wake-phrase).

3. **Spreekplek-filter in LUISTEREN**: ReSpeaker DoA ±30° (hoek) EN `see.py` zegt 1 persoon op plek → "spreker telt mee voor Mistral". Meer dan 1 persoon of overlappende stemmen (2 DoA-pieken) → DRUK. Knopmodus: USB-knop (GPIO of HID) → luistert alleen tijdens druk. 30s rust zonder knop → terug naar normaal.

**Test**:
- Wake-phrase test: 10 varianten (zie TESTPLAN_V2). ≥8 moet wakker maken, nul "een van 5 vrienden die het toevallig zegt in achtergrond" (want niemand op plek).
  - Nuance: wake-phrase mag vanaf elke richting komen (iemand loopt op Anna af), maar als wake triggert terwijl geen enkele face in frame → Anna zegt alleen WAKE_ACK, blijft in half-wakker. Pas als persoon op plek staat binnen 5s: OPENING. Anders terug RUST. **Dit voorkomt achtergrond-false-wakes zonder iemand voor haar.**
- Sleep-phrase test: Jolanda zegt mid-gesprek "slaap lekker" → binnen 2s SLEEP_ACK en terug naar RUST.
- Spreekplek-filter test: stem recht voor Anna telt; stem schuin achter telt niet.

🔔 **Beslismoment 6**: hoek-marge goed op 30°? Hoor-radius goed? Wake-ack kort of weg? Sleep-ack blijft?

### Bouwstap 8 — `anna/face.py` + scherm
**Wie**: ik + Jolanda. **Waar**: Pi + Chromium. **Tijd**: 45 min.

- `face/index.html`: 7 toestanden zichtbaar (rust/luistert/denkt/spreekt/afrekenen/print/knopmodus). Op aanraden van bron 1: hergebruik `web/face.html` CSS, mapping volgens tabel boven. Denkt-animatie mag haperen (draaikolk doet dat al). Knopmodus toont: "Druk op de knop om te praten."
- `anna/face.py`: websocket-server, stuurt state-wissels naar browser.

🔔 **Beslismoment 7**: 7 screenshots naast elkaar — welke state onduidelijk? Welke kleur niet raak?

**Test**: elke state forceren via flow → zichtbaar op Pi-scherm.

### Bouwstap 9 — Groepstest (5 vrienden)
**Wie**: Jolanda + 5 vrienden + ik in SSH. **Waar**: atelier. **Tijd**: 45 min.

1 persoon op plek, rest praat erdoorheen. Meten:
- Vals-positieven: hoe vaak reageert Anna op iemand ernaast?
- Gemist: hoe vaak reageert Anna niet terwijl de spreker op plek staat?
- Trigger-tijd: hoe lang na "iemand gaat op plek staan" tot OPENING?

Drempels bijstellen in `.env`: `SPREEKPLEK_HOEK`, `SPEAK_ANGLE_MARGIN`, VAD-drempel.

🔔 **Beslismoment 8**: hoeveel vals-positief is acceptabel? Strenger = frustratie, soepeler = verwarring.

**Test**: 10 min continu met 5 mensen. Tellen.

### Bouwstap 10 — Expositie-klaar
**Wie**: ik + Jolanda. **Waar**: Pi. **Tijd**: 60 min.

- systemd-unit `anna-nova.service` (gebruik oude als skelet, nieuwe `ExecStart=python3 -m anna.main`)
- Auto-restart on failure
- Hardware-watchdog (`/dev/watchdog`) — Pi hardware-reset bij hang
- Read-only overlay (`raspi-config` → "Overlay Filesystem") — SD-kaart beschermd tegen power-cut
- Bordje bij de installatie: *"Anna is AI. Ze hoort je en ziet dat je er bent. Ze bewaart niets. De bon is het enige exemplaar."*

🔔 **Beslismoment 9 (final)**: expositie-go? Of nog iets aanpassen?

**Test**: `sudo reboot` → Pi komt op → Anna zelf → 1 demo-gesprek zonder SSH.

---

## Parallelle tracks — hoe we niet op elkaar wachten

Jolanda heeft 1 dag. Serieel zou dit ~10u zijn. Parallel kan het in ~6u — als drie werkbanken tegelijk draaien.

### 🅰️ Hoofd-track — Jolanda + ik samen, op Pi
**Beslist alles wat de printer, de mic, het scherm, en het netwerk raakt.**

- Bouwstap 1 (printer pairen)
- Bouwstap 3 (printer.py hardware)
- Bouwstap 6 laatste 15 min (speak.py op Pi testen)
- Bouwstap 7 (hear/see koppelen)
- Bouwstap 8 (scherm)
- Bouwstap 9 (groepstest)
- Bouwstap 10 (expositie-klaar)

**Vast ritme**: Jolanda is nooit langer dan 20 min per blok actief. Beslissingen in tussentijd.

### 🅱️ Parallel-track "inhoud + bon" — ik autonoom lokaal
**Levert**: de brein-content en het papieren eindresultaat.

- Bouwstap 2 (`inhoud.json` + `bon.py` + `test_bon.py`) — levert 5 PNG-bonnen
- Bouwstap 5 (`brain.py` + 10 testvoorbeelden) — levert JSON-logs
- Bouwstap 6 eerste deel (`render_audio.py` draaien) — rendert alle vaste zinnen naar `audio/*.wav`

**Mergepunt**: wanneer 🅰️ bij stap 3 zit, merge 🅱️'s bon.py + inhoud.json → Pi test echte bon.

### 🅲️ Parallel-track "flow + scherm" — ik autonoom lokaal
**Levert**: de machine die alles aan elkaar knoopt.

- Bouwstap 4 (`flow.py` droogloop) — 2–3u aan één stuk, grote stuk werk
- Bouwstap 8 voorbereiding (`face.html` aanpassen, mapping oude→nieuwe states)

**Mergepunt**: wanneer flow.py droogloop werkt op laptop → Jolanda speelt 5 gesprekken (beslismoment 3), dan pullen we naar Pi en koppelen hear/see (bouwstap 7).

### Dagritme (ruw, laten bijstellen) — printer en dongel pas vanmiddag

| Tijd | 🅰️ Pi-track (Jolanda + ik) | 🅱️ Inhoud-track (ik solo) | 🅲️ Flow-track (ik solo) |
|---|---|---|---|
| 09:00 | Pi sanity + camera verifiëren (`rpicam-hello`) | start `content/inhoud.json` + `bon.py` | start `flow.py` skelet (incl. wake/sleep-states) |
| 10:00 | hear.py uitbouwen: wake-detect + sleep-detect op Pi | `test_bon.py` → **🔔 beslismoment 2** (5 PNG's) | flow.py tellers + vraagtrek-logica |
| 11:00 | hear.py test wake-woorden (10 varianten) → **🔔 beslismoment 4** (brain.py 10 voorbeelden na) | `brain.py` + 10 voorbeelden | flow.py droogloop compleet |
| 12:00 | LUNCH | LUNCH | **🔔 beslismoment 3** (5 droogloop-gesprekken met Jolanda) |
| 12:45 | **🅰️ hardware komt binnen**: printer + evt dongel uitpakken | `render_audio.py` draaien (15-30 min) | face.html aanpassen (7 states) |
| 13:15 | bouwstap 1 printer pairen → **🔔 beslismoment 1** | audio render af; `speak.py` cascade op Pi | — |
| 14:00 | bouwstap 3 printer.py integratie | — → **🔔 beslismoment 5** (stem-vergelijking) | — |
| 14:45 | bouwstap 7 complete: see.py camera + spreekplek-filter → **🔔 beslismoment 6** | — | — |
| 15:30 | bouwstap 8 scherm live → **🔔 beslismoment 7** (7 states) | — | — |
| 16:15 | bouwstap 9 groepstest met vrienden → **🔔 beslismoment 8** | — | — |
| 17:00 | bouwstap 10 expositie-klaar + eindsimulatie → **🔔 beslismoment 9** | — | — |

Totaal: ~8u. Buffer 17:30–18:30 voor fixes / tweede ronde drempels / SD-image.

**Belangrijke parallelliteit vóór hardware-aankomst**:
- Terwijl 🅱️ aan inhoud werkt en 🅲️ aan flow, kan 🅰️ al hear.py bouwen op Pi want **camera is al aangesloten** en wifi werkt al (tragelijk, maar werkt).
- Wake/sleep-detect kan volledig op Pi getest voor printer binnen is — gewoon via mic. Jolanda doet dat tussen beslismoment 2 en 3.
- Render_audio draait "in de lunch-window" — niets anders op laptop nodig.

**Als dongel niet komt**: render_audio-fallback is Piper offline (consistent, iets minder natuurlijk). Flow + brain + wake blijven werken op huidige wifi.

---

## Jolanda-beslismomenten (compleet)

Nieuwe lijst, vervangt de 7 uit `MORGEN_AANPAK.md`. Totaal 9 + 2 voorab = 11, maar kort.

### Voorab — al beslist door Jolanda (6 nov ochtend)

- ✅ **0a**: bestaande repo, branch `bouwplan-v2`
- ✅ **0b**: `web/face.html` hergebruiken, aanpassen voor 7 nieuwe toestanden

### Tijdens de bouwdag

🔔 **Beslismoment 2** (bouwstap 2, ±10:30): 5 PNG-bonnen OK (percentage-notatie, quote-selectie, prijs-plakking)?
🔔 **Beslismoment 4** (bouwstap 5, ±11:30): brain.py 10 testvoorbeelden — JSON-output natuurlijk?
🔔 **Beslismoment 3** (bouwstap 4, ±12:00): droogloop-gesprekken — voelen de zinnen als Anna? Wake-ack kort?
🔔 **Beslismoment 1** (bouwstap 1, ±13:15): printer-plan B als Bluetooth faalt?
🔔 **Beslismoment 5** (bouwstap 6, ±14:00): rendered audio vs live TTS — één stem of twee?
🔔 **Beslismoment 6** (bouwstap 7, ±14:45): spreekplek-marge 30°, wake-fuzzy ruim of strak?
🔔 **Beslismoment 7** (bouwstap 8, ±15:30): 7 state-screens — welke onduidelijk?
🔔 **Beslismoment 8** (bouwstap 9, ±16:15): groepstest-drempels OK?
🔔 **Beslismoment 9** (bouwstap 10, ±17:00): expositie-go?

**Totaal Jolanda-tijd aan beslissingen**: ~70 min over de hele dag.

### Camera-voorbereiding (nieuwe hardware-stap)

Camera is aangesloten (Arducam OV5647 via CSI, 6 nov ochtend).

Vóór bouwstap 7: `ssh annanova 'rpicam-hello --list-cameras'` → bevestigt detectie. `ssh annanova 'rpicam-still -o /tmp/cam-test.jpg'` → test foto (NB: dit tijdelijke bestand wordt direct weggegooid — geen persistentie, past bij privacy-principe).

Hailo-8L: SCRFD-HEF nog niet gedownload. In aangepaste `install.sh` toevoegen: `curl -L -o models/scrfd_2_5g.hef …`. `anna/see.py` gebruikt de HEF via de Hailo HailoRT-API om face-count te doen (nodig voor DRUK-detectie en "1 persoon op plek"-bevestiging).

---

## Risico's en afspraken

**Wat als Mistral trage dag heeft?** Elke call heeft 4s timeout → brugzin "Daar denk ik nog over na. Volgende halte." + `soort=antwoord`. Hooguit 1–2 keer per gesprek merkbaar.

**Wat als Voxtral-TTS tegoed op is?** Render-fase valt terug op Piper offline → alle vaste zinnen klinken dan als Piper. Live-TTS blijft Piper. Minder stem-variatie, maar werkt zonder internet.

**Wat als printer faalt op expositie-dag?** `anna/printer.py` cascade: mini → ESC/POS → PNG opslaan + Anna zegt `geenprint`. Bezoeker loopt dan weg met verhaal ipv papier — ook OK als noodplan.

**Wat als de Pi crasht?** Hardware-watchdog in bouwstap 10. systemd auto-restart. Read-only overlay voorkomt SD-corruptie.

**Wat als Jolanda zegt "stop, dit werkt niet voor mij" bij beslismoment 3?** We zijn nog pre-hardware-integratie. Rollback: terug naar `main`, fine-tunen oude Anna (mode fall-back naar MORGEN_AANPAK v4). Afhankelijk van moment nog 4–5u beschikbaar.

**Wat als Pi wifi uitvalt?** Alle offline delen (droogloop, bon-rendering, speak Piper, hear via Whisper tiny) draaien door. Brain.py en Voxtral vallen weg → Anna zegt alleen brugzin. Minder goed, maar niet stuk. Als wifi weg blijft: knopmodus met alleen vaste zinnen = gereduceerd kunstwerk, nog steeds werkbaar.

---

## Afspraken met Claude Code (ik)

Uit bron 2 overgenomen, niet-onderhandelbaar:

- Geen gesprekstekst / audio / beelden naar schijf, ook niet voor debug
- Geen eigen quotes of vragen verzinnen in `inhoud.json` (alleen placeholders met `goedgekeurd:null`)
- Geen extra services, databases, webservers — behalve de websocket voor het scherm
- Bij twijfel over een keuze die het kunstwerk raakt: **stoppen en Jolanda vragen**

Toegevoegd:

- Vandaag committen we minstens om de uur naar branch `bouwplan-v2`
- Elk afgerond bouwstap: aparte commit met test-resultaat in de message
- Ik doe geen `git push --force` en ik merge niet naar `main` zonder beslismoment 9

---

## Wat na vandaag

- Als beslismoment 9 = ja: merge `bouwplan-v2` → `main`, tag `v2.0-expositie`, maak SD-image.
- Als beslismoment 9 = niet helemaal: branch blijft open, oude `main` draait op Pi, we vervolgen zaterdagochtend met concrete fix-lijst.

Einde document. Zie `TESTPLAN_V2.md` voor de tests per bouwstap.
