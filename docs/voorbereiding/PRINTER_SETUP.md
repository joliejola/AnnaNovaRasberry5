# Printer setup voor Anna Nova

*Install-stappen voor de Agodeo mini printer (Fun Print-familie) op een Raspberry Pi 5 met Debian 13 "Trixie", kernel 6.12 aarch64. Deze file hoort bij bouwstap 1 uit `docs/BOUWPLAN_BRON.md`.*

## Over de printer

De Agodeo mini printer valt binnen de familie Chinese BLE "cat"-thermisch-printers (Fun Print, X6h, Phomemo T02, Peripage, M02/M03). Deze gebruiken **geen ESC/POS**, maar een eigen BLE-GATT-protocol over Bluetooth Low Energy. Daarom niet CUPS, geen `python-escpos`, maar een dedicated tool (TiMini-Print / funprint) of een ruwe `bleak` script. Nominale breedte: **384 px** op 58 mm papier (meest gebruikelijk), soms 576 px op 80 mm.

Officiële Android/iOS-apps zijn geen optie op een Pi; we gebruiken de community-tools.

## Vergelijking van tools

| Tool | Type | Werkt op Pi 5 Trixie | Input | Notities |
|---|---|---|---|---|
| **[TiMini-Print (NoeBrt fork)](https://github.com/NoeBrt/TiMini-Print)** | Python CLI + GUI | Ja (bleak-based) | PNG / JPG / PDF / TXT | **Aanbevolen**. Fork met meer modellen + CLI-flags. Fire-and-forget `--bluetooth MAC`. |
| [Dejniel/TiMini-Print](https://github.com/Dejniel/TiMini-Print) | Python desktop | Ja | PNG / PDF / text | Origineel. Minder modellen. |
| [funprint](https://github.com/Auxnon/funprint) | Rust CLI | Ja (statisch gelinkt) | PNG | Snelste maar minder modellen. Alternatief als TiMini stuk is. |

Werkt beide niet → USB ESC/POS fallback (zie onderaan).

---

## Stap 1 — Bluetooth stack op de Pi activeren

```bash
sudo apt update
sudo apt install -y bluez bluez-tools python3-pip python3-venv libbluetooth-dev
sudo systemctl enable --now bluetooth
systemctl status bluetooth --no-pager | head -3
```

**Verwacht**: `active (running)`.

**Als het faalt**: `rfkill unblock bluetooth` en probeer opnieuw.

## Stap 2 — Printertje aanzetten en pairen

Printertje aan, aan de lader, **telefoon-app afgesloten** (anders is de printer bezet).

```bash
bluetoothctl
# in de interactieve prompt:
power on
agent on
default-agent
scan on
# wacht tot je iets als "T02-XXXX" of "MX06" of "Agodeo-XXXX" ziet verschijnen
scan off
pair AA:BB:CC:DD:EE:FF   # <-- MAC van de printer
trust AA:BB:CC:DD:EE:FF
exit
```

**Verwacht**: `Pairing successful` + `Trusted: yes`.

**Als de printer niet in scan verschijnt**:
- Zet printer uit en aan (hold power ~3s)
- Check: `bluetoothctl show` → `Powered: yes`?
- Pi te ver weg? Probeer < 2m.

**Noteer de MAC** — zet 'm in `.env` als `PRINTER_MAC=AA:BB:CC:DD:EE:FF`.

## Stap 3 — TiMini-Print (NoeBrt fork) installeren

```bash
cd ~
git clone https://github.com/NoeBrt/TiMini-Print.git timini
cd timini
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Verwachte deps**: `bleak>=0.21`, `Pillow`, `pypdf`, `click`. Installatie ~20 sec.

**Als `pip install` faalt met "externally-managed-environment"** (PEP 668 op Trixie): `.venv` zorgt dat je niet in de system python installeert. Als je alsnog een foutmelding hebt, voeg toe: `pip install --upgrade pip setuptools wheel` eerst.

## Stap 4 — Testprint vanuit terminal

```bash
cd ~/timini && source .venv/bin/activate
echo "Anna Nova test $(date +%H:%M:%S)" > /tmp/test.txt
python -m timini --bluetooth AA:BB:CC:DD:EE:FF --file /tmp/test.txt
```

**Verwacht**: `[✓] connected` + `[✓] printed` + testregel uit het printertje.

**Als het faalt met "device not found"**: `bluetoothctl connect AA:BB:CC:DD:EE:FF` eerst, dan `-m timini` opnieuw. Soms werkt een `sudo hciconfig hci0 reset` als BLE vast zit.

**Als het hangt op "scanning"**: NoeBrt-fork heeft `--printer-model`-flag; probeer `--printer-model MX06` of `--printer-model T02` (zie repo README voor volledige lijst).

## Stap 5 — PRINT_BREEDTE_PX meten

Verwachte waarde: **384 px** (58 mm standaard) of **576 px** (80 mm).

Test-methode:

```bash
python3 <<'PY'
from PIL import Image, ImageDraw
img = Image.new("1", (600, 60), 1)   # 600 px breed, moet afgekapt worden op werkelijke breedte
dr = ImageDraw.Draw(img)
# Lineaal: streep elke 32 px
for x in range(0, 600, 32):
    dr.line([(x, 0), (x, 59)], fill=0, width=1)
    dr.text((x+2, 2), str(x), fill=0)
img.save("/tmp/ruler.png")
print("saved /tmp/ruler.png (600x60)")
PY

python -m timini --bluetooth AA:BB:CC:DD:EE:FF --file /tmp/ruler.png
```

**Op het papier**: tel welke genummerde streep nog net past op de rand. Als 384 het laatste nummer is dat volledig zichtbaar is → `PRINT_BREEDTE_PX=384`. Als 576 → `PRINT_BREEDTE_PX=576`.

```bash
# In ~/anna-nova/.env of waar Anna's env staat:
echo "PRINT_BREEDTE_PX=384" | sudo tee -a /home/anna/anna-nova/.env
```

## Stap 6 — Integratie met `anna/printer.py`

De `printer.py` wrapper roept TiMini aan als subprocess. Pseudocode:

```python
import subprocess
def print_bon_png(png_path, mac):
    r = subprocess.run(
        ["/home/anna/timini/.venv/bin/python", "-m", "timini",
         "--bluetooth", mac, "--file", png_path],
        capture_output=True, timeout=25
    )
    return r.returncode == 0
```

Timeout 25 s is ruim (printen duurt 3-8 s per bon).

## Fallback A — funprint (Rust)

Als TiMini blijft hangen of niet pairt, probeer funprint:

```bash
# Rust-toolchain via rustup (eenmalig)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
source "$HOME/.cargo/env"

git clone https://github.com/Auxnon/funprint.git ~/funprint
cd ~/funprint && cargo build --release
./target/release/funprint --help
```

Geeft kleinere modellen-lijst maar snellere Rust binary.

## Fallback B — USB ESC/POS

Als BLE helemaal niet lukt: koop een USB-bonprinter met ESC/POS protocol. Werkt direct met `python-escpos`:

```bash
sudo apt install -y python3-escpos
lsusb | grep -iE "prolific|star|epson|rongta"   # typisch zie je een van deze
sudo usermod -a -G lp,dialout anna
```

Voor Anna's `printer.py` dan:

```python
from escpos.printer import Usb
p = Usb(0x0416, 0x5011)   # vendor/product id uit lsusb
p.image("/tmp/bon.png")
p.cut()
```

**Modellen die goed werken**: Rongta RP326-USE (~€40), Star TSP143III (~€200, duurder maar plug-and-play). Vermijd printers zonder duidelijke Linux-ondersteuning (Epson TM-T20III vereist aparte driver-install).

## Troubleshooting-tabel

| Symptoom | Oorzaak | Fix |
|---|---|---|
| `bluetoothctl scan` ziet niets | Telefoon-app actief | Sluit app, printer uit/aan |
| `pair` → `Failed: no reply` | Printer slaapt | Druk feed-knopje, probeer binnen 30s |
| Print start, stopt halverwege | Batterij leeg / lader slecht | Fresh USB-C lader, min 2A |
| Print heel flauw | Thermisch papier verlopen | Nieuw rolletje |
| Print 2x per keer | Driver probeert reconnect | Timeout verhogen in printer.py (25→40 s) |
| TiMini CLI werkt alleen eerste keer | BLE connection cache vast | `bluetoothctl disconnect MAC` tussen prints OF gebruik `--keep-connected` flag |

## Timebox

Bron 2 bouwstap 1 geeft **1 uur**. Als na 1 uur de testregel nog niet uit het printertje komt: **stop**, meld aan Jolanda, en overweeg direct de USB-ESC/POS fallback te bestellen.

## Sources

- [TiMini-Print (NoeBrt fork)](https://github.com/NoeBrt/TiMini-Print)
- [Dejniel/TiMini-Print origineel](https://github.com/Dejniel/TiMini-Print)
- [funprint (Rust)](https://github.com/Auxnon/funprint)
- [GitHub topic bluetooth-printer](https://github.com/topics/bluetooth-printer)
- [python-escpos docs](https://python-escpos.readthedocs.io/)
- [Raspberry Pi forum — bluetooth printer troubleshooting](https://forums.raspberrypi.com/viewtopic.php?t=288349)
