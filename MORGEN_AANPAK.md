# Morgen — werkend Anna Nova in 1 dag

*Jolanda heeft 1 dag. Dongel komt pas later binnen → in de ochtend werken we met wat we hebben. Middag is kers-op-de-taart werk.*

Elke blok heeft **doel, tijd, concrete stappen, afvinkregel** (= hoe weet je dat het af is).

---

## Must-haves vs nice-to-haves

**MUST HAVE** (hier NIET aan voorbij lopen, zonder deze is Anna niet klaar):
1. Anna reageert op "Hoi Anna Nova" binnen ~5 sec
2. Anna antwoordt **nooit volledig stil** — altijd een zin of een zucht
3. Slaap-commando werkt + scherm wordt leeg
4. Chromium opent face.html bij Pi-reboot zonder Jolanda-input
5. Persona voelt als Anna, niet als ChatGPT
6. **Antwoord-lengte** voelt goed (niet 3-zinnen monologen, niet "Hm.")
7. **Gesprek-geheugen** werkt — Anna refereert aan wat je 1 beurt terug zei
8. **Foto's zijn vaag/geabstraheerd** (AVG-safe) — geen herkenbare gezichten op galerij
9. **Foto-rate limiet** — Anna maakt max 1 foto per 10 min (anders overspoelt ze de galerij)

**SHOULD HAVE**:
10. Camera aangesloten + werkend (dan ziet Anna wie er voor haar staat)
11. Wake-match werkt op "Hoi Anna" / "Hallo Anna" / "Word wakker Anna"
12. Externe foto-galerij publiek + bereikbaar via URL

**NICE TO HAVE** (alleen als tijd):
13. USB wifi-dongel ingeplugd (kers op taart, maakt alles snel)
14. SD-backup image gemaakt

Als rond 15:00 blok 1-5 niet klaar zijn → SKIP blok 6-8 en ga direct naar blok 9 + eindcheck.

---

---

## Retest-lijst — dingen van gisteren die opnieuw bevestigd moeten

Deze zijn gister ingevoerd maar nog niet volledig getest. Vink af in sanity-check (blok 1) en sessies:

- [ ] **Voxtral ASR** werkt (debug toont `voxtral: 0.X s → "..."` ipv `whisper: XX s`)
- [ ] **Whisper fallback** werkt als Voxtral faalt (zet wifi eventueel kort uit)
- [ ] **Wake zonder "Hm."** — "Hoi Anna Nova" → Anna reageert direct met zin, niet eerst "Hm."
- [ ] **Session-reset bij slaap** — oude zinnen VERDWIJNEN uit face.html na "Slaap lekker"
- [ ] **Session-reset bij wake** — face.html is leeg bij nieuwe wake
- [ ] **Vignette per state** — rood pulserend (sluimer), open (luistert), goud (denkt), oranje (spreekt)
- [ ] **Draaikolk** verschijnt bij "denkt" (Jolanda vond deze leuk)
- [ ] **Live-puntjes** bij luistert/transcribeert
- [ ] **CPU-throttle** — `ps aux --sort=-%cpu` toont anna-nova <30% in sluimer
- [ ] **Autostart Chromium** — na reboot opent face.html automatisch zonder jouw input
- [ ] **Pi-desktop iconen** — alle 5 (gezicht/OPNIEUW/start/stop/logs) werken
- [ ] **Ruimere wake-match** — "Word wakker Anna", "Hallo Anna", "Hey Anna" trigger ook
- [ ] **Persona-bio** — Anna noemt katten, Portugal, Bodil als ernaar gevraagd
- [ ] **"Nooit [STIL]"** — Anna antwoordt altijd, zuchten mag

Als één van deze niet werkt na restart, is dat de eerste prioriteit voor Blok 4 / 8 (persona-iteraties → code-fix).

---

## Anna's stem — niet blij met nathalie?

