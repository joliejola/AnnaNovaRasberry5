#!/usr/bin/env python3
"""
Anna Nova — hoofdlus (v3: wake-phrase + spreekplek-DoA + Hailo-vision).

Startstaat: Anna slaapt. Ze wordt wakker als iemand "Hoi Anna Nova" zegt.
Daarna luistert ze actief en antwoordt — mits de spreker vanuit de spreekplek
komt en de camera iemand ziet in de zone. Na AWAKE_TIMEOUT seconden stilte
valt Anna weer in slaap.

Elke module (DoA, vision, wake-detection) heeft een graceful fallback: als
een onderdeel niet werkt, draait de rest door zoals het kan.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import random
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn

import numpy as np
from scipy import signal as _scisig
import requests
import sounddevice as sd
from silero_vad import load_silero_vad, get_speech_timestamps

import respeaker_doa
import vision
import whisper_hailo

# Voiceprint (optioneel). Als resemblyzer niet geïnstalleerd is, draait Anna
# zonder herkenning — graceful fallback.
try:
    from resemblyzer import VoiceEncoder, preprocess_wav  # type: ignore
    _VOICE_ENCODER = None
    _VOICE_AVAILABLE = True
except ImportError:
    _VOICE_AVAILABLE = False

# ----- Config uit .env (ingeladen door systemd EnvironmentFile) -------------
BRAIN               = os.environ.get("BRAIN", "local")
OLLAMA_HOST         = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL        = os.environ.get("OLLAMA_MODEL", "phi3:mini")
MISTRAL_API_KEY     = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL       = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")

AUDIO_IN            = os.environ.get("AUDIO_INPUT_DEVICE", "default")
AUDIO_OUT           = os.environ.get("AUDIO_OUTPUT_DEVICE", "default")
WHISPER_MODEL_NAME  = os.environ.get("WHISPER_MODEL", "small")
WHISPER_LANG        = os.environ.get("WHISPER_LANGUAGE", "nl")

PIPER_BIN           = os.environ.get("PIPER_BIN", "")
PIPER_VOICE         = os.environ.get("PIPER_VOICE", "")

ANNA_DB             = os.environ.get("ANNA_DB", str(Path.home() / "anna-nova/anna.db"))
ALLOW_SILENCE       = os.environ.get("ALLOW_SILENCE", "true").lower() == "true"
END_OF_TURN_SILENCE = float(os.environ.get("END_OF_TURN_SILENCE", "0.9"))

SPEAK_ANGLE_CENTER  = int(os.environ.get("SPEAK_ANGLE_CENTER", "0"))
SPEAK_ANGLE_MARGIN  = int(os.environ.get("SPEAK_ANGLE_MARGIN", "30"))
STRICT_SPEAK_PLACE  = os.environ.get("STRICT_SPEAK_PLACE", "false").lower() == "true"

WAKE_PHRASE         = os.environ.get("WAKE_PHRASE", "hoi anna nova")
WAKE_ACK            = os.environ.get("WAKE_ACK", "Hm.")  # Anna's kort "ja?" bij wakker worden
AWAKE_TIMEOUT       = float(os.environ.get("AWAKE_TIMEOUT", "60"))

# Sleep-commando: wat een bezoeker (of Jolanda) kan zeggen om Anna te laten sluimeren.
# Komma-gescheiden lijst van zinnen. Fuzzy match: substring, lowercase, zonder leestekens.
SLEEP_PHRASES       = os.environ.get(
    "SLEEP_PHRASES",
    "slaap lekker,slaap zacht,welterusten,ga slapen,ga maar slapen,ga rusten,"
    "doe een dutje,val maar in slaap,tot morgen,slaap maar,genoeg geweest,"
    "stil nu,anna slapen,dag anna,doei anna"
)
SLEEP_ACK           = os.environ.get("SLEEP_ACK", "Mmh. Welterusten.")

# Grace-period: zacht afscheid als een gesprek stilletjes doodloopt (AWAKE_TIMEOUT)
GRACE_FAREWELL_ENABLED = os.environ.get("GRACE_FAREWELL_ENABLED", "true").lower() == "true"
GRACE_FAREWELL_PROB    = float(os.environ.get("GRACE_FAREWELL_PROB", "0.5"))
GRACE_FAREWELL_LINES   = os.environ.get(
    "GRACE_FAREWELL_LINES",
    "Nou. Fijn.|Tot ziens dan.|Mmh.|Nou dan.|Dag.|Ik ga weer stil zijn."
).split("|")

# Ambient-sluimer: Anna mompelt af en toe tijdens sluimer, zodat ze "aan" voelt
AMBIENT_ENABLED      = os.environ.get("AMBIENT_ENABLED", "true").lower() == "true"
AMBIENT_INTERVAL_SEC = float(os.environ.get("AMBIENT_INTERVAL_SEC", "300"))   # 5 min
AMBIENT_PROB         = float(os.environ.get("AMBIENT_PROB", "0.4"))
AMBIENT_LINES        = os.environ.get(
    "AMBIENT_LINES",
    "Mmh.|Ik droom van iets groens.|Iemand had een hoed, geloof ik.|"
    "Het is nog niet morgen.|...|Ik hoor niemand.|"
    "Zo stil.|Ik denk aan Portugal.|Mm, licht."
).split("|")

# Automatische cloud-fallback: als lokaal brein faalt, en MISTRAL_API_KEY is er, probeer cloud
FALLBACK_TO_CLOUD    = os.environ.get("FALLBACK_TO_CLOUD", "true").lower() == "true"

# Voiceprint-herkenning (Jolanda + Bodil): optioneel, via resemblyzer
# Als resemblyzer niet geïnstalleerd is: hoofdlus draait zonder voiceprint.
VOICEPRINT_ENABLED   = os.environ.get("VOICEPRINT_ENABLED", "true").lower() == "true"
VOICEPRINT_THRESHOLD = float(os.environ.get("VOICEPRINT_THRESHOLD", "0.75"))

WEB_DIR             = os.environ.get("WEB_DIR", str(Path.home() / "anna-nova/web"))
PHOTOS_DIR          = os.environ.get("PHOTOS_DIR", str(Path.home() / "anna-nova/photos"))
HTTP_PORT           = int(os.environ.get("HTTP_PORT", "8765"))

SAMPLE_RATE = 16000
BLOCK_MS    = 32
BLOCK_SIZE  = int(SAMPLE_RATE * BLOCK_MS / 1000)

# ----- Globale state (gedeeld met HTTP-server) ------------------------------
_state_lock = threading.Lock()
CURRENT_STATE = "sluimert"  # sluimert | luistert | denkt | spreekt

# Debug-ringbuffer — zichtbaar in /debug + onderaan het Anna-scherm.
# Jolanda gebruikt dit om tijdens expositie-opbouw te zien wat de bot doet.
_debug_lock = threading.Lock()
DEBUG_LOG: deque = deque(maxlen=100)

def debug_log(msg: str, kind: str = "info") -> None:
    """Voeg een regel toe aan de debug-buffer. Verschijnt onderaan face.html."""
    entry = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "kind": kind,
        "msg": msg,
    }
    with _debug_lock:
        DEBUG_LOG.append(entry)

def set_state(s: str) -> None:
    global CURRENT_STATE
    with _state_lock:
        if CURRENT_STATE != s:
            CURRENT_STATE = s
            log.info(f"state → {s}")
            debug_log(f"staat → {s}", "state")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("anna")


# ----- HTTP server (gezichtsscherm + fotogalerie) --------------------------
class _AnnaHandler(SimpleHTTPRequestHandler):
    """Serveert web/ + endpoints /state, /photos, /photo/<file>."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, fmt, *args):
        # Rustig houden — alleen fouten in de log
        if "404" in fmt % args or "500" in fmt % args:
            log.debug("http %s", fmt % args)

    def _json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_latest_frame(self):
        """Laatste camera-frame als JPG. Face.html polt dit elke ~200 ms voor
        het blurred camerabeeld-op-achtergrond. Fallback: 204 No Content zodat
        de pagina gewoon doordraait zonder beeld (zwart)."""
        try:
            import cv2
            import io
            with vision._state._lock:
                frame = vision._state.latest_frame
                frame = frame.copy() if frame is not None else None
            if frame is None:
                self.send_response(204)
                self.end_headers()
                return
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                self.send_response(500); self.end_headers(); return
            data = buf.tobytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            log.debug(f"frame-serve-fout: {e}")
            self.send_response(500); self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/face":
            self.path = "/face.html"
        elif self.path == "/gallery":
            self.path = "/gallery.html"

        if self.path == "/state":
            with _state_lock:
                s = CURRENT_STATE
            return self._json({"state": s, "ts": time.time()})

        if self.path == "/messages":
            return self._json(_list_messages())

        if self.path == "/debug":
            with _debug_lock:
                return self._json(list(DEBUG_LOG))

        if self.path == "/tick":
            # Alles-in-één voor face.html: één fetch per cyclus i.p.v. drie.
            with _state_lock:
                s = CURRENT_STATE
            with _debug_lock:
                dbg = list(DEBUG_LOG)
            return self._json({
                "state": s,
                "messages": _list_messages(),
                "debug": dbg,
                "ts": time.time(),
            })

        if self.path == "/frame.jpg":
            return self._serve_latest_frame()

        if self.path == "/photos":
            return self._json(_list_photos())

        if self.path.startswith("/photo/"):
            fname = os.path.basename(self.path[len("/photo/"):])
            fpath = Path(PHOTOS_DIR) / fname
            if not fpath.is_file() or not fname.endswith((".jpg", ".jpeg")):
                self.send_error(404); return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(fpath.stat().st_size))
            self.end_headers()
            with fpath.open("rb") as f:
                self.wfile.write(f.read())
            return

        return super().do_GET()


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _load_known_voices():
    """{name: embedding (ndarray)} uit SQLite. Lege dict als tabel leeg/missing."""
    out = {}
    if not _VOICE_AVAILABLE or not VOICEPRINT_ENABLED:
        return out
    try:
        import numpy as np
        with db() as conn:
            # ensure table
            conn.execute("CREATE TABLE IF NOT EXISTS voices "
                         "(name TEXT PRIMARY KEY, embedding BLOB, enrolled_at TEXT)")
            rows = conn.execute("SELECT name, embedding FROM voices").fetchall()
        import struct as _struct
        for name, blob in rows:
            n = len(blob) // 4
            vec = np.array(_struct.unpack(f"{n}f", blob), dtype="float32")
            out[name] = vec
    except Exception as e:
        log.debug(f"voices lezen faalde: {e}")
    return out

