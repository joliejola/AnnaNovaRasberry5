#!/usr/bin/env bash
# Optioneel: lokaal scherm aan Anna's kast via Chromium in kiosk-modus.
#
# Default is dat Anna's gezicht als webpagina op http://<pi-hostname>:8765/
# te zien is — open die URL op elke laptop/iPad/Mac Mini bij haar. Dat is
# meestal makkelijker én mooier (betere panelen, geen HDMI-gedoe).
#
# Alleen gebruiken als je ÉCHT een scherm aan de Pi zelf wilt hangen.
# Voegt cage (Wayland kiosk compositor) + chromium toe aan Trixie Lite,
# en een systemd-service die bij boot Anna's gezicht fullscreen weergeeft.
#
# Draai NA ./install.sh:
#   sudo ./install-screen.sh

set -euo pipefail

ANNA_USER="${SUDO_USER:-$USER}"
ANNA_UID=$(id -u "${ANNA_USER}")

log()  { printf "\n\033[1;36m» %s\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m!\033[0m %s\n" "$*"; }
die()  { printf "\n\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "sudo ./install-screen.sh"

log "cage + chromium installeren"
apt-get update
apt-get install -y cage chromium
ok "pakketten geïnstalleerd"

log "systemd-service voor Anna's gezicht (Chromium kiosk via cage)"
cat > /etc/systemd/system/anna-face.service <<EOF
[Unit]
Description=Anna Nova — gezicht op lokaal scherm (Chromium kiosk via cage)
After=anna-nova.service systemd-user-sessions.service
Wants=anna-nova.service

[Service]
Type=simple
User=${ANNA_USER}
Group=${ANNA_USER}
PAMName=login
TTYPath=/dev/tty1
StandardInput=tty
StandardOutput=tty
Environment=XDG_RUNTIME_DIR=/run/user/${ANNA_UID}
Environment=WLR_LIBINPUT_NO_DEVICES=1
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/cage -s -- /usr/bin/chromium \\
  --kiosk --noerrdialogs --disable-infobars \\
  --no-first-run --disable-features=TranslateUI \\
  --app=http://localhost:8765/
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Zorg dat getty op tty1 het podium vrij maakt voor cage
systemctl disable getty@tty1.service || true
loginctl enable-linger "${ANNA_USER}" || true

systemctl daemon-reload
systemctl enable anna-face.service
ok "anna-face.service ingeschakeld"

cat <<EOF

  Lokaal scherm geïnstalleerd. Reboot:

    sudo reboot

  Na reboot vult het aangesloten HDMI-scherm met Anna's gezicht.
  Zet 'r aan.

  Terugdraaien:
    sudo systemctl disable --now anna-face.service
    sudo systemctl enable getty@tty1.service
    sudo apt remove --purge cage chromium

EOF
