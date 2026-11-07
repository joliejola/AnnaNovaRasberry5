"""Gespreksmachine — vast script van 5 vragen (bron 2 sync 6 nov 14:50).

Toestanden (bron 2):

| Toestand    | Trigger-in              | Trigger-uit                                       |
|-------------|-------------------------|---------------------------------------------------|
| RUST        | start / LOSLATEN / sleep| wake → OPENING; lokzin af en toe                   |
| OPENING     | wake                    | → VRAAG (speelt opening-tekst)                     |
| VRAAG       | OPENING / REAGEREN      | → LUISTEREN (vraag uit reeks[i])                  |
| LUISTEREN   | VRAAG                   | spraak → REAGEREN; stilte → STIL; ruis → RUIS;    |
|             |                         | sleep → LOSLATEN                                   |
| REAGEREN    | LUISTEREN+spraak        | brain → reeks.reacties → volgende VRAAG / ZACHT / |
|             |                         | AFSLUITING (voor vraag 1 ja/nee/twijfel is route)  |
| STIL        | 8s stilte               | 1e: herhaal vraag → LUISTEREN; 2e: situaties.weg  |
|             |                         | → LOSLATEN zonder bon                              |
| RUIS        | ruis-event              | 1e: situaties.ruis → LUISTEREN; 2e: door naar VRAAG|
| ZACHT       | brain.soort=verdriet    | situaties.verdriet → AFSLUITING                    |
| AFSLUITING  | na v5, 2 zijwegen, 5min | afsluiting-zin, luister ja/nee/twijfel            |
| BON         | ja                      | bon+print+slotzin → LOSLATEN                       |
| LOSLATEN    | overal                  | wist sessie → RUST                                 |

Tellers:
- zijwegen: 2 → AFSLUITING (situaties.verdwaald)
- 5 min totaal → AFSLUITING (situaties.tijd)
- 2 stiltes achter elkaar op een vraag → LOSLATEN zonder bon
"""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from anna import bon, brain, hear, printer, see, speak

log = logging.getLogger(__name__)

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"
MAX_GESPREK_SEC = float(os.environ.get("MAX_GESPREK_SEC", "300"))
MAX_ZIJWEGEN = 2
PRINT_BREEDTE_PX = int(os.environ.get("PRINT_BREEDTE_PX", "384"))


class State(str, Enum):
    RUST = "RUST"
    OPENING = "OPENING"
    VRAAG = "VRAAG"
    LUISTEREN = "LUISTEREN"
    REAGEREN = "REAGEREN"
    STIL = "STIL"
    RUIS = "RUIS"
    ZACHT = "ZACHT"
    AFSLUITING = "AFSLUITING"
    ZEKER = "ZEKER"
    BON = "BON"
    LOSLATEN = "LOSLATEN"


@dataclass
class Session:
    start_tijd: float = field(default_factory=time.monotonic)
    vraag_index: int = 0  # 0..4 in reeks
    zijwegen: int = 0
    stil_count_op_vraag: int = 0  # reset bij nieuwe vraag
    ruis_count_op_vraag: int = 0
    laatste_soort: Optional[str] = None
    laatste_antwoord: str = ""
    sessie_id: int = field(default_factory=lambda: random.randint(1000, 9999))


