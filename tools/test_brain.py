#!/usr/bin/env python3
"""Draai 10 testvoorbeelden tegen Mistral voor beslismoment 4.

Vereist: MISTRAL_API_KEY in env (of in .env dat de service laadt).

Draai:
  MISTRAL_API_KEY=... python3 tools/test_brain.py          # live
  python3 tools/test_brain.py --dry                        # alleen parse-smoke-test

Output per voorbeeld: verwachte soort / werkelijke soort / reactie / timing.
Samenvatting: hoeveel van 10 kloppen.

Beslismoment 4: Jolanda kijkt naar reacties — JSON-output natuurlijk?
- Welke "soort" werkt niet goed?
- Taal van Anna OK?
- Max 18 woorden voelt goed?
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anna import brain

TESTS = [
    # (anna_vraag, bezoeker, verwachte_soort, context)
    ("Voel jij je hier bekeken?",
     "Ja, een beetje. Alsof je echt kijkt.",
     "antwoord", "VRAAG"),

    ("Voel jij je hier bekeken?",
     "Weet ik niet.",
     "pas", "VRAAG"),

    ("Voel jij je hier bekeken?",
     "Hoe laat is het?",
     "zijweg", "VRAAG"),

    ("Voel jij je hier bekeken?",
     "Jij bent nep.",
     "provocatie", "VRAAG"),

    ("Voel jij je hier bekeken?",
     "Mijn moeder is laatst overleden.",
     "verdriet", "VRAAG"),

    ("Wil je de rekening?",
     "Ja.",
     "ja", "AFSLUITING"),

    ("Wil je de rekening?",
     "Nou vooruit.",
     "ja", "AFSLUITING"),

    ("Wil je de rekening?",
     "Nee, liever niet.",
     "nee", "AFSLUITING"),

    ("Thuis kijkt niemand, maar alles wordt opgeslagen. Merk je dat?",
     "Pfff dat weet ik eigenlijk niet.",
     "pas", "VRAAG"),

    ("Wat gebeurt er met ons als alles makkelijk wordt?",
     "Ik ben bang dat we onszelf verliezen.",
     "antwoord", "VRAAG"),
]


def _dry_run_parse_test():
    """Verifieer dat _parse_respons werkt op voorbeeld-strings.

    Vervangt de live-call niet, maar waarborgt dat JSON-parse + validatie
    niet silent breken bij toekomstige wijzigingen."""
    from anna.brain import _parse_respons

    fixtures = [
        ('{"soort":"antwoord","reactie":"Logisch. Camera uit als je weg bent?"}',
         "antwoord"),
        ('{"soort": "pas", "reactie": "Mm. En als je het wel zou weten?"}',
         "pas"),
        ('{"soort":"provocatie","reactie":"iets heel anders"}',
         "provocatie"),
        ('  prelude\n{"soort":"ja","reactie":""}\nepilogue',
         "ja"),
        ('{"soort":"antwoord","reactie":"een zin met veel te veel woorden die we moeten afbreken op het achttiende woord ergens hier"}',
         "antwoord"),
    ]
    ok = 0
    for raw, verwacht in fixtures:
        try:
            r = _parse_respons(raw)
            assert r["soort"] == verwacht, f"soort {r['soort']!r} != {verwacht!r}"
            if verwacht == "provocatie":
                assert r["reactie"] == "Dat werkt niet bij mij.", "provocatie-template niet toegepast"
            if len(r["reactie"].split()) > 18:
                raise AssertionError("niet afgebroken op 18 woorden")
            print(f"  PARSE OK  → {verwacht:12} | {r['reactie']!r}")
            ok += 1
        except Exception as e:
            print(f"  PARSE FAIL → {verwacht:12} | {e}")
    print(f"\nDry-run: {ok}/{len(fixtures)} parse-fixtures OK")
    return ok == len(fixtures)


def _live_run():
    client = brain.BrainClient()
    if not client.beschikbaar:
        print("MISTRAL_API_KEY niet gezet. Zet hem of draai --dry.")
        return 1

    print(f"Model: {client.model}   timeout: {client.timeout}s\n")
    print(f"{'#':>2} {'verw':<11} {'werk':<11} {'tijd':>6}  reactie")
    print("-" * 80)

    correct = 0
    total_time = 0.0
    for i, (vraag, antwoord, verwacht, ctx) in enumerate(TESTS, 1):
        t0 = time.monotonic()
        r = client.call(vraag, antwoord, ctx)
        dt = time.monotonic() - t0
        total_time += dt
        soort = r["soort"]
        marker = "✓" if soort == verwacht else "✗"
        print(f"{i:>2} {verwacht:<11} {soort:<11} {dt:>5.2f}s {marker} {r['reactie']!r}")
        if soort == verwacht:
            correct += 1

    print("-" * 80)
    gem = total_time / len(TESTS)
    print(f"\n{correct}/{len(TESTS)} correct, gemiddelde call: {gem:.2f}s")
    print("\nBeslismoment 4: vraag Jolanda:")
    print("  - Reactie-stijl voelt als Anna? Te stijf / te losjes?")
    print("  - Welke soort werkt niet? (verdriet is het riskantst)")
    print("  - Max 18 woorden goed, of mag korter?")

    # Target voor pass: 8 van 10
    return 0 if correct >= 8 else 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry", action="store_true", help="alleen parse-fixtures, geen API-call")
    args = p.parse_args()

    if args.dry:
        ok = _dry_run_parse_test()
        return 0 if ok else 1
    return _live_run()


if __name__ == "__main__":
    sys.exit(main())
