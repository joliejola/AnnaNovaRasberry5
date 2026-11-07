"""Printer — stuurt een PIL.Image naar het printertje.

Droogloop-modus: slaat PNG op in /tmp en print pad in log.
Live-modus: Agodeo mini (via TiMini-Print) → USB ESC/POS → PNG-opslag fallback.

Env:
  PRINTER            mini | escpos | geen
  PRINTER_MAC        bluetooth-MAC van printertje (AA:BB:CC:DD:EE:FF)
  TIMINI_PYTHON      pad naar python in TiMini-venv (default /home/anna/timini/.venv/bin/python)
  TIMINI_MODEL       optioneel --printer-model flag voor NoeBrt-fork (bv MX06, T02)
  PRINT_TIMEOUT_S    subprocess-timeout, default 25
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"
PRINTER = os.environ.get("PRINTER", "geen")  # mini | escpos | geen
PRINTER_MAC = os.environ.get("PRINTER_MAC", "")
TIMINI_PYTHON = os.environ.get("TIMINI_PYTHON", "/home/anna/timini/.venv/bin/python")
TIMINI_MODEL = os.environ.get("TIMINI_MODEL", "")
PRINT_TIMEOUT_S = float(os.environ.get("PRINT_TIMEOUT_S", "25"))


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
    """Agodeo mini via Bluetooth — TiMini-Print subprocess.

    Schrijft PIL.Image naar tempfile en roept TiMini-CLI aan:
        <TIMINI_PYTHON> -m timini --bluetooth <MAC> --file <png>
        [--printer-model <model>]   # optioneel via TIMINI_MODEL
    """
    if not PRINTER_MAC:
        raise RuntimeError("PRINTER_MAC niet gezet in .env")
    if not Path(TIMINI_PYTHON).exists():
        raise RuntimeError(f"TiMini python niet gevonden: {TIMINI_PYTHON}")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img_pad = tmp.name
    img.save(img_pad)

    cmd = [TIMINI_PYTHON, "-m", "timini", "--bluetooth", PRINTER_MAC, "--file", img_pad]
    if TIMINI_MODEL:
        cmd += ["--printer-model", TIMINI_MODEL]

    try:
        r = subprocess.run(
            cmd, capture_output=True, timeout=PRINT_TIMEOUT_S, text=True
        )
    except subprocess.TimeoutExpired:
        return False, f"TiMini timeout na {PRINT_TIMEOUT_S}s"
    finally:
        try:
            os.unlink(img_pad)
        except OSError:
            pass

    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
        return False, f"TiMini exit {r.returncode}: {tail[0]}"
    return True, "mini-printer OK"


def _print_escpos(img: Image.Image) -> tuple[bool, str]:
    """USB ESC/POS via python-escpos (fallback). Vendor/product-id uit env.

    Env:
      ESCPOS_VID  hex (bv 0x0416)
      ESCPOS_PID  hex (bv 0x5011)
    """
    try:
        from escpos.printer import Usb  # type: ignore
    except ImportError as e:
        raise RuntimeError(f"python-escpos niet geinstalleerd: {e}")

    vid = os.environ.get("ESCPOS_VID", "")
    pid = os.environ.get("ESCPOS_PID", "")
    if not vid or not pid:
        raise RuntimeError("ESCPOS_VID / ESCPOS_PID niet gezet — zie `lsusb`")

    p = Usb(int(vid, 16), int(pid, 16))
    try:
        p.image(img)
        p.cut()
        return True, "escpos OK"
    finally:
        try:
            p.close()
        except Exception:
            pass
