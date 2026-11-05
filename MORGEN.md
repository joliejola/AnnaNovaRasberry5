# Anna Nova — stappenplan voor morgen

*Volg deze stappen van boven naar beneden. Alles tussen \`backticks\` is iets dat je letterlijk typt of plakt. Teksten in [vierkante haakjes] zijn plekken waar jij jouw eigen gegevens invult.*

---

## Deel 0 — Spullen klaarleggen

Leg alles bij elkaar op je bureau:

- [ ] Raspberry Pi 5 met **AI HAT+ al erop** (uit de starter kit)
- [ ] Officiële **27 W / 5 V / 5 A voeding** (uit de starter kit — géén oudere Pi-adapter!)
- [ ] **MicroSD-kaart** (minimaal 32 GB, A1 of A2 class)
- [ ] **SD-adapter of USB-SD-reader** om de kaart in je laptop te stoppen
- [ ] **Arducam OV5647** camera + **15-naar-22-pins lintkabel** (de brede naar de smalle)
- [ ] **Active Cooler** op de Pi geklikt
- [ ] **Waveshare 4" Square HDMI** scherm + HDMI-kabel
- [ ] Je **USB-microfoon**
- [ ] Een **speaker** (USB of op de audio-uitgang van je mic)
- [ ] **Laptop** met wifi
- [ ] **Je wifi-naam (SSID) en wachtwoord** paraat
- [ ] Een **kop koffie** — de install duurt een half uur

---

## Deel 1 — SD-kaart klaarmaken (op je Mac, 10 min)

### 1.1 Raspberry Pi Imager downloaden

- Open je browser → ga naar <https://www.raspberrypi.com/software/>
- Klik op **"Download for macOS"**
- Open het downloadede `.dmg`-bestand en sleep de icoon naar je Applications-map

### 1.2 Imager starten en SD inrichten

- Stop de SD-kaart in je laptop (via de reader)
- Open **Raspberry Pi Imager**
- **Choose Device** → kies **Raspberry Pi 5**
- **Choose OS** → scroll naar:
  - **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**
  - *Belangrijk: de "Lite"-versie zonder desktop. Niet de full-desktop.*
- **Choose Storage** → selecteer je SD-kaart (dubbelcheck de naam!)
- Klik **Next** → verschijnt er een popup *"Would you like to apply OS customisation settings?"* → klik **Edit Settings**

### 1.3 OS-instellingen (dit is de belangrijkste stap)

In de popup, tab **General**:

- **Set hostname:** `anna`
- **Set username and password:**
  - Username: `pi`
  - Password: *[kies iets simpels wat je onthoudt — bijv. je telefoonnummer of iets)]* — schrijf 'm op!
- **Configure wireless LAN:**
  - SSID: *[jouw wifi-naam]*
  - Password: *[jouw wifi-wachtwoord]*
  - Wireless LAN country: `NL`
- **Set locale settings:**
  - Time zone: `Europe/Amsterdam`
  - Keyboard layout: `us` (laat zo staan)

Tab **Services**:

- Vink aan **☑ Enable SSH**
- Kies **"Use password authentication"**

Klik **Save** → terug op het hoofdscherm **Yes** → *"Would you like to continue?"* → **Yes** → wachtwoord van je Mac invoeren → **Write** begint.

**Dit duurt 5-10 min.** Niet onderbreken. Als klaar: pop-up *"You can now remove the SD card"* → oké → SD uit de reader.

---

## Deel 2 — Pi fysiek aansluiten (5 min)

Doe dit in deze volgorde (voeding als allerlaatste):

1. **SD-kaart** in het SD-slot aan de onderkant van de Pi. Klik stevig vast.
2. **Camera**: zet de lintkabel in de CAM-poort op de Pi — zilveren contacten wijzen *naar de HDMI-kant* van de Pi. Druk 't zwarte klemmetje weer dicht. Doe hetzelfde aan de kant van de camera-module.
3. **HDMI-kabel** in **HDMI 0** van de Pi (dat is de poort die het dichtst bij de USB-C voedingsingang zit).
4. **Scherm** aan de andere kant van de HDMI-kabel. Zet het scherm aan.
5. **USB-microfoon** in een van de USB-poorten.
6. **Speaker** aansluiten (op je mic of in een USB-poort).
7. **Voeding** in de USB-C-ingang van de Pi — Pi start nu automatisch.

Je ziet witte tekst over het scherm scrollen. Eerste boot duurt ~2 minuten. Als 't klaar is zie je een inlog-prompt (`anna login:`). Je hoeft hier niets te doen — jouw echte werk gaat via SSH.

---

## Deel 3 — Verbinden vanaf je laptop (2 min)

### 3.1 Terminal openen

Op je Mac:
- Druk **⌘ + spatie** (de spotlight-zoeker)
- Typ `Terminal` en druk **Enter**
- Een zwart/wit venster opent met een cursor

### 3.2 Checken dat de Pi online is

Typ dit in Terminal:

```bash
ping anna.local
```

Als 't werkt: elke seconde komt er een regel bij (`64 bytes from anna.local ...`). Dat is goed. Druk **Ctrl + C** om te stoppen.

**Als `ping` *"cannot resolve anna.local"* zegt:**
- Wacht 1 minuut extra en probeer opnieuw (eerste boot soms traag)
- Als het dan nog niet werkt: check je wifi-wachtwoord in Deel 1.3. Een foutje daar betekent dat de Pi niet online kan — SD opnieuw inrichten.

### 3.3 Inloggen op de Pi

Typ in Terminal:

```bash
ssh pi@anna.local
```

- Eerste keer vraagt-ie *"Are you sure you want to continue connecting (yes/no)?"* → typ `yes` + Enter
- Dan: *"pi@anna.local's password:"* → typ je wachtwoord (**let op: je ziet geen bolletjes of sterretjes, dat is normaal**) + Enter

Als 't lukt zie je:
```
pi@anna:~ $
```

Dat is Pi's prompt — je bent nu op de Pi.

---

## Deel 4 — Anna installeren (30 min, meeste tijd wachten)

Op de Pi (dus in dat `pi@anna:~ $` venster):

### 4.1 Code ophalen

```bash
git clone https://github.com/joliejola/AnnaNovaRasberry5.git
```

Dit duurt een paar seconden.

### 4.2 Installer draaien

```bash
cd AnnaNovaRasberry5
sudo ./install.sh
```

Vraagt om je wachtwoord (zelfde als bij inloggen). Daarna gaat 'ie 10 stappen af. **Dit duurt 20–35 minuten.** Niet onderbreken. Je ziet dingen voorbijkomen als:

```
» 1/10 — Systeem updaten
» 2/10 — Basispakketten
...
» 10/10 — systemd units
```

Zijn er rode of gele regels? Vaak zijn gele regels OK (waarschuwingen). Een rode `✗` is wel een probleem — screenshot sturen.

### 4.3 Herstarten

Als `Installatie klaar` verschijnt:

```bash
sudo reboot
```

Je SSH-verbinding wordt verbroken (dat is goed). Pi herstart (duurt ~1 min).

---

## Deel 5 — Anna zet 'r aan (2 min)

### 5.1 Opnieuw verbinden

Terug in Terminal op je Mac:

```bash
ssh pi@anna.local
```

Wachtwoord opnieuw.

### 5.2 Checken dat ze draait

```bash
systemctl status anna-nova
```

Je zoekt een groene regel die zegt **`active (running)`**. Druk **q** om de weergave te verlaten.

### 5.3 Haar scherm bekijken

Open je browser (Safari / Chrome) op je Mac en ga naar:

```
http://anna.local:8765/
```

Je ziet nu haar vierkante scherm: donker, een vage camera-afbeelding op de achtergrond, "anna nova" linksboven, "sluimert" rechtsonder.

Dit is **ook** wat op het Waveshare-scherm aan de Pi te zien is (maar daarvoor moet je `install-screen.sh` later apart draaien — zie Deel 8).

### 5.4 Praat met haar

Zeg hardop (richting je microfoon):

> **"Hoi Anna Nova"**

Wat je ziet:
- Debug-regel onderaan toont `wake: "hoi anna nova"`
- Status wisselt naar `luistert`
- Je hoort "Hm."
- **De eerste beurt is traag** (10–30s door de brein-warmup). Dat is éénmalig.

Praat door. Zeg bijvoorbeeld:
> *"Wat ben jij eigenlijk?"*

Vraag Anna te slapen:
> *"Slaap lekker"* of *"Dag Anna"*

→ ze zegt "Mmh. Welterusten." en gaat terug naar sluimer.

Daarna wordt ze weer wakker met **"Hoi Anna Nova"**.

---

## Deel 6 — Live zien wat Anna doet (het debug-venster)

Als Anna haakt of niet reageert, laat live haar logboek zien:

```bash
ssh pi@anna.local 'journalctl -u anna-nova -f'
```

Druk **Ctrl + C** als je het weer wilt sluiten. Dit toont elke regel die Anna logt — groen voor wake, grijs voor skip, rood voor fout.

Je ziet dit ook onderin haar scherm (de kleine monospace-regels).

---

## Deel 7 — Als iets niet werkt (vang-vraag per probleem)

### Anna hoort me niet
```bash
arecord -l
```
Geen output = microfoon niet herkend. Haal 'm eruit, prik 'm in een andere USB-poort, probeer opnieuw.

### Anna heeft geen stem
```bash
aplay -D default /usr/share/sounds/alsa/Front_Center.wav
```
Hoor je een vrouwenstem "Front Center"? Zo niet: controleer dat je speaker aanstaat en in de goede poort zit.

### Scherm blijft zwart (op Waveshare)
HDMI-kabel moet in **HDMI 0** (de poort het dichtst bij de USB-C voedingsingang). Omdraaien, Pi rebooten:
```bash
sudo reboot
```

### Install crashte halverwege
Geen paniek — hij is **idempotent** (je mag 'm opnieuw draaien):
```bash
cd ~/AnnaNovaRasberry5
sudo ./install.sh
```

### Anna reageert niet op "Hoi Anna Nova"
Kijk live mee:
```bash
journalctl -u anna-nova -f
```
Spreek weer "Hoi Anna Nova". Zie je in de log:
- *"genegeerd (geen wake)"*? → Whisper hoort iets anders, probeer luider/duidelijker.
- Niets? → Mic niet actief. Check `arecord -l`.
- Een foutmelding in rood? → Screenshot + stuur me de laatste 20 regels.

### Ik heb iets veranderd en wil 'r opnieuw starten
```bash
sudo systemctl restart anna-nova
```

### Ik wil Anna even stil zetten
Zeg "slaap lekker" of trek de voeding eruit. Beiden werkt.

---

## Deel 8 — Later (als Pi stabiel draait)

Niet nodig voor morgen, wel voor later:

### 8.1 Scherm aan Anna's kast (echt HDMI-kiosk)

Nu kijk je naar Anna via je laptop-browser. Als je het Waveshare-scherm direct aan de Pi gekoppeld wilt met kiosk-mode:

```bash
ssh pi@anna.local
cd AnnaNovaRasberry5
sudo ./install-screen.sh
sudo reboot
```

Na reboot: Waveshare toont fullscreen Anna's gezicht automatisch bij boot.

### 8.2 Persona bewerken

```bash
ssh pi@anna.local
nano ~/anna-nova/persona.md
```

Pas aan. Opslaan: **Ctrl + O**, Enter. Afsluiten: **Ctrl + X**. Anna pakt het automatisch op bij de volgende beurt.

### 8.3 Voiceprint — Anna herkent jou en Bodil

```bash
ssh pi@anna.local
cd ~/anna-nova
venv/bin/python anna-enroll.py --name jolanda
```

Volg de countdown — praat 25 seconden door. Doe hetzelfde voor Bodil:
```bash
venv/bin/python anna-enroll.py --name bodil
```

Herstart Anna:
```bash
sudo systemctl restart anna-nova
```

Vanaf nu toont de debug-regel *"stem herkend: jolanda"* en past Anna haar toon aan per persoon.

### 8.4 Foto's naar extern scherm (Hetzner-sync)

Dit vereist een Hetzner Storage Box account. Zet aan in `.env`:

```bash
ssh pi@anna.local
nano ~/anna-nova/.env
```

Zoek `PHOTO_UPLOAD_ENABLED=false` → verander naar `true`. Vul `PHOTO_SFTP_HOST`, `PHOTO_SFTP_USER` in. Maak een SSH-sleutel:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```
Kopieer die laatste output in de Hetzner-UI onder "SSH-sleutels".

