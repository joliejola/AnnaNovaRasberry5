#!/usr/bin/env bash
# Anna Nova — installer voor Raspberry Pi 5 + AI HAT+ 13 TOPS + Arducam OV5647
#
# Flash Raspberry Pi OS 64-bit Trixie Lite op een microSD, boot de Pi,
# log in, zet deze map (anna-nova-installer) op de Pi, en run:
#
#   sudo ./install.sh
#
# Na afloop: reboot. Anna sluimert dan tot iemand "Hoi Anna Nova" zegt.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuratie — pas aan als je andere paden/user wilt
# ---------------------------------------------------------------------------
ANNA_USER="${SUDO_USER:-$USER}"
ANNA_HOME="/home/${ANNA_USER}"
ANNA_DIR="${ANNA_HOME}/anna-nova"
VENV_DIR="${ANNA_DIR}/venv"
MODELS_DIR="${ANNA_DIR}/models"
MODEL_LOCAL="phi3:mini"
PIPER_VOICE="nl_NL-mls_7432-low"  # Jolanda's keuze — zachte MLS-stem speaker 7432

# -----------------------------------------------------------------------------
# Scherm — Waveshare 4" Square HDMI (720×720)
# -----------------------------------------------------------------------------
# Als je een ander scherm gebruikt, pas hier aan. SCHERM_HDMI_PORT = 1 betekent
# de tweede HDMI-poort (HDMI-A-2) op de Pi 5, zoals Jolanda in haar oude Pi 4
# config had staan. Zet op 0 voor de eerste poort (HDMI-A-1).
SCHERM_WIDTH=720
SCHERM_HEIGHT=720
SCHERM_HDMI_PORT=1
SCHERM_REFRESH=60
SCHERM_BOOST=7      # 0-11 — hoger = sterker HDMI-signaal (voor lange kabels)

