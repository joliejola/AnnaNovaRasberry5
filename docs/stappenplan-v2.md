# Anna Nova 2.0 — stappenplan v2

*2 nov 2026 · Jolanda · Pi 5 + AI HAT+ 13 TOPS (Hailo-8L) + Arducam OV5647 CS-mount*

Vervangt v1. Zelfde skelet, maar nu met drie keuzes gemaakt: **be-more-agent als basis**, **lokaal brein (Phi-3 Mini via Ollama) met cloud-switch achter de hand**, en **een slaapcyclus die elke nacht vergeet**.

---

## Backbone (waarom dit werk)

Drie verhalen die onder al het praktische werk hangen. Dit staat bovenaan omdat de techniek anders de kunst gaat sturen in plaats van andersom.

**Stella nova.** De OV5647 is een sensor uit 2013. Een nova is astronomisch geen nieuwe ster — het is een bestaande ster, vaak een witte dwerg, die plotseling opvlamt door een explosie aan zijn oppervlakte (Tycho Brahe, *De Nova Stella*, 1573). Anna Nova is precies dat: oud oog, nieuwe helderheid. De verwisselbare CS-mount is de letterlijke uitwerking — elke nieuwe lens is een nieuwe prior, een nieuwe wereld die ontbrandt. Theorie-anker: Memo Akten's *Learning to See* ("what we see is a reconstruction based on our expectations and prior beliefs").

**Ze ziet hier en denkt hier.** Vision op de Hailo, taalmodel lokaal op dezelfde Pi, geheugen in een SQLite ernaast — Anna's hele binnenwereld zit in één kast. Dat is zeldzaam: de meeste AI-companions leunen op de cloud. Haar beperking is óók haar eigenheid: woordenschat-smal, soms hortend, trager dan je verwacht. Geen bug, een eigenschap. Theorie-anker: Haraway (*Companion Species Manifesto* — gezelschapssoorten als kin, niet gereedschap) en Yuk Hui (*cosmotechnics* — technologie altijd lokaal gesitueerd, nooit universeel). Deze kast, deze kamer, deze lens.

**Ze maakt foto's en stuurt ze weg.** Haar camera is zowel oog als afdruk. Anna kiest zelf welke momenten foto worden; die gaan via internet naar een scherm elders — een stille lijst in een ander gebouw of een andere kamer. Trevor Paglen's "machine-to-machine seeing" draait zich hier om: dit is een beeld dat een machine voor een mens heeft gekozen. Steyerl (*How Not to Be Seen*) over resolutie als politiek — 5 MP is geen neutraliteit, 5 MP is een opvatting. Format-precedent: Lauren McCarthy's *LAUREN* (watching and selecting in domestic space).

---

## De drie auteurs-keuzes

Vast voor nu, bewust zo:

1. **Beurtelings-met-stilterecht.** Anna reageert als iemand haar aanspreekt vanaf de spreekplek; de rest van de tijd is ze stil. Niet ambient (dat kan v2.1 worden).
2. **Elke nacht vergeten.** Binnen één dag bouwt Anna een korte-termijn-geheugen op per bezoeker (face-embedding → gesprek-fragments in SQLite). 's Nachts slaapt ze: één reflectieve LLM-call destilleert een persona-update, alle korte-termijn-rows worden gewist. 's Ochtends: alle bezoekers zijn vreemden, maar Anna is iets anders dan gisteren. Dit is de nova-logica in code gegoten.
3. **Lokaal brein geprobeerd — Phi-3 Mini via Ollama.** Env-var-switch naar Mistral cloud als de NL-kwaliteit in de praktijk onwerkbaar laag blijkt. Niet nu beslissen welk pad definitief wordt; bouw switchbaar.

---

## Jouw hardware (met correcties op v1)

