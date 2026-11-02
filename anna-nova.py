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
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn

import numpy as np
import requests
import sounddevice as sd
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps

import respeaker_doa
import vision

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
END_OF_TURN_SILENCE = float(os.environ.get("END_OF_TURN_SILENCE", "1.2"))

SPEAK_ANGLE_CENTER  = int(os.environ.get("SPEAK_ANGLE_CENTER", "0"))
SPEAK_ANGLE_MARGIN  = int(os.environ.get("SPEAK_ANGLE_MARGIN", "30"))
STRICT_SPEAK_PLACE  = os.environ.get("STRICT_SPEAK_PLACE", "false").lower() == "true"

WAKE_PHRASE         = os.environ.get("WAKE_PHRASE", "hoi anna nova")
WAKE_ACK            = os.environ.get("WAKE_ACK", "Hm.")  # Anna's kort "ja?" bij wakker worden
AWAKE_TIMEOUT       = float(os.environ.get("AWAKE_TIMEOUT", "60"))

WEB_DIR             = os.environ.get("WEB_DIR", str(Path.home() / "anna-nova/web"))
PHOTOS_DIR          = os.environ.get("PHOTOS_DIR", str(Path.home() / "anna-nova/photos"))
HTTP_PORT           = int(os.environ.get("HTTP_PORT", "8765"))

SAMPLE_RATE = 16000
BLOCK_MS    = 32
BLOCK_SIZE  = int(SAMPLE_RATE * BLOCK_MS / 1000)

# ----- Globale state (gedeeld met HTTP-server) ------------------------------
_state_lock = threading.Lock()
CURRENT_STATE = "sluimert"  # sluimert | luistert | denkt | spreekt

