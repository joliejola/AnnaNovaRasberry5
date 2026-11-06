# Morgen 7 nov — plan van aanpak + testplan

*Doel: Anna spreekt met nieuwe stem, printer werkt, nieuwe dialoog zit erin, 3 bezoekers hebben getest.*

---

## Status — wat is al klaar (6 nov avond)

- ✅ **Stem gekozen** — ElevenLabs voice-ID `o4g7vs6IQ4oCQwuS7wi7`, sample goedgekeurd
- ✅ **API-keys lokaal** — `ELEVENLABS_API_KEY` + `MISTRAL_API_KEY` in `/tmp/anna-bons/.env` op Mac (niet in git)
- ✅ **`anna/speak.py` live** — commit `8257c85`, ElevenLabs stream → mpg123, Piper fallback
- ✅ **`pi-setup-extras.sh`** — installeert mpg123 via apt
- ✅ **Wake-detect** — Vosk NL-small, "Hoi Anna Nova" werkt (getest 6 nov)
- ✅ **Scherm-states** — sluimert/luistert/denkt/spreekt kleuren + animaties (demo op `web/achtergrond-demo.html?demo=1`)
- ✅ **Bon-layout** — Pillow PNG, B&W logo, zonder "jouw aandeel"
- ✅ **Printer-guide** — `docs/voorbereiding/PRINTER_SETUP.md` compleet, bouwstap 1-6

## Wat Jolanda vanavond thuis doet

