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
# Vast op 'anna' — als root ingelogd (zonder sudo) kwam alles anders in
# /home/root/ terecht. Overschrijven kan: sudo ANNA_USER=pi ./install.sh
ANNA_USER="${ANNA_USER:-anna}"
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
# Model Zoo v2.17 hoort bij HailoRT 4.23 (wat hailo-all op Trixie installeert).
# Als deze URLs 404'en, controleer handmatig op:
#   https://github.com/hailo-ai/hailo_model_zoo/tree/v2.17/docs/public_models/HAILO8L
HEF_BASE="https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.17.0/hailo8l"
SCRFD_HEF_URL="${HEF_BASE}/scrfd_2.5g.hef"
FACE_ATTR_HEF_URL="${HEF_BASE}/face_attr_resnet_v1_18.hef"

# Alle downloads: falen bij HTTP-fouten en blijven proberen bij wifi-hikjes
CURL="curl -fL --retry 15 --retry-delay 5 --retry-all-errors"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
log()  { printf "\n\033[1;36m» %s\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m!\033[0m %s\n" "$*"; }
die()  { printf "\n\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run dit script als root: sudo ./install.sh"
[[ "${ANNA_USER}" != "root" ]] || die "ANNA_USER mag niet root zijn"
id "${ANNA_USER}" >/dev/null 2>&1 || die "Gebruiker '${ANNA_USER}' bestaat niet — maak die eerst aan (Raspberry Pi Imager) of zet ANNA_USER=..."

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
# Geen full-upgrade: crashte de Pi bij het uitpakken van chromium + qt.
ok "apt-lijsten bijgewerkt"

# ---------------------------------------------------------------------------
log "2/10 — Basispakketten"
apt-get install -y \
  git curl wget ca-certificates \
  python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config \
  sqlite3 \
  dkms \
  alsa-utils libportaudio2 \
  libopenblas-dev \
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
[[ -f "${CFG}.anna-backup" ]] || cp "$CFG" "${CFG}.anna-backup"
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

# cmdline.txt: Pi 5 (KMS) negeert hdmi_cvt hierboven — de resolutie moet via
# video=. IPv6 uit: TLS-timeouts naar Mistral/GitHub over wifi.
CMDLINE=/boot/firmware/cmdline.txt
if [[ -f "$CMDLINE" ]]; then
  [[ -f "${CMDLINE}.anna-backup" ]] || cp "$CMDLINE" "${CMDLINE}.anna-backup"
  HDMI_NAME="HDMI-A-$((SCHERM_HDMI_PORT + 1))"
  grep -q "video=${HDMI_NAME}:" "$CMDLINE" || \
    sed -i "1 s|\$| video=${HDMI_NAME}:${SCHERM_WIDTH}x${SCHERM_HEIGHT}@${SCHERM_REFRESH}|" "$CMDLINE"
  grep -q 'ipv6.disable=1' "$CMDLINE" || sed -i '1 s|$| ipv6.disable=1|' "$CMDLINE"
  ok "cmdline.txt: video=${HDMI_NAME}:${SCHERM_WIDTH}x${SCHERM_HEIGHT} + ipv6.disable=1"
else
  warn "${CMDLINE} niet gevonden — scherm-resolutie en IPv6 niet aangepast"
fi

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
  $CURL -sS https://ollama.com/install.sh | sh
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
  sudo -u "${ANNA_USER}" $CURL \
    "https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz" \
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
  sudo -u "${ANNA_USER}" $CURL "${VOICE_BASE}/${VOICE_PATH}.onnx"      -o "${PIPER_DIR}/${PIPER_VOICE}.onnx"
  sudo -u "${ANNA_USER}" $CURL "${VOICE_BASE}/${VOICE_PATH}.onnx.json" -o "${PIPER_DIR}/${PIPER_VOICE}.onnx.json"
fi
ok "Piper + ${PIPER_VOICE} klaar"

# ---------------------------------------------------------------------------
log "7/10 — Hailo HEF-modellen downloaden (SCRFD + face_attr)"
sudo -u "${ANNA_USER}" mkdir -p "${MODELS_DIR}"
if [[ ! -f "${MODELS_DIR}/scrfd_2_5g.hef" ]]; then
  if ! sudo -u "${ANNA_USER}" $CURL "${SCRFD_HEF_URL}" -o "${MODELS_DIR}/scrfd_2_5g.hef"; then
    warn "SCRFD-URL faalde — download handmatig vanaf Hailo Model Zoo en zet in ${MODELS_DIR}/"
    rm -f "${MODELS_DIR}/scrfd_2_5g.hef"
  fi
fi
if [[ ! -f "${MODELS_DIR}/face_attr_resnet_v1_18.hef" ]]; then
  if ! sudo -u "${ANNA_USER}" $CURL "${FACE_ATTR_HEF_URL}" -o "${MODELS_DIR}/face_attr_resnet_v1_18.hef"; then
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
for f in anna-nova.py nachtslaap.py vision.py respeaker_doa.py anna-sync.py anna-enroll.py whisper_hailo.py; do
  install -o "${ANNA_USER}" -g "${ANNA_USER}" -m 644 \
    "${SCRIPT_DIR}/${f}" "${ANNA_DIR}/${f}"
done
chmod +x "${ANNA_DIR}/anna-nova.py" "${ANNA_DIR}/nachtslaap.py" \
         "${ANNA_DIR}/anna-sync.py" "${ANNA_DIR}/anna-enroll.py"

# edge_whisper (optioneel: Hailo-encoder voor Whisper, ~8× sneller).
# Niet-fataal als clone faalt — WHISPER_BACKEND=cpu blijft werken.
if [[ ! -d "${ANNA_DIR}/edge-whisper" ]]; then
  if sudo -u "${ANNA_USER}" git clone --depth 1 \
      https://github.com/ktomanek/edge_whisper "${ANNA_DIR}/edge-whisper" 2>/dev/null; then
    ok "edge-whisper gecloned (zet WHISPER_BACKEND=hailo in .env om te gebruiken)"
  else
    warn "edge-whisper clone faalde — WHISPER_BACKEND=cpu blijft default"
  fi
fi

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
StartLimitBurst=10
StartLimitIntervalSec=120

[Service]
Type=simple
User=${ANNA_USER}
WorkingDirectory=${ANNA_DIR}
EnvironmentFile=${ANNA_DIR}/.env
ExecStart=${VENV_DIR}/bin/python ${ANNA_DIR}/anna-nova.py
Restart=always
RestartSec=5

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

# Wifi power-save uit — veroorzaakte SSH-timeouts en mislukte downloads
cat > /etc/systemd/system/wifi-powersave-off.service <<EOF
[Unit]
Description=Wifi power-save uit (wlan0)
After=sys-subsystem-net-devices-wlan0.device
BindsTo=sys-subsystem-net-devices-wlan0.device

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/iw dev wlan0 set power_save off

[Install]
WantedBy=sys-subsystem-net-devices-wlan0.device
EOF

systemctl daemon-reload
systemctl enable anna-nova.service
systemctl enable anna-slaap.timer
systemctl enable anna-sync.timer
systemctl enable wifi-powersave-off.service
ok "services ingeschakeld (anna-nova + slaap-timer + sync-timer + wifi-powersave-off)"

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