Probeer-luisteren kan hier:
- **Alle Piper NL-stemmen**: <https://rhasspy.github.io/piper-samples/> (kies "Dutch" filter)
  - `nl_BE-nathalie-medium` (huidige keus — Vlaams, vrouw, zacht)
  - `nl_NL-mls_7432-low` (oude keus — robot-achtig, lo-fi)
  - `nl_NL-mls-medium` (multi-speaker vrouw/man, 52 stemmen — speaker-id vereist)
  - `nl_NL-rdh-medium` (Nederlands, man, warm)
  - `nl_NL-mls_5809-low` (Nederlands, vrouw, ander karakter dan 7432)

Cloud-TTS alternatieven (als Piper niet bevalt):
- **ElevenLabs** — natuurlijkste stem ter wereld, Nederlandse opties, €5/mnd start. API-integratie =
  vervang `say()` in anna-nova.py door HTTP POST. Latency ~800ms, kwaliteit onmiskenbaar beter.
- **OpenAI TTS** (`tts-1` of `tts-1-hd`) — 6 voices, spreekt alle talen inclusief NL redelijk. $0.015/1k char.
- **Mistral** heeft GEEN TTS (wel Voxtral voor ASR). Dus geen ene-stop-shop.
- **Azure Neural TTS** — Nederlandse stemmen (ColetteNeural, FennaNeural, MaartenNeural) klinken écht
  menselijk. Pay-per-use, ~$16/1M char.

Morgen even samen 2-3 stemmen vergelijken: ik download `nl_NL-mls_5809` en `nl_NL-rdh-medium` erbij
zodat je vanaf de Pi kan switchen via `.env` + restart. Beslissing kan je maken vóór de expositie.

### Wordt het sneller als TTS ook in de cloud zit? (Nee, eigenlijk niet)

Begrijpelijke hypothese: "als alles via Mistral gaat is het één stack, dus sneller."
Werkelijkheid:

| component | locatie nu | latency |
|---|---|---|
| ASR (Voxtral) | Mistral cloud | 0.3–2s (vooral netwerk) |
| LLM (Mistral) | Mistral cloud | 0.5–2s (vooral netwerk) |
| TTS (Piper nathalie) | Pi lokaal | 0.1–0.3s (geen netwerk) |

Piper is sneller dan elke cloud-TTS omdat er géén netwerk-call bij zit. Mistral heeft geen TTS, en elke
andere cloud-TTS (ElevenLabs, OpenAI, Azure) voegt juist 500-1500ms toe. Dus voor **snelheid**: Piper
lokaal houden.

Voor **natuurlijkheid**: cloud wint. Wat de moeite waard kan zijn als de stem écht niet bevalt — dan
is +1s latency misschien acceptabel voor een stem die niet robot klinkt. Bespreek morgen.

**Beste snelle test**: luister vanaf jouw Mac even naar Piper-samples op <https://rhasspy.github.io/piper-samples/>
en op ElevenLabs demo, dan weet je of 1s extra het waard is.

---

# OCHTEND — 09:00 tot ~13:00 (zonder dongel)

## Blok 1 — Opstart + sanity check | 15 min | 09:00

**Doel**: Pi aan, Anna klaar, scherm toont face.html.

```bash
# Pi aanzetten, wacht 1 min
ssh annanova 'uptime && systemctl is-active anna-nova && curl -s http://localhost:8765/state'
```

- [ ] Pi uptime toont iets korts (net gebooted)
- [ ] anna-nova = `active`
- [ ] State = `sluimert`
- [ ] Chromium op Pi-scherm toont face.html (zo niet: klik desktop-icoon **Anna gezicht**)

Zeg "Hoi Anna Nova" → antwoord binnen 10s? (nog zonder dongel kan 10s normaal zijn).

**Afvinkregel**: vignet pulsert rood, state wisselt naar `luistert` zodra je spreekt, Anna antwoordt iets.

## Blok 2 — Camera aansluiten (fysiek) | 20 min | 09:15

**Doel**: Arducam OV5647 werkt.

