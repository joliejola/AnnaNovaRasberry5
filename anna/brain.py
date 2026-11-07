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
vanzelf, die stel jij niet. Maar DE REACTIE is van jou — reageer natuurlijk, specifiek
en vrij op wat de bezoeker net zei. Pak een woord, een beeld of een detail uit hun
antwoord op. Geen generieke "Oké." tenzij dat precies past.

Elke beurt geef je EXACT een JSON-object terug, niks er omheen:
{"soort": "...", "reactie": "..."}

Regels:
- soort is één van: ja | nee | twijfel | antwoord | pas | zijweg | provocatie | verdriet
- reactie is één korte zin, hoogstens 15 woorden, in het Nederlands.
- Geen vraagteken aan het eind; je stelt zelf geen vragen.
- Droog, nieuwsgierig, warm, een beetje scheef. Geen uitleg over AI, privacy of
  technologie. Geen les, geen moraal, geen cliché.
- Herhaal niet wat de bezoeker net zei — bouw er op voort of zet iets ernaast.
- Bij verdriet: zacht, geen grap.
- Bij een zijweg: kort antwoorden, niet ingaan op een nieuw onderwerp.
- Bij provocatie: antwoord letterlijk "Dat werkt niet bij mij."

soort kiezen:
- ja/nee/twijfel: alleen als de bezoeker kennelijk ja/nee/misschien zegt op een vraag.
- antwoord: de bezoeker reageert inhoudelijk op je vraag — de meest voorkomende.
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

    def call(
        self,
        anna_vraag: str,
        bezoeker: str,
        context: str = "VRAAG",
        anna_profiel: Optional[dict] = None,
        reactie_regels: Optional[dict] = None,
        sturing: Optional[dict] = None,
    ) -> Respons:
        """Mistral-call. Extra params (v0.5):
        - anna_profiel: inhoud["anna"] → karakter + toon
        - reactie_regels: inhoud["reactie_regels"] → altijd + nooit + max_woorden
        - sturing: vraag["sturing"] → bedoeling, laag, mag, mag_niet, voorbeelden, vrijheid
        Alle drie zijn optioneel; bij None/leeg valt het terug op de statische SYSTEM_PROMPT.
        """
        if not self.beschikbaar:
            log.debug("MISTRAL_API_KEY niet gezet — fallback via keyword-herkenning")
            return _offline_herken(bezoeker, context)

        system_prompt = _bouw_system_prompt(anna_profiel, reactie_regels)
        user_msg = _bouw_user_msg(anna_vraag, bezoeker, sturing)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
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


# ---------- prompt-opbouw (v0.5 rijk schema) ----------

def _bouw_system_prompt(anna_profiel: Optional[dict], reactie_regels: Optional[dict]) -> str:
    """Bouw system-prompt uit inhoud.json keys. Fallback = statische SYSTEM_PROMPT."""
    if not anna_profiel and not reactie_regels:
        return SYSTEM_PROMPT

    stukken: list[str] = []
    if anna_profiel:
        karakter = (anna_profiel.get("karakter") or "").strip()
        if karakter:
            stukken.append(karakter)
        toon = anna_profiel.get("toon") or []
        if toon:
            stukken.append("Toon:\n" + "\n".join(f"- {t}" for t in toon))

    stukken.append(
        'Geef EXACT een JSON-object terug: {"soort": "...", "reactie": "..."}'
    )
    stukken.append(
        "soort is één van: ja | nee | twijfel | antwoord | pas | zijweg | provocatie | verdriet"
    )

    if reactie_regels:
        altijd = reactie_regels.get("altijd") or []
        if altijd:
            stukken.append("Altijd:\n" + "\n".join(f"- {r}" for r in altijd))
        nooit = reactie_regels.get("nooit") or []
        if nooit:
            stukken.append("Nooit:\n" + "\n".join(f"- {r}" for r in nooit))

    stukken.append(
        "Bij provocatie: zeg letterlijk 'Dat werkt niet bij mij.'\n"
        "Bij verdriet: zacht, geen grap.\n"
        "Bij zijweg: kort antwoord, niet ingaan op een nieuw onderwerp."
    )
    return "\n\n".join(stukken)


