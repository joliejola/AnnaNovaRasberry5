"""
Anna's ogen — Hailo-8L + Picamera2.

Draait in een eigen thread. Doet elke ~100 ms:
  - frame grijpen (OV5647 via Picamera2)
  - SCRFD-2.5g inference op Hailo-8L → face bboxes
  - optioneel: face_attr (smile, mouth-open) voor mood-hint
  - state publiceren: hoeveel personen, wie staat in de spreekplek-zone,
    algemene mood-indicator.

Graceful fallback: als Hailo of camera niet beschikbaar is, blijft de
state op "iemand aanwezig" (True) zodat de hoofdlus doordraait zonder
visie.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger("anna.vision")

# ----- Config uit .env ------------------------------------------------------
VISION_ENABLED  = os.environ.get("VISION_ENABLED", "false").lower() == "true"
SCRFD_HEF       = os.environ.get("SCRFD_HEF", "/usr/share/hailo-models/scrfd_2_5g.hef")
FACE_ATTR_HEF   = os.environ.get("FACE_ATTR_HEF", "/usr/share/hailo-models/face_attr_resnet_v1_18.hef")

# Spreekplek-zone in frame-coordinaten (0-1 relatief).
# Default: centrum van beeld, 40% breed, van 20% tot 90% hoog.
PLACE_X_MIN = float(os.environ.get("PLACE_X_MIN", "0.30"))
PLACE_X_MAX = float(os.environ.get("PLACE_X_MAX", "0.70"))
PLACE_Y_MIN = float(os.environ.get("PLACE_Y_MIN", "0.20"))
PLACE_Y_MAX = float(os.environ.get("PLACE_Y_MAX", "0.90"))

CAM_WIDTH   = int(os.environ.get("CAM_WIDTH", "1280"))
CAM_HEIGHT  = int(os.environ.get("CAM_HEIGHT", "720"))


@dataclass
class VisionState:
    """Gedeelde, thread-safe state. Hoofdlus leest hiervan."""
    enabled: bool = False
    frame_ts: float = 0.0
    faces: List[Tuple[float, float, float, float]] = field(default_factory=list)  # (x, y, w, h) 0-1
    someone_at_place: bool = False
    visitor_count: int = 0
    mood_hint: str = ""
    latest_frame: Optional["np.ndarray"] = None  # type: ignore[name-defined]
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "someone_at_place": self.someone_at_place,
                "visitor_count": self.visitor_count,
                "mood_hint": self.mood_hint,
                "age_sec": (time.monotonic() - self.frame_ts) if self.frame_ts else -1,
            }


def save_latest_photo(path: str) -> bool:
    """Schrijf het laatst-gegrepen frame weg als JPG. True bij succes."""
    with _state._lock:
        frame = _state.latest_frame
    if frame is None:
        return False
    try:
        import cv2
        # RGB888 → BGR voor OpenCV JPEG-write
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return bool(cv2.imwrite(path, bgr, [cv2.IMWRITE_JPEG_QUALITY, 88]))
    except Exception as e:
        log.warning(f"foto-schrijven faalde: {e}")
        return False


_state = VisionState()
_worker: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _in_speak_zone(x: float, y: float, w: float, h: float) -> bool:
    cx, cy = x + w / 2, y + h / 2
    return PLACE_X_MIN <= cx <= PLACE_X_MAX and PLACE_Y_MIN <= cy <= PLACE_Y_MAX


def _loop() -> None:
    """Vision-thread hoofdlus. Alles in try/except — fallback is 'blind maar aanwezig'."""
    try:
        from picamera2 import Picamera2
    except Exception as e:
        log.warning(f"Picamera2 niet beschikbaar: {e} — vision uitgeschakeld")
        with _state._lock:
            _state.enabled = False
            _state.someone_at_place = True  # fallback: luister altijd
        return

    try:
        from hailo_platform import (  # type: ignore
            HEF, VDevice, HailoStreamInterface, FormatType, InputVStreamParams,
            OutputVStreamParams, InferVStreams,
        )
    except Exception as e:
        log.warning(f"hailo_platform niet beschikbaar: {e} — alleen camera, geen inference")
        _camera_only_loop(Picamera2)
        return

    scrfd_path = Path(SCRFD_HEF)
    if not scrfd_path.exists():
        log.warning(f"SCRFD HEF niet gevonden op {scrfd_path} — alleen camera")
        _camera_only_loop(Picamera2)
        return

    log.info("Hailo + camera starten")
    picam = Picamera2()
    config = picam.create_video_configuration(
        main={"size": (CAM_WIDTH, CAM_HEIGHT), "format": "RGB888"}
    )
    picam.configure(config)
    picam.start()
    time.sleep(0.5)

    hef = HEF(str(scrfd_path))
    with VDevice() as vdevice:
        cfg = vdevice.create_configure_params_from_hef(hef, interface=HailoStreamInterface.PCIe)
        network_group = vdevice.configure(hef, cfg)[0]
        input_params = InputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
        output_params = OutputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
        input_name = next(iter(input_params))
        in_shape = hef.get_input_vstream_infos()[0].shape  # (h, w, c)

        with network_group.activate(), InferVStreams(network_group, input_params, output_params) as infer:
            with _state._lock:
                _state.enabled = True
            log.info("Vision-thread actief")

            while not _stop_event.is_set():
                try:
                    frame = picam.capture_array()
                    tensor = _prep_tensor(frame, in_shape)
                    out = infer.infer({input_name: tensor})
                    faces = _parse_scrfd(out, CAM_WIDTH, CAM_HEIGHT)

                    at_place = any(_in_speak_zone(*f) for f in faces)
                    mood = "neutraal"  # TODO: face_attr branch wanneer HEF beschikbaar
                    with _state._lock:
                        _state.frame_ts = time.monotonic()
                        _state.faces = faces
                        _state.someone_at_place = at_place
                        _state.visitor_count = len(faces)
                        _state.mood_hint = mood
                        _state.latest_frame = frame.copy()
                except Exception as e:
                    log.debug(f"frame-fout: {e}")
                time.sleep(0.1)

    picam.stop()
    log.info("Vision-thread gestopt")


def _camera_only_loop(Picamera2Cls) -> None:
    """Fallback: camera draait maar zonder inference. Frames gaan wel in state
    zodat de fotograaf-functie kan triggeren. We nemen aan dat iemand aanwezig is."""
    try:
        picam = Picamera2Cls()
        picam.configure(picam.create_video_configuration(
            main={"size": (CAM_WIDTH, CAM_HEIGHT), "format": "RGB888"}))
        picam.start()
        time.sleep(0.5)
        with _state._lock:
            _state.enabled = False
            _state.someone_at_place = True
        while not _stop_event.is_set():
            try:
                frame = picam.capture_array()
                with _state._lock:
                    _state.frame_ts = time.monotonic()
                    _state.latest_frame = frame.copy()
            except Exception as e:
                log.debug(f"camera-only grab-fout: {e}")
            time.sleep(0.3)
        picam.stop()
    except Exception as e:
        log.warning(f"camera-fout: {e} — blind-aanwezig modus")
        with _state._lock:
            _state.enabled = False
            _state.someone_at_place = True


def _prep_tensor(frame, in_shape):
    """RGB888 → float32 tensor in de vorm die SCRFD verwacht."""
    import numpy as np
    h, w, _ = in_shape
    # Simpelste: resize+normalize. SCRFD standaard: 640×640, mean=127.5, scale=128
    import cv2  # komt met opencv-python
    resized = cv2.resize(frame, (w, h))
    tensor = (resized.astype("float32") - 127.5) / 128.0
    return np.expand_dims(tensor, axis=0)


def _parse_scrfd(out: dict, img_w: int, img_h: int):
    """Decode SCRFD-output naar lijst van (x, y, w, h) in 0-1 relatieve coords.

    Dit is een vereenvoudigde decoder — SCRFD heeft 9 output-tensors (score+bbox+kps
    op 3 strides). Voor een eerste werkende versie pikken we scores > 0.5 op stride 32,
    wat voor dichte frontale gezichten (galerij-afstand) prima is. Later uitbreiden
    voor kleinere gezichten op strides 8/16.
    """
    import numpy as np
    try:
        # Vindt de output-naam met 'score' + de bijbehorende bbox
        score_key = next(k for k in out if "score" in k.lower() and "32" in k)
        bbox_key  = next(k for k in out if "bbox"  in k.lower() and "32" in k)
    except StopIteration:
        return []
    scores = out[score_key].reshape(-1)
    bboxes = out[bbox_key].reshape(-1, 4)
    mask = scores > 0.5
    faces = []
    for i in np.where(mask)[0]:
        x, y, w, h = bboxes[i]
        faces.append((
            max(0.0, float(x) / img_w),
            max(0.0, float(y) / img_h),
            max(0.0, float(w) / img_w),
            max(0.0, float(h) / img_h),
        ))
    return faces


# ----- Publieke API ---------------------------------------------------------
def start() -> None:
    """Start de vision-thread. Niet-blocking. Idempotent."""
    global _worker
    if not VISION_ENABLED:
        log.info("VISION_ENABLED=false — vision overgeslagen")
        with _state._lock:
            _state.someone_at_place = True  # luister altijd
        return
    if _worker is not None and _worker.is_alive():
        return
    _stop_event.clear()
    _worker = threading.Thread(target=_loop, name="anna-vision", daemon=True)
    _worker.start()


def stop() -> None:
    _stop_event.set()
    if _worker is not None:
        _worker.join(timeout=3)


def get_state() -> dict:
    return _state.snapshot()