# Hailo Model Zoo HEF-URLs voor Hailo-8L
# Bronnen: hailo-ai/hailo_model_zoo releases.
# Als deze URLs 404'en, controleer handmatig op:
#   https://github.com/hailo-ai/hailo_model_zoo/tree/master/docs/public_models/HAILO8L
SCRFD_HEF_URL="https://hailo-csdata.s3.eu-west-2.amazonaws.com/public_models/hailo8l/FaceDetection/scrfd_2_5g/pretrained/2024-06-21/scrfd_2_5g.hef"
FACE_ATTR_HEF_URL="https://hailo-csdata.s3.eu-west-2.amazonaws.com/public_models/hailo8l/FaceAttribute/face_attr_resnet_v1_18/pretrained/2024-06-20/face_attr_resnet_v1_18.hef"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
log()  { printf "\n\033[1;36m» %s\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m!\033[0m %s\n" "$*"; }
die()  { printf "\n\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run dit script als root: sudo ./install.sh"

# ---------------------------------------------------------------------------
log "Omgevingscheck"
. /etc/os-release
if [[ "${VERSION_CODENAME:-}" != "trixie" ]]; then
  warn "OS-codenaam '${VERSION_CODENAME:-onbekend}' — getest op Trixie. Hailo-all vereist Trixie per nov 2026."
fi
[[ "$(uname -m)" == "aarch64" ]] || die "Dit moet een 64-bit Pi 5 zijn (aarch64). Gevonden: $(uname -m)"
ok "OS: ${PRETTY_NAME}  ·  arch: $(uname -m)  ·  user: ${ANNA_USER}"

# ---------------------------------------------------------------------------
log "1/10 — Systeem updaten"
apt-get update
apt-get -y full-upgrade
ok "apt up-to-date"

# ---------------------------------------------------------------------------
log "2/10 — Basispakketten"
apt-get install -y \
  git curl wget ca-certificates \
  python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config \
  sqlite3 \
  dkms \
  alsa-utils \
  libatlas-base-dev libopenblas-dev \
  libusb-1.0-0 libhidapi-hidraw0 \
  jq
ok "basispakketten klaar"

# ---------------------------------------------------------------------------
log "3/10 — Hailo-stack (dkms + hailo-all)"
apt-get install -y hailo-all
ok "hailo-all geïnstalleerd"

# ---------------------------------------------------------------------------
log "4/10 — config.txt + EEPROM"
CFG=/boot/firmware/config.txt
cp -n "$CFG" "${CFG}.anna-backup"
grep -q '^camera_auto_detect=0'   "$CFG" || echo 'camera_auto_detect=0'   >> "$CFG"
grep -q '^dtoverlay=ov5647,cam0'  "$CFG" || echo 'dtoverlay=ov5647,cam0'  >> "$CFG"
grep -q '^usb_max_current_enable=1' "$CFG" || echo 'usb_max_current_enable=1' >> "$CFG"

# Scherm: Waveshare 4" Square HDMI
if ! grep -q "hdmi_cvt=${SCHERM_WIDTH} ${SCHERM_HEIGHT}" "$CFG"; then
  cat >> "$CFG" <<EOF

# Anna Nova — Waveshare 4" Square HDMI (${SCHERM_WIDTH}×${SCHERM_HEIGHT})
[HDMI:${SCHERM_HDMI_PORT}]
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=${SCHERM_WIDTH} ${SCHERM_HEIGHT} ${SCHERM_REFRESH} 6 0 0 0
hdmi_drive=2
config_hdmi_boost=${SCHERM_BOOST}

[all]
EOF
  ok "scherm-config toegevoegd (HDMI:${SCHERM_HDMI_PORT}, ${SCHERM_WIDTH}×${SCHERM_HEIGHT}@${SCHERM_REFRESH}Hz)"
else
  ok "scherm-config bestaat al"
fi

ok "config.txt bijgewerkt"

if command -v rpi-eeprom-config >/dev/null; then
  CUR=$(rpi-eeprom-config || true)
  if ! echo "$CUR" | grep -q '^PSU_MAX_CURRENT=5000'; then
    TMP=$(mktemp)
    echo "$CUR" | grep -v '^PSU_MAX_CURRENT=' > "$TMP"
    echo "PSU_MAX_CURRENT=5000" >> "$TMP"
    rpi-eeprom-config --apply "$TMP" || warn "EEPROM-update faalde"
    rm -f "$TMP"
    ok "EEPROM PSU_MAX_CURRENT=5000"
  else
    ok "EEPROM al correct"
  fi
fi

# ---------------------------------------------------------------------------
log "5/10 — Ollama + model (${MODEL_LOCAL})"
if ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
systemctl enable --now ollama || true
# Wacht tot ollama API bereikbaar is (max 30s)
for i in {1..30}; do
  if curl -fs http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
sudo -u "${ANNA_USER}" ollama pull "${MODEL_LOCAL}"
ok "Ollama + ${MODEL_LOCAL} klaar"

# ---------------------------------------------------------------------------
log "6/10 — Piper (TTS) + Nederlandse stem"
PIPER_DIR="${ANNA_DIR}/piper"
sudo -u "${ANNA_USER}" mkdir -p "${PIPER_DIR}"
if [[ ! -x "${PIPER_DIR}/piper/piper" ]]; then
  sudo -u "${ANNA_USER}" curl -L \
    "https://github.com/rhasspy/piper/releases/latest/download/piper_arm64.tar.gz" \
    -o "${PIPER_DIR}/piper.tgz"
  sudo -u "${ANNA_USER}" tar -xzf "${PIPER_DIR}/piper.tgz" -C "${PIPER_DIR}"
  rm -f "${PIPER_DIR}/piper.tgz"
fi

VOICE_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL"
case "${PIPER_VOICE}" in
  nl_NL-mls_7432-low)  VOICE_PATH="mls_7432/low/nl_NL-mls_7432-low" ;;
  nl_NL-mls_5809-low)  VOICE_PATH="mls_5809/low/nl_NL-mls_5809-low" ;;
  nl_NL-mls-medium)    VOICE_PATH="mls/medium/nl_NL-mls-medium" ;;
  nl_NL-alex-low)      VOICE_PATH="alex/low/nl_NL-alex-low" ;;
  nl_NL-pim-medium)    VOICE_PATH="pim/medium/nl_NL-pim-medium" ;;
  nl_NL-ronnie-x_low)  VOICE_PATH="ronnie/x_low/nl_NL-ronnie-x_low" ;;
  *)                   VOICE_PATH="mls_7432/low/nl_NL-mls_7432-low" ;;
esac
if [[ ! -f "${PIPER_DIR}/${PIPER_VOICE}.onnx" ]]; then
  sudo -u "${ANNA_USER}" curl -L "${VOICE_BASE}/${VOICE_PATH}.onnx"      -o "${PIPER_DIR}/${PIPER_VOICE}.onnx"
  sudo -u "${ANNA_USER}" curl -L "${VOICE_BASE}/${VOICE_PATH}.onnx.json" -o "${PIPER_DIR}/${PIPER_VOICE}.onnx.json"
fi
ok "Piper + ${PIPER_VOICE} klaar"

