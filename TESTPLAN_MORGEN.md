# Anna Nova — testplan morgen (fine-tune dag)

*Doel: conversatie scherp krijgen, camera erbij, foto-galerij publiek, en alles stabiel voor open-atelier weekend.*

Werkvolgorde van onderen naar boven: eerst zekerheid (werkt alles nog?), dan nieuwe dingen erbij. Niet alles hoeft op één dag.

---

## Blok 0 — Sanity check (10 min, bij de koffie)

- [ ] Pi aanzetten, wacht 1 min
- [ ] Open `http://anna.local:8765/face.html` op laptop — rood pulserend vignet, "sluimert" in status-balk?
- [ ] Chromium auto-opent op Pi-scherm? (anders klik icoon **Anna gezicht** op Pi desktop)
- [ ] `ssh annanova 'systemctl is-active anna-nova'` → `active`
- [ ] `ssh annanova 'curl -s https://api.mistral.ai/v1/models -o /dev/null -w "%{http_code} %{time_total}s\n"'` → HTTP 401 binnen 2 sec = internet OK
- [ ] Zeg "Hoi Anna Nova" → reactie binnen 3 sec?

Als alles ✅ → door naar Blok 1. Als niet → Pi desktop icoon **Anna OPNIEUW** klikken.

---

## Blok 1 — Conversatie fine-tunen (1-2 uur)

**Doel:** bepalen welke uitingen van Anna werken en welke niet. Persona.md aanscherpen in iteraties.

### 1.1 Baseline-gesprek opnemen (15 min)

Voer 3 verschillende gesprekken, elk 5-6 beurten:

1. **Open-atelier bezoeker** — "Hoi Anna Nova. Wat ben jij?"
2. **Kind van 8** — "Hoi. Ben jij echt?"
3. **Jolanda zelf** — iets persoonlijks

Notities per gesprek:
- Wat zei Anna dat mooi was?
- Wat zei Anna dat raar was?
- Reactietijd (gevoelsmatig: snappy / wacht lang)?

Verzamel via:
```bash
ssh annanova 'curl -s http://localhost:8765/messages | jq ".[-30:]"' > ~/Desktop/gesprek-$(date +%H%M).json
```

### 1.2 Persona-ronde 1 (30 min)

Open `persona.md` in editor. Pas aan op basis van wat NIET werkte:

- Te lang antwoord? → verscherp sectie 2 "meestal één zin"
- Stelt géén vraag? → verscherp "altijd eindigen met vraag"
- Te zoet? → Schrap "warm" uit sectie 2
- Te koud? → Voeg warmer voorbeeld toe
- Te veel over "AI zijn"? → Schrap sectie
- Mist referentie naar open-atelier context? → Versterk sectie "Context — waar je NU staat"

Commit elke verandering:
```bash
cd ~/AnnaNovaRasberry5 && git add persona.md && git commit -m "persona: [wat je veranderde]" && git push
ssh annanova 'cd /home/anna/anna-nova && git pull && sudo systemctl restart anna-nova'
```

### 1.3 Hertestronde (15 min)

Zelfde 3 gesprekken opnieuw. Beter?

### 1.4 Openingsvragen uitbreiden (optioneel)

Als Anna te weinig varieert: voeg 3-5 nieuwe openingsvragen toe in persona.md sectie "Openingsvragen die je graag stelt".

---

## Blok 2 — Camera installeren + debuggen (30 min)

**Doel:** Arducam OV5647 aansluiten zodat Anna ziet wie er voor haar staat.

### 2.1 Kabel aansluiten

- Pi uit (`sudo shutdown -h now`)
- 15-naar-22-pins lintkabel: brede kant in Pi CAM0 poort (dichtbij USB), smalle kant in cam
- **Blauwe strip van de kabel naar de ETHERNET poort toe**
- Pi aan

### 2.2 Camera detecteren

```bash
ssh annanova 'rpicam-hello --list-cameras'
```

Verwacht: `Available cameras: 0 : imx219` (OV5647 of imx219, afhankelijk van sensor).

Test-snapshot:
```bash
ssh annanova 'rpicam-still -o /tmp/test.jpg --nopreview -t 1000 && ls -la /tmp/test.jpg'
scp annanova:/tmp/test.jpg ~/Desktop/pi-cam-test.jpg
open ~/Desktop/pi-cam-test.jpg
```

Als snapshot OK → camera werkt.

### 2.3 Anna's vision-thread activeren

Vision is al in anna-nova.py geïntegreerd (zie `vision.py`). Na restart zou Anna
"camera" moeten zien:
```bash
ssh annanova 'sudo systemctl restart anna-nova && sleep 5 && journalctl -u anna-nova -n 20 --no-pager | grep -iE "camera|vision"'
```

Verwacht: `anna.vision: camera aan` ipv `camera-fout: No camera number 0 found`.

### 2.4 Live beeld in face.html

Open `http://anna.local:8765/face.html` — je zou nu LIVE camerabeeld onder de vignette moeten zien (niet meer de backdrop.webp).

### 2.5 Spreekplek-zone kalibreren

