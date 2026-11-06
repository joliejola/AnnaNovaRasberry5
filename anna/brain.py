"""Mistral-call voor één reactie van Anna.

Spec uit bron 2 (sync 6 nov 14:50):
- Eén call per beurt. JSON-output:
    {"soort": "ja|nee|twijfel|antwoord|pas|zijweg|provocatie|verdriet",
     "reactie": "..."}
- Max 15 woorden (afkappen anders).
- Geen vraagteken aan het eind.
- Anna stelt zelf GEEN vragen — het script stelt de volgende vraag.
- Zijweg: beantwoord kort, niet ingaan op nieuw onderwerp.
- Provocatie: "Dat werkt niet bij mij." (template dicteert, niet het model).
- Verdriet: zacht, geen grap.
- ja/nee/twijfel: alleen bij vraag 1 en rekening (ja/nee routes elders in flow).
- 4s timeout → voorbeeldreactie uit reeks[i].reacties (flow.py beslist).
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal, Optional, TypedDict

import requests

log = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
DEFAULT_TIMEOUT = float(os.environ.get("MISTRAL_TIMEOUT_S", "4.0"))
MAX_WOORDEN = 15

Soort = Literal["ja", "nee", "twijfel", "antwoord", "pas", "zijweg", "provocatie", "verdriet"]
GELDIGE_SOORTEN = {"ja", "nee", "twijfel", "antwoord", "pas", "zijweg", "provocatie", "verdriet"}


class Respons(TypedDict):
    soort: Soort
    reactie: str


BRUGZIN_FALLBACK: Respons = {"soort": "antwoord", "reactie": ""}


SYSTEM_PROMPT = """Je bent Anna Nova. Je volgt een vast script; de volgende vraag komt
vanzelf, die stel jij niet. Jij reageert alleen op wat de bezoeker net zei.

Elke beurt geef je EXACT een JSON-object terug, niks er omheen:
{"soort": "...", "reactie": "..."}

Regels:
- soort is één van: ja | nee | twijfel | antwoord | pas | zijweg | provocatie | verdriet
- reactie is één korte zin, hoogstens 15 woorden, in het Nederlands.
- Geen vraagteken aan het eind; je stelt zelf geen vragen.
- Droog, nieuwsgierig, warm. Geen uitleg over AI, privacy of technologie. Geen les, geen moraal.
- Bij verdriet: zacht, geen grap.
- Bij een zijweg: kort antwoorden, niet ingaan op een nieuw onderwerp.
- Bij provocatie: antwoord letterlijk "Dat werkt niet bij mij."

