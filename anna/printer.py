"""Printer — stuurt een PIL.Image naar het printertje.

Droogloop-modus: slaat PNG op in /tmp en print pad in log.
Live-modus (bouwstap 3): Agodeo mini → USB ESC/POS → PNG-opslag fallback.
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"
PRINTER = os.environ.get("PRINTER", "geen")  # mini | escpos | geen


def print_bon(img: Image.Image) -> tuple[bool, str]:
    """Print of simuleer print. Returns (succes, info-string).

    In droogloop: saves to /tmp/bon_droogloop_<ts>.png.
    Live: probeer mini → escpos → PNG-opslag + 'geenprint'-signal.
    """
    if DROOGLOOP or PRINTER == "geen":
        return _save_tijdelijk(img)

    if PRINTER == "mini":
        try:
            return _print_mini(img)
        except Exception as e:
            log.warning("Agodeo mini faalt: %s → probeer ESC/POS", e)

    if PRINTER in ("escpos", "mini"):
        try:
            return _print_escpos(img)
        except Exception as e:
            log.warning("ESC/POS faalt: %s → PNG-fallback", e)

    return _save_tijdelijk(img, meld_geenprint=True)


def _save_tijdelijk(img: Image.Image, meld_geenprint: bool = False) -> tuple[bool, str]:
    ts = int(time.time())
    pad = Path(tempfile.gettempdir()) / f"bon_droogloop_{ts}.png"
    img.save(pad)
    msg = f"bon gesaved → {pad}"
    if meld_geenprint:
        msg = f"GEEN PRINTER — bon niet geprint, {msg}"
    log.info(msg)
    return True, msg


def _print_mini(img: Image.Image) -> tuple[bool, str]:
    """Agodeo mini via Bluetooth (TiMini-Print / funprint CLI).

    Bouwstap 3 vult dit in; placeholder faalt expliciet."""
    raise NotImplementedError("bouwstap 3: Agodeo mini-integratie")


def _print_escpos(img: Image.Image) -> tuple[bool, str]:
    """USB ESC/POS via python-escpos.

    Bouwstap 3 vult dit in."""
    raise NotImplementedError("bouwstap 3: USB ESC/POS-integratie")