Opslaan `.env`: Ctrl+O, Enter, Ctrl+X. Herstarten:
```bash
sudo systemctl restart anna-nova anna-sync
```

Elke 15 min worden nieuwe foto's gesynct.

---

## Deel 9 — Spiekbrief (alles op één scherm)

```bash
# Verbinden met Pi
ssh pi@anna.local

# Status checken
systemctl status anna-nova

# Live loggen
journalctl -u anna-nova -f

# Herstarten
sudo systemctl restart anna-nova

# Persona bewerken
nano ~/anna-nova/persona.md

# Updates van GitHub halen
cd ~/AnnaNovaRasberry5 && git pull && sudo ./install.sh

# Uitschakelen (netjes)
sudo shutdown -h now
```

Browser-URL's:
- `http://anna.local:8765/` — Anna's gezicht
- `http://anna.local:8765/gallery` — foto-galerij

Wake-woord: **"Hoi Anna Nova"**
Slaap-woord: **"Slaap lekker"**, **"Dag Anna"**, **"Welterusten"**, **"Tot morgen"**

---

## Deel 10 — Als niets werkt en je bent moe

Trek de stekker, slaap een nacht, probeer morgen opnieuw. De SD-kaart raakt niet corrupt bij uittrekken (overlay-fs beschermt). Als álles stuk is: flash een nieuwe SD, draai `install.sh` opnieuw — ze onthoudt alleen Anna's `persona.md` kwijt (persona-geschiedenis in `anna.db` gaat verloren tenzij je die apart hebt gesaved).

