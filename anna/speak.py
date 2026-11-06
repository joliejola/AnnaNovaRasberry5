"""Spreken — speelt vaste audio of live TTS af.

Droogloop-modus: print naar stdout + simuleert duur (sleep).
Live-modus: cascade: audio/<id>.wav (vooraf gerenderd) → live Piper TTS → stil.

Afspelen gaat via `aplay` of `paplay`; eerste gevonden wint.
Env: PIPER_BIN (default .venv/bin/piper of PATH), PIPER_VOICE (.onnx-pad),
AUDIO_OUTPUT_DEVICE (voor aplay ALSA-device-string, default 'default').
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
    # 1. vooraf gerenderd WAV
    if audio_id:
        wav = AUDIO_DIR / f"{audio_id}.wav"
        if wav.exists():
            _play_wav(wav, blocking=blocking)
            return
        log.warning("[speak] audio/%s.wav ontbreekt — val terug op live-TTS", audio_id)

    # 2. live Piper TTS
    try:
        _say_piper_live(tekst, blocking=blocking)
    except Exception as e:
        log.error("[speak] live Piper faalt: %s", e)


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
