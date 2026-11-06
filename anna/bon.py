"""Bouw een bon-PNG uit een gesprek.

Aangeroepen door flow.py bij toestand BON. Levert een PIL.Image terug die
printer.py kan versturen, of een pad naar een PNG als DROOGLOOP=1.

Regels uit bron 2:
- Quote: willekeurig uit goedgekeurde quotes met matching halte (longest-halte
  van gesprek), nooit een van de laatste 5, na soort=verdriet alleen halte
  "zacht". Leeg → willekeurig goedgekeurd.
- Percentage: prijs_eur / 2_670_000_000_000 * 100, afgekapt op 2 significante
  cijfers in decimale notatie. €0,00 → "0 %".
- Datum Nederlands.
- Font: vrije monospace (Courier Prime bij voorkeur).
"""
from __future__ import annotations

import json
import math
import os
import random
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
INHOUD_PATH = ROOT / "content" / "inhoud.json"
LOGO_PATH = ROOT / "assets" / "logo.png"
FONT_CANDIDATES = [
    ROOT / "assets" / "fonts" / "CourierPrime-Regular.ttf",
    Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSansMono.ttf"),
]
FONT_BOLD_CANDIDATES = [
    ROOT / "assets" / "fonts" / "CourierPrime-Bold.ttf",
    Path("/System/Library/Fonts/Supplemental/Courier New Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
]

NL_MAANDEN = {
    1: "januari", 2: "februari", 3: "maart", 4: "april", 5: "mei", 6: "juni",
    7: "juli", 8: "augustus", 9: "september", 10: "oktober", 11: "november", 12: "december",
}


# ---------- content ----------

def laad_inhoud(pad: Path = INHOUD_PATH) -> dict:
    return json.loads(pad.read_text(encoding="utf-8"))


# ---------- quote-keuze ----------

def longest_halte(gespreksbeurten: Iterable[str]) -> str | None:
    """Welke halte heeft de meeste beurten gekregen? Tie-break: laatste wint.

    `gespreksbeurten` is een lijst van halte-strings ('bekeken'/'bewaard'/'wrijving'),
    1 per beurt. Lege lijst → None.
    """
    beurten = [b for b in gespreksbeurten if b]
    if not beurten:
        return None
    teller = Counter(beurten)
    max_count = max(teller.values())
    kandidaten = [h for h in reversed(beurten) if teller[h] == max_count]
    return kandidaten[0]


def kies_quote(
    inhoud: dict,
    halte: str | None,
    soort: str | None = None,
    recent_ids: list[str] | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Trek een quote volgens de regels in bron 2.

    - soort == "verdriet" → alleen halte "zacht"
    - halte None → willekeurig uit goedgekeurde
    - nooit een id uit `recent_ids` (laatste 5)
    - fallback als geen kandidaat: willekeurig goedgekeurd incl eerder gezien
    """
    rng = rng or random.Random()
    recent = set(recent_ids or [])
    quotes = inhoud["quotes"]

    # Tijdens bouw: goedgekeurd=null = behandel als "beschikbaar" (concept).
    # Op expositie zal flow.py alleen goedgekeurd=true toelaten (drempel-flag).
    def beschikbaar(q):
        return q.get("goedgekeurd") is not False  # null of true → ok

    pool = [q for q in quotes if beschikbaar(q)]

    if soort == "verdriet":
        halte = "zacht"

    if halte:
        gericht = [q for q in pool if q.get("halte") == halte and q["id"] not in recent]
        if gericht:
            return rng.choice(gericht)
        # fallback 1: zelfde halte, ook recent toegestaan
        gericht_ongefilterd = [q for q in pool if q.get("halte") == halte]
        if gericht_ongefilterd:
            return rng.choice(gericht_ongefilterd)

    # fallback 2: willekeurig uit goedgekeurde, bij voorkeur niet recent
    niet_recent = [q for q in pool if q["id"] not in recent]
    if niet_recent:
        return rng.choice(niet_recent)
    return rng.choice(pool)


# ---------- formatting ----------

def format_percentage(prijs_eur: float, ai_wereld_usd: int = 2_670_000_000_000) -> str:
    """Prijs als percentage van 2026 AI-wereld-investering, 2 sig fig.

    Komma als decimaal-scheiding (NL).
    """
    if prijs_eur is None or prijs_eur <= 0:
        return "0"
    pct = float(prijs_eur) / ai_wereld_usd * 100.0
    if pct == 0:
        return "0"
    exp = math.floor(math.log10(pct))
    # 2 significante cijfers: rond op (1 - exp) decimalen
    decimals = 1 - exp
    rounded = round(pct, decimals)
    if decimals <= 0:
        s = f"{rounded:.0f}"
    else:
        s = f"{rounded:.{decimals}f}"
    # Trim trailing zeros na non-zero digit (behalve de precies-2-sig-fig vorm)
    if "." in s:
        s = s.rstrip("0").rstrip(".") if s.endswith("0") and s != "0" else s
    return s.replace(".", ",")


def format_prijs(prijs_eur: float) -> str:
    """€0,04 stijl. 0,00 → '0,00'."""
    return f"€{prijs_eur:.2f}".replace(".", ",")


def format_datum_nl(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.day} {NL_MAANDEN[d.month]} {d.year}"


def format_ai_bedrag(usd: int) -> str:
    """2670000000000 → '$ 2.670.000.000.000' (NL-punt-separator)."""
    s = f"{usd:,}".replace(",", ".")
    return f"$ {s}"


# ---------- font ----------

def _load_font(size: int, bold: bool = False):
    kandidaten = FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES
    for pad in kandidaten:
        try:
            if pad.exists():
                return ImageFont.truetype(str(pad), size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------- tekst-wrap voor smalle bon ----------

def _wrap(tekst: str, font, max_breedte_px: int) -> list[str]:
    """Simpele word-wrap op monospace. Retourneert lijst van regels."""
    woorden = tekst.split()
    regels, huidig = [], ""
    for w in woorden:
        kandidaat = (huidig + " " + w).strip()
        box = font.getbbox(kandidaat)
        breedte = box[2] - box[0]
        if breedte <= max_breedte_px or not huidig:
            huidig = kandidaat
        else:
            regels.append(huidig)
            huidig = w
    if huidig:
        regels.append(huidig)
    return regels


# ---------- de bon zelf ----------

def render_bon(
    quote: dict,
    ai_wereld_usd: int,
    url: str,
    breedte_px: int = 384,
    datum: date | None = None,
    logo_pad: Path = LOGO_PATH,
) -> Image.Image:
    """Bouw een PIL.Image met de bon, klaar voor printer of PNG.

    Lay-out volgt bron 2. Breedte in pixels is de printer-print-breedte.
    Hoogte is dynamisch — tekst-afhankelijk.
    """
    # Font-sizes — monospace, leesbaar op thermisch papier
    FS_HEADER = 22
    FS_CAPTION = 16
    FS_BODY = 18
    FS_SMALL = 14

    font_body = _load_font(FS_BODY)
    font_body_b = _load_font(FS_BODY, bold=True)
    font_caption = _load_font(FS_CAPTION)
    font_caption_b = _load_font(FS_CAPTION, bold=True)
    font_header_b = _load_font(FS_HEADER, bold=True)
    font_small = _load_font(FS_SMALL)

    # Geschat werkbare tekst-breedte (met margin)
    margin = 12
    werk_breedte = breedte_px - 2 * margin

    # --- content-regels samenstellen ---
    quote_regels = _wrap(quote["tekst"], font_body, werk_breedte)
    prijs_str = format_prijs(quote["prijs_eur"])
    pct_str = format_percentage(quote["prijs_eur"], ai_wereld_usd)
    ai_bedrag = format_ai_bedrag(ai_wereld_usd)
    datum_str = format_datum_nl(datum)

    # --- hoogte-pas: tel hoogte-blokken ---
    LINE = FS_BODY + 6
    SMLINE = FS_SMALL + 4
    SEP_HEIGHT = 10
    LOGO_H = 56 if logo_pad.exists() else 0

    hoogte = margin
    hoogte += LOGO_H + 8  # logo of ruimte
    hoogte += FS_CAPTION + 4  # "AI VRIENDIN GEZOCHT"
    hoogte += SEP_HEIGHT  # ----
    hoogte += len(quote_regels) * LINE + 4  # quote
    hoogte += SEP_HEIGHT  # ----
    hoogte += LINE + 6  # Dit gesprek  €X,XX
    hoogte += LINE  # (leeg)
    hoogte += LINE  # Wereldwijd in AI
    hoogte += LINE  # gestoken in 2026:
    hoogte += LINE + 6  # $ 2.670...
    hoogte += SEP_HEIGHT  # ----
    hoogte += SMLINE  # datum
    hoogte += SMLINE  # url
    hoogte += SMLINE  # (leeg)
    hoogte += SMLINE  # groetjes, Anna Nova
    hoogte += SMLINE  # creator: JolieJola
    hoogte += margin

    img = Image.new("L", (breedte_px, int(hoogte)), 255)  # L = grayscale, 255=wit
    dr = ImageDraw.Draw(img)

    y = margin

    # --- logo ---
    if logo_pad.exists():
        try:
            logo = Image.open(logo_pad).convert("L")
            ratio = LOGO_H / logo.height
            new_w = int(logo.width * ratio)
            logo = logo.resize((new_w, LOGO_H))
            x_logo = (breedte_px - new_w) // 2
            img.paste(logo, (x_logo, y))
        except Exception:
            pass
    y += LOGO_H + 8

    # --- "AI VRIENDIN GEZOCHT" ---
    _tekst_centraal(dr, "AI VRIENDIN GEZOCHT", y, breedte_px, font_caption_b)
    y += FS_CAPTION + 4

    # sep
    _horizontale_lijn(dr, y, breedte_px, margin)
    y += SEP_HEIGHT

    # quote (gecentreerd, meerdere regels)
    for regel in quote_regels:
        _tekst_centraal(dr, regel, y, breedte_px, font_body)
        y += LINE
    y += 4

    _horizontale_lijn(dr, y, breedte_px, margin)
    y += SEP_HEIGHT

    # "Dit gesprek       €X,XX"
    dr.text((margin, y), "Dit gesprek", font=font_body, fill=0)
    _tekst_rechts(dr, prijs_str, y, breedte_px - margin, font_body_b)
    y += LINE + 6

    y += LINE  # lege regel

    dr.text((margin, y), "Wereldwijd in AI", font=font_body, fill=0)
    y += LINE
    dr.text((margin, y), "gestoken in 2026:", font=font_body, fill=0)
    y += LINE
    dr.text((margin, y), ai_bedrag, font=font_body_b, fill=0)
    y += LINE + 6

    _horizontale_lijn(dr, y, breedte_px, margin)
    y += SEP_HEIGHT

    dr.text((margin, y), datum_str, font=font_small, fill=0)
    y += SMLINE
    dr.text((margin, y), url, font=font_small, fill=0)
    y += SMLINE
    y += SMLINE  # lege
    dr.text((margin, y), "Groetjes, Anna Nova", font=font_small, fill=0)
    y += SMLINE
    dr.text((margin, y), "creator: JolieJola", font=font_small, fill=0)

    return img


# ---------- hulpjes voor tekst-plaatsing ----------

def _tekst_centraal(dr, tekst, y, totale_breedte, font):
    box = font.getbbox(tekst)
    tekst_breedte = box[2] - box[0]
    x = (totale_breedte - tekst_breedte) // 2
    dr.text((x, y), tekst, font=font, fill=0)


def _tekst_rechts(dr, tekst, y, x_rechts, font):
    box = font.getbbox(tekst)
    tekst_breedte = box[2] - box[0]
    x = x_rechts - tekst_breedte
    dr.text((x, y), tekst, font=font, fill=0)


def _horizontale_lijn(dr, y, totale_breedte, margin):
    dr.line([(margin, y + 3), (totale_breedte - margin, y + 3)], fill=0, width=1)


# ---------- publieke API voor flow.py ----------

def maak_bon(
    inhoud: dict,
    halte_log: list[str],
    soort_laatste: str | None = None,
    recent_quote_ids: list[str] | None = None,
    breedte_px: int = 384,
    datum: date | None = None,
    rng: random.Random | None = None,
) -> tuple[Image.Image, dict]:
    """Volledige bon vanaf gesprek. Retourneert (image, quote)."""
    halte = longest_halte(halte_log)
    quote = kies_quote(inhoud, halte=halte, soort=soort_laatste,
                       recent_ids=recent_quote_ids, rng=rng)
    img = render_bon(
        quote=quote,
        ai_wereld_usd=inhoud["ai_wereld_2026_usd"],
        url=inhoud["url"],
        breedte_px=breedte_px,
        datum=datum,
    )
    return img, quote