def set_state(s: str) -> None:
    global CURRENT_STATE
    with _state_lock:
        if CURRENT_STATE != s:
            CURRENT_STATE = s
            log.info(f"state → {s}")

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

    def do_GET(self):
        if self.path == "/" or self.path == "/face":
            self.path = "/face.html"
        elif self.path == "/gallery":
            self.path = "/gallery.html"

        if self.path == "/state":
            with _state_lock:
                s = CURRENT_STATE
            return self._json({"state": s, "ts": time.time()})

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

    core = _load_persona_core()
    arc = current_persona()

    # Context die per beurt wisselt — hangt onder de persona-kern
    runtime_context = f"""

---

## VANDAAG (door jezelf vannacht geschreven)

{arc}

## WIE ER NU IS

- GESPREKSPARTNER: de persoon op de spreekplek. Aan haar of hem richt je je antwoord.
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
def think_local(user_text: str, vision_state: dict) -> str:
    r = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": build_system_prompt(vision_state)},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
            "options": {"temperature": 0.8, "num_predict": 120},
        },
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()

def think_cloud(user_text: str, vision_state: dict) -> str:
    if not MISTRAL_API_KEY:
        raise RuntimeError("BRAIN=cloud maar MISTRAL_API_KEY leeg")
    r = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
        json={
            "model": MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": build_system_prompt(vision_state)},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.8,
            "max_tokens": 160,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def think(user_text: str, vision_state: dict) -> str:
    try:
        return (think_local if BRAIN == "local" else think_cloud)(user_text, vision_state)
    except Exception as e:
        log.warning(f"brein-fout: {e}")
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
        return None
    log.info(f"foto opgeslagen: {fname} — \"{caption[:60]}\"")
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
def say(text: str) -> None:
    if not text or text.strip() == "[STIL]":
        log.info("(zwijgen)")
        return
    if not PIPER_BIN or not Path(PIPER_BIN).exists():
        log.info(f"Piper niet gevonden; print: {text}")
        return
    log.info(f"Anna: {text}")
    set_state("spreekt")
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
    log_fragment(text, "anna")


# ----- Wake-detectie --------------------------------------------------------
def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-zàâçéèêëîïôûùüÿñæœ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def wake_match(transcript: str, phrase: str = WAKE_PHRASE) -> bool:
    """Fuzzy match: 'hoi anna nova', 'hoi anna', 'hallo anna nova', 'anna nova' etc.

    Vereist dat ten minste 'anna' + ('nova' of een groet) voorkomt."""
    t = _normalize(transcript)
    want = _normalize(phrase)
    # Exacte substring: altijd goed
    if want in t:
        return True
    # Soepel: 'anna' moet erin, en 'nova' of een duidelijke groet
    groet_hits = any(g in t for g in ("hoi", "hallo", "hey", "hé", "dag", "goedemiddag", "goedemorgen", "goedenavond"))
    heeft_anna = "anna" in t
    heeft_nova = "nova" in t
    return heeft_anna and (heeft_nova or groet_hits)


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
        log.info(f"Whisper laden ({WHISPER_MODEL_NAME}, int8)")
        self.asr = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
        self.audio_q: queue.Queue[np.ndarray] = queue.Queue()

    def _callback(self, indata, frames, time_info, status):
        if status:
            log.debug(f"audio-status: {status}")
        self.audio_q.put(indata[:, 0].copy())

    def listen_once(self) -> str | None:
        buf: list[np.ndarray] = []
        last_voice_ts: float | None = None
        heard_voice = False

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=BLOCK_SIZE,
            dtype="float32",
            device=_resolve_audio_device(AUDIO_IN),
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
            return None

        audio = np.concatenate(buf)
        segments, _ = self.asr.transcribe(
            audio, language=WHISPER_LANG, vad_filter=False, beam_size=1
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return text or None


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
    time.sleep(1.0)

    # Warmup: de system-prompt is lang (persona.md ~4000 tokens). Zonder dit
    # duurt de eerste échte beurt op lokaal Phi-3 ~20-30s omdat de hele prompt
    # dan pas door de CPU-tokenizer gaat. Eén dummy-call zet de KV-cache
    # warm, daarna zijn volgende beurten snel.
    try:
        log.info("brein-warmup — eerste prompt opbouwen (dit duurt even)")
        t0 = time.monotonic()
        _ = think("hallo", vision.get_state())
        log.info(f"warmup klaar in {time.monotonic()-t0:.1f}s")
    except Exception as e:
        log.warning(f"warmup faalde (niet-fataal): {e}")

    listener = Listener()

    is_awake = False
    last_activity = time.monotonic()
    set_state("sluimert")
    log.info("Anna sluimert — zeg 'Hoi Anna Nova' om haar wakker te maken.")

    while not stop:
        try:
            heard = listener.listen_once()
        except Exception as e:
            log.warning(f"luister-fout: {e}")
            time.sleep(1)
            continue

        if not heard:
            if is_awake and (time.monotonic() - last_activity > AWAKE_TIMEOUT):
                log.info("stilte duurt — Anna valt terug in sluimer")
                is_awake = False
                set_state("sluimert")
            continue

        if not is_awake:
            if wake_match(heard):
                log.info(f"wake: '{heard}'")
                is_awake = True
                last_activity = time.monotonic()
                log_fragment(heard, "visitor")
                set_state("luistert")
                if WAKE_ACK:
                    say(WAKE_ACK)
                set_state("luistert")
            else:
                log.debug(f"(sluimer, niet-wake): {heard}")
            continue

        last_activity = time.monotonic()

        if not from_speak_place():
            log.info(f"gehoord maar buiten spreekplek — negeer: {heard}")
            continue

        log.info(f"Bezoeker: {heard}")
        log_fragment(heard, "visitor")

        set_state("denkt")
        vs = vision.get_state()
        answer = think(heard, vs)

        if answer.strip() == "[STIL]" and ALLOW_SILENCE:
            log.info("(Anna zwijgt)")
            log_fragment("[STIL]", "anna")
            set_state("luistert")
            continue

        # [FOTO]-tag verwerken: foto nemen + tag strippen uit de uit te spreken tekst
        answer = _handle_photo_tag(answer)
        if not answer:
            # Alleen [FOTO] zonder woorden — foto is al genomen, we zwijgen hoorbaar
            set_state("luistert")
            continue

        say(answer)
        set_state("luistert")
        last_activity = time.monotonic()

    vision.stop()
    log.info("Anna slaapt in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
