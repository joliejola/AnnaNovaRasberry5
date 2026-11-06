#!/usr/bin/env python3
"""Render 5 voorbeeldbonnen uit content/inhoud.json voor Jolanda.

Beslismoment 2 in bouwplan-v2: Jolanda bekijkt de PNG's en checkt:
- Logo + "AI VRIENDIN GEZOCHT" leesbaar?
- Quote past, lay-out klopt?
- Prijs-plakking en percentage-notatie OK?
- Datum NL, URL, afzenders staan correct onderaan?

Draai: python3 tools/test_bon.py
Output: ./out/bon_01.png t/m bon_05.png
"""
from __future__ import annotations

import random
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anna import bon

OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

inhoud = bon.laad_inhoud()


def render_specifiek(idx: int, quote_id: str, halte_log: list[str], soort: str | None, tag: str):
    """Geef een quote mee om deterministisch 5 verschillende bonnen te krijgen."""
    quote = next(q for q in inhoud["quotes"] if q["id"] == quote_id)
    img = bon.render_bon(
        quote=quote,
        ai_wereld_usd=inhoud["ai_wereld_2026_usd"],
        url=inhoud["url"],
        breedte_px=384,
        datum=date(2026, 11, 6),
    )
    pad = OUT / f"bon_{idx:02d}_{tag}.png"
    img.save(pad)
    pct = bon.format_percentage(quote["prijs_eur"], inhoud["ai_wereld_2026_usd"])
    prijs = bon.format_prijs(quote["prijs_eur"])
    print(f"  bon_{idx:02d}_{tag}: {quote['id']} halte={quote['halte']} prijs={prijs} pct={pct}%")
    print(f"           quote: {quote['tekst']!r}")
    print(f"           PNG:   {pad}")


print("Rendert 5 voorbeeldbonnen voor beslismoment 2...\n")

# 1 — bekeken, goedkope quote (percentage zeer klein)
render_specifiek(1, "q01", ["bekeken", "bekeken", "bewaard"], None, "bekeken_laag")

# 2 — bewaard, middel prijs
render_specifiek(2, "q07", ["bewaard", "bewaard", "wrijving"], None, "bewaard_midden")

# 3 — wrijving, duurdere quote (percentage merkbaar groter)
render_specifiek(3, "q13", ["wrijving", "wrijving", "bekeken"], None, "wrijving_duur")

# 4 — zacht, na verdriet-soort
render_specifiek(4, "q17", ["bekeken", "bewaard"], "verdriet", "zacht_na_verdriet")

# 5 — langere quote (test tekst-wrap)
render_specifiek(5, "q13", ["wrijving"], None, "lange_quote_wrap")

print("\nKlaar. Open de PNG's in", OUT)

# Verificatie percentage-berekening (bron 2 noemt specifieke voorbeelden)
print("\n--- percentage-verificatie (bron 2 referenties) ---")
for prijs in [0.04, 0.25, 1.50, 9.99, 0.00]:
    pct = bon.format_percentage(prijs, inhoud["ai_wereld_2026_usd"])
    print(f"  €{prijs:>5.2f} → {pct} %")
