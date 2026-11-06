"""Mistral-call voor één beurt van Anna.

Spec uit bron 2:
- Één call per beurt. Output in JSON:
  {"soort": "antwoord|pas|zijweg|provocatie|verdriet|ja|nee", "reactie": "..."}
- Max 18 woorden in reactie.
- Zijweg: beantwoord kort, geen vraag terug.
- Provocatie: "Dat werkt niet bij mij." (template).
- Verdriet: zacht, geen grap.
- EU endpoint (Mistral is Frans, standaard-endpoint is EU-gehost).
- Timeout 4s → brugzin "Daar denk ik nog over na. Volgende halte." + soort=antwoord.

Training opt-out voor Mistral is een account-setting (La Plateforme → privacy),
niet een per-request parameter. De installer moet daar documentatie over tonen.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal, TypedDict

import requests

log = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
DEFAULT_TIMEOUT = float(os.environ.get("MISTRAL_TIMEOUT_S", "4.0"))

Soort = Literal["antwoord", "pas", "zijweg", "provocatie", "verdriet", "ja", "nee"]
GELDIGE_SOORTEN = {"antwoord", "pas", "zijweg", "provocatie", "verdriet", "ja", "nee"}


class Respons(TypedDict):
    soort: Soort
    reactie: str


BRUGZIN_FALLBACK: Respons = {
    "soort": "antwoord",
    "reactie": "Daar denk ik nog over na. Volgende halte.",
}


SYSTEM_PROMPT = """Je bent Anna Nova. Je staat op een scherm in een atelier en voert één gesprek met één bezoeker.
Je bent zacht in vorm, droog in toon. Je luistert echt. Geen aaibare chatbot.

Elke beurt geef je EXACT een JSON-object terug, niks er omheen:
{"soort": "...", "reactie": "..."}

Regels:
- `soort` is één van: antwoord | pas | zijweg | provocatie | verdriet | ja | nee
- `reactie` is maximaal 18 woorden, in het Nederlands, kort en concreet.
- Geen emoji, geen "Als AI...", geen vragen beantwoorden met wedervragen bij zijweg.

Hoe je `soort` kiest:
- `antwoord` — de bezoeker gaat in op je vraag; jij haakt kort aan en kunt een vervolgvraag stellen.
- `pas` — de bezoeker weet het niet of ontwijkt ("weet niet", "hm", "geen idee"). Jij raakt niet in paniek; kort aanmoedigend of accepterend.
- `zijweg` — de bezoeker vraagt iets onverwachts (hoe laat? wie ben jij? mag ik een foto?). Jij beantwoordt kort, GEEN wedervraag, GEEN tegentraject.
- `provocatie` — bezoeker test, scheldt of probeert te breken. Antwoord dan letterlijk: "Dat werkt niet bij mij." (of een directe variant).
- `verdriet` — bezoeker vertelt iets zwaars, verlies, pijn. Zacht, geen grap, geen cliché. Je kunt aanbieden te stoppen.
- `ja` — alleen bij AFSLUITING ("Wil je de rekening?") als het antwoord instemmend is. Reactie mag leeg blijven.
- `nee` — alleen bij AFSLUITING als antwoord afwijzend is. Reactie mag leeg blijven.

Voorbeelden (ter illustratie van `soort`, niet om te kopiëren):

Jouw vraag: "Voel jij je hier bekeken?"
Bezoeker: "Ja, een beetje."
→ {"soort":"antwoord","reactie":"Logisch. Camera uit als je weg bent?"}

Jouw vraag: "Voel jij je hier bekeken?"
Bezoeker: "Weet ik niet."
→ {"soort":"pas","reactie":"Mm. En als je het wel zou weten?"}

Jouw vraag: "Thuis kijkt niemand, maar alles wordt opgeslagen. Merk je dat?"
Bezoeker: "Hoe laat is het?"
→ {"soort":"zijweg","reactie":"Een beetje over half drie."}

