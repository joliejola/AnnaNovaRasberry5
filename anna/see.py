"""Zien — hoeveel mensen op spreekplek, DoA-hoek (indirect).

Droogloop-modus: toggelbaar via #weg / #druk uit hear.py.
Live-modus (bouwstap 7): Hailo-8L SCRFD + ReSpeaker DoA-matching.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"

PlekStatus = Literal["leeg", "een", "meer"]


@dataclass
class ZieStatus:
    """Momentopname wat see.py 'nu' denkt."""
    plek: PlekStatus = "een"  # droogloop-default: 1 persoon op plek
    in_ruimte: int = 1
    doa_graden: float | None = 0.0

    def is_leeg(self) -> bool:
        return self.plek == "leeg"

    def is_druk(self) -> bool:
        return self.plek == "meer"


class ZieBron:
    """Houdt live status bij. In droogloop verandert dat via hear.py-events
    (#weg → leeg, #druk → meer, iets anders → terug naar een)."""

    def __init__(self) -> None:
        self.status = ZieStatus()

    def set(self, plek: PlekStatus, **kw) -> None:
        self.status = ZieStatus(plek=plek, **kw)

    def get(self) -> ZieStatus:
        return self.status