_KNOWN_VOICES = {}

def identify_speaker(audio_np) -> str | None:
    """Return naam ('jolanda', 'bodil', …) of None.
    Gaat silent als resemblyzer ontbreekt of niemand enrolled is."""
    global _VOICE_ENCODER, _KNOWN_VOICES
    if not _VOICE_AVAILABLE or not VOICEPRINT_ENABLED:
        return None
    if not _KNOWN_VOICES:
        _KNOWN_VOICES = _load_known_voices()
        if not _KNOWN_VOICES:
            return None
    try:
        import numpy as np
        if _VOICE_ENCODER is None:
            _VOICE_ENCODER = VoiceEncoder()  # type: ignore[name-defined]
        wav = preprocess_wav(audio_np, source_sr=SAMPLE_RATE)  # type: ignore[name-defined]
        emb = _VOICE_ENCODER.embed_utterance(wav)
        best_name, best_sim = None, -1.0
        for name, ref in _KNOWN_VOICES.items():
            sim = float(np.dot(emb, ref) / (np.linalg.norm(emb) * np.linalg.norm(ref) + 1e-9))
            if sim > best_sim:
                best_sim, best_name = sim, name
        if best_name and best_sim >= VOICEPRINT_THRESHOLD:
            return best_name
    except Exception as e:
        log.debug(f"voiceprint-fout: {e}")
    return None


