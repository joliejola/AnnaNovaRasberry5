#!/usr/bin/env python3
"""Genereer een placeholder-logo tot Jolanda een echte levert.

Simpele monochroom afbeelding, geschikt voor thermische printer.
Een cirkel met 'AN' in het midden — geen pretentie.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "logo.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

size = 120
img = Image.new("L", (size, size), 255)
dr = ImageDraw.Draw(img)

# Cirkel
margin = 6
dr.ellipse([(margin, margin), (size - margin, size - margin)], outline=0, width=3)

# Letters AN
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Courier New Bold.ttf", 54)
except Exception:
    font = ImageFont.load_default()

tekst = "AN"
box = font.getbbox(tekst)
tw, th = box[2] - box[0], box[3] - box[1]
dr.text(((size - tw) / 2 - box[0], (size - th) / 2 - box[1] - 4), tekst, font=font, fill=0)

img.save(OUT)
print(f"Placeholder logo opgeslagen: {OUT}")
