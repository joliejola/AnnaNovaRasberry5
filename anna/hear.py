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
    """Placeholder voor live-mic in bouwstap 7."""
    raise NotImplementedError(
        "Live-mode hear.py komt in bouwstap 7. Draai met DROOGLOOP=1."
    )