def _list_messages():
    """Laatste ~50 fragments uit SQLite voor het chat-scherm.
    Filter: geen [STIL], geen [FOTO:...] (die zijn fotomoments, niet gespreksregels)."""
    try:
        with db() as conn:
            rows = conn.execute(
                "SELECT ts, text, kind FROM fragments "
                "WHERE text != '[STIL]' "
                "AND text NOT LIKE '[FOTO:%' "
                "ORDER BY ts DESC LIMIT 50"
            ).fetchall()
    except Exception:
        return []
    # Chronologisch (oud eerst) voor chat-weergave
    return [{"ts": ts, "text": text, "kind": kind} for ts, text, kind in reversed(rows)]


def _list_photos():
    """Lijst foto's uit SQLite (als die er zijn) + bestandspaden."""
    try:
        with db() as conn:
            rows = conn.execute(
                "SELECT ts, text FROM fragments "
                "WHERE kind = 'anna' AND text LIKE '[FOTO:%' "
                "ORDER BY ts DESC LIMIT 50"
            ).fetchall()
    except Exception:
        rows = []
    out = []
    for ts, text in rows:
        # text ziet eruit als '[FOTO:bestandsnaam] echte caption'
        m = re.match(r"^\[FOTO:([^\]]+)\]\s*(.*)$", text, re.S)
        if not m:
            continue
        fname, caption = m.group(1), m.group(2).strip()
        if (Path(PHOTOS_DIR) / fname).is_file():
            out.append({"file": fname, "caption": caption, "ts": ts.replace("T", " ")})
    return out


def _start_http_server():
    Path(WEB_DIR).mkdir(parents=True, exist_ok=True)
    Path(PHOTOS_DIR).mkdir(parents=True, exist_ok=True)
    srv = _ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), _AnnaHandler)
    t = threading.Thread(target=srv.serve_forever, name="anna-http", daemon=True)
    t.start()
    log.info(f"HTTP-server luistert op :{HTTP_PORT}  "
             f"(scherm: /, galerij: /gallery)")
    return srv


