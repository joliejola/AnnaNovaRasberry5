#!/usr/bin/env python3
"""End-to-end flow-test op Pi met echte speak/brain/bon + mocked hear.

Werkt met MISTRAL_API_KEY in env (brain-call echt). Hear wordt gemocked
zodat we geen mic nodig hebben om het hele pad te lopen.

Draai op Pi:
    bash -c 'set -a && while IFS= read -r l; do [[ -z "$l" || "$l" == \\#* ]] && continue; k=${l%%=*}; v=${l#*=}; export "$k=$v"; done < .env && .venv/bin/python tools/test_pi_flow.py'

Of korter via start-anna.sh patroon.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from anna import bon, flow, hear, face

# Start face-server (poort 8765)
face.start()

# Mock sequence: wake → 5 vraag-antwoorden → ja op rekening
MOCK = iter([
    hear.Event(type="wake", tekst="hoi anna nova"),
    hear.Event(type="spraak", tekst="Ja ik wil."),
    hear.Event(type="spraak", tekst="Een beetje, denk ik."),
    hear.Event(type="spraak", tekst="Mijn zoekgeschiedenis."),
    hear.Event(type="spraak", tekst="Afgelopen week, een vriend."),
    hear.Event(type="spraak", tekst="Misschien wel."),
    hear.Event(type="spraak", tekst="Ja graag."),
])


def mock_wake(prompt: str = "") -> hear.Event:
    try:
        return next(MOCK)
    except StopIteration:
        raise KeyboardInterrupt


def mock_spraak(prompt: str = "", stilte_na_s: float = 8.0) -> hear.Event:
    try:
        return next(MOCK)
    except StopIteration:
        raise KeyboardInterrupt


hear.luister_wake = mock_wake
hear.luister_spraak = mock_spraak

inhoud = bon.laad_inhoud()
f = flow.Flow(inhoud, state_cb=lambda s: face.push_state(s.value))

# Stop na eerste LOSLATEN
losgelaten = [False]
orig_switch = f._switch

def tracked_switch(nieuwe):
    orig_switch(nieuwe)
    if nieuwe == flow.State.LOSLATEN:
        losgelaten[0] = True
        f._should_stop = True

f._switch = tracked_switch  # type: ignore

try:
    f.run_tot_stop()
except KeyboardInterrupt:
    print("[test] script leeg → einde")
finally:
    face.stop()
    print(f"\n[test] losgelaten={losgelaten[0]}")
