#!/usr/bin/env bash
# Pi-setup voor bouwplan v2 — draai dit op de Pi nadat je `git pull`.
#
# Installeert Python-deps + ALSA/PortAudio + rendert de 32 WAV-bestanden
# met Piper nathalie. Idempotent: hergebruikt bestaande venv/wav's.
#
# Draai: bash scripts/pi-setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
echo "== Anna Nova bouwplan v2 — Pi-setup =="
echo "   repo: $ROOT"
echo

# 1. apt deps voor sounddevice/piper
if ! dpkg -s portaudio19-dev >/dev/null 2>&1; then
  echo "[apt] portaudio19-dev + libsndfile1 installeren..."
  sudo apt-get update -qq
  sudo apt-get install -y portaudio19-dev libsndfile1
else
  echo "[apt] portaudio19-dev al geïnstalleerd."
fi

# 2. venv
if [ ! -d .venv ]; then
  echo "[venv] aanmaken..."
  python3 -m venv .venv
fi
echo "[venv] pip + requirements..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -q -r requirements.txt

# 3. voices aanwezig?
if [ ! -f assets/voices/nl_BE-nathalie-medium.onnx ]; then
  echo "[voice] nathalie-medium ontbreekt — git pull eerst"
  exit 1
fi

# 4. Vosk NL-small model (voor offline wake-detect in hear_live.py)
VOSK_DIR="models/vosk-model-small-nl-0.22"
if [ ! -d "$VOSK_DIR" ]; then
  echo "[vosk] downloaden NL-small-model (~40 MB)..."
  mkdir -p models
  curl -sL -o /tmp/vosk-nl.zip https://alphacephei.com/vosk/models/vosk-model-small-nl-0.22.zip
  unzip -q /tmp/vosk-nl.zip -d models/
  rm /tmp/vosk-nl.zip
  echo "[vosk] model bij $VOSK_DIR"
else
  echo "[vosk] model al aanwezig in $VOSK_DIR"
fi

# 5. audio renderen
if [ ! -d audio ] || [ "$(ls audio/*.wav 2>/dev/null | wc -l)" -lt 30 ]; then
  echo "[audio] rendert 32 WAV-files via Piper nathalie..."
  .venv/bin/python tools/render_audio.py
else
  echo "[audio] al $(ls audio/*.wav | wc -l) bestanden aanwezig — skip."
fi

# 6. Toon devices
echo
echo "== Audio-devices =="
.venv/bin/python -c "import sounddevice as sd; print(sd.query_devices())" || echo "(sounddevice test faalt — check portaudio install)"

echo
echo "== Klaar =="
echo
echo "Live-test:        DROOGLOOP=0 .venv/bin/python -m anna.main"
echo "Droogloop:        DROOGLOOP=1 .venv/bin/python -m anna.main"
echo "Scherm:           http://localhost:8765/"
echo
echo "Zet MISTRAL_API_KEY in .env voor live brain + Voxtral-ASR."
echo "Zet VOSK_MODEL_PATH in .env als Vosk-model ergens anders staat dan models/vosk-model-small-nl-0.22"