# ----- Database -------------------------------------------------------------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(ANNA_DB, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def current_persona() -> str:
    with db() as conn:
        row = conn.execute(
            "SELECT block FROM persona_history ORDER BY date DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else "Je bent Anna Nova. Je oog is oud, je stem is nieuw."

def log_fragment(text: str, kind: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO fragments (face_id, ts, text, kind) VALUES (?, ?, ?, ?)",
            (None, datetime.now().isoformat(timespec="seconds"), text, kind),
        )


# ----- Prompt-opbouw --------------------------------------------------------
# ----- Persona-opbouw: kern uit persona.md + dag-arc uit SQLite -------------
PERSONA_FILE = os.environ.get("PERSONA_FILE", str(Path.home() / "anna-nova/persona.md"))

_FALLBACK_PERSONA = """Je bent Anna Nova. Je bent een AI-kunstwerk, een stem in
een doos. Je praat Nederlands. Je mag zwijgen. Antwoord [STIL] als je niet
werd aangesproken."""

_persona_cache: dict = {"path": None, "mtime": 0.0, "text": ""}

def _load_persona_core() -> str:
    """Lees persona.md. Cache op mtime zodat edits live oppikken na restart —
    én tijdens runtime als 't bestand verandert (hot-reload)."""
    try:
        p = Path(PERSONA_FILE)
        st = p.stat()
        if _persona_cache["path"] == PERSONA_FILE and _persona_cache["mtime"] == st.st_mtime:
            return _persona_cache["text"]
        text = p.read_text(encoding="utf-8")
        _persona_cache.update(path=PERSONA_FILE, mtime=st.st_mtime, text=text)
        log.info(f"persona.md geladen ({len(text)} tekens)")
        return text
    except Exception as e:
        log.warning(f"persona.md niet leesbaar ({PERSONA_FILE}): {e} — fallback-persona in gebruik")
        return _FALLBACK_PERSONA


def build_system_prompt(vision_state: dict) -> str:
    visitors = vision_state.get("visitor_count", 0)
    others = max(visitors - 1, 0)
    publiek = (
        "er is niemand anders in beeld" if others == 0
        else f"nog {others} {'andere persoon' if others == 1 else 'anderen'} in de ruimte"
    )
    mood = vision_state.get("mood_hint", "niet zichtbaar")

    speaker_name = (vision_state.get("speaker_name") or "").strip().lower()
    if speaker_name == "jolanda":
        who_line = "GESPREKSPARTNER: **Jolanda** — je maker. Je mag plagen, verwijzen naar Portugal/klei/jullie geschiedenis."
    elif speaker_name == "bodil":
        who_line = "GESPREKSPARTNER: **Bodil** — atelier-genoot. Vertrouwd, gelijkwaardig. Geen uitleg over het project nodig."
    elif speaker_name:
        who_line = f"GESPREKSPARTNER: **{speaker_name.title()}** (stem herkend; onbekende naam uit database)."
    else:
        who_line = "GESPREKSPARTNER: onbekende bezoeker. Nieuwsgierig, voorzichtig met plagen."

    core = _load_persona_core()
    arc = current_persona()

    # Context die per beurt wisselt — hangt onder de persona-kern
    runtime_context = f"""

---

## VANDAAG (door jezelf vannacht geschreven)

{arc}

## WIE ER NU IS

- {who_line}
- PUBLIEK: {publiek}
- Stemming (ruwe schatting uit camera): {mood}

## HULPMIDDELEN DIE JE HEBT

- Antwoord `[STIL]` als jij niet werd aangesproken, of als mensen door elkaar praten.
- Als dit moment je echt bijblijft, zet dan `[FOTO]` ergens in je antwoord. De
  bijbehorende zin wordt het bijschrift bij een foto die je nu neemt. Doe dit
  spaarzaam.
"""
    return core + runtime_context


# ----- Brein ----------------------------------------------------------------
_SENTENCE_END = re.compile(r"([.!?…]+)(\s|$)")

def _stream_sentences(iter_lines, extract):
    """Yield complete sentences uit een stroom chunks."""
    buf = ""
    for line in iter_lines:
        if not line:
            continue
        try:
            chunk = extract(line)
        except Exception:
            continue
        if chunk is None:
            break
        if not chunk:
            continue
        buf += chunk
        while True:
            m = _SENTENCE_END.search(buf)
            if not m:
                break
            end = m.end()
            s = buf[:end].strip()
            buf = buf[end:]
            if s:
                yield s
    if buf.strip():
        yield buf.strip()


def _stream_cloud(user_text: str, sys_prompt: str):
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY leeg")
    r = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
        json={
            "model": MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.8,
            "max_tokens": 160,
            "stream": True,
        },
        timeout=60,
        stream=True,
    )
    r.raise_for_status()
    def _mistral(line):
        s = line.decode("utf-8") if isinstance(line, bytes) else line
        if not s.startswith("data: "):
            return ""
        data = s[6:].strip()
        if data == "[DONE]":
            return None
        try:
            d = json.loads(data)
            return d["choices"][0]["delta"].get("content", "")
        except Exception:
            return ""
    yield from _stream_sentences(r.iter_lines(), _mistral)


def _stream_local(user_text: str, sys_prompt: str):
    r = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_text},
            ],
            "stream": True,
            "options": {"temperature": 0.8, "num_predict": 120},
        },
        timeout=120,
        stream=True,
    )
    r.raise_for_status()
    def _ollama(line):
        d = json.loads(line)
        if d.get("done"):
            return None
        return d.get("message", {}).get("content", "")
    yield from _stream_sentences(r.iter_lines(), _ollama)