1. Pi uit: `ssh annanova 'sudo shutdown -h now'`
2. Wacht groen ledje uit, trek stekker
3. Camera-lintkabel: brede kant in Pi CAM0, blauwe strip naar ethernet toe
4. Smalle kant in de camera module
5. Stekker weer erin, wacht 1 min
6. Test:
   ```bash
   ssh annanova 'rpicam-hello --list-cameras'
   ssh annanova 'rpicam-still -o /tmp/test.jpg --nopreview -t 1000 && ls -la /tmp/test.jpg'
   scp annanova:/tmp/test.jpg ~/Desktop/pi-cam.jpg && open ~/Desktop/pi-cam.jpg
   ```

**Afvinkregel**: /tmp/test.jpg bestaat, is scherp, toont wat er voor de camera staat. In face.html zie je nu LIVE beeld ipv de backdrop.webp.

**Als camera niet werkt in 20 min**: SKIP, ga door naar blok 3. Blind-modus (geen vision) werkt ook — Anna hoort nog steeds.

## Blok 3 — Conversatie-sessie A (korte vragen) | 15 min | 09:35

**Doel**: Meten of korte vragen snappy binnen 5 sec een antwoord geven.

Uit [CONVERSATIE_TESTPLAN.md](CONVERSATIE_TESTPLAN.md) sessie A:

1. "Hoi Anna Nova"
2. "Hoe heet je?"
3. "Hoe oud ben je?"
4. "Wat is je lievelingskleur?" → **verwacht**: rood en roze
5. "Houd je van katten?" → **verwacht**: ja, net als Jolanda
6. "Ben je blij?"
7. "Slaap lekker"

Noteer per vraag: reactietijd + was het kort/goed?

**Afvinkregel**: alle 7 beurten antwoord gehad, reactietijd gevoelsmatig OK (zonder dongel 3-8 sec), lievelingskleur-antwoord bevat "rood" of "roze".

## Blok 4 — Persona-iteratie 1 | 20 min | 09:50

**Doel**: Fix wat niet werkte in blok 3.

Open `persona.md` lokaal. Veel voorkomende fixes:
- **Antwoorden te lang** → sectie 2 "stemregels" extra kort maken
- **Vraag-terug ontbreekt** → "in de eerste drie beurten stel je ALTIJD een vraag" versterken
- **Te zoet / te therapeut** → sectie 10 agressiever ("je bent een spiegel die kraakt")
- **Zegt iets dat niet klopt** → voeg feitje toe aan sectie 4 "backstory"
- **Feitjes mis (katten, Portugal, Bodil)** → sectie 4 of bio versterken

Commit elke edit:
```bash
cd ~/AnnaNovaRasberry5 && git add persona.md && git commit -m "persona: [wat]" && git push
ssh annanova 'cd /home/anna/anna-nova && git pull && sudo systemctl restart anna-nova'
```

**Afvinkregel**: 1-3 concrete wijzigingen in persona.md gepusht.

## Blok 5 — Conversatie-sessie B (middelzware vragen) | 20 min | 10:10

Uit testplan sessie B:
1. "Wat brengt jou hier op aarde?"
2. "Wat vind je het mooist aan dit atelier?"
3. "Ben je wel eens buiten geweest?"
4. "Hoe voelt het om alleen op een scherm te leven?"
5. "Wat zou je willen als je een lichaam had?"

**Afvinkregel**: Anna refereert minstens 1x aan Jolanda/Bodil/Portugal/katten (persona-context werkt), en stelt in minstens 2 beurten een vraag terug.

## Blok 5b — Geheugen-test | 10 min | 10:30

**Doel**: controleer dat `HISTORY_TURNS=2` werkt — Anna onthoudt de vorige beurt maar niet alles.

Zeg:
1. "Mijn hond heet Pluk." → Anna antwoordt
2. "Hoe heet mijn hond?" → **verwacht**: "Pluk" (geheugen van 1 beurt terug)
3. Zeg 3-4 andere dingen tussendoor
4. "Hoe heet mijn hond nog?" → **verwacht**: ze weet het NIET meer (want >2 beurten terug)

