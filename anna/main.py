"""Entry-point. Laadt content/inhoud.json en start de flow.

Draai lokaal in droogloop:
    DROOGLOOP=1 python3 -m anna.main

Op Pi (bouwstap 7+):
    python3 -m anna.main
"""
from __future__ import annotations

import logging
import os
import sys

from anna import bon, flow


def main() -> int:
    level = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    inhoud = bon.laad_inhoud()
    f = flow.Flow(inhoud)
    print("── Anna Nova — droogloop ──" if os.environ.get("DROOGLOOP") == "1" else "── Anna Nova ──")
    print("Typ 'Hoi Anna Nova' om wakker te maken. Enter = stilte. #ruis / #druk / #weg.")
    print("Ctrl-C om te stoppen.\n")
    f.run_tot_stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
