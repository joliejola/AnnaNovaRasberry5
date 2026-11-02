"""
Whisper via Hailo-8L encoder (ervaring: ~250ms refresh, ~8× sneller dan CPU).

Dit is een adapter rond de community-port `ktomanek/edge_whisper`. Als die
niet geïnstalleerd is of de HEF ontbreekt, valt deze module graceful terug
op faster-whisper CPU — exact dezelfde API, dus de hoofdlus merkt niets.

Enable in .env:
    WHISPER_BACKEND=hailo

Dependencies:
    git clone https://github.com/ktomanek/edge_whisper ~/anna-nova/edge-whisper
    # HEF-file voor whisper-base-encoder downloaden van Hailo Model Zoo

Als Hailo-pad faalt tijdens inference: automatische fallback naar CPU
voor die ene call. Bij herhaalde fouten → fallback-flag permanent.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

log = logging.getLogger("anna.whisper_hailo")

EDGE_WHISPER_DIR = os.environ.get(
    "EDGE_WHISPER_DIR", str(Path.home() / "anna-nova/edge-whisper")
)
WHISPER_HEF = os.environ.get(
    "WHISPER_HEF", str(Path.home() / "anna-nova/models/whisper_base_encoder.hef")
)
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "base")
WHISPER_LANG = os.environ.get("WHISPER_LANGUAGE", "nl")


class _HailoWhisper:
    """Thin wrapper die edge_whisper's encoder (op Hailo) combineert met de
    normale openai-whisper decoder (op CPU)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._encoder = None
        self._decoder_pipeline = None
        self._load_ok = False
        self._load()

    def _load(self):
        # Zorg dat edge_whisper op het Python-pad staat
        if EDGE_WHISPER_DIR not in sys.path:
            sys.path.insert(0, EDGE_WHISPER_DIR)
        if not Path(WHISPER_HEF).exists():
            raise FileNotFoundError(f"WHISPER_HEF ontbreekt: {WHISPER_HEF}")
        try:
            from edge_whisper import HailoWhisperPipeline  # type: ignore
        except Exception as e:
            raise ImportError(
                f"edge_whisper niet gevonden in {EDGE_WHISPER_DIR}. "
                "Clone: git clone https://github.com/ktomanek/edge_whisper "
                f"{EDGE_WHISPER_DIR}"
            ) from e
        self._decoder_pipeline = HailoWhisperPipeline(
            hef_path=WHISPER_HEF,
            model_name=WHISPER_MODEL_NAME,
            language=WHISPER_LANG,
        )
        self._load_ok = True
        log.info(f"edge_whisper geladen: {WHISPER_MODEL_NAME} / nl")

    def transcribe(self, audio, language=None, vad_filter=False, beam_size=1):
        """Zelfde signature als faster-whisper. Returnt (segments, info)."""
        with self._lock:
            text = self._decoder_pipeline.transcribe(audio, language=language or WHISPER_LANG)
        class _Seg:
            def __init__(self, t): self.text = t
        return [_Seg(text)], None


# ----- Public API -----------------------------------------------------------
def load_asr():
    """Return een object met .transcribe(audio, …) methode.

    Probeert eerst Hailo. Faalt → faster-whisper (CPU) als fallback.
    """
    backend = os.environ.get("WHISPER_BACKEND", "cpu").lower()
    if backend == "hailo":
        try:
            return _HailoWhisper()
        except Exception as e:
            log.warning(f"Hailo-whisper laden faalde ({e}) — val terug op CPU")
    # CPU fallback
    from faster_whisper import WhisperModel
    return WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
