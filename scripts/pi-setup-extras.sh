#!/usr/bin/env bash
# Pi-extras voor bouwplan v2 — draai dit NA scripts/pi-setup.sh.
#
# Voegt toe (idempotent — veilig om nog eens te draaien):
#   - BlueZ + bleak      → bouwstap 1, Agodeo mini-printer via Bluetooth
#   - picamera2          → bouwstap 9, camera-capture
#   - python-escpos      → optionele printer-fallback
#
# (Vosk-model + vosk-pakket + venv + voices worden door scripts/pi-setup.sh
# geïnstalleerd. Draai die eerst.)
#
# Draai:  bash scripts/pi-setup-extras.sh
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
echo "== Anna Nova bouwplan v2 — Pi-extras =="
echo "   repo: $ROOT"
echo

if [ ! -d .venv ]; then
  echo "[fout] .venv ontbreekt — draai eerst scripts/pi-setup.sh"
  exit 1
fi

# ----- 1. BlueZ + bleak voor printer (bouwstap 1) ---------------------------
echo "== Bluetooth voor Agodeo mini-printer =="
if ! dpkg -s bluez >/dev/null 2>&1; then
  echo "[apt] bluez installeren..."
  sudo apt-get update -qq
  sudo apt-get install -y bluez libbluetooth-dev
else
  echo "[apt] bluez al aanwezig."
fi

# bleak is Python-only, pure userland
if ! "$ROOT/.venv/bin/python" -c "import bleak" 2>/dev/null; then
  echo "[bleak] pip install bleak..."
  "$ROOT/.venv/bin/pip" install -q bleak
else
  echo "[bleak] python-pakket al aanwezig."
fi

# anna user in bluetooth-groep
if ! id -nG anna | grep -qw bluetooth; then
  echo "[groep] anna toevoegen aan bluetooth..."
  sudo usermod -aG bluetooth anna
  echo "  → log opnieuw in of reboot voor dit effect"
else
  echo "[groep] anna al in bluetooth-groep."
fi

echo "[bluetooth] service-status:"
systemctl is-active bluetooth || sudo systemctl enable --now bluetooth
echo
echo "[bluetooth] koppel-flow (handmatig uitvoeren wanneer printertje aan is):"
echo "  bluetoothctl"
echo "    > power on"
echo "    > scan on          # wacht tot je Agodeo-printertje ziet"
echo "    > pair AA:BB:CC:DD:EE:FF"
echo "    > trust AA:BB:CC:DD:EE:FF"
echo "    > connect AA:BB:CC:DD:EE:FF"
echo "    > quit"
echo

# ----- 3. picamera2 + libcamera (bouwstap 9) --------------------------------
echo "== Camera (picamera2) =="
if ! dpkg -s python3-picamera2 >/dev/null 2>&1; then
  echo "[apt] python3-picamera2 installeren..."
  sudo apt-get install -y python3-picamera2 --no-install-recommends
else
  echo "[apt] python3-picamera2 al aanwezig."
fi
echo "[picamera] lijst detect:"
rpicam-hello --list-cameras 2>&1 | head -5 || echo "  (geen camera gezien — check lintkabel)"
echo

# ----- 4. ESC/POS fallback (optioneel) --------------------------------------
echo "== ESC/POS printer-fallback (optioneel) =="
if ! "$ROOT/.venv/bin/python" -c "import escpos" 2>/dev/null; then
  echo "[escpos] pip install python-escpos..."
  "$ROOT/.venv/bin/pip" install -q python-escpos
else
  echo "[escpos] al aanwezig."
fi

# ----- 5. Printer-breedte (eenmalig zelf invullen in .env) ------------------
echo
echo "== Klaar =="
echo
echo "Volgende stappen:"
echo "  1. Bluetoothctl voor printertje (zie boven)"
echo "  2. Print een testregel met TiMini-Print volgens docs/voorbereiding/PRINTER_SETUP.md"
echo "  3. Vul PRINT_BREEDTE_PX in .env in (meet met lineaal-PNG)"
echo "  4. Druk camera-kabel stevig vast als 'frontend timeout' blijft"
echo
echo "Live-test wake-detectie:"
echo "  DROOGLOOP=0 .venv/bin/python -c 'from anna.hear_live import WakeListener; import time; WakeListener(lambda t: print(\"wake:\", t)).start(); time.sleep(60)'"