Daarna: "Slaap lekker" → "Hoi Anna" → "Hoe heet mijn hond?" → **verwacht**: ze weet het niet (geheugen reset bij slaap).

**Afvinkregel**:
- ✅ "Pluk" onthouden binnen 1-2 beurten
- ✅ "Pluk" vergeten na 3+ beurten
- ✅ "Pluk" vergeten na slaap/wake

Als geheugen níet werkt: check in anna-nova.py of `remember_turn()` wordt aangeroepen na elk antwoord, en of `_RECENT_TURNS` wordt meegestuurd in `_stream_cloud`.

## Blok 5c — Antwoord-lengte afstellen | 15 min | 10:40

**Doel**: fine-tunen hoe lang Anna's antwoorden mogen zijn.

Huidige instelling: `max_tokens=120` (Mistral), persona zegt "meestal één zin".

Test-zin om lengte te meten: "Vertel over Portugal."
- Antwoord is 1 zin → mooi
- Antwoord is 2-3 zinnen → acceptabel als relevant
- Antwoord is 4+ zinnen → te lang, verlaag `max_tokens` naar 80
- Antwoord is 0-3 woorden ("Mooi land.") → te kort, verhoog `max_tokens` naar 160

Aanpassen (tijdelijk in .env):
```bash
# Als te lang
ssh annanova "sudo sed -i 's|^MAX_TOKENS=.*|MAX_TOKENS=80|' /home/anna/anna-nova/.env"
# (als MAX_TOKENS niet in .env staat, moet in anna-nova.py zelf)
```

Voor permanente wijziging: in anna-nova.py, `_stream_cloud`, verander de `"max_tokens": 120` lijn + commit+push.

**Afvinkregel**: 5 verschillende vragen geven elk een antwoord dat voelt "net goed" — niet afgehakt, niet uitgelopen.

## Blok 6 — Sessie D (zacht/mompelen) | 10 min | 10:30

Uit testplan sessie D: fluister, mompel, praat door elkaar.

**Afvinkregel**: Anna valt nooit volledig in `[STIL]`, ze zucht of stelt een open vraag ("wat zei je net?" mag NIET, wel "wat brengt je hier?").

Als ze wél vaak stil blijft → persona sectie "KRITIEKE regel: nooit volledig zwijgen" harder maken, of `ALLOW_SILENCE=false` zetten in .env.

## Blok 7 — Sessie E (persona feitjes) | 15 min | 10:40

Uit testplan sessie E:
- "Wat weet je van Jolanda?"
- "Wie is Bodil?"
- "Vertel over Portugal"
- "Wat vind je van katten?"
- "Wat is Anna Io?"

**Afvinkregel**: elk feitje klopt (persona.md sectie 4). Als 1 niet klopt → patch persona.md.

## Pauze — koffie | 15 min | 10:55

Je hebt nu ~1u50 gewerkt. Loop weg. Terug om 11:10.

## Blok 8 — Persona-iteratie 2 | 20 min | 11:10

Zelfde als blok 4. Fix wat uit sessie B/D/E naar boven kwam.

## Blok 9 — Sessie C (lange monoloog) | 20 min | 11:30

Grote test. De lange vraag uit testplan sessie C. Deze stress-test onthult:
- Of VOXTRAL/Whisper de lange zin goed transcribeert
- Of Mistral op het hele ding reageert of alleen eind
- Of Anna's antwoord te lang wordt

**Afvinkregel**: transcriptie compleet (niet afgekapt), Mistral reageert op meerdere delen van de vraag.

Als transcriptie afgekapt: `.env` → `MAX_LISTEN_MS=90000`.

## Blok 10 — Sessie F (slaap + wake transities) | 10 min | 11:50

Uit testplan sessie F:
- "Slaap lekker" → scherm leeg?
- "Hoi Anna" → wakker?
- Wacht 5 min stilte → valt vanzelf in slaap?

