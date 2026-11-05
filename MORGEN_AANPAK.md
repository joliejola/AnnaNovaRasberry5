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

**SHOULD HAVE**:
6. Camera aangesloten + werkend (dan ziet Anna wie er voor haar staat)
7. Wake-match werkt op "Hoi Anna" / "Hallo Anna" / "Word wakker Anna"

**NICE TO HAVE** (alleen als tijd):
8. Externe foto-galerij publiek
9. USB wifi-dongel ingeplugd (kers op taart, maakt alles snel)

Als rond 15:00 blok 1-5 niet klaar zijn → SKIP blok 6-8 en ga direct naar blok 9 + eindcheck.

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

## Blok 14 — Externe foto-galerij (optioneel, als tijd) | 1 uur

Volg [TESTPLAN_MORGEN.md blok 3](TESTPLAN_MORGEN.md#blok-3). Alleen doen als blokken 1-13 ✅ zijn en je nog tijd/energie hebt.

Keuze kort: Netlify/GitHub Pages gratis. Pi doet elke 15 min rsync.

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
