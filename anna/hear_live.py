"""Live-modus horen op de Pi — Vosk-wake + Voxtral/Whisper transcriptie.

Twee-laags luisteren:

1. **Vosk** (offline, lokaal) — continu wake-woord detecteren. Lichtgewicht
   (~40 MB NL-small-model), geen wifi, <200 ms latency. Activeert zodra
   "hoi anna nova" (of een ASR-mishoor-variant via `hear.wake_match`) in
   het Vosk-partial resultaat opduikt.

2. **Voxtral** (Mistral cloud) — ná wake, voor volledige zins-transcriptie
   tijdens LUISTEREN-state. ~0.5-1.5 s per zin. Fallback: faster-whisper
   tiny lokaal (~5-7 s per zin op Pi CPU) als Voxtral faalt of timeout.

Deze module wordt alleen op de Pi geïmporteerd. In droogloop blijft
`hear.luister_wake()` / `hear.luister_spraak()` werken via stdin.

VAD-throttle 128 ms (uit oude anna-nova.py:826) → Pi CPU in sluimer blijft
~20% ipv 140%.

Install Pi-deps (één keer):
    pip install vosk sounddevice scipy numpy requests
    mkdir -p ~/anna-nova/models
    cd ~/anna-nova/models
    wget https://alphacephei.com/vosk/models/vosk-model-small-nl-0.22.zip
    unzip vosk-model-small-nl-0.22.zip
"""
from __future__ import annotations

import io
import json
import logging
import os
import queue
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from anna import hear as _hear  # voor wake_match / sleep_match / Event

log = logging.getLogger(__name__)

# ----- Config (uit .env) ----------------------------------------------------
VOSK_MODEL_PATH = os.environ.get(
    "VOSK_MODEL_PATH",
    str(Path.home() / "anna-nova/models/vosk-model-small-nl-0.22"),
)
AUDIO_INPUT_DEVICE = os.environ.get("AUDIO_INPUT_DEVICE", "default")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL_VOXTRAL = os.environ.get("VOXTRAL_MODEL", "voxtral-mini-latest")
WHISPER_LANG = os.environ.get("WHISPER_LANGUAGE", "nl")
ASR_ENGINE = os.environ.get("ASR_ENGINE", "voxtral").lower()  # voxtral | whisper

# Audio
SAMPLE_RATE = 16000     # Vosk + VAD + Whisper verwachten dit
BLOCK_MS = 32           # ~2 ms per sample @ 16 kHz, dus 512 samples per chunk
VAD_EVERY_N = 4         # VAD-check elke 4e chunk = ~128 ms (CPU-fix)
END_OF_TURN_SILENCE = float(os.environ.get("END_OF_TURN_SILENCE", "1.2"))
MAX_LISTEN_MS = int(os.environ.get("MAX_LISTEN_MS", "60000"))

# Voxtral timeouts
VOXTRAL_CONNECT_S = 5
VOXTRAL_READ_S = 30


# ----- Lazy imports (alleen bij live-use) -----------------------------------

def _load_vosk():
    try:
        from vosk import Model, KaldiRecognizer  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "vosk niet geïnstalleerd. Op Pi: pip install vosk"
        ) from e
    if not Path(VOSK_MODEL_PATH).exists():
        raise RuntimeError(
            f"Vosk model ontbreekt op {VOSK_MODEL_PATH}. "
            "Download: wget https://alphacephei.com/vosk/models/vosk-model-small-nl-0.22.zip"
        )
    return Model(VOSK_MODEL_PATH), KaldiRecognizer


def _load_sounddevice():
    try:
        import sounddevice as sd  # type: ignore
        import numpy as np  # type: ignore
        from scipy import signal as scisig  # type: ignore
    except ImportError as e:
        raise RuntimeError("Pi-audio deps ontbreken: pip install sounddevice numpy scipy") from e
    return sd, np, scisig


def _resolve_input_device(spec: str, sd) -> Optional[int]:
    """Zoek sounddevice input-index op basis van naam (bv 'PD100X') of index."""
    if not spec or spec.lower() in ("default", "none", ""):
        return None
    try:
        return int(spec)
    except ValueError:
        pass
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and spec.lower() in d["name"].lower():
            log.info(f"audio device: '{d['name']}' (index {i}) voor '{spec}'")
            return i
    log.warning(f"audio device '{spec}' niet gevonden; default gebruikt")
    return None


# ----- Vosk wake-listener (continu, lokaal, lichtgewicht) -------------------

