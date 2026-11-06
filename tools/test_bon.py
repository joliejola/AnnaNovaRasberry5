#!/usr/bin/env python3
"""Render voorbeeldbonnen uit content/inhoud.json voor Jolanda.

Draai: python3 tools/test_bon.py
Output: ./out/bon_*.png

Rendert:
- 5 gewone bonnen met verschillende quote-ids
- 1 "verdriet"-pad: lege bon (€ 0,00) omdat er geen zacht:true quotes zijn
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anna import bon

OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

inhoud = bon.laad_inhoud()


def render_met_quote(idx: int, quote_id: int, tag: str):
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
    print(f"  bon_{idx:02d}_{tag}: q{quote['id']} prijs={quote['prijs']!r}")
    print(f"           {quote['tekst']!r}")


print("Rendert voorbeeldbonnen voor beslismoment 2 (nieuwe schema)...\n")

render_met_quote(1, 2,  "vriendin_of_slaaf")   # € 0,99
render_met_quote(2, 14, "nulbon_moeite")        # € 0,00 — randgeval
render_met_quote(3, 16, "gemak_abo_per_maand")  # € 9,99 p/m
render_met_quote(4, 11, "vriend_zonder_nee")    # € 1,99
render_met_quote(5, 1,  "eenzaamheid_markt")    # € 4,10

# Verdriet-pad: geen zacht:true quotes → lege bon met € 0,00
print("\nVerdriet-pad (geen zacht:true in deze inhoud.json):")
img, q = bon.maak_bon(inhoud, soort_laatste="verdriet")
pad = OUT / "bon_06_verdriet_leeg.png"
img.save(pad)
print(f"  bon_06_verdriet_leeg: quote.id={q['id']} prijs={q['prijs']!r} tekst={q['tekst']!r}")

print("\nKlaar. Open PNG's in", OUT)