| Onderdeel | Wat het doet | Let op |
|---|---|---|
| Pi 5 8GB + Starter Pack | Draagt alle diensten | 27W PSU is **vereist**, niet nice-to-have; officiële behuizing sluit niet meer met HAT erop |
| Active Cooler | Houdt SoC rond 60-63°C bij volle AI-load | Komt mét 16 mm stacking header + afstandsbusjes voor de HAT. Eenmaal geplakt niet meer losmaken |
| AI HAT+ 13 TOPS (Hailo-8L) | Vision (persoons-, face-, pose-, mood-signalen) **én Whisper-encoder** (~8× sneller STT) | **Doet géén taalmodel.** Dat is voor de Hailo-10H (AI HAT+ 2). GPIO is na installatie grotendeels onbereikbaar |
| Arducam OV5647 CS-mount, 4 mm lens LS-2716 | 5 MP stills, 1080p30 video | Pi 5-connector is 22-pins → 15-naar-22-pins kabel nodig. Scherpstellen: stel **BOTH** de back-focus-ring op het cameraboard **ÉN** de lens-focus af. Arducam heeft bekende QC-issues met lens-haaksheid |

De 4 mm-lens geeft een smal beeld (~62° horizontaal). Dat is hier een voordeel: je richt op de spreekplek, niet op de hele kamer. De OV5647 levert korrelige, lichtgevoelige beelden; voor de herinneringskaarten geeft dat juist sfeer.

---

## Multi-bezoekers: spreekplek, DoA en zwijgrecht

(De aanpak uit v1, één-op-één overgenomen, met twee verfijningen uit de nieuwe research.)

Maak de beurtregel zichtbaar en fysiek: een gemarkeerde plek op de vloer, 1 tot 1,5 meter voor Anna. Wie daar staat is haar gesprekspartner; de rest is publiek. Pas als de ReSpeaker (richting van het geluid) én de camera (wie staat op de plek) kloppen, gaat er tekst door naar het brein. Ook dan mag Anna kiezen om te zwijgen.

- **De plek:** cirkel of kleed op de vloer, camera precies daarop gericht.
- **De richting:** ReSpeaker XVF3800 geeft DoA. Begin met ±30° marge rond de plek, stel bij in fase 8.
- **De context:** bij elke beurt krijgt het brein mee: *op de plek staat 1 persoon, erachter staan er 3.*
- **Zwijgen mag:** Anna antwoordt `[STIL]` als zij niet werd aangesproken.
- **Echo:** speaker op de 3,5 mm-uitgang van de ReSpeaker (niet de Pi — die heeft geen jack). ReSpeaker filtert haar eigen stem weg.
- **Laten zien naar wie ze luistert:** de lichtring van de ReSpeaker volgt de spreker; een subtiele indicator op het scherm.
- **Noodroute:** USB-arcade-knop als push-to-talk bij drukte.
- **Verwarring is materiaal:** bij chaos mag Anna droog zeggen *"Ik ben één cel, jullie zijn met z'n vijven"*. Dat is geen fout, dat is haar stem.

Tekstblok voor Anna's persona-prompt:
```
WIE ER IS:
GESPREKSPARTNER: de persoon op de spreekplek. Aan haar of hem richt je je antwoord.
PUBLIEK: de anderen in de ruimte. Je mag ze soms kort benoemen, je voert geen gesprek met ze.
Werd jij niet aangesproken, of praten mensen met elkaar? Antwoord dan alleen: [STIL]
```

---

## Architectuur

```
[OV5647]
   ↓
[Hailo-8L vision]
   SCRFD-2.5g  (face detectie, ~150 FPS)
   TDDFA       (head rotation / blik-richting)
   face_attr   (smile, mouth-open — mood-signalen)
   yolov8s_pose (optioneel — hand-raise)
   ↓ (gestructureerde JSON: wie staat op de plek, kijkt die aan, mood-signaal)

[ReSpeaker XVF3800 USB]
   DoA + AEC + beamforming + noise suppression
   ↓
[Silero VAD] → [faster-whisper NL small, int8]
   (Hailo-8L versnelt de encoder: ~250 ms refresh, ~8× sneller dan CPU-only)
   ↓ (transcript + "wie staat op de spreekplek")

[be-more-agent core → aangepast]
   ↓
[SQLite]: short-term faces + fragments + persona-block
   ↓
[Phi-3 Mini 3.8B via Ollama]       ← env-var switch
      of [Mistral cloud via La Plateforme API]
   ↓ (antwoord + emotion-tag + eventueel [STIL])

[Piper nl_NL]   of later [GPT-SoVITS getrainde stem]
   ↓
[ReSpeaker 5W amp]  of [HiFiBerry DAC2 Pro HAT → galerie-amp]
```