In `.env` staat `PLACE_X_MIN/MAX/Y_MIN/MAX` (default: centrum, 40% breed). Als Anna reageert op mensen buiten het frame — maak zone smaller. Als ze iemand mist — maak hem breder.

---

## Blok 3 — Externe foto-galerij (publieke site) (1-2 uur)

**Doel:** foto's die Anna maakt (via `[FOTO]`-tag in haar antwoord) komen op een publieke webpagina die bezoekers thuis kunnen bekijken.

### 3.1 Hosting kiezen

Twee opties (rank: eenvoudig → krachtig):

**A. Hetzner Storage Box (€4/mnd)** — origineel in config.sample.env. SFTP-only, direct serveerbaar als static site via eigen web-frontend of via Hetzner's ingebouwde preview.

**B. Netlify + GitHub Pages (gratis)** — Pi rsynct naar een git-repo, GitHub rendert. Meest flexibel voor custom galerij-design.

**Mijn aanbeveling voor open-atelier dag:** B, want gratis + eigen URL (`jolanda.github.io/anna-nova-galerij`).

### 3.2 SSH-key genereren op Pi

```bash
ssh annanova 'ssh-keygen -t ed25519 -f ~/.ssh/id_annasync -N "" -C "anna-nova-sync"'
ssh annanova 'cat ~/.ssh/id_annasync.pub'
```

Kopieer die publieke sleutel naar:
- Hetzner Storage Box dashboard (SSH keys sectie)
- OF GitHub Deploy Keys van de galerij-repo

### 3.3 .env invullen

```bash
ssh annanova "sudo sed -i 's|^PHOTO_UPLOAD_ENABLED=.*|PHOTO_UPLOAD_ENABLED=true|' /home/anna/anna-nova/.env"
ssh annanova "sudo nano /home/anna/anna-nova/.env"
# Vul in:
#   PHOTO_SFTP_HOST=jouw-host
#   PHOTO_SFTP_USER=jouw-user
#   PHOTO_SFTP_KEY=/home/anna/.ssh/id_annasync
#   PHOTO_SFTP_REMOTE_PATH=anna-nova/photos
```

### 3.4 Timer activeren

```bash
ssh annanova 'sudo systemctl enable --now anna-sync.timer && systemctl list-timers anna-sync.timer'
```

Draait elke 15 min.

### 3.5 Eerste foto maken + syncen

Zeg tegen Anna iets persoonlijks zodat ze `[FOTO]` triggert. Of handmatig:
```bash
ssh annanova 'sudo systemctl start anna-sync.service && journalctl -u anna-sync.service -n 20 --no-pager'
```

### 3.6 Publieke galerij-site opzetten (als B gekozen)

Maak nieuwe GitHub repo `anna-nova-galerij` publiek, enable GitHub Pages op main.
Op Pi: `PHOTO_SFTP_REMOTE_PATH=/photos` + schrijf een eenvoudig `index.html` dat alle JPGs uit `/photos/` grid-weergeeft. Of forker iets bestaands zoals [nanogallery2](https://nanogallery2.nanostudio.org/).

URL die je kan delen: `https://joliejola.github.io/anna-nova-galerij/`

---

## Blok 4 — USB wifi adapter (als T3U is binnen)

Volg **Deel 11** van `MORGEN.md`. 15 min werk.

Winst: Voxtral van 0.5-2s → 0.3-0.8s, geen DNS-fails meer.

---

## Blok 5 — Eindcheck voor expositie (15 min)

- [ ] Reboot Pi, laat 'm 2 min met rust → face.html komt vanzelf op
- [ ] "Hoi Anna Nova" → antwoord in <3s
- [ ] "Slaap lekker" → sluimert, vignet rood pulserend
- [ ] Camerabeeld zichtbaar (als Blok 2 gedaan)
- [ ] Foto gemaakt verschijnt op galerij-site (als Blok 3 gedaan)
- [ ] Trek stekker eruit, plug weer in → zelfde flow

Als alles ✅ → klaar voor open atelier.

---

## Blok 6 — Afterparty: backup maken

```bash
# SD-kaart image van de werkende Pi (vanaf Mac met kaartlezer)
sudo dd if=/dev/diskX of=~/Desktop/anna-werkend-$(date +%Y%m%d).img bs=4M status=progress
```

Zodat als iets stuk gaat tijdens expositie, snelle restore mogelijk is.

---

## Appendix — handige commando's

```bash
# Live wat Anna hoort/zegt
ssh annanova 'curl -s http://localhost:8765/debug | jq ".[-10:]"'

# Anna-persona herladen zonder restart
ssh annanova 'sudo systemctl reload-or-restart anna-nova'

# Laatste 5 foto's bekijken
ssh annanova 'ls -lt /home/anna/anna-nova/photos | head -5'

# CPU / geheugen / wifi
ssh annanova 'uptime && free -h | head -2 && iwconfig wlan0 2>&1 | grep Bit'

# Full restart (als niets werkt)
ssh annanova 'sudo reboot'   # Pi komt 1 min later vanzelf terug + Chromium auto-start
```
