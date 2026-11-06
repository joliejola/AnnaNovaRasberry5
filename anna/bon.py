"""Bouw een bon-PNG uit een gesprek.

Aangeroepen door flow.py bij toestand BON. Levert een PIL.Image terug die
printer.py kan versturen, of een pad naar een PNG als DROOGLOOP=1.

Regels uit bron 2 (sync 6 nov 14:50):
- Quote: willekeurig uit quotes met goedgekeurd=true, nooit een van de laatste 5.
  Na soort "verdriet": alleen uit quotes met zacht:true; zijn die er niet, dan
  bon zonder quote met prijs € 0,00.
- Tijdens bouw: --alle-quotes (ALLE_QUOTES=1 env) laat ook goedgekeurd:null toe.
- Prijs is STRING ("€ 4,10" of "€ 9,99 p/m") — Jolanda formatteert zelf.
- Geen "Jouw aandeel %" regel (parent-commit 44220fa).
- Datum Nederlands. Font: vrije monospace (Courier Prime bij voorkeur).
"""
from __future__ import annotations

import json
import os
import random
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
INHOUD_PATH = ROOT / "content" / "inhoud.json"
LOGO_PATH = ROOT / "assets" / "logo.png"

ALLE_QUOTES = os.environ.get("ALLE_QUOTES", "1") == "1"  # bouwdag-default: alles toegestaan

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

LEGE_QUOTE = {"id": 0, "tekst": "", "prijs": "€ 0,00", "zacht": True, "goedgekeurd": True}


def _beschikbaar(q: dict) -> bool:
    if q.get("goedgekeurd") is True:
        return True
    if ALLE_QUOTES and q.get("goedgekeurd") is not False:
        return True
    return False