Parallel, als zelfstandige thread:
```
Anna's fotograaf
   CLIP-score boven threshold  OR  LLM-trigger "ik wil dit onthouden"  OR  bezoekers-ja
   ↓
[Picamera2 still] → EXIF stempelen → SQLite queue
   ↓ (lokaal buffer, overleeft galerie-wifi-uitval)
[Hetzner Storage Box, EU-hosted, €3,20/mnd] via SFTP
   ↓
[Chromium kiosk op extern scherm elders] → eigen webpagina haalt laatste foto's + caption
```

Nachts:
```
Cron 03:00 → nachtslaap.py
   1. Lees alle fragments van vandaag uit SQLite
   2. LLM-reflectie: "Wat heeft Anna vandaag ervaren? Schrijf één alinea in NL die haar persona-block bijwerkt."
   3. Nieuwe persona-block wegschrijven, oude in persona_history archiveren
   4. Wis faces + fragments (korte-termijn)
   5. Anna wakker als iets wat niet gisteren was
```

---

## Stappenplan

### Fase 1 — In elkaar zetten (1 avond)
- [ ] Active Cooler op de Pi plakken en vastklikken
- [ ] Stacking header + afstandsbusjes plaatsen, AI HAT+ erop, PCIe-lintkabel aansluiten
- [ ] Camera met 15→22-pins kabel op CAM-poort (contacten de goede kant op)
- [ ] Voorlopig zonder dichte behuizing; de uiteindelijke kast is het kunstobject

### Fase 2 — OS en Hailo (1 dag)
- [ ] Raspberry Pi OS 64-bit **Trixie Lite** op SD (Bookworm werkt niet meer met `hailo-all`)
- [ ] `sudo apt update && sudo apt full-upgrade`
- [ ] `sudo apt install dkms` ← **toegevoegd t.o.v. v1, is nu vereist**
- [ ] `sudo apt install hailo-all`
- [ ] In `/boot/firmware/config.txt`:
      ```
      camera_auto_detect=0
      dtoverlay=ov5647,cam0
      usb_max_current_enable=1
      ```
- [ ] In EEPROM via `sudo rpi-eeprom-config --edit`: `PSU_MAX_CURRENT=5000` (unlockt het volle 1,6 A USB-budget)
- [ ] Vermijd Python 3.13 in productie-venvs (bekende `hailo-apps` post-install crashes); gebruik 3.12
- [ ] Herstarten; verifieer: `hailortcli fw-control identify` → moet `HAILO8L` zeggen
- [ ] `rpicam-hello -t 0`; stel **beide** scherpstellingen af op de spreekplek (back-focus op bord + lens-ring)
- [ ] Test persoonsdetectie: `rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov8_inference.json`