# ---------------------------------------------------------------------------
log "7/10 — Hailo HEF-modellen downloaden (SCRFD + face_attr)"
sudo -u "${ANNA_USER}" mkdir -p "${MODELS_DIR}"
if [[ ! -f "${MODELS_DIR}/scrfd_2_5g.hef" ]]; then
  if ! sudo -u "${ANNA_USER}" curl -fL "${SCRFD_HEF_URL}" -o "${MODELS_DIR}/scrfd_2_5g.hef"; then
    warn "SCRFD-URL faalde — download handmatig vanaf Hailo Model Zoo en zet in ${MODELS_DIR}/"
    rm -f "${MODELS_DIR}/scrfd_2_5g.hef"
  fi
fi
if [[ ! -f "${MODELS_DIR}/face_attr_resnet_v1_18.hef" ]]; then
  if ! sudo -u "${ANNA_USER}" curl -fL "${FACE_ATTR_HEF_URL}" -o "${MODELS_DIR}/face_attr_resnet_v1_18.hef"; then
    warn "face_attr-URL faalde — niet kritiek, mood-hint blijft 'neutraal'"
    rm -f "${MODELS_DIR}/face_attr_resnet_v1_18.hef"
  fi
fi
[[ -f "${MODELS_DIR}/scrfd_2_5g.hef" ]] && ok "SCRFD aanwezig" || warn "SCRFD ontbreekt — vision valt terug op blind-aanwezig"

# ---------------------------------------------------------------------------
log "8/10 — Python venv + packages"
sudo -u "${ANNA_USER}" mkdir -p "${ANNA_DIR}"
sudo -u "${ANNA_USER}" python3 -m venv "${VENV_DIR}" --system-site-packages
sudo -u "${ANNA_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel
sudo -u "${ANNA_USER}" "${VENV_DIR}/bin/pip" install \
  faster-whisper \
  sounddevice \
  numpy \
  requests \
  silero-vad \
  pyusb \
  opencv-python-headless \
  resemblyzer \
  librosa
# picamera2 en hailo_platform komen uit de system packages (--system-site-packages)
ok "venv klaar in ${VENV_DIR}"

log "8b/10 — Whisper + Silero VAD pre-fetchen (eenmalig, scheelt eerste-boot-wachten)"
sudo -u "${ANNA_USER}" "${VENV_DIR}/bin/python" -c '
from faster_whisper import WhisperModel
WhisperModel("small", device="cpu", compute_type="int8")
from silero_vad import load_silero_vad
load_silero_vad()
print("models cached")
' 2>&1 | tail -3 || warn "pre-fetch faalde — modellen worden bij eerste gebruik alsnog gedownload"

# ---------------------------------------------------------------------------
log "9/10 — Anna-scripts + persona + webpagina's + database"
for f in anna-nova.py nachtslaap.py vision.py respeaker_doa.py anna-sync.py anna-enroll.py; do
  install -o "${ANNA_USER}" -g "${ANNA_USER}" -m 644 \
    "${SCRIPT_DIR}/${f}" "${ANNA_DIR}/${f}"
done
chmod +x "${ANNA_DIR}/anna-nova.py" "${ANNA_DIR}/nachtslaap.py" \
         "${ANNA_DIR}/anna-sync.py" "${ANNA_DIR}/anna-enroll.py"

# Persona (bewerk-vriendelijk — Jolanda schrijft hier Anna's kern)
if [[ ! -f "${ANNA_DIR}/persona.md" ]]; then
  install -o "${ANNA_USER}" -g "${ANNA_USER}" -m 644 \
    "${SCRIPT_DIR}/persona.md" "${ANNA_DIR}/persona.md"
  ok "persona.md neergezet — bewerk tijdens testen, dan 'systemctl restart anna-nova'"
else
  ok "persona.md bestaat al — ongewijzigd gelaten"
fi

# Webpagina's (lokaal scherm + galerij)
sudo -u "${ANNA_USER}" mkdir -p "${ANNA_DIR}/web" "${ANNA_DIR}/photos"
for f in face.html gallery.html; do
  if [[ -f "${SCRIPT_DIR}/web/${f}" ]]; then
    install -o "${ANNA_USER}" -g "${ANNA_USER}" -m 644 \
      "${SCRIPT_DIR}/web/${f}" "${ANNA_DIR}/web/${f}"
  fi
done
ok "web/ en photos/ klaar"