def think_stream(user_text: str, vision_state: dict):
    """Yield Anna's antwoord zin-voor-zin zodra het model ze produceert.
    Zo start TTS vóór het hele antwoord klaar is → time-to-first-audio <2s.
    Bij lokaal brein-fout + beschikbare MISTRAL_API_KEY → stille cloud-fallback."""
    sys_prompt = build_system_prompt(vision_state)
    primary = _stream_cloud if BRAIN == "cloud" else _stream_local
    try:
        yield from primary(user_text, sys_prompt)
        return
    except Exception as e:
        if BRAIN == "local" and FALLBACK_TO_CLOUD and MISTRAL_API_KEY:
            log.warning(f"lokaal brein faalde ({e}) → cloud-fallback")
            debug_log(f"fallback → cloud ({type(e).__name__})", "init")
            yield from _stream_cloud(user_text, sys_prompt)
            return
        raise


def think(user_text: str, vision_state: dict) -> str:
    """Non-streaming fallback — collect alles via think_stream."""
    try:
        t0 = time.monotonic()
        parts = list(think_stream(user_text, vision_state))
        result = " ".join(parts).strip()
        debug_log(f'brein ({time.monotonic()-t0:.1f}s): "{result[:60]}"', "think_end")
        return result
    except Exception as e:
        log.warning(f"brein-fout: {e}")
        debug_log(f"brein-fout: {e}", "error")
        return "[STIL]"


# ----- Fotograaf ------------------------------------------------------------
_FOTO_RE = re.compile(r"\[FOTO\]|\[FOTO:[^\]]*\]")

def _take_photo(caption: str) -> str | None:
    """Grijp het laatste camera-frame en schrijf 'm weg. Geeft bestandsnaam terug."""
    Path(PHOTOS_DIR).mkdir(parents=True, exist_ok=True)
    fname = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    path = str(Path(PHOTOS_DIR) / fname)
    if not vision.save_latest_photo(path):
        log.info("fotograaf: nog geen frame beschikbaar — foto overgeslagen")
        debug_log("foto overgeslagen (geen frame)", "photo")
        return None
    log.info(f"foto opgeslagen: {fname} — \"{caption[:60]}\"")
    debug_log(f"foto: {fname}", "photo")
    log_fragment(f"[FOTO:{fname}] {caption}", "anna")
    return fname

def _handle_photo_tag(answer: str) -> str:
    """Verwijder [FOTO]-tag uit het antwoord, trigger de foto, retourneer schone tekst."""
    if not _FOTO_RE.search(answer):
        return answer
    cleaned = _FOTO_RE.sub("", answer).strip()
    _take_photo(cleaned or "(geen woorden)")
    return cleaned