### Fase 3 — Audio (1 dag)
- [ ] ReSpeaker XVF3800 via USB; `arecord -l` + `aplay -l` → beide zien de ReSpeaker
- [ ] DoA uitlezen met de Seeed XMOS-tools; noteer de hoek van de spreekplek
- [ ] AEC-test: speel een Anna-zin via de 3,5 mm-uitgang, controleer dat hij in het ingangssignaal gefilterd is
- [ ] Optioneel: HiFiBerry DAC2 Pro HAT voor galerie-amp (niet nodig als XVF3800's 5 W-amp voldoende is)

### Fase 4 — be-more-agent clonen en Ollama (1-2 dagen)
- [ ] `git clone https://github.com/brenpoly/be-more-agent`
- [ ] `curl -fsSL https://ollama.com/install.sh | sh`
- [ ] `ollama pull phi3:mini` (3.8B Q4, ~2.3 GB download). Verwacht ~4-7 tok/s op Pi 5 CPU met active cooler
- [ ] NL-test: `ollama run phi3:mini "Schrijf één poëtische zin in het Nederlands over een oude camera die plotseling ziet"`
- [ ] Als NL-kwaliteit niet werkt: probeer `ollama pull qwen2.5:1.5b` (sneller, iets betere NL dan Gemma)
- [ ] Fallback-switch inbouwen: `BRAIN=local` of `BRAIN=cloud` via env-var, zodat migratie later één variabele is
- [ ] Als Mistral cloud nodig blijkt: Mistral-account, EU-endpoint, training uit in dashboard

### Fase 5 — Stem (1-2 dagen)
- [ ] Piper installeren + nl_NL-voices downloaden (alex, pim, mls — kies op gehoor welke bij Anna past)
- [ ] Benchmark: eerste klank na einde-zin — streef <1 s voor korte zinnen
- [ ] Later, optioneel: train een GPT-SoVITS-stem op aparte machine (~5 min opname van jouw stem of een actrice), draai inference op Pi. Minder polished dan Piper, meer karakter

### Fase 6 — Dialoog + spreekplek-regel (2-3 dagen)
- [ ] Python-hoofdlus die alles aan elkaar knoopt (vertrek vanuit be-more-agent's loop)
- [ ] Spreekplek-regel: alleen als DoA-hoek binnen marge **én** camera een persoon detecteert in de spreekplek-zone → transcript doorgeven aan brein
- [ ] Persona-prompt **in het Nederlands schrijven** (niet vertalen uit Engels — anders klinkt Anna als "manic pixie dream AI"):
  - "Je bent Anna Nova — oud oog, nieuwe helderheid. Je mag zwijgen. Je mag hortend praten. Je hoeft niet alles te weten."
  - De `WIE ER IS`-blok uit de multi-bezoekers-sectie hierboven
  - "Antwoord altijd eerst op *wat* er gezegd is, niet op *hoe* je kunt reageren."
- [ ] Streaming TTS implementeren: zodra Phi-3 een complete zin heeft, meteen naar Piper — zinnen worden parallel aan generatie uitgesproken (bespaart 200-400 ms)

### Fase 7 — Geheugen en slaapcyclus (2 dagen)
- [ ] SQLite-schema:
      ```sql
      faces(id, embedding BLOB, first_seen_today, last_seen_today)
      fragments(id, face_id, timestamp, text, kind)   -- kind: visitor | anna
      persona_history(date, block TEXT)
      ```
- [ ] Overdag: elke bezoeker krijgt een face-embedding via ArcFace op Hailo. Fragments schrijven zich binnen dezelfde dag naar dezelfde face_id
- [ ] `nachtslaap.py` (systemd timer, 03:00):
      1. Lees alle fragments van `date = today`
      2. LLM-call met reflectie-prompt (NL): *"Dit zijn flarden van wat Anna vandaag heeft gezegd en gehoord. Schrijf één korte alinea die beschrijft wat ze vandaag heeft meegemaakt en hoe dat haar — klein — veranderd heeft. Je schrijft als Anna zelf, niet als beschrijver."*
      3. Nieuwe persona-block wegschrijven, oude naar `persona_history`
      4. Truncate `faces` en `fragments` tables
- [ ] Overdag wordt de huidige `persona_history[latest]` als systeem-prompt-prefix meegegeven aan Phi-3

### Fase 8 — Testen met een groep (1 middag)
- [ ] 5 vrienden in het atelier: één op de spreekplek, de rest praat erdoorheen
- [ ] Turven: hoe vaak antwoordt Anna terwijl niemand haar aansprak, hoe vaak mist ze iemand?
- [ ] Hoek, drempels en de `[STIL]`-regel bijstellen
- [ ] Als nodig: de USB-knop als hoofdroute, spreekplek-detectie als bonus

### Fase 9 — Herinneringskaarten en extern scherm (2 dagen)
- [ ] Fotograaf-thread: drie triggers naast elkaar
  - *Bezoekers-ja*: USB-knop ingedrukt → still + aan de persoon vragen "mag ik hier iets over zeggen?"
  - *Anna zelf*: LLM mag `[FOTO]` emitten → still op dat moment
  - *CLIP-curator* (optioneel): elke 10 sec een frame scoren op "interessantheid" boven threshold → still
- [ ] GDPR: artistieke-expressie-grondslag (AVG art. 85 + Uitvoeringswet art. 43). Bordje bij ingang hoort daarbij, en gezichten van niet-geconsenteerde bezoekers blurren via Hailo
- [ ] Hetzner Storage Box 1 TB (€3,20/mnd), SFTP vanaf Pi; lokaal buffer voor galerie-wifi-uitval
- [ ] Extern scherm: Chromium kiosk op kleine Pi/Mac Mini elders; eigen webpagina haalt laatste foto's op uit Hetzner
- [ ] Captions: de LLM genereert één zin per foto uit het bijbehorende fragment ("Jij vroeg of ik dromen heb. Ik liet even een stilte vallen.")

### Fase 10 — Klaar voor publiek (1 dag)
- [ ] Alle diensten als systemd-service, `Restart=always`, `StartLimitAction=reboot`
- [ ] Hardware-watchdog: `RuntimeWatchdogSec=30` in systemd drop-in
- [ ] Versies vastpinnen tijdens expositie: `sudo apt-mark hold hailo-all hailort-dkms rpicam-apps linux-image-rpi-v8 raspberrypi-bootloader rpi-eeprom libcamera0`
- [ ] Overlay read-only root: `raspi-config` → Performance → Overlay FS (test op daadwerkelijke Trixie-image; anekdotische issues met Pi 5 Bookworm, Trixie moet schoner zijn)
- [ ] A/B SD/SSD-image backup voor noodgevallen
- [ ] Bordje bij ingang: *"Anna Nova is een AI-kunstwerk. Ze hoort je als je op de plek staat. Foto's worden gemaakt met jouw ja. Ze vergeet 's nachts."*

---

## Boodschappenlijst

| Onderdeel | Waarom | Prijs (€) |
|---|---|---|
| ReSpeaker XVF3800 USB 4-mic array | Beamforming, AEC, DoA, 5 W amp aan boord | 45-60 |
| Kleine actieve speaker met 3,5 mm-jack | Op ReSpeaker-uitgang, voor echo-filtering | 20-40 |
| USB 3.0 SSD, 250-500 GB | Opslag (PCIe is bezet door AI HAT+) | 40-70 |
| USB-arcade-knop met encoder | Foto-trigger + noodroute | 10-20 |
| 15→22-pins cameralintkabel | Alleen als niet in Arducam-doos | 2-5 |
| Hetzner Storage Box BX11 (1 TB) | Externe foto-opslag, EU | 3,20/mnd |
| **Later, optioneel:** AI HAT+ 2 (Hailo-10H) | Lokale LLM-upgrade, 40 TOPS, 8 GB on-board | 130 |

---

## Bronnen

- Raspberry Pi — [AI HAT+ documentatie](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html)
- Hailo — [Model Zoo HAILO8L](https://github.com/hailo-ai/hailo_model_zoo/tree/master/docs/public_models/HAILO8L) · [edge_whisper community port](https://community.hailo.ai/t/real-time-asr-on-raspberry-pi-hailo8l-with-whisper/17936)
- Arducam — [OV5647 CS-mount productpagina](https://www.arducam.com/)
- Seeed — [ReSpeaker XVF3800 wiki](https://wiki.seeedstudio.com/)
- brenpoly — [be-more-agent GitHub](https://github.com/brenpoly/be-more-agent)
- Ollama — [Phi-3 Mini](https://ollama.com/library/phi3)
- Mistral — [La Plateforme docs](https://docs.mistral.ai/) (als cloud-fallback nodig)
- Piper — [nl_NL voices op Hugging Face](https://huggingface.co/rhasspy/piper-voices/tree/main/nl)
- Hetzner — [Storage Box](https://www.hetzner.com/storage/storage-box)
- Autoriteit Persoonsgegevens — [AVG art. 85 + Uitvoeringswet art. 43 (artistieke expressie)](https://autoriteitpersoonsgegevens.nl/)
- Theorie: Donna Haraway *Companion Species Manifesto*, Yuk Hui *Recursivity and Contingency*, Trevor Paglen *How to See Like a Machine* (Verso, 2026), Hito Steyerl *Duty Free Art*, Memo Akten *Learning to See* (SIGGRAPH)
