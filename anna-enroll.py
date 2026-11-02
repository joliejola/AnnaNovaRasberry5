#!/usr/bin/env python3
"""
Anna Nova — voiceprint enrollment.

Neemt 20-30 seconden stem op, extraheert een embedding via Resemblyzer,
en slaat die op in SQLite onder een naam. Daarna herkent Anna die persoon
automatisch via cosine similarity in haar hoofdlus.

Gebruik:
  python3 ~/anna-nova/anna-enroll.py --name jolanda
  python3 ~/anna-nova/anna-enroll.py --name bodil --seconds 25

Dit script is interactief — het geeft een countdown en vraagt je door te
blijven praten tot het klaar is.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import struct
import sys
import time
from pathlib import Path

ANNA_DB            = os.environ.get("ANNA_DB", str(Path.home() / "anna-nova/anna.db"))
AUDIO_INPUT_DEVICE = os.environ.get("AUDIO_INPUT_DEVICE", "")
SAMPLE_RATE        = 16000

def _resolve_device(spec):
    """Zie anna-nova.py — zelfde helper."""
    import sounddevice as sd
    if not spec or spec.lower() in ("default", "none", ""):
        return None
    try:
        return int(spec)
    except ValueError:
        pass
    for i, d in enumerate(sd.query_devices()):
        if spec.lower() in d.get("name", "").lower():
            return i
    return None

def ensure_schema() -> None:
    with sqlite3.connect(ANNA_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voices (
                name TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                enrolled_at TEXT NOT NULL
            )
        """)

def record(seconds: int) -> "np.ndarray":  # type: ignore[name-defined]
    import numpy as np
    import sounddevice as sd
    device = _resolve_device(AUDIO_INPUT_DEVICE)
    print(f"\nOpnemen gaat zo starten. Praat {seconds} seconden door — eender wat.")
    for n in range(3, 0, -1):
        print(f"  {n}...", flush=True)
        time.sleep(1)
    print(f"  OPNEMEN")
    buf = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                 channels=1, dtype="float32", device=device)
    sd.wait()
    print("  klaar\n")
    return buf.flatten()

def embed(audio) -> bytes:
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav  # type: ignore
    except ImportError:
        print("ERROR: resemblyzer niet geïnstalleerd. Run:", file=sys.stderr)
        print("  ~/anna-nova/venv/bin/pip install resemblyzer", file=sys.stderr)
        sys.exit(1)
    import numpy as np
    print("Embedding berekenen...")
    enc = VoiceEncoder()
    wav = preprocess_wav(audio, source_sr=SAMPLE_RATE)
    emb = enc.embed_utterance(wav)
    return struct.pack(f"{len(emb)}f", *emb.astype("float32"))

def save(name: str, emb_bytes: bytes) -> None:
    from datetime import datetime
    with sqlite3.connect(ANNA_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO voices (name, embedding, enrolled_at) VALUES (?, ?, ?)",
            (name.lower(), emb_bytes, datetime.now().isoformat(timespec="seconds")),
        )
    print(f"Opgeslagen: '{name}' ({len(emb_bytes)//4} float32-coëfficiënten).")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="naam (bv. jolanda, bodil)")
    ap.add_argument("--seconds", type=int, default=25, help="opnameduur (20-45)")
    args = ap.parse_args()

    if args.seconds < 15 or args.seconds > 60:
        print("Opname moet tussen 15 en 60 seconden zijn.", file=sys.stderr)
        return 2

    ensure_schema()
    audio = record(args.seconds)
    emb = embed(audio)
    save(args.name, emb)
    print(f"\nKlaar. Anna herkent '{args.name}' zodra ze draait.")
    print("Herstart Anna om het meteen te zien: sudo systemctl restart anna-nova")
    return 0

if __name__ == "__main__":
    sys.exit(main())