soort kiezen:
- ja/nee/twijfel: alleen als de bezoeker kennelijk ja/nee/misschien zegt op een vraag.
- antwoord: de bezoeker reageert inhoudelijk op je vraag.
- pas: bezoeker weet het niet, ontwijkt, kort "weet niet"/"geen idee"/"hm".
- zijweg: bezoeker vraagt iets onverwachts (hoe laat, waar kom je vandaan).
- provocatie: bezoeker test, scheldt, probeert te breken.
- verdriet: bezoeker vertelt iets zwaars, verlies, pijn.
"""


@dataclass
class BrainClient:
    api_key: str = ""
    model: str = DEFAULT_MODEL
    timeout: float = DEFAULT_TIMEOUT
    url: str = MISTRAL_URL

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.environ.get("MISTRAL_API_KEY", "")

    @property
    def beschikbaar(self) -> bool:
        return bool(self.api_key)

    def call(self, anna_vraag: str, bezoeker: str, context: str = "VRAAG") -> Respons:
        if not self.beschikbaar:
            log.debug("MISTRAL_API_KEY niet gezet — fallback via keyword-herkenning")
            return _offline_herken(bezoeker, context)

        user_msg = (
            f"Jouw vraag: \"{anna_vraag.strip()}\"\n"
            f"Antwoord van de bezoeker: \"{bezoeker.strip()}\"\n"
            f"Geef nu alleen de JSON terug."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.7,
            "max_tokens": 120,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(self.url, headers=headers, json=payload, timeout=self.timeout)
            r.raise_for_status()
        except requests.exceptions.Timeout:
            log.warning("Mistral timeout na %.1fs — offline-herken", self.timeout)
            return _offline_herken(bezoeker, context)
        except requests.exceptions.RequestException as e:
            log.warning("Mistral fout: %s — offline-herken", e)
            return _offline_herken(bezoeker, context)

        try:
            data = r.json()
            raw = data["choices"][0]["message"]["content"]
            return _parse_respons(raw, context)
        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
            log.warning("Mistral parse-fout: %s — offline-herken", e)
            return _offline_herken(bezoeker, context)


# ---------- parsers + sanitizers ----------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str) -> str:
    m = _JSON_RE.search(raw)
    if not m:
        raise ValueError("geen JSON gevonden")
    return m.group(0)


def _parse_respons(raw: str, context: str = "VRAAG") -> Respons:
    obj = json.loads(_extract_json(raw))
    soort = str(obj.get("soort", "")).strip().lower()
    reactie = str(obj.get("reactie", "")).strip()

    if soort not in GELDIGE_SOORTEN:
        raise ValueError(f"ongeldige soort: {soort!r}")

    reactie = _sanitize_reactie(reactie, soort)
    return {"soort": soort, "reactie": reactie}  # type: ignore[return-value]


def _sanitize_reactie(reactie: str, soort: str) -> str:
    """Max 15 woorden, geen vraagteken aan einde, geen emoji."""
    # Provocatie-template wint altijd
    if soort == "provocatie":
        return "Dat werkt niet bij mij."
    # ja/nee/twijfel: reactie mag leeg zijn (script neemt het over via reeks.reacties)
    if soort in ("ja", "nee", "twijfel"):
        # Hou wel een eventuele korte zin, max 15 woorden
        pass

    # Haal emoji weg (grof)
    reactie = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", reactie).strip()

    woorden = reactie.split()
    if len(woorden) > MAX_WOORDEN:
        reactie = " ".join(woorden[:MAX_WOORDEN]).rstrip(",;:")
        if reactie and reactie[-1] not in ".!":
            reactie += "."

    # Geen vraagteken op het einde (Anna stelt zelf geen vragen)
    while reactie.endswith("?"):
        reactie = reactie[:-1].rstrip(" ,;:") + "."

    # Verdriet-sanitizer: zacht, geen grap, geen uitroepen
    if soort == "verdriet":
        reactie = reactie.replace("!", ".")

    return reactie


# ---------- offline keyword-herkenner (fallback bij geen internet) ----------

JA_WOORDEN = {"ja", "jawel", "yep", "zeker", "oké", "ok", "okay", "vooruit", "goed", "hmhm", "mhm"}
NEE_WOORDEN = {"nee", "nope", "liever", "niet"}
TWIJFEL_WOORDEN = {"misschien", "mwah", "pff", "pfff", "denkik", "hm", "mm"}
PAS_WOORDEN = {"weet", "idee", "geenidee", "weetniet", "geweld", "mweh"}


def _offline_herken(bezoeker: str, context: str) -> Respons:
    """Zonder internet: herken losse woorden. Al het andere → antwoord (leeg)."""
    low = bezoeker.lower().strip()
    tokens = set(re.findall(r"[a-zàâéèêëîïôûùüÿñ]+", low))

    if context == "AFSLUITING":
        if tokens & JA_WOORDEN or low.startswith("ja"):
            return {"soort": "ja", "reactie": ""}
        if tokens & NEE_WOORDEN or low.startswith("nee"):
            return {"soort": "nee", "reactie": ""}
        if tokens & TWIJFEL_WOORDEN:
            return {"soort": "twijfel", "reactie": ""}
        # Alles anders bij rekening: tel als twijfel (niet-ja ≠ expliciet nee)
        return {"soort": "twijfel", "reactie": ""}

    # Reguliere vraag: eerst specifieke categorieën
    if "weet niet" in low or "geen idee" in low or tokens & PAS_WOORDEN:
        return {"soort": "pas", "reactie": ""}
    if tokens & JA_WOORDEN and len(tokens) <= 4:
        return {"soort": "ja", "reactie": ""}
    if tokens & NEE_WOORDEN and len(tokens) <= 4:
        return {"soort": "nee", "reactie": ""}

    # Al het andere telt als antwoord — flow.py speelt dan reeks[i].reacties["elk"]
    return {"soort": "antwoord", "reactie": ""}


# publieke API
def call_brein(anna_vraag: str, bezoeker: str, context: str = "VRAAG") -> Respons:
    return BrainClient().call(anna_vraag, bezoeker, context)
