"""Scherm-bridge. HTTP-server die web/face.html + state-polling-endpoint doet.

flow.py roept face.push_state(flow_state) → mapping naar scherm-state →
browser pakt via /tick elke 500ms op.

Bron 2 noemt websocket maar HTTP-polling is pragmatisch:
- 500ms is snel genoeg voor state-wissels
- geen extra dependency (stdlib only)
- werkt met bestaande face.html-structuur

Mapping flow-toestanden → scherm (6 states, bron 2 sync 6 nov 14:50):
  RUST, LOSLATEN           → "rust"
  OPENING, VRAAG, ZACHT    → "spreekt"
  LUISTEREN, STIL, RUIS    → "luistert"
  REAGEREN                 → "denkt"
  AFSLUITING               → "afrekenen"
  BON                      → "print"
"""
from __future__ import annotations

import http.server
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
PORT = int(os.environ.get("FACE_PORT", "8765"))

FLOW_TO_SCHERM = {
    "RUST": "rust",
    "LOSLATEN": "rust",
    "OPENING": "spreekt",
    "VRAAG": "spreekt",
    "ZACHT": "spreekt",
    "LUISTEREN": "luistert",
    "STIL": "luistert",
    "RUIS": "luistert",
    "REAGEREN": "denkt",
    "AFSLUITING": "afrekenen",
    "BON": "print",
}


class _State:
    def __init__(self) -> None:
        self.state: str = "rust"
        self.visitor: str = ""
        self.anna: str = ""
        self.action: str = ""
        self.heard: str = ""
        self.lock = threading.Lock()

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "state": self.state,
                "visitor": self.visitor,
                "anna": self.anna,
                "action": self.action,
                "heard": self.heard,
            }


_STATE = _State()
_SERVER: Optional[http.server.ThreadingHTTPServer] = None


# ---------- publieke API ----------

def push_state(flow_state: str) -> None:
    """Roep aan uit flow.state_cb. flow_state is bijv. 'LUISTEREN'."""
    scherm = FLOW_TO_SCHERM.get(flow_state, "rust")
    with _STATE.lock:
        _STATE.state = scherm
        if scherm == "rust":
            # wissen bij terug naar rust
            _STATE.visitor = ""
            _STATE.anna = ""


def push_visitor(tekst: str) -> None:
    with _STATE.lock:
        _STATE.visitor = tekst[:100]


def push_anna(tekst: str) -> None:
    with _STATE.lock:
        _STATE.anna = tekst[:120]


def push_action(tekst: str) -> None:
    with _STATE.lock:
        _STATE.action = tekst[:40]


def push_heard(tekst: str) -> None:
    with _STATE.lock:
        _STATE.heard = tekst[:80]


# ---------- HTTP-server ----------

class _Handler(http.server.SimpleHTTPRequestHandler):
    # Serveer uit WEB_DIR
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/tick"):
            body = json.dumps(_STATE.snapshot()).encode()
            self._json(body)
            return
        if self.path.startswith("/raster"):
            # Camera-raster + pose voor achtergrond.js (HTTP-polling)
            try:
                from anna import see_live
                payload = {
                    "grid": see_live.get_raster(),
                    "pts": see_live.get_pose(),
                }
            except Exception:
                payload = {"grid": None, "pts": None}
            body = json.dumps(payload).encode()
            self._json(body)
            return
        if self.path in ("/", "/index.html"):
            self.path = "/face.html"
        return super().do_GET()

    def _json(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Quiet HTTP log — logger pakt errors op elders
        if "/tick" not in self.path:
            log.debug("%s - %s", self.address_string(), fmt % args)


def start(port: int = PORT) -> http.server.ThreadingHTTPServer:
    """Start de HTTP-server in een daemon-thread. Idempotent."""
    global _SERVER
    if _SERVER is not None:
        return _SERVER
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    t = threading.Thread(target=server.serve_forever, name="face-http", daemon=True)
    t.start()
    log.info("face.py: http://localhost:%d/  (serveert %s)", port, WEB_DIR)
    _SERVER = server
    return server


def stop() -> None:
    global _SERVER
    if _SERVER:
        _SERVER.shutdown()
        _SERVER = None