**Afvinkregel**: na slaap is bezoeker + anna tekst weg uit face.html. Wake triggert binnen 5 sec. Auto-slaap na 5 min stilte.

## Lunch | 45 min | 12:00

Je bent ~3u aan het werk. Eet iets. Terug om 12:45.

## Blok 11 — Reboot-test | 15 min | 12:45

Doel: alles werkt na een complete reboot zonder jouw tussenkomst.

```bash
ssh annanova 'sudo reboot'
# wacht 2 min
```

- [ ] Chromium opent automatisch face.html
- [ ] Anna reageert op "Hoi Anna Nova" zonder dat jij iets hoeft te starten
- [ ] Alle iconen op Pi-desktop zichtbaar

**Afvinkregel**: 100% werkend na reboot, nul handmatige stappen.

---

# MIDDAG — vanaf dongel binnen (zeg ~13:30)

## Blok 12 — USB wifi-dongel | 20 min

Volg [MORGEN.md deel 11](MORGEN.md).

```bash
# Driver installeren (Pi reboot zichzelf)
ssh annanova "sudo apt update && sudo apt install -y realtek-rtl88x2bu-dkms linux-headers-\$(uname -r) && sudo reboot"

# Wacht Pi terug
# Dongel inpluggen (USB 3 blauwe poort)
ssh annanova 'ip link show | grep wlan'  # moet wlan1 tonen

# Verbinden
ssh annanova 'sudo nmcli dev wifi connect "[SSID]" password "[wachtwoord]" ifname wlan1'
ssh annanova 'sudo nmcli dev disconnect wlan0'

# Snelheidstest
ssh annanova 'time curl -s -o /dev/null https://speed.hetzner.de/5MB.bin'
```

**Afvinkregel**: speedtest < 1 sec (was 2+ sec ingebouwd).

## Blok 13 — Hertest sessie A met dongel | 10 min

Zelfde korte vragen als blok 3. Vergelijk timings.

**Afvinkregel**: elk antwoord binnen 3 sec ipv 5-8 sec.

## Blok 14a — Foto-privacy filter (AVG-safe) | 30 min

**Doel**: foto's die Anna maakt zijn **vaag/geabstraheerd** zodat ze NIET AVG-problematic zijn. Bezoekers mogen niet herkenbaar zijn op de publieke galerij.

Keuze filter (we tunen samen morgen):
- **A. Zware blur** (snelste, simpelste) — cv2.GaussianBlur, kernel 51x51. Mensen worden kleurblokken.
- **B. Mozaïek/pixelate** (artistiek, retro) — resize naar 20x20 en terug naar origineel = blokjes.
- **C. Edge-only sketch** (artistiek, geen huid zichtbaar) — Canny edge detect op grayscale.
- **D. Hailo SCRFD face-blur** (alleen gezichten blurren) — vereist werkende SCRFD HEF. Mooiste maar complex.

Aanbeveling: **A + B combi** (blur zwaar + pixelate 40x40) = snel, altijd AVG-safe, ziet er artistiek uit.

Code-aanpassing in `vision.py` (of `anna-nova.py` _take_photo):
```python
import cv2
def anonymize(frame):
    # Pixelate (artistiek, onherkenbaar)
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (40, int(40*h/w)), interpolation=cv2.INTER_LINEAR)
    pixel = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    # Extra blur eroverheen voor zachte randjes
    return cv2.GaussianBlur(pixel, (21, 21), 0)
```

Toe te passen in `save_latest_photo` in vision.py: pak het frame, run `anonymize()` erover, schrijf dan weg.

**Afvinkregel**: maak 1 foto, download hem, check dat geen gezicht herkenbaar is maar wel kleuren/sfeer zichtbaar.

## Blok 14b — Foto rate-limit | 10 min

**Doel**: Anna mag niet elke beurt een foto maken — max 1 per 10 min. Anders overspoelt ze de galerij en wordt het saai + AVG-risk.