class Flow:
    def __init__(self, inhoud: dict, state_cb=None):
        self.inhoud = inhoud
        self.rng = random.Random()
        self.state: State = State.RUST
        self.sessie: Optional[Session] = None
        self.brain_client = brain.BrainClient()
        self.see_bron = see.ZieBron()
        self.recent_quote_ids: list = []  # laatste 5 geprinte quote-ids
        self._state_cb = state_cb or (lambda s: None)
        self._should_stop = False

    # ----- helpers -----

    def _switch(self, nieuwe: State) -> None:
        if nieuwe != self.state:
            log.info("[flow] %s → %s", self.state.value, nieuwe.value)
            self.state = nieuwe
            self._state_cb(nieuwe)

    def _speel(self, item: dict | None) -> None:
        if not item:
            return
        speak.say(item.get("tekst", ""), audio_id=item.get("id"))

    def _rand_item(self, lijst: list) -> dict | None:
        return self.rng.choice(lijst) if lijst else None

    def _vraag(self) -> dict:
        assert self.sessie
        return self.inhoud["reeks"][self.sessie.vraag_index]

    def _check_timers(self) -> Optional[State]:
        if not self.sessie:
            return None
        tijd = time.monotonic() - self.sessie.start_tijd
        if tijd >= MAX_GESPREK_SEC:
            self._speel(self.inhoud["situaties"]["tijd"])
            return State.AFSLUITING
        if self.sessie.zijwegen >= MAX_ZIJWEGEN:
            self._speel(self.inhoud["situaties"]["verdwaald"])
            return State.AFSLUITING
        return None

    # ----- main loop -----

    def run_tot_stop(self) -> None:
        self._state_cb(State.RUST)
        try:
            while not self._should_stop:
                getattr(self, f"handle_{self.state.value.lower()}")()
        except KeyboardInterrupt:
            print("\n[flow] stop.")
        except Exception:
            log.exception("[flow] onverwachte fout — terug naar RUST")
            self._speel(self.inhoud["situaties"]["fout"])
            self._switch(State.LOSLATEN)

    # ----- toestanden -----

    def handle_rust(self) -> None:
        self.sessie = None
        ev = hear.luister_wake(prompt=f"[{self.state.value}] ")
        if ev.type == "wake":
            self.sessie = Session()
            self._switch(State.OPENING)
        elif ev.type == "druk":
            self.see_bron.set("meer")
        elif ev.type == "weg":
            self.see_bron.set("leeg")
        # sleep/debug/spraak in RUST: negeren, blijf

    def handle_opening(self) -> None:
        # Nieuw schema v0.5: v0 is zelf de opening-vraag.
        # Oude schema (openingen[]-lijst) wordt genegeerd als 'openingen' niet bestaat.
        openings = self.inhoud.get("openingen")
        if openings:
            self._speel(self._rand_item(openings))
        self._switch(State.VRAAG)

    def handle_vraag(self) -> None:
        assert self.sessie
        if self.sessie.vraag_index >= len(self.inhoud["reeks"]):
            self._switch(State.AFSLUITING)
            return
        v = self._vraag()
        self.sessie.stil_count_op_vraag = 0
        self.sessie.ruis_count_op_vraag = 0
        # v0.5: aanloop vóór de vraag-tekst (indien niet leeg)
        aanloop = v.get("aanloop")
        if isinstance(aanloop, dict) and (aanloop.get("tekst") or "").strip():
            self._speel(aanloop)
        self._speel(v)
        self._switch(State.LUISTEREN)

    def handle_luisteren(self) -> None:
        assert self.sessie
        timer = self._check_timers()
        if timer:
            self._switch(timer)
            return

        ev = hear.luister_spraak(prompt=f"[{self.state.value}] ")
        if ev.type == "wake":
            log.debug("[wake midden-gesprek] genegeerd")
            return
        if ev.type == "sleep":
            self._switch(State.LOSLATEN)
            return
        if ev.type == "weg":
            self.see_bron.set("leeg")
            self._switch(State.LOSLATEN)
            return
        if ev.type == "druk":
            # Bron 2 heeft geen aparte DRUK-state meer; speel situatie, blijf luisteren
            self._speel(self._rand_item([self.inhoud["situaties"]["ruis"]]))
            return
        if ev.type == "stilte":
            self._switch(State.STIL)
            return
        if ev.type == "ruis":
            self._switch(State.RUIS)
            return
        if ev.type == "spraak":
            self.sessie.laatste_antwoord = ev.tekst
            self._switch(State.REAGEREN)

    def handle_reageren(self) -> None:
        assert self.sessie
        v = self._vraag()
        bezoeker = self.sessie.laatste_antwoord

        # wachtzin af en toe — niet elke beurt (irriteert). ~30% kans,
        # en nooit twee beurten op rij in dezelfde sessie.
        if self.brain_client.beschikbaar:
            vorige = getattr(self.sessie, "_vorige_wachtzin", False)
            if not vorige and random.random() < 0.3:
                self._speel(self._rand_item(self.inhoud["wachtzinnen"]))
                self.sessie._vorige_wachtzin = True
            else:
                self.sessie._vorige_wachtzin = False

        # v0.5: geef anna-profiel + reactie_regels + per-vraag sturing mee
        r = self.brain_client.call(
            v["tekst"], bezoeker, context="VRAAG",
            anna_profiel=self.inhoud.get("anna"),
            reactie_regels=self.inhoud.get("reactie_regels"),
            sturing=v.get("sturing"),
        )
        self.sessie.laatste_soort = r["soort"]

        # Verdriet → ZACHT
        if r["soort"] == "verdriet":
            if r["reactie"]:
                speak.say(r["reactie"])
            self._switch(State.ZACHT)
            return

        # Provocatie of zijweg → speel reactie, zelfde vraag nog één keer
        if r["soort"] in ("provocatie", "zijweg"):
            if r["reactie"]:
                speak.say(r["reactie"])
            if r["soort"] == "zijweg":
                self.sessie.zijwegen += 1
            # Check teller voor volgende stap
            timer = self._check_timers()
            if timer:
                self._switch(timer)
                return
            # zelfde vraag, luister opnieuw
            self._switch(State.LUISTEREN)
            return

        # Normale paden: ja/nee/twijfel/antwoord/pas
        self._speel_reactie(r, v)

        # Volgende vraag, of afsluiting als klaar
        self.sessie.vraag_index += 1
        if self.sessie.vraag_index >= len(self.inhoud["reeks"]):
            self._switch(State.AFSLUITING)
        else:
            self._switch(State.VRAAG)

    def _speel_reactie(self, respons: dict, vraag: dict) -> None:
        """Speel brain-reactie, met fallback naar reserve uit vraag.

        v0.5 schema: vraag["reserve"][soort|"elk"].
        Fallback naar vraag["reacties"][...] voor backward compat.
        Na brain-reactie: speel vraag["na_reactie"] als die bestaat.
        """
        reactie_tekst = (respons.get("reactie") or "").strip()
        reserve = vraag.get("reserve") or vraag.get("reacties") or {}
        soort = respons["soort"]
        voorbeeld = reserve.get(soort) or reserve.get("elk")

        if reactie_tekst:
            speak.say(reactie_tekst)
        elif voorbeeld:
            self._speel(voorbeeld)

        # na_reactie: zin die Anna soms na de vrije reactie zegt.
        # Als "kans" is gezet (0..1), speelt hij alleen met die kans af —
        # zo dringt een stillete overweging zoals "Thuis kijkt er niemand
        # mee... denk je?" zich niet op bij iedere bezoeker.
        na_reactie = vraag.get("na_reactie")
        if isinstance(na_reactie, dict) and (na_reactie.get("tekst") or "").strip():
            kans = na_reactie.get("kans")
            if kans is None or random.random() < float(kans):
                self._speel(na_reactie)

    def handle_stil(self) -> None:
        assert self.sessie
        self.sessie.stil_count_op_vraag += 1
        if self.sessie.stil_count_op_vraag >= 2:
            # 2e stilte op zelfde vraag → LOSLATEN zonder bon
            self._speel(self.inhoud["situaties"]["weg"])
            self._switch(State.LOSLATEN)
            return
        # 1e stilte: herhaal vraag (geen aparte "korte" versie in nieuwe schema)
        self._speel(self.inhoud["situaties"]["pas"])
        self._speel(self._vraag())  # herhaal
        self._switch(State.LUISTEREN)

    def handle_ruis(self) -> None:
        assert self.sessie
        self.sessie.ruis_count_op_vraag += 1
        if self.sessie.ruis_count_op_vraag >= 2:
            # 2e ruis → door naar volgende vraag (telt als verloren beurt)
            self.sessie.vraag_index += 1
            if self.sessie.vraag_index >= len(self.inhoud["reeks"]):
                self._switch(State.AFSLUITING)
            else:
                self._switch(State.VRAAG)
            return
        self._speel(self.inhoud["situaties"]["ruis"])
        self._switch(State.LUISTEREN)

    def handle_zacht(self) -> None:
        # Bron 2: biedt afbouwen aan
        self._speel(self.inhoud["situaties"]["verdriet"])
        self._switch(State.AFSLUITING)

    def handle_afsluiting(self) -> None:
        assert self.sessie
        self._speel(self.inhoud["afsluiting"])
        ev = hear.luister_spraak(prompt="[AFSLUITING] ")
        if ev.type in ("sleep", "weg"):
            self._switch(State.LOSLATEN)
            return
        if ev.type == "stilte":
            # v0.5: stilte op rekening → bon (zie afsluiting.takken.stilte = bon)
            self._switch(State.BON)
            return

        # Beslis ja/nee/twijfel via brain
        r = self.brain_client.call(
            self.inhoud["afsluiting"]["tekst"],
            ev.tekst or "",
            context="AFSLUITING",
        )
        # v0.5 takken: nee → zeker, rest (ja/twijfel/antwoord/pas/stilte/zijweg) → bon
        if r["soort"] == "nee":
            self._switch(State.ZEKER)
        else:
            self._switch(State.BON)

    def handle_zeker(self) -> None:
        assert self.sessie
        zeker = self.inhoud.get("zeker")
        if not zeker:
            # Backward compat: oude schema zonder zeker-state → na_nee + LOSLATEN
            self._speel(self.inhoud.get("na_nee"))
            self._switch(State.LOSLATEN)
            return
        self._speel(zeker)
        ev = hear.luister_spraak(prompt="[ZEKER] ")
        if ev.type in ("sleep", "weg"):
            self._switch(State.LOSLATEN)
            return
        if ev.type == "stilte":
            # stilte bij "weet je het zeker?" → toch printen (takken.stilte=bon)
            self._switch(State.BON)
            return
        r = self.brain_client.call(zeker["tekst"], ev.tekst or "", context="AFSLUITING")
        # takken: ja → einde+na_nee, rest → bon
        if r["soort"] == "ja":
            self._speel(self.inhoud.get("na_nee"))
            self._switch(State.LOSLATEN)
        else:
            self._switch(State.BON)

    def handle_bon(self) -> None:
        assert self.sessie
        img, quote = bon.maak_bon(
            inhoud=self.inhoud,
            soort_laatste=self.sessie.laatste_soort,
            recent_quote_ids=self.recent_quote_ids,
            breedte_px=PRINT_BREEDTE_PX,
            rng=self.rng,
        )
        ok, info = printer.print_bon(img)
        if ok:
            log.info("[bon] %s (quote %s)", info, quote["id"])
            self.recent_quote_ids.append(quote["id"])
            self.recent_quote_ids = self.recent_quote_ids[-5:]
        else:
            self._speel(self.inhoud["situaties"]["geenprint"])

        self._speel(self._rand_item(self.inhoud["slotzinnen"]))
        self._switch(State.LOSLATEN)

    def handle_loslaten(self) -> None:
        if self.sessie:
            log.info("[loslaten] gesprek %d — gewist", self.sessie.sessie_id)
        self.sessie = None
        self._switch(State.RUST)