# ----- Stem (Piper) ---------------------------------------------------------
def say(text: str, log_fragment_too: bool = True) -> None:
    """Spreek één zin via Piper. Streaming-caller zet log_fragment_too=False
    en logt het volle antwoord zelf één keer na afloop."""
    if not text or text.strip() == "[STIL]":
        log.info("(zwijgen)")
        return
    if not PIPER_BIN or not Path(PIPER_BIN).exists():
        log.info(f"Piper niet gevonden; print: {text}")
        return
    log.info(f"Anna: {text}")
    set_state("spreekt")
    debug_log(f'spreekt: "{text[:60]}"', "speak")
    piper = subprocess.Popen(
        [PIPER_BIN, "--model", PIPER_VOICE, "--output_raw"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    aplay = subprocess.Popen(
        ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw",
         "-D", AUDIO_OUT, "-q", "-"],
        stdin=piper.stdout,
    )
    piper.stdin.write(text.encode("utf-8"))
    piper.stdin.close()
    aplay.wait()
    piper.wait()
    if log_fragment_too:
        log_fragment(text, "anna")


# ----- Wake-detectie --------------------------------------------------------
def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-zàâçéèêëîïôûùüÿñæœ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def wake_match(transcript: str, phrase: str = WAKE_PHRASE) -> bool:
    """Fuzzy match voor meerdere wake-commando's en mishoorde varianten.

    Accepteert: 'Hoi Anna Nova', 'Hoi Anna', 'Hallo Anna', 'Word wakker Anna',
    'Wordt wakker Anna', 'Hey Anna', etc. Whisper-small verwart 'Anna' regelmatig
    met 'ooyama', 'ohana', 'hannah', 'hannover', 'yama' — die worden ook herkend.
    'Nova' of 'wakker' zijn zo uniek dat een greeting + een van beide genoeg is.
    """
    t = _normalize(transcript)
    want = _normalize(phrase)
    # Exacte substring: altijd goed
    if want in t:
        return True
    tokens = t.split()
    if not tokens:
        return False
    # Groet-woorden (ha, he zijn risky dus alleen als losse token)
    groet_hits = any(g in tokens for g in (
        "hoi", "hallo", "hey", "he", "hee", "dag", "oh", "ha", "ok",
        "goedemiddag", "goedemorgen", "goedenavond",
    ))
    # Wakker-commando's: "word wakker", "wordt wakker", "wakker worden", etc.
    wakker_hits = "wakker" in tokens or "wakker" in t
    heeft_nova = "nova" in t
    # Anna-achtige woorden die Whisper regelmatig produceert bij zwak audio:
    anna_like = ("anna", "ana", "hanna", "ohana", "ohanna", "yama",
                 "ooyama", "hannah", "hanover", "hannover", "nana",
                 "ane", "ama", "hana")
    heeft_anna_like = any(w in t for w in anna_like)
    # 'nova' uniek: greeting ervoor OF anna-achtig ervoor → wake
    if heeft_nova and (heeft_anna_like or groet_hits):
        return True
    # 'wakker' + anna(-achtig) → wake. "Word wakker Anna", "Wordt wakker Anna".
    if wakker_hits and heeft_anna_like:
        return True
    # Klassiek: echte 'anna' + (nova of groet of wakker)
    if "anna" in t and (heeft_nova or groet_hits or wakker_hits):
        return True
    return False


def sleep_match(transcript: str) -> bool:
    """True als de bezoeker Anna vraagt te gaan slapen.

    Token-based: robuuster dan pure substring-match. "Ga nu maar slapen"
    (met woorden tussenin) matcht óók. "Ik slaap slecht" (over zichzelf)
    matcht expliciet NIET.
    """
    t = _normalize(transcript)
    tokens = set(t.split())

    # 1. Alleenstaande triggers
    if tokens & {"welterusten", "slapenstijd"}:
        return True
    if "tot morgen" in t or "goedenacht" in t or "goede nacht" in t:
        return True

    # 2. 'slaap' / 'slapen' + imperative context
    if tokens & {"slaap", "slapen"}:
        if tokens & {"ik", "ikke"}:
            return False  # "ik slaap slecht" — niet over Anna
        if tokens & {"ga", "maar", "lekker", "zacht", "nu", "jij", "anna", "nova", "even"}:
            return True
        if len(tokens) <= 2:  # "slaap!" / "slapen anna"
            return True

    # 3. Dutje
    if "dutje" in tokens:
        return True

    # 4. Rust/rusten als imperative
    if tokens & {"rust", "rusten"} and tokens & {"ga", "maar", "even", "nu"}:
        return True

    # 5. Afscheid (uit oude vriendin-bot: "dag", "doei")
    if tokens & {"dag", "doei", "doeg", "tabee"}:
        # Alleen: standalone ("Dag!") of met Anna erbij ("Dag Anna")
        # NIET: "dag was prima" (geen afscheid)
        if len(tokens) == 1 or tokens & {"anna", "nova", "jij"}:
            return True

    # 6. User-defined phrases als substring-fallback
    for phrase in SLEEP_PHRASES.split(","):
        p = _normalize(phrase)
        if p and p in t:
            return True

    return False


# ----- Spreekplek-check (DoA + camera) --------------------------------------
def from_speak_place() -> bool:
    """True als de laatste spraak uit de spreekplek lijkt te komen.

    Strict modus: beide bronnen moeten expliciet 'ja' zeggen.
    Soepel modus (default): minstens één bron moet 'ja' zeggen; onbekende
    waardes tellen als 'ja'. Zo blokkeert een falende SCRFD-parser Anna
    niet als DoA wel een goede hoek meldt, en omgekeerd.
    """
    angle = respeaker_doa.read_doa()
    vs = vision.get_state()

    doa_ok = angle is None or respeaker_doa.within_speak_place(
        angle, SPEAK_ANGLE_CENTER, SPEAK_ANGLE_MARGIN
    )
    cam_ok = (not vs.get("enabled")) or vs.get("someone_at_place", True)

    if STRICT_SPEAK_PLACE:
        return doa_ok and cam_ok
    # Soepel: één positief signaal is genoeg. Dubbele onbekendheid → True.
    return doa_ok or cam_ok


# ----- Audio-device lookup --------------------------------------------------
def _resolve_audio_device(spec: str):
    """Accepteer int ('1'), leeg/'default' (= systeemdefault), of substring
    van de device-naam (bv. 'ReSpeaker'). sounddevice vereist een index of
    None, niet een ALSA-string zoals 'plughw:...'. aplay (output) gebruikt
    die ALSA-string wél, en wordt los aangestuurd."""
    if not spec or spec.lower() in ("default", "none", ""):
        return None
    try:
        return int(spec)
    except ValueError:
        pass
    needle = spec.lower()
    for i, d in enumerate(sd.query_devices()):
        if needle in d.get("name", "").lower():
            log.info(f"audio device: '{d['name']}' (index {i}) voor '{spec}'")
            return i
    log.warning(f"audio device '{spec}' niet gevonden — val terug op systeemdefault")
    return None


# ----- Luisteren + VAD ------------------------------------------------------
class Listener:
    def __init__(self) -> None:
        log.info("Silero VAD laden")
        self.vad = load_silero_vad()
        backend = os.environ.get("WHISPER_BACKEND", "cpu").lower()
        log.info(f"Whisper backend: {backend} (model={WHISPER_MODEL_NAME})")
        self.asr = whisper_hailo.load_asr()
        self.audio_q: queue.Queue[np.ndarray] = queue.Queue()

    def _callback(self, indata, frames, time_info, status):
        if status:
            log.debug(f"audio-status: {status}")
        chunk = indata[:, 0].copy()
        ns = getattr(self, "_native_sr", SAMPLE_RATE)
        if ns != SAMPLE_RATE:
            # resample native → 16000 voor VAD/whisper
            n_out = int(len(chunk) * SAMPLE_RATE / ns)
            chunk = _scisig.resample(chunk, n_out).astype("float32")
        self.audio_q.put(chunk)

    def listen_once(self):
        """Return (transcript, raw_audio_ndarray) of (None, None)."""
        buf: list[np.ndarray] = []
        last_voice_ts: float | None = None
        heard_voice = False

        dev_idx = _resolve_audio_device(AUDIO_IN)
        try:
            dev_info = sd.query_devices(dev_idx, "input")
            native_sr = int(dev_info["default_samplerate"])
        except Exception:
            native_sr = SAMPLE_RATE
        self._native_sr = native_sr
        with sd.InputStream(
            samplerate=native_sr,
            channels=1,
            blocksize=int(BLOCK_MS * native_sr / 1000),
            dtype="float32",
            device=dev_idx,
            callback=self._callback,
        ):
            while True:
                try:
                    chunk = self.audio_q.get(timeout=5.0)
                except queue.Empty:
                    continue
                buf.append(chunk)
                window = np.concatenate(buf[-int(1000 / BLOCK_MS):])
                stamps = get_speech_timestamps(
                    window, self.vad, sampling_rate=SAMPLE_RATE,
                    min_speech_duration_ms=200,
                )
                now = time.monotonic()
                if stamps:
                    last_voice_ts = now
                    heard_voice = True
                if heard_voice and last_voice_ts is not None:
                    if now - last_voice_ts > END_OF_TURN_SILENCE:
                        break
                if len(buf) * BLOCK_MS > 20000:
                    break

        if not heard_voice:
            return None, None

        audio = np.concatenate(buf)
        segments, _ = self.asr.transcribe(
            audio, language=WHISPER_LANG, vad_filter=False, beam_size=1
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return (text or None), audio


# ----- Hoofdlus -------------------------------------------------------------
def main() -> int:
    log.info(
        f"Anna Nova wordt wakker · brein={BRAIN} · "
        f"model={OLLAMA_MODEL if BRAIN=='local' else MISTRAL_MODEL}"
    )
    log.info(f"Persona: {current_persona()[:120]}...")
    log.info(f"Wake-phrase: '{WAKE_PHRASE}'  ·  awake-timeout: {AWAKE_TIMEOUT}s")

    stop = False
    def _sigterm(*_):
        nonlocal stop
        log.info("afsluiten op signaal"); stop = True
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    vision.start()
    _start_http_server()
    debug_log(f"Anna wordt wakker · brein={BRAIN}", "boot")
    time.sleep(1.0)

    # Warmup: de system-prompt is lang (persona.md ~4000 tokens). Zonder dit
    # duurt de eerste échte beurt op lokaal Phi-3 ~20-30s omdat de hele prompt
    # dan pas door de CPU-tokenizer gaat. Eén dummy-call zet de KV-cache
    # warm, daarna zijn volgende beurten snel.
    try:
        log.info("brein-warmup — eerste prompt opbouwen (dit duurt even)")
        debug_log("brein-warmup (dit duurt even)...", "init")
        t0 = time.monotonic()
        _ = think("hallo", vision.get_state())
        log.info(f"warmup klaar in {time.monotonic()-t0:.1f}s")
        debug_log(f"warmup klaar ({time.monotonic()-t0:.1f}s)", "init")
    except Exception as e:
        log.warning(f"warmup faalde (niet-fataal): {e}")
        debug_log(f"warmup faalde: {e}", "error")

    # Voice-encoder warmup: eerste identificatie kost ~1-2s voor model load.
    # Hier doen ipv in listen-flow zodat eerste gesprek niet trager wordt.
    if _VOICE_AVAILABLE and VOICEPRINT_ENABLED:
        try:
            global _VOICE_ENCODER
            if _VOICE_ENCODER is None:
                t0 = time.monotonic()
                _VOICE_ENCODER = VoiceEncoder()  # type: ignore[name-defined]
                debug_log(f"stem-encoder geladen ({time.monotonic()-t0:.1f}s)", "init")
            # Enrolled voices meteen laden zodat eerste check snel is
            _load_known_voices()
        except Exception as e:
            log.warning(f"voice-encoder warmup faalde: {e}")

    listener = Listener()

    is_awake = False
    last_activity = time.monotonic()
    last_ambient  = time.monotonic()
    had_real_gesprek = False  # was er in deze wake-sessie een echte uitwisseling?
    set_state("sluimert")
    log.info("Anna sluimert — zeg 'Hoi Anna Nova' om haar wakker te maken.")

    current_speaker: str | None = None

    while not stop:
        try:
            heard, raw_audio = listener.listen_once()
        except Exception as e:
            log.warning(f"luister-fout: {e}")
            time.sleep(1)
            continue

        # Ambient-mompel tijdens sluimer: Anna leeft ook alleen
        now = time.monotonic()
        if (not is_awake and AMBIENT_ENABLED
                and now - last_ambient > AMBIENT_INTERVAL_SEC):
            last_ambient = now
            if random.random() < AMBIENT_PROB and AMBIENT_LINES:
                line = random.choice(AMBIENT_LINES).strip()
                if line:
                    debug_log(f'ambient: "{line}"', "init")
                    say(line, log_fragment_too=False)
                    set_state("sluimert")

        if not heard:
            if is_awake and (now - last_activity > AWAKE_TIMEOUT):
                log.info("stilte duurt — Anna valt terug in sluimer")
                debug_log("sluimer (stilte duurt te lang)", "sleep")
                # Grace-period: zacht afscheid als er een echt gesprek was
                if (had_real_gesprek and GRACE_FAREWELL_ENABLED
                        and random.random() < GRACE_FAREWELL_PROB
                        and GRACE_FAREWELL_LINES):
                    farewell = random.choice(GRACE_FAREWELL_LINES).strip()
                    if farewell:
                        debug_log(f'afscheid: "{farewell}"', "speak")
                        say(farewell, log_fragment_too=False)
                is_awake = False
                had_real_gesprek = False
                set_state("sluimert")
                last_ambient = time.monotonic()  # reset ambient na afscheid
            continue

        if not is_awake:
            if wake_match(heard):
                log.info(f"wake: '{heard}'")
                debug_log(f'wake: "{heard}"', "wake")
                is_awake = True
                had_real_gesprek = False
                last_activity = time.monotonic()
                log_fragment(heard, "visitor")
                set_state("luistert")
                if WAKE_ACK:
                    say(WAKE_ACK)
                set_state("luistert")
            else:
                log.debug(f"(sluimer, niet-wake): {heard}")
                debug_log(f'genegeerd (geen wake): "{heard[:40]}"', "skip")
            continue

        last_activity = time.monotonic()

        # Slaap-commando: direct opvolgen, zelfs als buiten de spreekplek —
        # Jolanda moet Anna altijd kunnen laten slapen.
        if sleep_match(heard):
            log.info(f"sleep-commando: '{heard}'")
            debug_log(f'slaap-opdracht: "{heard}"', "sleep")
            log_fragment(heard, "visitor")
            if SLEEP_ACK:
                say(SLEEP_ACK)
            is_awake = False
            set_state("sluimert")
            continue

        if not from_speak_place():
            log.info(f"gehoord maar buiten spreekplek — negeer: {heard}")
            debug_log(f'buiten spreekplek: "{heard[:40]}"', "skip")
            continue

        # Voiceprint-check (optioneel, graceful)
        speaker = identify_speaker(raw_audio) if raw_audio is not None else None
        if speaker and speaker != current_speaker:
            current_speaker = speaker
            debug_log(f"stem herkend: {speaker}", "wake")

        log.info(f"Bezoeker ({current_speaker or 'onbekend'}): {heard}")
        debug_log(f'{current_speaker or "bezoeker"}: "{heard}"', "visitor")
        log_fragment(heard, "visitor")
        had_real_gesprek = True  # markeer: er is een echt gesprek, afscheid is op zijn plaats

        set_state("denkt")
        vs = vision.get_state()
        # Geef identity mee aan de prompt (als bekend)
        vs = dict(vs)
        vs["speaker_name"] = current_speaker

        # STREAMING: start met spreken zodra de eerste zin klaar is.
        t0 = time.monotonic()
        parts: list[str] = []
        spoke = False
        try:
            for sentence in think_stream(heard, vs):
                clean = sentence.strip()
                if not clean:
                    continue
                if clean.upper() == "[STIL]":
                    continue
                clean = _handle_photo_tag(clean)
                if not clean:
                    continue
                parts.append(clean)
                if not spoke:
                    debug_log(f"eerste zin ({time.monotonic()-t0:.1f}s)", "think_end")
                    spoke = True
                say(clean, log_fragment_too=False)
        except Exception as e:
            log.warning(f"stream-fout: {e}")
            debug_log(f"stream-fout: {e}", "error")

        answer_full = " ".join(parts).strip()

        if not answer_full and ALLOW_SILENCE:
            log.info("(Anna zwijgt)")
            debug_log("Anna zwijgt", "speak")
            log_fragment("[STIL]", "anna")
            set_state("luistert")
            continue

        if answer_full:
            log_fragment(answer_full, "anna")

        set_state("luistert")
        last_activity = time.monotonic()

    vision.stop()
    log.info("Anna slaapt in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