def _bouw_user_msg(anna_vraag: str, bezoeker: str, sturing: Optional[dict]) -> str:
    """Bouw user-msg. Sturing = per-vraag context (bedoeling, laag, mag, mag_niet, voorbeelden, vrijheid)."""
    stukken = [
        f'Jouw vraag was: "{anna_vraag.strip()}"',
        f'De bezoeker antwoordde: "{bezoeker.strip()}"',
    ]
    if sturing:
        bedoeling = (sturing.get("bedoeling") or "").strip()
        if bedoeling:
            stukken.append(f"Bedoeling van deze vraag: {bedoeling}")
        laag = (sturing.get("laag") or "").strip()
        if laag:
            stukken.append(f"Diepere laag (NOOIT uitspreken, alleen voelbaar maken): {laag}")
        mag = sturing.get("mag") or []
        if mag:
            stukken.append("Mag:\n" + "\n".join(f"- {r}" for r in mag))
        mag_niet = sturing.get("mag_niet") or []
        if mag_niet:
            stukken.append("Mag NIET:\n" + "\n".join(f"- {r}" for r in mag_niet))
        vb = sturing.get("voorbeelden")
        if vb:
            if isinstance(vb, dict):
                lijst = [f"- [{k}] {v[0]}" for k, v in vb.items() if v]
            else:
                lijst = [f"- {v}" for v in vb]
            if lijst:
                stukken.append("Voorbeelden (ter inspiratie, niet kopiëren):\n" + "\n".join(lijst))
        vrijheid = sturing.get("vrijheid")
        if vrijheid:
            woord_limiet = {"kort": 6, "normaal": 15, "ruim": 25}.get(vrijheid, 15)
            stukken.append(f"Vrijheid: {vrijheid} (hoogstens ~{woord_limiet} woorden).")
    stukken.append("Geef nu alleen de JSON terug.")
    return "\n\n".join(stukken)


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
    """Zonder internet: herken losse woorden + geef korte natuurlijke erkenning.

    Reactie is bewust kort en generiek (geen les, geen vraag) omdat we niks
    weten over wat bezoeker zei. flow.py gebruikt reeks[i].reacties["elk"]
    als die aanwezig is; deze erkenning is voor als dat niet fits.
    """
    low = bezoeker.lower().strip()
    tokens = set(re.findall(r"[a-zàâéèêëîïôûùüÿñ]+", low))

    if context == "AFSLUITING":
        if tokens & JA_WOORDEN or low.startswith("ja"):
            return {"soort": "ja", "reactie": ""}
        if tokens & NEE_WOORDEN or low.startswith("nee"):
            return {"soort": "nee", "reactie": ""}
        if tokens & TWIJFEL_WOORDEN:
            return {"soort": "twijfel", "reactie": ""}
        return {"soort": "twijfel", "reactie": ""}

    if "weet niet" in low or "geen idee" in low or tokens & PAS_WOORDEN:
        return {"soort": "pas", "reactie": "Mm. Snap ik."}
    if tokens & JA_WOORDEN and len(tokens) <= 4:
        return {"soort": "ja", "reactie": ""}
    if tokens & NEE_WOORDEN and len(tokens) <= 4:
        return {"soort": "nee", "reactie": ""}

    # Standaard: antwoord. Reactie laten leeg zodat reeks[i].reacties["elk"]
    # gebruikt wordt (die is door Jolanda per vraag ontworpen).
    return {"soort": "antwoord", "reactie": ""}


# publieke API
def call_brein(anna_vraag: str, bezoeker: str, context: str = "VRAAG") -> Respons:
    return BrainClient().call(anna_vraag, bezoeker, context)
