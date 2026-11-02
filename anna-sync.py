#!/usr/bin/env python3
"""
Anna Nova — foto-sync naar extern scherm (Hetzner Storage Box of andere SFTP).

Loopt als systemd-timer elke 15 minuten. Pakt alle JPGs uit ~/anna-nova/photos/
en pusht ze via rsync+SSH naar de ingestelde SFTP-host. Bijbehorende captions
uit SQLite worden mee-geüpload als sidecar JSON zodat het externe scherm
alles bij elkaar krijgt.

Config (uit ~/anna-nova/.env, al door systemd ingeladen):
  PHOTO_UPLOAD_ENABLED=true
  PHOTO_SFTP_HOST=u123456.your-storagebox.de
  PHOTO_SFTP_USER=u123456
  PHOTO_SFTP_KEY=/home/pi/.ssh/id_ed25519
  PHOTO_SFTP_REMOTE_PATH=anna-nova/photos  (optioneel, default dit)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ENABLED      = os.environ.get("PHOTO_UPLOAD_ENABLED", "false").lower() == "true"
HOST         = os.environ.get("PHOTO_SFTP_HOST", "")
USER         = os.environ.get("PHOTO_SFTP_USER", "")
KEY          = os.environ.get("PHOTO_SFTP_KEY", str(Path.home() / ".ssh/id_ed25519"))
REMOTE_PATH  = os.environ.get("PHOTO_SFTP_REMOTE_PATH", "anna-nova/photos")
PHOTOS_DIR   = os.environ.get("PHOTOS_DIR", str(Path.home() / "anna-nova/photos"))
ANNA_DB      = os.environ.get("ANNA_DB", str(Path.home() / "anna-nova/anna.db"))

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] sync: {msg}", flush=True)

def build_captions_json() -> dict:
    """Verzamel {fname: {caption, ts}} voor alle foto's die in SQLite staan."""
    try:
        with sqlite3.connect(ANNA_DB) as conn:
            rows = conn.execute(
                "SELECT ts, text FROM fragments "
                "WHERE kind='anna' AND text LIKE '[FOTO:%' "
                "ORDER BY ts DESC LIMIT 500"
            ).fetchall()
    except Exception as e:
        log(f"db-leesfout: {e}")
        return {}
    out = {}
    for ts, text in rows:
        m = re.match(r"^\[FOTO:([^\]]+)\]\s*(.*)$", text, re.S)
        if m:
            out[m.group(1)] = {"caption": m.group(2).strip(), "ts": ts}
    return out

def main() -> int:
    if not ENABLED:
        log("PHOTO_UPLOAD_ENABLED=false — niets te doen")
        return 0
    if not HOST or not USER:
        log("HOST/USER niet ingesteld — niets te doen")
        return 1
    photos = Path(PHOTOS_DIR)
    if not photos.is_dir():
        log(f"{photos} bestaat niet"); return 1

    jpgs = sorted(photos.glob("*.jpg"))
    if not jpgs:
        log("geen foto's om te sturen")
        return 0

    # Captions.json ernaast leggen
    captions = build_captions_json()
    (photos / "captions.json").write_text(
        json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cmd = [
        "rsync", "-az", "--timeout=60",
        "-e", f"ssh -i {KEY} -o StrictHostKeyChecking=accept-new -o BatchMode=yes",
        f"{photos}/",
        f"{USER}@{HOST}:{REMOTE_PATH}/",
    ]
    log(f"rsync → {USER}@{HOST}:{REMOTE_PATH}/  ({len(jpgs)} foto's)")
    try:
        subprocess.run(cmd, check=True, timeout=600)
        log("klaar")
        return 0
    except subprocess.CalledProcessError as e:
        log(f"rsync faalde (exit {e.returncode})")
        return e.returncode
    except subprocess.TimeoutExpired:
        log("rsync time-out na 10 min")
        return 1

if __name__ == "__main__":
    sys.exit(main())