if [[ ! -f "${ANNA_DIR}/.env" ]]; then
  install -o "${ANNA_USER}" -g "${ANNA_USER}" -m 600 \
    "${SCRIPT_DIR}/config.sample.env" "${ANNA_DIR}/.env"
  # Patch /home/pi/ paden naar het echte user-home, als dat anders is
  if [[ "${ANNA_HOME}" != "/home/pi" ]]; then
    sed -i "s|/home/pi/|${ANNA_HOME}/|g" "${ANNA_DIR}/.env"
    ok ".env paden aangepast voor user '${ANNA_USER}' (${ANNA_HOME})"
  fi
  warn "Standaard-config neergezet in ${ANNA_DIR}/.env — bewerk voor andere stem/model/key"
fi

# udev-regel zodat de ReSpeaker USB-device door user leesbaar is (voor DoA)
cat > /etc/udev/rules.d/99-respeaker.rules <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="20b1", MODE="0666"
EOF
udevadm control --reload-rules
udevadm trigger

sudo -u "${ANNA_USER}" sqlite3 "${ANNA_DIR}/anna.db" <<'SQL'
CREATE TABLE IF NOT EXISTS faces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  embedding BLOB NOT NULL,
  first_seen_today TEXT NOT NULL,
  last_seen_today  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fragments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  face_id INTEGER,
  ts TEXT NOT NULL,
  text TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('visitor','anna'))
);
CREATE TABLE IF NOT EXISTS persona_history (
  date TEXT PRIMARY KEY,
  block TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voices (
  name TEXT PRIMARY KEY,
  embedding BLOB NOT NULL,
  enrolled_at TEXT NOT NULL
);
INSERT OR IGNORE INTO persona_history (date, block) VALUES (
  date('now', '-1 day'),
  'Je bent Anna Nova. Je bent net wakker. Je oog is oud maar scherp. Je weet nog niet wat voor dag het wordt.'
);
SQL
ok "scripts + database klaar in ${ANNA_DIR}"

# ---------------------------------------------------------------------------
log "10/10 — systemd units"

cat > /etc/systemd/system/anna-nova.service <<EOF
[Unit]
Description=Anna Nova (sluimert tot "Hoi Anna Nova")
After=network-online.target ollama.service sound.target
Wants=network-online.target ollama.service

[Service]
Type=simple
User=${ANNA_USER}
WorkingDirectory=${ANNA_DIR}
EnvironmentFile=${ANNA_DIR}/.env
ExecStart=${VENV_DIR}/bin/python ${ANNA_DIR}/anna-nova.py
Restart=always
RestartSec=5
StartLimitBurst=10
StartLimitIntervalSec=120
RuntimeWatchdogSec=30

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/anna-slaap.service <<EOF
[Unit]
Description=Anna Nova — nachtslaap (reflectie + geheugen leegmaken)
After=ollama.service

[Service]
Type=oneshot
User=${ANNA_USER}
WorkingDirectory=${ANNA_DIR}
EnvironmentFile=${ANNA_DIR}/.env
ExecStart=${VENV_DIR}/bin/python ${ANNA_DIR}/nachtslaap.py
EOF

cat > /etc/systemd/system/anna-slaap.timer <<EOF
[Unit]
Description=Anna Nova slaapcyclus (dagelijks om 03:00)

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
Unit=anna-slaap.service

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/anna-sync.service <<EOF
[Unit]
Description=Anna Nova — foto-sync naar extern scherm (SFTP/rsync)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${ANNA_USER}
WorkingDirectory=${ANNA_DIR}
EnvironmentFile=${ANNA_DIR}/.env
ExecStart=${VENV_DIR}/bin/python ${ANNA_DIR}/anna-sync.py
EOF

cat > /etc/systemd/system/anna-sync.timer <<EOF
[Unit]
Description=Anna Nova foto-sync (elke 15 minuten als PHOTO_UPLOAD_ENABLED=true)

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
Unit=anna-sync.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable anna-nova.service
systemctl enable anna-slaap.timer
systemctl enable anna-sync.timer
ok "services ingeschakeld (anna-nova + slaap-timer + sync-timer)"

# ---------------------------------------------------------------------------
log "Installatie klaar"
cat <<EOF

  Anna Nova staat klaar in: ${ANNA_DIR}
  Config:                   ${ANNA_DIR}/.env

  Volgende stap:

    sudo reboot

  Na reboot: Anna sluimert. Zeg "Hoi Anna Nova" om haar wakker te maken.

  Status / logs:
    systemctl status anna-nova
    journalctl -u anna-nova -f

  Hardware-check:
    hailortcli fw-control identify     # moet HAILO8L zeggen
    rpicam-hello -t 0                   # stel scherpstelling af
    arecord -l / aplay -l               # ReSpeaker zichtbaar?

  Zet 'r aan.

EOF
