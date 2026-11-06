"""Horen — wake/sleep-detectie + spraak-capture.

Droogloop-modus (`DROOGLOOP=1`): leest regels van stdin ipv mic.
- Lege regel (Enter) = stilte
- "#ruis" = ruis-event
- "#druk" = meerdere mensen op plek (via see.py)
- "#weg" = plek leeg (via see.py)
- "#status" = toon flow-state (debug)
- Normale tekst = gesproken zin — fuzzy match op wake/sleep gebeurt hier.

Live-modus (later op Pi): wrapt VAD + Voxtral ASR + wake/sleep-fuzzy-match.
De interface is gelijk zodat flow.py niet hoeft te weten of we droogloop of
echte mic doen.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Literal, Optional

log = logging.getLogger(__name__)

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"

# Fuzzy wake/sleep-patronen. Komma-lijsten uit .env (hergebruik oude config).
WAKE_PATTERNS = [p.strip().lower() for p in os.environ.get(
    "WAKE_PHRASE_PATTERNS",
    "hoi anna nova, hallo anna nova, hoi anna, hey anna nova, anna nova, oké anna nova"
).split(",") if p.strip()]

SLEEP_PATTERNS = [p.strip().lower() for p in os.environ.get(
    "SLEEP_PHRASES",
    "slaap lekker,slaap zacht,welterusten,ga slapen,ga maar slapen,"
    "doe een dutje,tot morgen,slaap maar,genoeg geweest,stil nu,"
    "anna slapen,dag anna,doei anna"
).split(",") if p.strip()]


EventType = Literal[
    "wake",       # wake-phrase gehoord
    "sleep",      # sleep-phrase gehoord
    "spraak",    # gewone spraak
    "stilte",    # geen geluid binnen timeout
    "ruis",      # geluid maar geen woorden
    "druk",      # meerdere sprekers detecteerd (via see)
    "weg",       # plek is leeg geraakt
    "debug",      # debug-command, flow mag beslissen wat
]


@dataclass
class Event:
    type: EventType
    tekst: str = ""
    raw: str = ""


# ---------- fuzzy match ----------

_PUNCT = re.compile(r"[^\w\s]")


def _normaliseer(s: str) -> str:
    return _PUNCT.sub(" ", s.lower()).strip()


def match_wake(tekst: str) -> bool:
    n = _normaliseer(tekst)
    return any(p in n for p in WAKE_PATTERNS)


def match_sleep(tekst: str) -> bool:
    n = _normaliseer(tekst)
    for pat in SLEEP_PATTERNS:
        if pat in n:
            return True
    return False


# ---------- droogloop-input ----------

def _lees_regel(prompt: str = "", timeout: Optional[float] = None) -> str:
    """Lees een regel van stdin.

    In droogloop negeren we `timeout` omdat input() blokkeert; stiltes
    simuleer je door Enter te drukken.
    """
    try:
        return input(prompt)
    except EOFError:
        return ""


def _is_debug_cmd(regel: str) -> bool:
    return regel.strip().startswith("#")


def _classificeer_regel(regel: str) -> Event:
    """Droogloop-regel → Event."""
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
    if match_sleep(stripped):
        return Event("sleep", tekst=stripped, raw=stripped)
    if match_wake(stripped):
        return Event("wake", tekst=stripped, raw=stripped)
    return Event("spraak", tekst=stripped, raw=stripped)


# ---------- publieke API (flow.py gebruikt deze) ----------

def luister_wake(prompt: str = "[rust] ") -> Event:
    """Blokkeer tot een wake-event, sleep-event, of iets dat flow mag zien.

    In RUST-toestand roept flow deze aan. Alleen wake, sleep, weg, druk,
    en debug komen terug. Spraak-zonder-wake wordt genegeerd (we zijn RUST).
    """
    while True:
        regel = _lees_regel(prompt) if DROOGLOOP else _lees_regel_live(prompt)
        ev = _classificeer_regel(regel)
        if ev.type in ("wake", "sleep", "weg", "druk", "debug"):
            return ev
        # stilte / ruis / spraak → doorgaan, Anna blijft slapen
        if DROOGLOOP:
            log.debug("[RUST negeert] %r", regel)


def luister_spraak(prompt: str = "[luistert] ", stilte_na_s: float = 8.0) -> Event:
    """Luister in een actieve toestand. Timeout → stilte-event.

    In droogloop blokkeren we tot input; stilte-event krijg je door Enter.
    """
    regel = _lees_regel(prompt) if DROOGLOOP else _lees_regel_live(prompt, timeout=stilte_na_s)
    return _classificeer_regel(regel)


def _lees_regel_live(prompt: str, timeout: Optional[float] = None) -> str:
    """Placeholder voor live-mic in latere bouwstap 7.

    Stub die exception geeft als per ongeluk aangeroepen zonder droogloop.
    """
    raise NotImplementedError(
        "Live-mode hear.py komt in bouwstap 7. Draai met DROOGLOOP=1."
    )
