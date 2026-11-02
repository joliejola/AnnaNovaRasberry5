# Anna Nova — installer

Installer voor een microSD-kaart met Raspberry Pi OS 64-bit Trixie Lite. Je zet de Pi aan, logt één keer in, draait `sudo ./install.sh`, reboot — Anna sluimert dan tot iemand haar roept.

## Startscenario: USB-microfoon eerst, ReSpeaker later

Voor de eerste test werkt elke standaard USB-mic. Standaard-config staat op:
```
AUDIO_INPUT_DEVICE=       # leeg = systeemdefault
AUDIO_OUTPUT_DEVICE=default
```
Dat werkt out-of-the-box met de meeste USB-headsets / USB-condensors / USB-speakers. Twee gevolgen:
- **Geen DoA**: Anna weet niet uit welke richting het geluid komt. De spreekplek-check valt in soepele modus (`STRICT_SPEAK_PLACE=false`) terug op alleen de camera. Zonder camera reageert ze op elke stem.
- **Geen hardware-AEC**: als speaker en mic dicht bij elkaar staan kan Anna haar eigen stem oppakken. De code is half-duplex (ze luistert niet terwijl ze praat), dus dit valt mee — maar galm uit een luide speaker kan problemen geven. Zet speaker en mic uit elkaar, of gebruik een USB-headset voor de test.

Als de ReSpeaker XVF3800 binnenkomt, verander in `~/anna-nova/.env`:
```
AUDIO_INPUT_DEVICE=ReSpeaker
AUDIO_OUTPUT_DEVICE=plughw:CARD=ReSpeaker,DEV=0
```
`systemctl restart anna-nova` en de spreekplek-DoA begint vanzelf te werken.

## Wat zit erin

| Bestand | Wat het doet |
|---|---|
| `install.sh` | Idempotente installer. Hailo-stack, config.txt + EEPROM, Ollama + Phi-3 Mini, Piper + Nederlandse stem, SCRFD + face_attr HEF-models, Python-venv, SQLite, systemd-services, udev-regel voor ReSpeaker. |
| `anna-nova.py` | Hoofdlus. Sluimert tot wake-phrase, luistert dan actief, combineert spreekplek-DoA met Hailo-vision, denkt met Phi-3 (of cloud), spreekt via Piper, onthoudt binnen de dag. |
| `vision.py` | Ogen-thread: Picamera2 + Hailo-8L SCRFD. Publiceert "iemand in de spreekplek?", aantal personen in beeld, mood-hint. Graceful fallback bij ontbrekende hardware/HEF. |
| `respeaker_doa.py` | Leest de richting-van-geluid uit de ReSpeaker XVF3800 (USB HID control). Fallback bij ontbrekend device: DoA uit, hoofdlus luistert alsnog. |
| `nachtslaap.py` | Draait elke nacht om 03:00. Reflecteert de dag → nieuwe persona-alinea; wist korte-termijn (fragments + gezichten). |
| `config.sample.env` | Alle instellingen. Wordt bij install gekopieerd naar `~/anna-nova/.env`. |

## Zo gebruik je het

### 1. SD-kaart klaarmaken
- Flash **Raspberry Pi OS 64-bit Trixie Lite** met de Raspberry Pi Imager.
- In de Imager: hostname `anna`, user `pi` (of ander), SSH aan, wifi aan.

### 2. Installer op de Pi zetten

**Via SSH:**
```
# vanaf je laptop:
scp -r anna-nova-installer/ pi@anna.local:~/
ssh pi@anna.local
```

**Via USB:**
Kopieer `anna-nova-installer/` naar een USB-stick, prik 'm in de Pi, kopieer naar `~/`.

### 3. Installer draaien
```
cd ~/anna-nova-installer
chmod +x install.sh
sudo ./install.sh
```

**15–30 minuten** eerste keer: Hailo, Ollama + Phi-3 (~2.3 GB), Piper, HEF-models, Python-packages.

### 4. Reboot
```
sudo reboot
```

### 5. Anna zet 'r aan
Na reboot sluimert Anna. Zeg:

> **"Hoi Anna Nova"**

Ze zegt kort "Hm." (configureerbaar als `WAKE_ACK` in `.env`), en luistert dan actief. Praat met haar. Na 60 seconden stilte valt ze terug in sluimer en moet je haar opnieuw roepen.

Alle variaties werken (fuzzy match): *"Hoi Anna"*, *"Hallo Anna Nova"*, *"Hey Anna"*. Puur "Anna Nova" zonder groet werkt ook.

### Status
```
systemctl status anna-nova
journalctl -u anna-nova -f           # live log
systemctl list-timers anna-slaap     # wanneer slaapt ze?
journalctl -u anna-slaap --since yesterday
```

## Hardware-check (één keer)

```
hailortcli fw-control identify         # moet "HAILO8L" zeggen
rpicam-hello -t 0                      # stel BEIDE scherpstellingen af
arecord -l                             # ReSpeaker zichtbaar?
aplay -l
ollama run phi3:mini "Hallo"           # brein reageert?
python3 ~/anna-nova/respeaker_doa.py   # DoA-hoek print?
```

