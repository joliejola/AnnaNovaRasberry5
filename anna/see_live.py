"""Zien — camera naar raster + pose (live op Pi).

Opent picamera2, leest 10 fps, resample naar 64x48 grijsraster, stuurt
dat via een thread-safe holder naar face.py (/raster-endpoint).

Pose: optioneel via Hailo later. Nu alleen stippen (werkt zonder HEF).

Privacy-regel: originele frame blijft in geheugen van deze module, alleen
het 64x48 raster (3072 floats 0..1) wordt doorgegeven. Niks naar schijf.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

COLS = 64
ROWS = 48
FPS = 10

_LATEST_RASTER: list[float] | None = None
_LATEST_POSE: list[list[float]] | None = None
_LOCK = threading.Lock()
_THREAD: Optional[threading.Thread] = None
_STOP = threading.Event()


def get_raster() -> list[float] | None:
    with _LOCK:
        return _LATEST_RASTER


def get_pose() -> list[list[float]] | None:
    with _LOCK:
        return _LATEST_POSE


def _set_raster(grid: list[float]) -> None:
    global _LATEST_RASTER
    with _LOCK:
        _LATEST_RASTER = grid


def start() -> None:
    """Start camera-thread als die nog niet draait."""
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _STOP.clear()
    _THREAD = threading.Thread(target=_run, name="see-live", daemon=True)
    _THREAD.start()


def stop() -> None:
    _STOP.set()


def _run() -> None:
    try:
        from picamera2 import Picamera2
        import numpy as np
    except ImportError as e:
        log.error("see_live: picamera2/numpy niet beschikbaar (%s) — raster blijft leeg", e)
        return

    try:
        cam = Picamera2()
        # 640x480 is de laagste native OV5647-mode — betrouwbaarder dan 160x120
        cfg = cam.create_preview_configuration(
            main={"size": (640, 480), "format": "YUV420"},
            buffer_count=4,
        )
        cam.configure(cfg)
        cam.start()
        log.info("see_live: picamera2 open (640x480 YUV)")
        # Eerste frame kan traag zijn — warm-up
        time.sleep(1.5)
    except Exception as e:
        log.error("see_live: picamera2 start faalt: %s", e)
        return

    period = 1.0 / FPS
    try:
        while not _STOP.is_set():
            t0 = time.monotonic()
            try:
                frame = cam.capture_array("main")
                # YUV420: Y-plane = eerste H rijen. 640x480 → 480 rijen Y.
                y = frame[:480, :640]
                raster = _downsample_to_64x48(y)
                _set_raster(raster)
            except Exception as e:
                log.warning("see_live: capture fout: %s", e)
                time.sleep(period * 4)
                continue

            dt = time.monotonic() - t0
            if dt < period:
                time.sleep(period - dt)
    finally:
        try:
            cam.stop()
        except Exception:
            pass
        log.info("see_live: gestopt")


def _downsample_to_64x48(y) -> list[float]:
    """Y-plane (120x160 uint8) → 48x64 grijsraster, flat list, 0..1."""
    import numpy as np
    # Gewoon mean pooling: (120,160) → (48,64)
    # 120/48 = 2.5, 160/64 = 2.5. Nearest resize via numpy slicing.
    # Simpeler: average pool 2x2 → dan interpolate. Of resize via PIL.
    from PIL import Image
    img = Image.fromarray(y)
    img = img.resize((COLS, ROWS), Image.Resampling.BILINEAR)
    arr = np.asarray(img, dtype="float32") / 255.0
    # Mirror horizontaal voor "spiegelbeeld" effect
    arr = arr[:, ::-1]
    return arr.flatten().tolist()
