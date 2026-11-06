#!/usr/bin/env python3
"""Scripted droogloop — speel 5 gesprekken na zonder stdin.

Verifieert de state-machine end-to-end in deze afwezigheid van Mistral-key
(brain-calls vallen dan automatisch op brugzin). Op Pi met key: zelfde script
levert echte reacties.

Draai:
    .venv/bin/python tools/droogloop_sim.py        # 5 gesprekken
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

from anna import bon, brain, flow, hear, printer


# ---- scripted gesprekken (regels zoals Jolanda ze zou typen) ----

GESPREKKEN = {
    "A - rechte lijn + rekening ja": [
        "Hoi Anna Nova",
        "Ja, een beetje. Alsof je echt kijkt.",
        "Thuis? Nou, ik let er niet op.",
        "Pfff ik weet het niet.",
        "Ja, misschien verveling wel.",
        "Ja",  # rekening
    ],
    "B - 2 zijwegen -> vroege afsluiting": [
        "Hallo Anna Nova",
        "Hoe laat is het?",                # zijweg 1
        "Mag ik een foto maken?",          # zijweg 2
        "Ja",  # rekening
    ],
    "C - stilte stilte stilte (pas-cascade)": [
        "Hoi Anna Nova",
        "",                                 # stilte 1
        "",                                 # stilte 2 → door
        "Ja een beetje.",
        "",                                 # stilte 1
        "",                                 # stilte 2 → door
        "Mm.",                              # kort antwoord
        "Ja, soms.",
        "Ja",  # rekening
    ],
    "D - ruis + druk": [
        "Hoi Anna Nova",
        "#ruis",                           # ruis 1
        "Ja, ik voel het soms.",
        "#druk",                           # druk-event
        "Ja",  # rekening
    ],
    "E - sleep-phrase midden-gesprek": [
        "Hoi Anna Nova",
        "Ja, een beetje bekeken.",
        "slaap lekker",                    # sleep → LOSLATEN, geen bon
    ],
}


def _dict_reader(regels: list[str]):
    """Vervangt hear._lees_regel: pop uit de lijst, EOF bij leeg."""
    it = iter(regels)

    def lees(prompt: str = "", timeout=None) -> str:
        try:
            r = next(it)
        except StopIteration:
            raise KeyboardInterrupt  # beëindig flow na script
        print(f"\033[90m{prompt}\033[0m\033[36m{r}\033[0m")
        return r

    return lees


def speel(naam: str, regels: list[str]) -> None:
    print("\n" + "=" * 70)
    print(f"GESPREK: {naam}")
    print("=" * 70)

    inhoud = bon.laad_inhoud()
    f = flow.Flow(inhoud)

    # Stop zodra het script op is + max 2 LOSLATEN cycles
    los_count = [0]
    orig_switch = f._switch

    def tracked_switch(nieuwe):
        orig_switch(nieuwe)
        if nieuwe == flow.State.LOSLATEN:
            los_count[0] += 1
            if los_count[0] >= 1:
                f._should_stop = True

    f._switch = tracked_switch  # type: ignore

    # Mock brain als geen key — anders hergebruiken we echte Mistral
    if not brain.BrainClient().beschikbaar:
        def fake_call(self, vraag, bezoeker, context="VRAAG"):
            low = bezoeker.lower()
            if context == "AFSLUITING":
                if low.startswith("ja") or "vooruit" in low:
                    return {"soort": "ja", "reactie": ""}
                return {"soort": "nee", "reactie": ""}
            if "hoe laat" in low or "foto" in low or "wc" in low:
                return {"soort": "zijweg", "reactie": "Later misschien."}
            if "nep" in low or "stom" in low:
                return {"soort": "provocatie", "reactie": "Dat werkt niet bij mij."}
            if "overleden" in low or "dood" in low:
                return {"soort": "verdriet", "reactie": "Dat is zwaar."}
            if "weet" in low or low in ("mm.", "mm"):
                return {"soort": "pas", "reactie": "En als je het wel zou weten?"}
            return {"soort": "antwoord", "reactie": "Mm. En jij?"}

        brain.BrainClient.call = fake_call  # type: ignore

    with patch.object(hear, "_lees_regel", _dict_reader(regels)):
        try:
            f.run_tot_stop()
        except KeyboardInterrupt:
            print("\033[90m(script leeg → stop)\033[0m")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s", datefmt="%H:%M:%S")
    # Stille Pillow
    logging.getLogger("PIL").setLevel(logging.WARNING)

    keuze = sys.argv[1] if len(sys.argv) > 1 else None
    namen = list(GESPREKKEN.keys())
    if keuze:
        idx = int(keuze) - 1
        namen = [namen[idx]]
    for n in namen:
        speel(n, GESPREKKEN[n])
    print("\n" + "=" * 70)
    print("Alle gesprekken klaar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