class WakeListener:
    """Continu luisteren naar wake-phrase via Vosk. Geen wifi, lage CPU."""

    def __init__(self, on_wake: Callable[[str], None]):
        self.on_wake = on_wake
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="wake-listener")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        model, KaldiRecognizer = _load_vosk()
        sd, np, _scisig = _load_sounddevice()

        dev = _resolve_input_device(AUDIO_INPUT_DEVICE, sd)
        native_sr = SAMPLE_RATE
        try:
            info = sd.query_devices(dev, "input") if dev is not None else sd.query_devices(kind="input")
            native_sr = int(info["default_samplerate"])
        except Exception:
            pass

        import json as _json
        # Beperkt vocabulair = veel accurater herkennen van wake-phrase.
        # Vosk NL-small is zonder grammar te zwak voor "hoi anna nova" (hoort
        # het bv als "op zoek te gaan maken samen"). Met deze grammar mag Vosk
        # alleen wake-woorden herkennen; alles anders → leeg partial.
        _wake_grammar = _json.dumps([
            "hoi anna nova",
            "hoi anna",
            "hallo anna nova",
            "hallo anna",
            "hey anna nova",
            "hey anna",
            "anna nova",
            "ohana nova",
            "ohana",
            "anna",
            "hoi",
            "hallo",
            "hey",
            "word wakker anna",
            "wakker",
            "[unk]",
        ])
        rec = KaldiRecognizer(model, SAMPLE_RATE, _wake_grammar)
        rec.SetWords(False)

        q: queue.Queue = queue.Queue()

        def cb(indata, frames, time_info, status):
            if status:
                log.debug(f"wake-audio-status: {status}")
            chunk = indata[:, 0].copy()
            if native_sr != SAMPLE_RATE:
                n_out = int(len(chunk) * SAMPLE_RATE / native_sr)
                chunk = _scisig.resample(chunk, n_out).astype("float32")
            # Vosk wil int16 PCM
            pcm = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            q.put(pcm)

        blocksize = int(BLOCK_MS * native_sr / 1000)
        with sd.InputStream(
            samplerate=native_sr, channels=1, blocksize=blocksize,
            dtype="float32", device=dev, callback=cb,
        ):
            log.info("Vosk wake-listener actief — zeg 'Hoi Anna Nova'")
            while not self._stop.is_set():
                try:
                    pcm = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(pcm):
                    txt = json.loads(rec.Result()).get("text", "")
                else:
                    txt = json.loads(rec.PartialResult()).get("partial", "")
                if txt and _hear.wake_match(txt):
                    log.info(f"wake via Vosk: '{txt}'")
                    self.on_wake(txt)
                    rec.Reset()  # vergeet partial zodat wake niet dubbel triggert


# ----- Voxtral transcriptie (cloud) + Whisper fallback (lokaal) -------------