def kies_quote(
    inhoud: dict,
    soort_laatste: str | None = None,
    recent_ids: list | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Trek een quote volgens bron 2.

    - soort_laatste == "verdriet" → alleen zacht:true. Geen match → LEGE_QUOTE
      (€ 0,00, geen tekst).
    - anders: alle beschikbare quotes.
    - Nooit een id uit `recent_ids` (laatste 5), tenzij geen alternatief.
    """
    rng = rng or random.Random()
    recent = set(recent_ids or [])
    quotes = inhoud["quotes"]
    pool = [q for q in quotes if _beschikbaar(q)]

    if soort_laatste == "verdriet":
        zacht = [q for q in pool if q.get("zacht") is True]
        if not zacht:
            return dict(LEGE_QUOTE)
        niet_recent = [q for q in zacht if q["id"] not in recent]
        return rng.choice(niet_recent or zacht)

    niet_recent = [q for q in pool if q["id"] not in recent]
    if niet_recent:
        return rng.choice(niet_recent)
    return rng.choice(pool) if pool else dict(LEGE_QUOTE)


# ---------- formatting ----------

def format_datum_nl(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.day} {NL_MAANDEN[d.month]} {d.year}"


def format_ai_bedrag(usd: int) -> str:
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
    if not tekst:
        return []
    woorden = tekst.split()
    regels, huidig = [], ""
    for w in woorden:
        kandidaat = (huidig + " " + w).strip()
        breedte = font.getbbox(kandidaat)[2] - font.getbbox(kandidaat)[0]
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
    """Bouw PIL.Image van de bon volgens bron-2 lay-out (zonder 'Jouw aandeel')."""
    FS_CAPTION = 16
    FS_BODY = 18
    FS_SMALL = 14

    font_body = _load_font(FS_BODY)
    font_body_b = _load_font(FS_BODY, bold=True)
    font_caption_b = _load_font(FS_CAPTION, bold=True)
    font_small = _load_font(FS_SMALL)

    margin = 12
    werk_breedte = breedte_px - 2 * margin

    quote_tekst = quote.get("tekst", "")
    prijs_str = str(quote.get("prijs", "€ 0,00"))
    ai_bedrag = format_ai_bedrag(ai_wereld_usd)
    datum_str = format_datum_nl(datum)

    quote_regels = _wrap(quote_tekst, font_body, werk_breedte)

    LINE = FS_BODY + 6
    SMLINE = FS_SMALL + 4
    SEP_HEIGHT = 10
    LOGO_H = 72 if logo_pad.exists() else 0

    hoogte = margin
    hoogte += LOGO_H + 8
    hoogte += FS_CAPTION + 6
    hoogte += SEP_HEIGHT
    if quote_regels:
        hoogte += len(quote_regels) * LINE + 4
    else:
        hoogte += LINE  # lege gereserveerde regel om de bon niet te krap te krijgen
    hoogte += SEP_HEIGHT
    hoogte += LINE + 6             # "Dit gesprek  €X,XX"
    hoogte += LINE                 # lege
    hoogte += LINE                 # "Wereldwijd in AI"
    hoogte += LINE                 # "gestoken in 2026:"
    hoogte += LINE + 6             # bedrag
    hoogte += SEP_HEIGHT
    hoogte += SMLINE               # datum
    hoogte += SMLINE               # url
    hoogte += SMLINE               # (leeg)
    hoogte += SMLINE               # Groetjes, Anna Nova
    hoogte += SMLINE               # creator: JolieJola
    hoogte += margin

    img = Image.new("L", (breedte_px, int(hoogte)), 255)
    dr = ImageDraw.Draw(img)
    y = margin

    if logo_pad.exists():
        try:
            logo = Image.open(logo_pad).convert("L")
            ratio = LOGO_H / logo.height
            new_w = int(logo.width * ratio)
            logo = logo.resize((new_w, LOGO_H))
            img.paste(logo, ((breedte_px - new_w) // 2, y))
        except Exception:
            pass
    y += LOGO_H + 8

    _tekst_centraal(dr, "AI VRIENDIN GEZOCHT", y, breedte_px, font_caption_b)
    y += FS_CAPTION + 6

    _horizontale_lijn(dr, y, breedte_px, margin)
    y += SEP_HEIGHT

    if quote_regels:
        for regel in quote_regels:
            _tekst_centraal(dr, regel, y, breedte_px, font_body)
            y += LINE
        y += 4
    else:
        y += LINE

    _horizontale_lijn(dr, y, breedte_px, margin)
    y += SEP_HEIGHT

    dr.text((margin, y), "Dit gesprek", font=font_body, fill=0)
    _tekst_rechts(dr, prijs_str, y, breedte_px - margin, font_body_b)
    y += LINE + 6

    y += LINE

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
    y += SMLINE
    dr.text((margin, y), "Groetjes, Anna Nova", font=font_small, fill=0)
    y += SMLINE
    dr.text((margin, y), "creator: JolieJola", font=font_small, fill=0)

    return img


# ---------- hulpjes ----------

def _tekst_centraal(dr, tekst, y, totale_breedte, font):
    box = font.getbbox(tekst)
    x = (totale_breedte - (box[2] - box[0])) // 2
    dr.text((x, y), tekst, font=font, fill=0)


def _tekst_rechts(dr, tekst, y, x_rechts, font):
    box = font.getbbox(tekst)
    x = x_rechts - (box[2] - box[0])
    dr.text((x, y), tekst, font=font, fill=0)


def _horizontale_lijn(dr, y, totale_breedte, margin):
    dr.line([(margin, y + 3), (totale_breedte - margin, y + 3)], fill=0, width=1)


# ---------- publieke API voor flow.py ----------

def maak_bon(
    inhoud: dict,
    soort_laatste: str | None = None,
    recent_quote_ids: list | None = None,
    breedte_px: int = 384,
    datum: date | None = None,
    rng: random.Random | None = None,
) -> tuple[Image.Image, dict]:
    """Volledige bon vanaf gesprek. Retourneert (image, quote)."""
    quote = kies_quote(inhoud, soort_laatste=soort_laatste,
                       recent_ids=recent_quote_ids, rng=rng)
    img = render_bon(
        quote=quote,
        ai_wereld_usd=inhoud["ai_wereld_2026_usd"],
        url=inhoud["url"],
        breedte_px=breedte_px,
        datum=datum,
    )
    return img, quote