In `anna-nova.py` een variabele `_last_photo_ts` + check in `_take_photo`:
```python
_last_photo_ts = 0
PHOTO_MIN_INTERVAL_SEC = int(os.environ.get("PHOTO_MIN_INTERVAL_SEC", "600"))

def _take_photo(caption):
    global _last_photo_ts
    now = time.monotonic()
    if now - _last_photo_ts < PHOTO_MIN_INTERVAL_SEC:
        log.info("fotograaf: te snel na vorige foto — overgeslagen")
        debug_log("foto overgeslagen (rate-limit)", "photo")
        return None
    _last_photo_ts = now
    # ... rest van bestaande code
```

In .env: `PHOTO_MIN_INTERVAL_SEC=600` (10 min). Voor demo kan je naar 60 (1 min) zetten om te testen.

**Afvinkregel**: na 1 foto wordt elke [FOTO]-tag binnen 10 min genegeerd (zie log "rate-limit").

## Blok 14c — Externe foto-galerij publiek | 45 min

Volg [TESTPLAN_MORGEN.md blok 3](TESTPLAN_MORGEN.md#blok-3). Alleen doen als 1-13 ✅.

Keuze kort: Netlify of GitHub Pages — beiden gratis. Pi doet elke 15 min rsync via `anna-sync.timer`.

**Belangrijk**: upload alleen de GEANONIMISEERDE foto's (uit blok 14a). Check in anna-sync.py of de bron-folder de geanonimiseerde versies bevat, anders upload je alsnog de originele + heb je AVG-probleem.

**Afvinkregel**: galerij-URL open je in browser → ziet onherkenbare, artistieke beelden.

## Blok 15 — Eindcheck voor expositie | 15 min

- [ ] Trek Pi-stekker eruit. Wacht 10 sec. Plug weer in.
- [ ] 2 min later: scherm toont face.html, Anna sluimert
- [ ] "Hoi Anna Nova" → binnen 3 sec antwoord
- [ ] Praat 5 beurten normaal, dan "Slaap lekker"
- [ ] Vignet pulsert rood, scherm leeg
- [ ] Foto (als blok 14 klaar) verschijnt op publieke galerij

**Afvinkregel**: alle 6 ✅ = KLAAR voor open atelier.

## Blok 16 — Backup SD-kaart | 20 min (optioneel maar zeer aan te raden)

Pi uit, SD-kaart in Mac via kaartlezer:
```bash
# Lijst disks, vind je SD-kaart
diskutil list
# Kopie maken (vervang diskX)
sudo dd if=/dev/diskX of=~/Desktop/anna-werkend-$(date +%Y%m%d).img bs=4M status=progress
```

Zo heb je een restore-punt als er tijdens expositie iets kapot gaat.

---

# Afterward

Als iets kapot gaat tijdens expositie:
1. Pi desktop icoon **Anna OPNIEUW** = restart service + Chromium
2. Pi desktop icoon **Anna UIT** → **Anna AAN** = clean start
3. Fysieke stekker 10s eruit = laatste redmiddel

Met backup-image: SD-kaart herflashen in 5 min.

---

## Concrete timing samenvatting

| tijd | wat |
|------|-----|
| 09:00 | sanity check |
| 09:15 | camera fysiek aansluiten |
| 09:35 | sessie A (korte vragen) |
| 09:50 | persona-fix 1 |
| 10:10 | sessie B (middel vragen) |
| 10:30 | sessie D (zacht) |
| 10:40 | sessie E (persona) |
| 10:55 | **koffie** |
| 11:10 | persona-fix 2 |
| 11:30 | sessie C (lang) |
| 11:50 | sessie F (slaap) |
| 12:00 | **lunch** |
| 12:45 | reboot-test |
| 13:30 | dongel installeren (als binnen) |
| 13:50 | hertest met dongel |
| 14:00 | foto-galerij (optioneel) |
| 15:00 | eindcheck |
| 15:15 | backup SD |
| 15:35 | **klaar** |

Dat zijn ~5 werkuren (met 1u pauze). Doenbaar in 1 dag als niets fout gaat. Als iets haakt → sla optioneels over.