def _audio_to_wav_bytes(audio_f32, sr: int = SAMPLE_RATE) -> bytes:
    """numpy float32 mono → PCM16 WAV bytes (voor HTTP upload)."""
    _sd, np, _ = _load_sounddevice()
    pcm = (np.clip(audio_f32, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def transcribe_voxtral(audio_f32) -> Optional[str]:
    """POST audio naar Mistral Voxtral. ~0.5-1.5 s. Raises bij fout."""
    import requests
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY leeg")
    wav = _audio_to_wav_bytes(audio_f32)
    r = requests.post(
        "https://api.mistral.ai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
        files={"file": ("speech.wav", io.BytesIO(wav), "audio/wav")},
        data={"model": MISTRAL_MODEL_VOXTRAL, "language": WHISPER_LANG},
        timeout=(VOXTRAL_CONNECT_S, VOXTRAL_READ_S),
    )
    r.raise_for_status()
    text = (r.json().get("text") or "").strip()
    return text or None


_WHISPER_ASR = None  # lazy init

def _whisper_asr():
    """Lazy-load faster-whisper tiny (fallback)."""
    global _WHISPER_ASR
    if _WHISPER_ASR is None:
        from faster_whisper import WhisperModel  # type: ignore
        _WHISPER_ASR = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _WHISPER_ASR


def transcribe_whisper(audio_f32) -> Optional[str]:
    """Lokaal faster-whisper tiny. ~5-7 s per zin op Pi. Fallback bij Voxtral-fout."""
    asr = _whisper_asr()
    segments, _ = asr.transcribe(
        audio_f32, language=WHISPER_LANG, vad_filter=False, beam_size=1,
        initial_prompt=(
            "Nederlands gesprek met Anna Nova. "
            "Hoi Anna Nova. Hallo Anna. Word wakker Anna. "
            "Wat zie je? Wie ben jij? Slaap lekker."
        ),
        temperature=0.0, without_timestamps=True, condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return text or None


def transcribe_with_fallback(audio_f32) -> Optional[str]:
    """Probeer Voxtral; bij fout whisper tiny. Logt latency."""
    t0 = time.monotonic()
    if ASR_ENGINE == "voxtral":
        try:
            text = transcribe_voxtral(audio_f32)
            log.info(f"voxtral: {time.monotonic()-t0:.1f}s → '{(text or '…')[:40]}'")
            return text
        except Exception as e:
            log.warning(f"voxtral faalde ({type(e).__name__}) → whisper fallback")
    text = transcribe_whisper(audio_f32)
    log.info(f"whisper: {time.monotonic()-t0:.1f}s → '{(text or '…')[:40]}'")
    return text


# ----- VAD-opname tijdens LUISTEREN (met 128ms throttle) --------------------

def capture_speech_turn(max_ms: int = MAX_LISTEN_MS) -> Optional["np.ndarray"]:
    """Open mic, wacht op VAD-spraak, stop na END_OF_TURN_SILENCE stilte.
    Return: float32 ndarray @ 16 kHz, of None bij geen spraak."""
    sd, np, scisig = _load_sounddevice()
    from silero_vad import load_silero_vad, get_speech_timestamps  # type: ignore

    vad = load_silero_vad()
    dev = _resolve_input_device(AUDIO_INPUT_DEVICE, sd)
    native_sr = SAMPLE_RATE
    try:
        info = sd.query_devices(dev, "input") if dev is not None else sd.query_devices(kind="input")
        native_sr = int(info["default_samplerate"])
    except Exception:
        pass

    buf: list = []
    last_voice_ts: Optional[float] = None
    heard_voice = False
    q: queue.Queue = queue.Queue()

    def cb(indata, frames, time_info, status):
        chunk = indata[:, 0].copy()
        if native_sr != SAMPLE_RATE:
            n_out = int(len(chunk) * SAMPLE_RATE / native_sr)
            chunk = scisig.resample(chunk, n_out).astype("float32")
        q.put(chunk)

    blocksize = int(BLOCK_MS * native_sr / 1000)
    with sd.InputStream(
        samplerate=native_sr, channels=1, blocksize=blocksize,
        dtype="float32", device=dev, callback=cb,
    ):
        tick = 0
        while True:
            try:
                chunk = q.get(timeout=5.0)
            except queue.Empty:
                continue
            buf.append(chunk)
            tick += 1
            # VAD-throttle: niet elke 32ms-chunk langs Silero (CPU-spaarzaam)
            if tick % VAD_EVERY_N != 0:
                now = time.monotonic()
                if heard_voice and last_voice_ts is not None \
                   and now - last_voice_ts > END_OF_TURN_SILENCE:
                    break
                if len(buf) * BLOCK_MS > max_ms:
                    break
                continue
            window = np.concatenate(buf[-int(1000 / BLOCK_MS):])
            stamps = get_speech_timestamps(
                window, vad, sampling_rate=SAMPLE_RATE, min_speech_duration_ms=200,
            )
            now = time.monotonic()
            if stamps:
                last_voice_ts = now
                heard_voice = True
            if heard_voice and last_voice_ts is not None \
               and now - last_voice_ts > END_OF_TURN_SILENCE:
                break
            if len(buf) * BLOCK_MS > max_ms:
                break

    if not heard_voice:
        return None
    return np.concatenate(buf)


# ----- High-level API die flow.py aanroept ----------------------------------

def listen_for_wake_blocking() -> _hear.Event:
    """Blokkeer tot wake-phrase gedetecteerd door Vosk. Fallback: direct Voxtral-match."""
    result: dict = {}
    done = threading.Event()

    def on_wake(text: str):
        result["text"] = text
        done.set()

    listener = WakeListener(on_wake)
    listener.start()
    try:
        done.wait()
    finally:
        listener.stop()
    return _hear.Event(type="wake", tekst=result.get("text", ""), raw=result.get("text", ""))


def listen_for_speech_turn() -> _hear.Event:
    """Open mic, wacht op spraak, transcribeer. Classificeer als wake/sleep/spraak."""
    audio = capture_speech_turn()
    if audio is None:
        return _hear.Event(type="stilte")
    text = transcribe_with_fallback(audio)
    if not text:
        return _hear.Event(type="ruis")
    if _hear.wake_match(text):
        return _hear.Event(type="wake", tekst=text, raw=text)
    if _hear.sleep_match(text):
        return _hear.Event(type="sleep", tekst=text, raw=text)
    return _hear.Event(type="spraak", tekst=text, raw=text)