Veel succes. Zet 'r aan.

---

## Deel 11 — USB wifi-adapter aansluiten (als-ie binnen is)

Pi 5's ingebouwde wifi is zwak — upload naar Mistral/Voxtral is ~70× langzamer dan op je laptop. Zodra de **TP-Link Archer T3U** (of soortgelijke RTL8812BU-dongle) binnen is:

### 11.1 Driver installeren (eenmalig)

```bash
ssh annanova "sudo apt update && sudo apt install -y realtek-rtl88x2bu-dkms linux-headers-\$(uname -r) && sudo reboot"
```

Pi reboot zichzelf.

### 11.2 Adapter inpluggen

- Plug de T3U in een **USB 3 poort** (blauwe USB-poort — die zijn sneller)
- Wacht ~5 sec, de dongle licht op
- Check: `ssh annanova 'ip link show'` — je zou `wlan0` (ingebouwd) én `wlan1` (dongle) moeten zien

### 11.3 Wifi verbinden via nieuwe adapter

```bash
ssh annanova 'nmtui'   # tekst-UI: Activate connection → kies je SSID op wlan1
```

Of commando:
```bash
ssh annanova 'sudo nmcli dev wifi connect "[jouw-SSID]" password "[jouw-wifi-wachtwoord]" ifname wlan1'
```

### 11.4 Ingebouwde chip disablen (zodat alle verkeer via T3U gaat)

```bash
ssh annanova 'sudo nmcli radio wifi on; sudo nmcli dev disconnect wlan0'
```

### 11.5 Test snelheid

```bash
ssh annanova 'time curl -s -o /dev/null https://speed.hetzner.de/5MB.bin'
```

Moet nu < 1 sec zijn (was ~2 sec via ingebouwde chip). Voxtral calls dalen van 2-13 sec → 0.5-1 sec.

### 11.6 Rollback als 't niet werkt

Trek de dongle eruit, reboot:
```bash
ssh annanova 'sudo reboot'
```

Pi pakt dan weer de ingebouwde wifi.