**1. Dialoog** → `content/inhoud.json` ([bouwplan-v2 branch](https://github.com/joliejola/AnnaNovaRasberry5/blob/bouwplan-v2/content/inhoud.json))
- `openingen`, `reeks[]` (5 vragen), `wachtzinnen`, `situaties{}`, `afsluiting`, `slotzinnen`
- `quotes[]` → zet `goedgekeurd: true` bij versies die je wil toelaten

Commit + push naar `bouwplan-v2` als je klaar bent.

---

## Morgen 7 nov — timeline

### 09:00 — Pi klaarzetten (15 min)

```bash
cd ~/anna-nova
git pull origin bouwplan-v2
bash scripts/pi-setup-extras.sh       # installeert mpg123
```

Dan `.env` op de Pi aanvullen (keys staan in `/tmp/anna-bons/.env` op Mac):
```
TTS_MODE=elevenlabs
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_VOICE_ID=o4g7vs6IQ4oCQwuS7wi7
MISTRAL_API_KEY=mstrl_...
```

### 09:15 — Stem live-test op Pi (15 min)

```bash
cd ~/anna-nova && source .venv/bin/activate
python -c "from anna.speak import say; import os; os.environ['DROOGLOOP']='0'; say('Hoi. Ik ben Anna Nova.')"
```
**Verwacht:** ElevenLabs-stem uit de boxjes binnen ~1 s. Als Piper klinkt → `.env` niet geladen.

### 09:30 — Bouwstap 1: printer live (1 uur timebox)

Volg `docs/voorbereiding/PRINTER_SETUP.md`:
- [ ] BlueZ actief
- [ ] `bluetoothctl` → pair + trust → MAC in `.env` als `PRINTER_MAC=...`
- [ ] TiMini-Print clone + venv
- [ ] Testregel print
- [ ] Lineaal-PNG → `PRINT_BREEDTE_PX=384|576`
- [ ] Echte bon via `anna.bon.render_bon()` + `anna.printer.print_bon_png()`

**Als pairen na 30 min nog niet lukt → stop**, bestel USB ESC/POS fallback, ga door met rest.

### 10:30 — Nieuwe dialoog laden (15 min)

```bash
git pull origin bouwplan-v2    # haalt Jolanda's inhoud.json op
```

Snelle droogloop:
```bash
DROOGLOOP=1 .venv/bin/python -m anna.main
```
Tik antwoorden in, check dat alle 5 vragen + `elk`-reacties werken. Zie je `???` of een lege zin → `inhoud.json` aanpassen.

### 10:45 — Full stack test (echte hardware, 1 uur)

Zie **Testplan** hieronder. Alles doorlopen. Elk falend ✗ item = fix of noteer.

### 12:00 — Lunch + fixes

Werk de defects van 10:45 weg.

### 13:00 — Style-ronde (30 min)

- Scherm-states check op echte display — kleuren te hard/zacht?
- Hint-tekst in cel — grootte?
- Bon-layout — wit genoeg marge?
- Georgia italic hint — vervangen?

### 13:30 — 3 echte bezoekers droogloop

3 mensen (vriend, buur, toevallige) die Anna nog niet kennen. Geen uitleg vooraf.

Observeer per persoon:
- [ ] Vindt wake-woord uit zichzelf?
- [ ] Antwoordt op vragen of loopt weg?
- [ ] Leest het bonnetje?
- [ ] Opmerking uit zichzelf? (positief/negatief)
- [ ] Zou opnieuw willen?

Noteer, pas `inhoud.json` aan waar nodig, commit.

### 15:00 — Buffer / nice-to-have

- Camera-lintkabel aandrukken als `/frame.jpg` nog leeg (pose-overlay)
- Nachtmodus / kiosk-resolutie
- Eventuele vragen-tweaks na bezoekerstest

### 16:00 — Dag klaar / rust

---

## Testplan — acceptatiecriteria

Anna is "klaar voor publiek" als **alle 15 testen** slagen.

### A. Stem (ElevenLabs)

| # | Test | Verwacht |
|---|---|---|
| A1 | `.env` TTS_MODE=elevenlabs + key gezet, `say("hallo")` | ElevenLabs-stem, geen Piper |
| A2 | Netwerk uitzetten + `say("hallo")` | Piper fallback, geen crash |
| A3 | Latency van wake tot eerste klank van opening | < 2 s |

### B. Brein (Mistral)

| # | Test | Verwacht |
|---|---|---|
| B1 | `MISTRAL_API_KEY` gezet, bezoeker zegt iets off-topic | JSON-reactie met "soort"+"reactie", < 3 s |
| B2 | Mistral key leegmaken, vraag stellen | Situatie `fout` ("Ik hapte even…") |

### C. Wake / slaap

| # | Test | Verwacht |
|---|---|---|
| C1 | "Hoi Anna Nova" op 2 m afstand | Binnen 2 s opening-zin |
| C2 | "Slaap lekker" | Terug naar `state-sluimert` binnen 3 s |
| C3 | 10 s stil tijdens vraag | Situatie `ruis` ("Nog een keer, langzaam?") |

### D. Vragen-reeks

| # | Test | Verwacht |
|---|---|---|
| D1 | Vraag 1 "Ja" | "Snel. Dat zeggen ze allemaal." |
| D2 | Vraag 1 "Nee" | "Verstandig. Laten we toch kennismaken." |
| D3 | Vraag 1 "Misschien" | "Twijfel is gezond. Ik heb het niet." |
| D4 | Vraag 1-5 "Pas" | Elke keer situatie `pas`, geen vastloper |
| D5 | 5 vragen in gewoon tempo | Flow klaar binnen 3 min, geen hangen |

### E. Printer

| # | Test | Verwacht |
|---|---|---|
| E1 | Afsluiting "Ja" → bon print | Binnen 8 s uit printertje met quote + prijs + URL + datum |
| E2 | Printer uit → afsluiting | Situatie `geenprint` ("Mijn printer is op…"), geen crash |
| E3 | Lezen — alle tekst scherp? | Geen afgekapte rand |

### F. Privacy

| # | Check | Verwacht |
|---|---|---|
| F1 | `ls audio/` na 5 bezoekers | Geen nieuwe files (alleen vooraf gerenderd) |
| F2 | Journal: `journalctl -u anna-nova \| grep -iE "zei\|tekst"` | Geen gesprekstekst in logs |
| F3 | WebSocket `:8766` sniff | Alleen `stippen` + `pose` keypoints, geen beeld |
| F4 | `git status` + `cat .env` | `.env` niet getrackt, keys alleen in `.env` |

**Scherm-states zichtbaar tijdens flow:**
- `state-sluimert` (rood, trage puls) — bij wachten
- `state-luistert` (mint, rustig) — bij mic-opname
- `state-denkt` (goud, draaien) — bij Mistral-call
- `state-spreekt` (oranje, snelle puls) — bij TTS

---

## Fallbacks (als iets niet werkt)

| Systeem valt uit | Fallback | Wat merkt bezoeker? |
|---|---|---|
| Netwerk | Piper lokaal + brain uit (hardcoded reacties) | Minder mooie stem, geen vraag-afwijking opvangen |
| Printer | Situatie `geenprint` | "Mijn printer is op. Je krijgt hem in gedachten." |
| Camera | Pose-overlay leeg, alleen stippen | Scherm werkt nog, geen pose-reactie |
| Mic (totaal) | Knopmodus (zie `state-knopmodus`) | Druk op knop ipv spreken (nice-to-have, nog niet gebouwd) |
| Mistral | Situatie `fout` | "Ik hapte even. Ik ben met de hand gemaakt." |

---

## Nog open voor Jolanda vanavond

1. `content/inhoud.json` uitwerken + commit
2. (Optioneel) stability/similarity-waarden kiezen in ElevenLabs — zeg maar, standaard is 0.5 / 0.75
