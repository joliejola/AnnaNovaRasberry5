#!/usr/bin/env python3
"""Scripted droogloop — vaste 5-vragen reeks uit bron 2 (sync 14:50).

Draai:
    .venv/bin/python tools/droogloop_sim.py        # 6 gesprekken
    .venv/bin/python tools/droogloop_sim.py 2      # alleen gesprek 2
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ["DROOGLOOP"] = "1"
os.environ.setdefault("DROOGLOOP_SIM", "0")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anna import bon, brain, flow, hear


GESPREKKEN = {
    "A - rechte lijn + rekening ja": [
        "Hoi Anna Nova",
        "Ja, ik wil je vriendin worden.",             # v1 → ja
        "Een beetje wel, ik ben me bewust van jou.",  # v2
        "Mijn zoekgeschiedenis, denk ik.",             # v3
        "Afgelopen week, een vriend verhuisde.",       # v4
        "Misschien wel, maar niet in alles.",          # v5
        "Ja graag.",                                   # rekening
    ],
    "B - vraag 1 twijfel + 2 zijwegen → vroege AFSLUITING": [
        "Hallo Anna Nova",
        "Misschien wel, moeilijke vraag.",            # v1 → twijfel
        "Hoe laat is het eigenlijk?",                  # v2 → zijweg 1
        "Wie heeft jou gemaakt?",                      # v2 opnieuw → zijweg 2 → AFSLUITING
        "Ja graag.",                                   # rekening
    ],
    "C - 2× stilte op v2 → LOSLATEN zonder bon": [
        "Hoi Anna Nova",
        "Ja laten we vrienden worden.",                # v1 → ja
        "",                                             # stilte 1 op v2 → herhaal
        "",                                             # stilte 2 op v2 → LOSLATEN
    ],
    "D - ruis + voortgang": [
        "Hoi Anna Nova",
        "Nee, geen vriendin worden.",                  # v1 → nee
        "#ruis",                                        # ruis 1 op v2 → opnieuw
        "Ja, misschien wel.",                           # v2
        "#ruis",                                        # ruis 1 op v3 → opnieuw
        "#ruis",                                        # ruis 2 op v3 → volgende
        "Ja soms wel.",                                 # v4
        "Jij bent een goede vriendin, denk ik.",       # v5
        "Ja graag.",                                   # rekening
    ],
    "E - sleep-phrase midden-gesprek": [
        "Hoi Anna Nova",
        "Ja, wil ik.",
        "slaap lekker",                                # sleep → LOSLATEN
    ],
    "F - verdriet-pad → ZACHT → AFSLUITING → lege bon": [
        "Hoi Anna Nova",
        "Ja oké.",
        "Mijn moeder is laatst overleden.",            # v2 → verdriet → ZACHT → AFSLUITING
        "Ja graag.",                                   # rekening
    ],
}


def _dict_reader(regels: list[str]):
    it = iter(regels)

    def lees(prompt: str = "", timeout=None) -> str:
        try:
            r = next(it)
        except StopIteration:
            raise KeyboardInterrupt
        print(f"\033[90m{prompt}\033[0m\033[36m{r}\033[0m")
        return r

    return lees


def speel(naam: str, regels: list[str]) -> None:
    print("\n" + "=" * 70)
    print(f"GESPREK: {naam}")
    print("=" * 70)

    inhoud = bon.laad_inhoud()
    f = flow.Flow(inhoud)

    los_count = [0]
    orig_switch = f._switch

    def tracked_switch(nieuwe):
        orig_switch(nieuwe)
        if nieuwe == flow.State.LOSLATEN:
            los_count[0] += 1
            if los_count[0] >= 1:
                f._should_stop = True

    f._switch = tracked_switch  # type: ignore

    with patch.object(hear, "_lees_regel", _dict_reader(regels)):
        try:
            f.run_tot_stop()
        except KeyboardInterrupt:
            print("\033[90m(script leeg → stop)\033[0m")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("PIL").setLevel(logging.WARNING)

    keuze = sys.argv[1] if len(sys.argv) > 1 else None
    namen = list(GESPREKKEN.keys())
    if keuze:
        idx = int(keuze) - 1
        namen = [namen[idx]]
    for n in namen:
        speel(n, GESPREKKEN[n])
    print("\n" + "=" * 70)
    print(f"Klaar. {len(namen)} gespreken afgespeeld.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