## Spreekplek instellen

Twee lagen: *waar het geluid vandaan komt* (DoA) en *waar iemand in beeld staat* (camera-zone).

**DoA** (`.env`):
- `SPEAK_ANGLE_CENTER=0` — hoek voor Anna (0° = recht voor haar). Draai de ReSpeaker voor andere richting.
- `SPEAK_ANGLE_MARGIN=30` — hoe tolerant (±30° default).

**Camera-zone** (`.env`, 0–1 relatief in frame):
- `PLACE_X_MIN=0.30`, `PLACE_X_MAX=0.70` — horizontale strook in het midden.
- `PLACE_Y_MIN=0.20`, `PLACE_Y_MAX=0.90` — van kort onder de bovenrand tot bijna de onderrand.

**Strict?** `STRICT_SPEAK_PLACE=true` — alleen reageren als *beide* checks positief zijn. Default `false` (soepel: onbekende waardes tellen als "misschien", wat beter werkt in de testfase).

## Wake-phrase aanpassen

In `.env`:
```
WAKE_PHRASE=hoi anna nova
WAKE_ACK=Hm.
AWAKE_TIMEOUT=60
```

Fuzzy match: elke zin met "anna" + ("nova" OR groetwoord) telt als wake. `WAKE_ACK` leeg laten = Anna geeft geen hoorbaar bevestiging bij wakker worden.

## Vision aan/uit

In `.env`:
- `VISION_ENABLED=true` — camera + Hailo-thread aan.
- `VISION_ENABLED=false` — alleen audio. Hoofdlus doet dan geen camera-check.

Als Hailo of SCRFD-HEF niet beschikbaar is: `vision.py` valt automatisch terug op "blind-aanwezig" (iemand aanwezig = true), zonder crash.

## Debuggen

| Symptoom | Check |
|---|---|
| Anna wordt niet wakker | `journalctl -u anna-nova -f` — zie je transcripties? Komt wake-phrase binnen? Pas `WAKE_PHRASE` aan of voeg synoniemen toe in `wake_match()`. |
| Hoort niets | `AUDIO_INPUT_DEVICE` in `.env` moet matchen met `arecord -l`. ReSpeaker heet soms `plughw:CARD=ArrayUAC10,DEV=0`. |
| Geen stem | `AUDIO_OUTPUT_DEVICE` idem. Test: `aplay -D plughw:... /usr/share/sounds/alsa/Front_Center.wav`. |
| Vision niet actief | Check `SCRFD_HEF`-pad bestaat. Zo niet: download handmatig van [Hailo Model Zoo HAILO8L](https://github.com/hailo-ai/hailo_model_zoo/tree/master/docs/public_models/HAILO8L). |
| DoA onbekend | `python3 ~/anna-nova/respeaker_doa.py` — als "niet gevonden" check `lsusb` voor XMOS/Seeed VID. udev-regel zit al in installer; mogelijk logout nodig. |
| Te traag | `BRAIN=cloud` + `MISTRAL_API_KEY` in `.env`. Alternatief: `OLLAMA_MODEL=qwen2.5:1.5b`. |

## Nieuwe stem (Piper)

Beschikbare NL-stemmen: `nl_NL-mls-medium`, `nl_NL-alex-low`, `nl_NL-pim-medium`, Vlaams `nl_BE-nathalie-medium` en `nl_BE-rdh-medium`.

Download handmatig:
```
cd ~/anna-nova/piper
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL/pim/medium/nl_NL-pim-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL/pim/medium/nl_NL-pim-medium.onnx.json
```
Dan `PIPER_VOICE=/home/pi/anna-nova/piper/nl_NL-pim-medium.onnx` in `.env`.

## Startpersona overschrijven

```
sqlite3 ~/anna-nova/anna.db \
  "INSERT OR REPLACE INTO persona_history VALUES (date('now'), 'Je bent Anna Nova. Vandaag voel je je ongeduldig.');"
systemctl restart anna-nova
```

## Expositie-modus (klaar voor publiek)

```
sudo apt-mark hold hailo-all hailort-dkms rpicam-apps linux-image-rpi-v8 \
                   raspberrypi-bootloader rpi-eeprom libcamera0
```
Optioneel: `raspi-config` → Performance → Overlay FS voor read-only root (geen SD-corruptie bij stroomuitval).

## Wat NIET in de installer zit

- **Fotograaf-pijplijn** (foto's naar Hetzner → extern scherm): fase 9 van het stappenplan.
- **GPT-SoVITS karakter-stem**: fase 5, optioneel.
- **Dutch wake-word als openWakeWord-model**: nu doen we wake via faster-whisper + fuzzy match. openWakeWord-training is efficiënter (lagere CPU) en kan er later bij.

## Terugdraai

`/boot/firmware/config.txt.anna-backup` bestaat na install. Voor een complete reset: flash een nieuwe SD, draai `install.sh` opnieuw. Bewaar `~/anna-nova/anna.db` vooraf om Anna's persona-geschiedenis mee te nemen.
