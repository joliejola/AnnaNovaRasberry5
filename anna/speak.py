"""Spreken — speelt vaste audio of live TTS af.

Droogloop-modus: print naar stdout + simuleert duur (sleep).
Live-modus (bouwstap 6): cascade audio/<id>.wav → Voxtral-TTS → Piper.
"""
from __future__ import annotations

import logging
import os
import sys
import time

log = logging.getLogger(__name__)

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"
# Simuleer afspeel-tempo: 2.4 woorden/sec is rustig-Nederlands
_WORDS_PER_S = 2.4
_SIM_FACTOR = float(os.environ.get("DROOGLOOP_SIM", "0.2"))  # maal werkelijke tijd


def _duur_schatting(tekst: str) -> float:
    return len(tekst.split()) / _WORDS_PER_S


def say(tekst: str, audio_id: str | None = None, blocking: bool = True) -> None:
    """Speel een zin af.

    `audio_id` wordt in bouwstap 6 gebruikt om een vast WAV-bestand te spelen;
    in droogloop printen we alleen.
    """
    if not tekst:
        return

    label = f"[anna:{audio_id}]" if audio_id else "[anna]"
    duur = _duur_schatting(tekst)
    if DROOGLOOP:
        sys.stdout.write(f"\033[1m{label}\033[0m {tekst}\n")
        sys.stdout.flush()
        if blocking:
            time.sleep(duur * _SIM_FACTOR)
        return

    _say_live(tekst, audio_id, blocking)


def _say_live(tekst: str, audio_id: str | None, blocking: bool) -> None:
    raise NotImplementedError(
        "Live-mode speak.py komt in bouwstap 6. Draai met DROOGLOOP=1."
    )
