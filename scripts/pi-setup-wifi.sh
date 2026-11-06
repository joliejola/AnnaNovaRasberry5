#!/usr/bin/env bash
# TP-Link Archer T3U (Realtek RTL8812BU / RTL8822BU) driver + wifi-config.
#
# Dit script is al EEN KEER door Claude uitgevoerd op annanova (6 nov 2026).
# Het blijft hier voor reproduceerbaarheid: na een verse flash of op een
# tweede Pi draai je het opnieuw. Idempotent: herkent een al werkende state.
#
# Wat het doet:
#   1. Kernel headers + dkms + build-tools installeren
#   2. morrownr/88x2bu-20210702 driver clone + DKMS install (blacklist in-
#      kernel rtw88_8822bu driver die niet correct data transporteert)
#   3. NetworkManager connection kloneren van wlan0 → wlan1 (T3U gebruikt
#      zelfde wifi-password dat al in NM-keyring staat)
#   4. T3U voorrang geven: metric 50 vs 700 voor ingebouwde wlan0
#   5. Reboot nodig voor driver-switch — script vraagt het aan einde
#
# Gemeten resultaat op annanova:
#   wlan0 (ingebouwd): 91 kB/s download, nauwelijks bruikbaar
#   wlan1 (T3U):       17 MB/s download, Mistral latency ~100ms
#
# Draai: bash scripts/pi-setup-wifi.sh
set -euo pipefail

WLAN0_CONN="netplan-wlan0-Haaks boven"   # pas aan als jouw SSID anders heet
T3U_CONN="Haaks-boven-T3U"
T3U_METRIC=50
WLAN0_METRIC=700
DRIVER_REPO="https://github.com/morrownr/88x2bu-20210702"
DRIVER_DIR="/tmp/88x2bu"

echo "== T3U wifi-dongel setup =="
echo

# 1. Check T3U present
if ! lsusb | grep -qiE "tp-link.*archer|rtl8812bu|rtl8822bu"; then
  echo "[err] T3U niet gezien door lsusb. Steek de dongel in en draai opnieuw."
  exit 1
fi
echo "[ok]  T3U aanwezig volgens lsusb"

# 2. Headers + dkms
if ! dpkg -s dkms >/dev/null 2>&1; then
  echo "[apt] dkms + build tools + kernel headers..."
  sudo apt-get update -q
  sudo apt-get install -y dkms git build-essential bc linux-headers-"$(uname -r)"
else
  echo "[ok]  dkms al geïnstalleerd"
fi

# 3. Driver installeren als nog niet actief
if lsmod | grep -q "^88x2bu"; then
  echo "[ok]  88x2bu driver al geladen"
else
  echo "[dkms] morrownr/88x2bu clonen + installeren..."
  rm -rf "$DRIVER_DIR"
  git clone --depth 1 "$DRIVER_REPO" "$DRIVER_DIR"
  cd "$DRIVER_DIR"
  sudo ./install-driver.sh NoPrompt
  cd - > /dev/null
  echo "[!]   REBOOT nodig om oude rtw88_8822bu te vervangen door 88x2bu."
  NEEDS_REBOOT=1
fi

# 4. NetworkManager connection klonen
if nmcli -g NAME connection show | grep -qxF "$T3U_CONN"; then
  echo "[ok]  connection '$T3U_CONN' bestaat al"
else
  if ! nmcli -g NAME connection show | grep -qxF "$WLAN0_CONN"; then
    echo "[err] bron-connection '$WLAN0_CONN' niet gevonden."
    echo "      Pas WLAN0_CONN bovenin dit script aan of verbind eerst handmatig."
    exit 2
  fi
  echo "[nm]  clonen $WLAN0_CONN → $T3U_CONN..."
  sudo nmcli connection clone "$WLAN0_CONN" "$T3U_CONN"
  sudo nmcli connection modify "$T3U_CONN" connection.interface-name wlan1
  sudo nmcli connection modify "$T3U_CONN" connection.autoconnect yes
fi

# 5. Metric: T3U voorrang
echo "[nm]  route-metric: $T3U_CONN=$T3U_METRIC, wlan0=$WLAN0_METRIC"
sudo nmcli connection modify "$T3U_CONN" ipv4.route-metric "$T3U_METRIC"
sudo nmcli connection modify "$WLAN0_CONN" ipv4.route-metric "$WLAN0_METRIC"

# 6. Als driver al werkte: activeer connectie nu; anders na reboot
if [ -z "${NEEDS_REBOOT:-}" ]; then
  echo "[nm]  connectie activeren..."
  sudo nmcli connection up "$T3U_CONN" || echo "(activatie faalt — misschien is wlan1 nog niet klaar)"
  sudo nmcli connection up "$WLAN0_CONN" > /dev/null || true

  echo
  echo "== Snelheidsmeting =="
  echo "wlan1 (T3U):"
  timeout 15 curl -s -o /dev/null --interface wlan1 \
    -w "  download: %{speed_download} B/s in %{time_total}s\n" \
    "https://speed.cloudflare.com/__down?bytes=1000000" || echo "  wlan1 test faalt"
fi

echo
echo "== Klaar =="
if [ -n "${NEEDS_REBOOT:-}" ]; then
  echo "REBOOT nu: sudo reboot"
  echo "Na reboot zie je T3U actief via: nmcli dev status"
fi
