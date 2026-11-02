"""
ReSpeaker XVF3800 — Direction of Arrival reader.

Leest de hoek (0-359°) waar het laatste geluid vandaan kwam.
Graceful fallback: als het apparaat niet gevonden wordt, retourneert None
en de hoofdlus negeert de spreekplek-check.

Gebaseerd op de XMOS XVF3800 USB HID control-interface.
"""
from __future__ import annotations

import logging
import struct
import time
from typing import Optional

log = logging.getLogger("anna.doa")

# XMOS XVF3800 USB IDs (meest gangbare Seeed-variant)
XVF3800_VID = 0x20B1  # XMOS Ltd
XVF3800_PID_CANDIDATES = [0x0010, 0x0014, 0x4010]  # verschillende Seeed-revisies

# Control-parameters volgens XVF3800 datasheet
CMD_DOA = 0x37     # Direction of Arrival in degrees (0-359)
CMD_SPEECH = 0x1F  # Speech detected (0/1)

_dev = None

def _try_import_usb():
    try:
        import usb.core  # pyusb
        import usb.util
        return usb.core, usb.util
    except ImportError:
        log.warning("pyusb niet beschikbaar — DoA uitgeschakeld")
        return None, None

def _find_device():
    usb_core, _ = _try_import_usb()
    if usb_core is None:
        return None
    for pid in XVF3800_PID_CANDIDATES:
        dev = usb_core.find(idVendor=XVF3800_VID, idProduct=pid)
        if dev is not None:
            log.info(f"XVF3800 gevonden (vid={XVF3800_VID:04x}, pid={pid:04x})")
            return dev
    log.warning("XVF3800 niet gevonden op USB — DoA uitgeschakeld")
    return None

def _init_once():
    global _dev
    if _dev is None:
        _dev = _find_device()
    return _dev

def read_doa() -> Optional[int]:
    """Return hoek 0-359° of None als niet beschikbaar."""
    dev = _init_once()
    if dev is None:
        return None
    try:
        # XMOS HID control transfer: GET report voor DOA command
        # bmRequestType = 0xA1 (device-to-host, class, interface)
        # bRequest = 0x01 (GET_REPORT)
        # wValue = 0x0300 | report_id (0x00)
        # wIndex = interface (meestal 3 voor control-interface)
        resp = dev.ctrl_transfer(
            bmRequestType=0xA1,
            bRequest=0x01,
            wValue=0x0300,
            wIndex=3,
            data_or_wLength=64,
            timeout=200,
        )
        if resp is None or len(resp) < 8:
            return None
        # Parse response — eerste 4 bytes zijn vaak header, daarna uint32 LE
        value = struct.unpack_from("<I", resp, 4)[0]
        return value % 360
    except Exception as e:
        log.debug(f"DoA-read-fout: {e}")
        return None


def within_speak_place(angle: int, center: int, margin: int) -> bool:
    """True als 'angle' binnen [center-margin, center+margin] (met wrap-around)."""
    diff = (angle - center + 180) % 360 - 180
    return abs(diff) <= margin


if __name__ == "__main__":
    # Simpele test: elke 500ms de hoek printen
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("DoA-test — spreek vanaf verschillende hoeken. Ctrl-C om te stoppen.")
    while True:
        a = read_doa()
        print(f"  hoek: {a}°" if a is not None else "  (geen DoA)")
        time.sleep(0.5)
