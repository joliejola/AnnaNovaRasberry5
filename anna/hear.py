"""Horen — wake/sleep-detectie + spraak-capture.

Droogloop-modus (`DROOGLOOP=1`): leest regels van stdin ipv mic.
- Lege regel (Enter) = stilte
- "#ruis" = ruis-event
- "#druk" = meerdere mensen op plek (via see.py)
- "#weg" = plek leeg (via see.py)
- Normale tekst = gesproken zin — fuzzy match op wake/sleep gebeurt hier.

Live-modus (bouwstap 7 op Pi): wrapt VAD + Voxtral ASR; roept dezelfde
match-functies aan. De Event-interface blijft gelijk zodat flow.py
niet hoeft te weten of we droogloop of echte mic doen.

wake_match en sleep_match zijn overgenomen uit huidige anna-nova.py (716-803)
en kennen ASR-mishoor-varianten (Ohana, Yama, Hannover) en imperative
context-detectie voor sleep ("ik slaap slecht" matcht NIET).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Literal, Optional

log = logging.getLogger(__name__)

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"

# Primaire wake-phrase + user-defined extras uit .env (komma-lijst)
WAKE_PHRASE = os.environ.get("WAKE_PHRASE", "hoi anna nova")
EXTRA_WAKE_PATTERNS = [p.strip().lower() for p in os.environ.get(
    "WAKE_PHRASE_PATTERNS", ""
).split(",") if p.strip()]

SLEEP_PHRASES = os.environ.get(
    "SLEEP_PHRASES",
    "slaap lekker,slaap zacht,welterusten,ga slapen,ga maar slapen,"
    "doe een dutje,tot morgen,slaap maar,genoeg geweest,stil nu,"
    "anna slapen,dag anna,doei anna"
)


EventType = Literal[
    "wake", "sleep", "spraak", "stilte", "ruis", "druk", "weg", "debug",
]


@dataclass
class Event:
    type: EventType
    tekst: str = ""
    raw: str = ""


# ---------- normalisatie ----------

_PUNCT = re.compile(r"[^a-zàâçéèêëîïôûùüÿñæœ ]+")
_SP = re.compile(r"\s+")


def _normalize(s: str) -> str:
    s = s.lower()
    s = _PUNCT.sub(" ", s)
    s = _SP.sub(" ", s).strip()
    return s


# ---------- wake_match (rijk: ASR-mishoor-varianten) ----------

ANNA_LIKE = (
    "anna", "ana", "hanna", "ohana", "ohanna", "yama",
    "ooyama", "hannah", "hanover", "hannover", "nana",
    "ane", "ama", "hana",
)
GROET_WOORDEN = {
    "hoi", "hallo", "hey", "he", "hee", "dag", "oh", "ha", "ok",
    "goedemiddag", "goedemorgen", "goedenavond",
}


def wake_match(transcript: str, phrase: str = WAKE_PHRASE) -> bool:
    """Fuzzy match voor meerdere wake-commando's en ASR-mishoor-varianten.

    Accepteert: 'Hoi Anna Nova', 'Hoi Anna', 'Hallo Anna', 'Word wakker Anna',
    'Hey Anna', etc. Whisper/Voxtral verwart 'Anna' regelmatig met 'ooyama',
    'ohana', 'hannah', 'hannover', 'yama' — die worden ook herkend.
    'Nova' of 'wakker' zijn zo uniek dat een greeting + een van beide volstaat.
    Extra patterns uit WAKE_PHRASE_PATTERNS matchen als pure substring.
    """
    t = _normalize(transcript)
    want = _normalize(phrase)
    if want in t:
        return True
    # Extra patterns uit .env (bijv. een nickname)
    for pat in EXTRA_WAKE_PATTERNS:
        if _normalize(pat) in t:
            return True

    tokens = t.split()
    if not tokens:
        return False
    groet_hits = any(g in tokens for g in GROET_WOORDEN)
    wakker_hits = "wakker" in tokens or "wakker" in t
    heeft_nova = "nova" in t
    heeft_anna_like = any(w in t for w in ANNA_LIKE)

    if heeft_nova and (heeft_anna_like or groet_hits):
        return True
    if wakker_hits and heeft_anna_like:
        return True
    if "anna" in t and (heeft_nova or groet_hits or wakker_hits):
        return True
    return False


# ---------- sleep_match (token-based, context-aware) ----------

def sleep_match(transcript: str) -> bool:
    """True als bezoeker Anna vraagt te gaan slapen.

    "Ik slaap slecht" matcht NIET (gaat over spreker zelf).
    "Ga nu maar slapen" matcht WEL.
    """
    t = _normalize(transcript)
    tokens = set(t.split())

    if tokens & {"welterusten", "slapenstijd"}:
        return True
    if "tot morgen" in t or "goedenacht" in t or "goede nacht" in t:
        return True

    if tokens & {"slaap", "slapen"}:
        if tokens & {"ik", "ikke"}:
            return False  # "ik slaap slecht"
        if tokens & {"ga", "maar", "lekker", "zacht", "nu", "jij", "anna", "nova", "even"}:
            return True
        if len(tokens) <= 2:
            return True

    if "dutje" in tokens:
        return True

    if tokens & {"rust", "rusten"} and tokens & {"ga", "maar", "even", "nu"}:
        return True

    if tokens & {"dag", "doei", "doeg", "tabee"}:
        if len(tokens) == 1 or tokens & {"anna", "nova", "jij"}:
            return True

    for phrase in SLEEP_PHRASES.split(","):
        p = _normalize(phrase)
        if p and p in t:
            return True

    return False


# ---------- droogloop-input ----------

def _lees_regel(prompt: str = "", timeout: Optional[float] = None) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def _classificeer_regel(regel: str) -> Event:
    stripped = regel.strip()
    if stripped == "":
        return Event("stilte")
    if stripped.lower() == "#ruis":
        return Event("ruis")
    if stripped.lower() == "#druk":
        return Event("druk")
    if stripped.lower() == "#weg":
        return Event("weg")
    if stripped.startswith("#"):
        return Event("debug", raw=stripped)
    if sleep_match(stripped):
        return Event("sleep", tekst=stripped, raw=stripped)
    if wake_match(stripped):
        return Event("wake", tekst=stripped, raw=stripped)
    return Event("spraak", tekst=stripped, raw=stripped)


# ---------- publieke API (flow.py gebruikt deze) ----------

def luister_wake(prompt: str = "[rust] ") -> Event:
    """Blokkeer in RUST tot wake / sleep / weg / druk / debug.

    Spraak-zonder-wake wordt genegeerd (Anna moet eerst aangesproken). Dit
    is bewust: het atelier zit vol stemmen. Alleen een expliciete wake
    (of een Jolanda-sleep-commando) brengt Anna uit RUST.
    """
    while True:
        regel = _lees_regel(prompt) if DROOGLOOP else _lees_regel_live(prompt)
        ev = _classificeer_regel(regel)
        if ev.type in ("wake", "sleep", "weg", "druk", "debug"):
            return ev
        if DROOGLOOP:
            log.debug("[RUST negeert — geen wake] %r", regel)


def luister_spraak(prompt: str = "[luistert] ", stilte_na_s: float = 8.0) -> Event:
    """Luister in een actieve toestand. Timeout → stilte-event.

    Droogloop blokkeert tot input (Enter = stilte).
    """
    regel = _lees_regel(prompt) if DROOGLOOP else _lees_regel_live(prompt, timeout=stilte_na_s)
    return _classificeer_regel(regel)


def _lees_regel_live(prompt: str, timeout: Optional[float] = None) -> str:
    """Live-mode: één listen-cycle via Listener. Return getranscribeerde tekst.

    Lege string = stilte (geen voice). Transcript wordt NIET op schijf geschreven
    (privacy-regel bron 2). Callers (luister_wake / luister_spraak) doen wake/
    sleep-match op de teruggegeven string.
    """
    lst = _get_listener()
    text, _audio = lst.listen_once(timeout=timeout)
    return (text or "").strip()


# ============================================================================
# Live-mode: mic + VAD + Voxtral/Whisper ASR
# ============================================================================
# Geport uit anna-nova.py (regel 519, 850, 876) met kleine aanpassingen:
# - Lazy imports: sounddevice, silero_vad, scipy niet nodig in droogloop
# - Geen class Listener state lekken tussen sessies (bouw nieuwe InputStream
#   voor élke listen_once; ReSpeaker houdt niet van gedeelde streams)
# - transcribe_voxtral: dezelfde Mistral /v1/audio/transcriptions endpoint

SAMPLE_RATE = 16000  # VAD + Voxtral verwachten 16kHz mono float32
BLOCK_MS = 32  # mic-callback chunk-grootte
VAD_EVERY_MS = 128  # elke zoveel ms silero VAD aanroepen (CPU-fix)
END_OF_TURN_SILENCE = float(os.environ.get("END_OF_TURN_SILENCE", "1.5"))
MAX_LISTEN_MS = int(float(os.environ.get("MAX_LISTEN_SEC", "30.0")) * 1000)

AUDIO_IN = os.environ.get("AUDIO_INPUT_DEVICE", "")

_LISTENER_SINGLETON = None  # lazy, één instance per proces


def _get_listener() -> "Listener":
    global _LISTENER_SINGLETON
    if _LISTENER_SINGLETON is None:
        _LISTENER_SINGLETON = Listener()
    return _LISTENER_SINGLETON


class Listener:
    """Opent mic on-demand, VAD-trimt, transcribeert via Voxtral (fallback Whisper).

    Niet thread-safe: één call tegelijk. Dat is prima voor flow.py's sync-loop.
    """

    def __init__(self) -> None:
        # Lazy imports — stuk code werkt alleen in live-mode op Pi/mac met deps
        import numpy as np  # noqa
        import sounddevice as sd  # noqa
        try:
            from silero_vad import load_silero_vad  # noqa
        except ImportError as e:
            raise RuntimeError(
                "Live-mode vereist silero-vad. Installeer via "
                "pip install silero-vad (op Pi: install.sh doet dat)."
            ) from e
        self._np = __import__("numpy")
        self._sd = __import__("sounddevice")
        self._vad = load_silero_vad()
        try:
            from scipy import signal as scisig
            self._resample = scisig.resample
        except ImportError:
            self._resample = None  # dan accepteren we native SR

        log.info("Listener klaar — VAD geladen, ASR via Voxtral%s",
                 " + Whisper-fallback" if _whisper_available() else "")

    def _resolve_device(self):
        """Mic-device index of None voor systeemdefault."""
        if not AUDIO_IN or AUDIO_IN.lower() in ("default", "none", ""):
            return None
        try:
            return int(AUDIO_IN)
        except ValueError:
            pass
        needle = AUDIO_IN.lower()
        for i, d in enumerate(self._sd.query_devices()):
            if needle in d.get("name", "").lower():
                log.info("audio device: '%s' (index %d)", d["name"], i)
                return i
        log.warning("audio device '%s' niet gevonden — systeemdefault", AUDIO_IN)
        return None

    def listen_once(self, timeout: Optional[float] = None) -> tuple[Optional[str], Optional[object]]:
        """Open mic, wacht op VAD-start, neem op tot VAD-stop, transcribeer.

        Returns (text, audio_ndarray). Beide None als er geen spraak was.
        """
        from silero_vad import get_speech_timestamps  # noqa
        import queue
        import time

        np = self._np
        sd = self._sd
        audio_q: "queue.Queue" = queue.Queue()

        dev = self._resolve_device()
        try:
            dev_info = sd.query_devices(dev, "input")
            native_sr = int(dev_info["default_samplerate"])
        except Exception:
            native_sr = SAMPLE_RATE

        def _cb(indata, frames, time_info, status):
            if status:
                log.debug("audio status: %s", status)
            chunk = indata[:, 0].copy()
            if native_sr != SAMPLE_RATE and self._resample is not None:
                n_out = int(len(chunk) * SAMPLE_RATE / native_sr)
                chunk = self._resample(chunk, n_out).astype("float32")
            audio_q.put(chunk)

        buf: list = []
        last_voice = None
        heard = False
        hard_deadline = time.monotonic() + (timeout or 3600.0)

        with sd.InputStream(
            samplerate=native_sr,
            channels=1,
            blocksize=int(BLOCK_MS * native_sr / 1000),
            dtype="float32",
            device=dev,
            callback=_cb,
        ):
            vad_every_n = max(1, VAD_EVERY_MS // BLOCK_MS)
            tick = 0
            while True:
                if time.monotonic() > hard_deadline:
                    break
                try:
                    chunk = audio_q.get(timeout=1.0)
                except queue.Empty:
                    continue
                buf.append(chunk)
                tick += 1
                if tick % vad_every_n != 0:
                    now = time.monotonic()
                    if heard and last_voice and now - last_voice > END_OF_TURN_SILENCE:
                        break
                    if len(buf) * BLOCK_MS > MAX_LISTEN_MS:
                        break
                    continue
                window = np.concatenate(buf[-int(1000 / BLOCK_MS):])
                stamps = get_speech_timestamps(
                    window, self._vad, sampling_rate=SAMPLE_RATE,
                    min_speech_duration_ms=200,
                )
                now = time.monotonic()
                if stamps:
                    last_voice = now
                    heard = True
                if heard and last_voice and now - last_voice > END_OF_TURN_SILENCE:
                    break
                if len(buf) * BLOCK_MS > MAX_LISTEN_MS:
                    break

        if not heard:
            return None, None

        audio = np.concatenate(buf)
        text = _transcribe(audio)
        return (text or None), audio


# ---------- transcriptie (Voxtral primary, Whisper fallback) ----------

def _transcribe(audio_f32) -> Optional[str]:
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if api_key:
        try:
            return _transcribe_voxtral(audio_f32, api_key)
        except Exception as e:
            log.warning("voxtral faalt (%s) — whisper fallback", e)
    return _transcribe_whisper(audio_f32)


def _transcribe_voxtral(audio_f32, api_key: str) -> Optional[str]:
    """POST float32 mono 16kHz naar Mistral Voxtral, return transcript."""
    import io, wave
    import numpy as np
    import requests

    pcm = (np.clip(audio_f32, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    buf.seek(0)

    model = os.environ.get("VOXTRAL_MODEL", "voxtral-mini-latest")
    r = requests.post(
        "https://api.mistral.ai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": ("speech.wav", buf, "audio/wav")},
        data={"model": model, "language": "nl"},
        timeout=(5, 30),
    )
    r.raise_for_status()
    text = (r.json().get("text") or "").strip()
    return text or None


def _whisper_available() -> bool:
    try:
        import faster_whisper  # noqa
        return True
    except ImportError:
        return False


_WHISPER_ASR = None


def _transcribe_whisper(audio_f32) -> Optional[str]:
    """Lokale Whisper als Voxtral faalt. Vereist faster-whisper."""
    global _WHISPER_ASR
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log.error("Whisper-fallback niet beschikbaar: pip install faster-whisper")
        return None
    if _WHISPER_ASR is None:
        model_size = os.environ.get("WHISPER_MODEL", "tiny")
        log.info("Whisper laadt: %s", model_size)
        _WHISPER_ASR = WhisperModel(model_size, device="cpu", compute_type="int8")
    prompt = ("Nederlands gesprek met Anna Nova. "
              "Hoi Anna Nova. Hallo Anna. Slaap lekker.")
    segments, _ = _WHISPER_ASR.transcribe(
        audio_f32,
        language="nl",
        vad_filter=False,
        beam_size=1,
        initial_prompt=prompt,
        temperature=0.0,
        without_timestamps=True,
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return text or None


# ---------- lifecycle (optioneel; flow.py gebruikt dit niet actief) ----------

def start_listening(on_transcript_callback) -> None:
    """Deprecated voor flow.py-sync-loop. Hier voor externe callers die
    een event-pump willen. Blokkeert tot stop() of KeyboardInterrupt."""
    import threading
    stop = threading.Event()
    lst = _get_listener()
    try:
        while not stop.is_set():
            text, _ = lst.listen_once(timeout=None)
            if text:
                on_transcript_callback(text)
    except KeyboardInterrupt:
        stop.set()


def stop() -> None:
    """Niet nodig in huidige impl (geen persistent background thread).
    Placeholder voor toekomstige event-pump variant."""
    pass
