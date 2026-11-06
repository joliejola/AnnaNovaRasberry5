"""Entry-point. Laadt content/inhoud.json, start face-server + flow.

Draai lokaal in droogloop:
    DROOGLOOP=1 python3 -m anna.main
    # scherm: http://localhost:8765/

Op Pi (bouwstap 7+):
    python3 -m anna.main
    # Chromium opent http://localhost:8765/ full-screen (autostart)
"""
from __future__ import annotations

import logging
import os
import sys

from anna import bon, face, flow


def main() -> int:
    level = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    inhoud = bon.laad_inhoud()

    # Start face-server tenzij uitgezet
    if os.environ.get("NO_FACE") != "1":
        face.start()

    f = flow.Flow(inhoud, state_cb=lambda s: face.push_state(s.value))

    print("── Anna Nova — droogloop ──" if os.environ.get("DROOGLOOP") == "1" else "── Anna Nova ──")
    print(f"Scherm: http://localhost:{face.PORT}/")
    print("Typ 'Hoi Anna Nova' om wakker te maken. Enter = stilte. #ruis / #druk / #weg.")
    print("Ctrl-C om te stoppen.\n")

    try:
        f.run_tot_stop()
    finally:
        face.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