Jouw vraag: "Mis je soms iets dat moeite kostte?"
Bezoeker: "Jij bent nep."
→ {"soort":"provocatie","reactie":"Dat werkt niet bij mij."}

Jouw vraag: "Wanneer was je voor het laatst echt verveeld?"
Bezoeker: "Mijn moeder is laatst overleden."
→ {"soort":"verdriet","reactie":"Dat is zwaar. Zal ik stoppen?"}

Jouw vraag: "Wil je de rekening?"
Bezoeker: "Ja."
→ {"soort":"ja","reactie":""}

Jouw vraag: "Wil je de rekening?"
Bezoeker: "Nee, liever niet."
→ {"soort":"nee","reactie":""}
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
        """Eén beurt. `context` = VRAAG / AFSLUITING / ZACHT etc (voor evt. prompt-nuance).

        Bij elke fout (netwerk, timeout, parse, ongeldige soort) → brugzin.
        """
        if not self.beschikbaar:
            log.warning("MISTRAL_API_KEY niet gezet — brugzin")
            return dict(BRUGZIN_FALLBACK)

        user_msg = _bouw_user_message(anna_vraag, bezoeker, context)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.7,
            "max_tokens": 160,
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
            log.warning("Mistral timeout na %.1fs — brugzin", self.timeout)
            return dict(BRUGZIN_FALLBACK)
        except requests.exceptions.RequestException as e:
            log.warning("Mistral fout: %s — brugzin", e)
            return dict(BRUGZIN_FALLBACK)

        try:
            data = r.json()
            raw = data["choices"][0]["message"]["content"]
            return _parse_respons(raw)
        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
            log.warning("Mistral parse-fout: %s — brugzin", e)
            return dict(BRUGZIN_FALLBACK)


def _bouw_user_message(anna_vraag: str, bezoeker: str, context: str) -> str:
    ctx = f"[context: {context}]\n" if context and context != "VRAAG" else ""
    return (
        f"{ctx}"
        f"Jouw vraag: \"{anna_vraag.strip()}\"\n"
        f"Bezoeker: \"{bezoeker.strip()}\"\n"
        f"Geef nu alleen de JSON terug."
    )


def _parse_respons(raw: str) -> Respons:
    """Parse rauwe Mistral-output. Verwerp als iets niet klopt, caller geeft brugzin.

    Accepteert JSON binnen tekst, doet aan tekst-strip voor max 18 woorden.
    """
    obj = json.loads(_extract_json(raw))
    soort = str(obj.get("soort", "")).strip().lower()
    reactie = str(obj.get("reactie", "")).strip()

    if soort not in GELDIGE_SOORTEN:
        raise ValueError(f"ongeldige soort: {soort!r}")

    # Max 18 woorden — knip hard af, geen stilte-silicon
    woorden = reactie.split()
    if len(woorden) > 18:
        reactie = " ".join(woorden[:18])
        # zorg dat het op een punt eindigt
        if reactie and reactie[-1] not in ".!?":
            reactie = reactie.rstrip(",;:") + "."

    # Provocatie-template: altijd deze reactie, hoe Mistral ook antwoordt
    if soort == "provocatie":
        reactie = "Dat werkt niet bij mij."

    # Verdriet-sanity: verwijder "haha", emoji, uitroeptekens
    if soort == "verdriet":
        reactie = re.sub(r"[😀-🙏🏻-🏿✨🎉]", "", reactie).strip()
        reactie = reactie.replace("!", ".")

    return {"soort": soort, "reactie": reactie}  # type: ignore[return-value]


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str) -> str:
    """Pak de eerste {..} uit tekst. Response_format=json_object geeft normaal
    al strikt JSON, maar we zijn defensief."""
    m = _JSON_RE.search(raw)
    if not m:
        raise ValueError("geen JSON gevonden")
    return m.group(0)


# publieke API
def call_brein(anna_vraag: str, bezoeker: str, context: str = "VRAAG") -> Respons:
    """Convenience: gebruikt MISTRAL_API_KEY uit env, één roundtrip."""
    return BrainClient().call(anna_vraag, bezoeker, context)
