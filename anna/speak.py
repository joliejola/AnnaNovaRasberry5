"""Spreken — speelt vaste audio of live TTS af.

Droogloop-modus: print naar stdout + simuleert duur (sleep).
Live-modus cascade:
  1. audio/<id>.wav (vooraf gerenderd, 0 ms latency)
  2. ElevenLabs stream → mpg123 (als TTS_MODE=elevenlabs + API-key gezet)
  3. Piper lokaal → aplay (fallback bij netwerk-uitval)

Env:
  TTS_MODE               elevenlabs | piper   (default piper)
  ELEVENLABS_API_KEY     sk_...
  ELEVENLABS_VOICE_ID    bv o4g7vs6IQ4oCQwuS7wi7
  ELEVENLABS_MODEL       eleven_multilingual_v2
  ELEVENLABS_STABILITY   0.5
  ELEVENLABS_SIMILARITY  0.75
  PIPER_BIN              .venv/bin/piper of PATH
  PIPER_VOICE            .onnx-pad
  AUDIO_OUTPUT_DEVICE    ALSA-device-string voor aplay (default 'default')
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
DEFAULT_VOICE = ROOT / "assets" / "voices" / "nl_BE-nathalie-medium.onnx"

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"
_WORDS_PER_S = 2.4
_SIM_FACTOR = float(os.environ.get("DROOGLOOP_SIM", "0.2"))

AUDIO_OUT = os.environ.get("AUDIO_OUTPUT_DEVICE", "default")
PIPER_VOICE = Path(os.environ.get("PIPER_VOICE", "")) if os.environ.get("PIPER_VOICE") else DEFAULT_VOICE

TTS_MODE = os.environ.get("TTS_MODE", "piper").lower()
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVENLABS_STABILITY = float(os.environ.get("ELEVENLABS_STABILITY", "0.5"))
ELEVENLABS_SIMILARITY = float(os.environ.get("ELEVENLABS_SIMILARITY", "0.75"))
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"
ELEVENLABS_TIMEOUT = float(os.environ.get("ELEVENLABS_TIMEOUT_S", "8.0"))


def _duur_schatting(tekst: str) -> float:
    return len(tekst.split()) / _WORDS_PER_S


def say(tekst: str, audio_id: str | None = None, blocking: bool = True) -> None:
    """Speel een zin af.

    `audio_id` → als `audio/<id>.wav` bestaat, speel die. Anders live Piper-TTS.
    In droogloop: print + sleep.
    """
    if not tekst:
        return

    label = f"[anna:{audio_id}]" if audio_id else "[anna]"

    if DROOGLOOP:
        sys.stdout.write(f"\033[1m{label}\033[0m {tekst}\n")
        sys.stdout.flush()
        if blocking:
            time.sleep(_duur_schatting(tekst) * _SIM_FACTOR)
        return

    _say_live(tekst, audio_id, blocking)


def _say_live(tekst: str, audio_id: str | None, blocking: bool) -> None:
    # 1. vooraf gerenderd WAV (komt later; nu nog niet)
    if audio_id:
        wav = AUDIO_DIR / f"{audio_id}.wav"
        if wav.exists():
            _play_wav(wav, blocking=blocking)
            return
        log.debug("[speak] audio/%s.wav ontbreekt — live-TTS", audio_id)

    # 2. ElevenLabs (als geconfigureerd)
    if TTS_MODE == "elevenlabs" and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
        if _say_elevenlabs_live(tekst, blocking=blocking):
            return
        log.warning("[speak] ElevenLabs faalt — fallback Piper")

    # 3. live Piper TTS (fallback)
    try:
        _say_piper_live(tekst, blocking=blocking)
    except Exception as e:
        log.error("[speak] live Piper faalt: %s", e)


def _say_elevenlabs_live(tekst: str, blocking: bool = True) -> bool:
    """Stream ElevenLabs MP3 → mpg123. Return True op succes, False bij
    netwerkfout / ontbrekende binary → caller valt terug op Piper."""
    try:
        import requests  # lazy — droogloop werkt zonder
    except ImportError:
        log.error("[speak] python-requests ontbreekt")
        return False

    mpg = shutil.which("mpg123")
    if not mpg:
        log.error("[speak] mpg123 niet gevonden — sudo apt install mpg123")
        return False

    url = ELEVENLABS_URL.format(voice=ELEVENLABS_VOICE_ID)
    try:
        r = requests.post(
            url,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": tekst,
                "model_id": ELEVENLABS_MODEL,
                "voice_settings": {
                    "stability": ELEVENLABS_STABILITY,
                    "similarity_boost": ELEVENLABS_SIMILARITY,
                    "use_speaker_boost": True,
                },
            },
            stream=True,
            timeout=ELEVENLABS_TIMEOUT,
        )
    except Exception as e:
        log.error("[speak] ElevenLabs HTTP faalt: %s", e)
        return False

    if r.status_code != 200:
        log.error("[speak] ElevenLabs HTTP %d: %s", r.status_code, r.text[:200])
        return False

    # mpg123 decodeert MP3 → raw PCM naar stdout; aplay speelt dat af op
    # dezelfde route als Piper. Op Debian 13 + USB-mic actief weigert
    # mpg123 direct op het USB-speaker-device te schrijven (PipeWire-
    # conflict); via aplay-pipe werkt het wel omdat aplay pipewire-alsa
    # correct gebruikt.
    aplay_bin = shutil.which("aplay") or "aplay"
    try:
        mpg_proc = subprocess.Popen(
            # --rate/--stereo forceren: anders streamt mpg123 op source-SR en
            # vervormt aplay bij -r 44100 (klinkt snel/raar).
            [mpg, "-q", "--rate", "44100", "--stereo", "-s", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        aplay_proc = subprocess.Popen(
            [aplay_bin, "-q", "-D", AUDIO_OUT, "-f", "S16_LE", "-r", "44100", "-c", "2"],
            stdin=mpg_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        mpg_proc.stdout.close()
    except Exception as e:
        log.error("[speak] mpg123|aplay start faalt: %s", e)
        return False

    try:
        for chunk in r.iter_content(chunk_size=4096):
            if chunk:
                mpg_proc.stdin.write(chunk)
        mpg_proc.stdin.close()
        if blocking:
            aplay_proc.wait(timeout=30)
            mpg_proc.wait(timeout=5)
        return True
    except Exception as e:
        log.error("[speak] stream naar mpg123|aplay faalt: %s", e)
        for pr in (mpg_proc, aplay_proc):
            try:
                pr.kill()
            except Exception:
                pass
        return False


def _player_bin() -> list[str] | None:
    """Vind aplay of paplay. aplay heeft voorkeur op Pi (ALSA direct)."""
    for exe in ("aplay", "paplay"):
        if shutil.which(exe):
            if exe == "aplay":
                return [exe, "-q", "-D", AUDIO_OUT]
            return [exe]
    return None


def _play_wav(wav_pad: Path, blocking: bool = True) -> None:
    cmd = _player_bin()
    if not cmd:
        log.error("[speak] geen aplay / paplay gevonden")
        return
    cmd = cmd + [str(wav_pad)]
    if blocking:
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _find_piper_bin() -> str | None:
    env = os.environ.get("PIPER_BIN")
    if env and Path(env).exists():
        return env
    venv_bin = ROOT / ".venv" / "bin" / "piper"
    if venv_bin.exists():
        return str(venv_bin)
    return shutil.which("piper")


def _say_piper_live(tekst: str, blocking: bool = True) -> None:
    """Pipe-streamt tekst → Piper → aplay (realtime, geen tussen-bestand)."""
    piper = _find_piper_bin()
    if not piper:
        log.error("[speak] piper-binary niet gevonden — install piper-tts")
        return
    if not PIPER_VOICE.exists():
        log.error("[speak] voice-ONNX niet gevonden: %s", PIPER_VOICE)
        return

    player = _player_bin()
    if not player:
        log.error("[speak] geen aplay / paplay gevonden")
        return

    # Piper schrijft WAV naar stdout met --output-raw of -f /dev/stdout;
    # makkelijker: tijdelijk WAV, dan spelen
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name
    try:
        subprocess.run(
            [piper, "-m", str(PIPER_VOICE), "-f", tmp_wav],
            input=tekst.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        _play_wav(Path(tmp_wav), blocking=blocking)
    except subprocess.CalledProcessError as e:
        log.error("[speak] piper exit %d", e.returncode)
    except subprocess.TimeoutExpired:
        log.error("[speak] piper timeout")
    finally:
        try:
            os.unlink(tmp_wav)
        except Exception:
            pass
