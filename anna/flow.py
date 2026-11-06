"""Gespreksmachine — state-machine van RUST naar BON en terug.

Toestanden en overgangen volgens bron 2 + revisie 6 nov (wake-phrase + sleep).

| Toestand    | Trigger-in                     | Trigger-uit                                      |
|-------------|--------------------------------|--------------------------------------------------|
| RUST        | start, LOSLATEN, sleep         | wake → OPENING                                   |
| OPENING     | wake                           | → VRAAG (na WAKE_ACK + opening-zin)              |
| VRAAG       | OPENING, REAGEREN              | → LUISTEREN                                       |
| LUISTEREN   | VRAAG                          | spraak → REAGEREN; stilte → STIL; ruis → RUIS;   |
|             |                                | sleep → LOSLATEN; weg → LOSLATEN                 |
| REAGEREN    | LUISTEREN+spraak               | brain-call → VRAAG / AFSLUITING / ZACHT          |
| STIL        | 8s stilte in LUISTEREN         | → LUISTEREN of VRAAG                              |
| RUIS        | ruis in LUISTEREN              | → LUISTEREN of VRAAG                              |
| DRUK        | meerdere mensen op plek        | 10s wacht → KNOPMODUS                             |
| KNOPMODUS   | DRUK-timeout                   | 30s rust → LUISTEREN                              |
| ZACHT       | brain.soort == verdriet        | → AFSLUITING                                      |
| AFSLUITING  | 4 vragen klaar / 5 min /       | ja → BON; nee → LOSLATEN                          |
|             | 2 zijwegen / ZACHT             |                                                   |
| BON         | ja                             | print → slotzin → LOSLATEN                        |
| LOSLATEN    | BON / nee / 6s weg / sleep     | wist session → RUST                               |

Tellers (op session):
- zijwegen: 2 → AFSLUITING
- 5 min totaal → AFSLUITING
- 6s plek leeg (in actieve toestand) → LOSLATEN
"""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from anna import bon, brain, hear, printer, see, speak

log = logging.getLogger(__name__)

DROOGLOOP = os.environ.get("DROOGLOOP", "0") == "1"
MAX_GESPREK_SEC = float(os.environ.get("MAX_GESPREK_SEC", "300"))  # 5 min
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
    DRUK = "DRUK"
    KNOPMODUS = "KNOPMODUS"
    ZACHT = "ZACHT"
    AFSLUITING = "AFSLUITING"
    BON = "BON"
    LOSLATEN = "LOSLATEN"


@dataclass
class Session:
    """Alles wat voor één gesprek bestaat — gewist in LOSLATEN."""
    start_tijd: float = field(default_factory=time.monotonic)
    vraag_rij: list[dict] = field(default_factory=list)  # getrokken 4
    vraag_index: int = 0
    halte_log: list[str] = field(default_factory=list)  # halte per beantwoorde vraag
    zijwegen: int = 0
    stil_tellers: int = 0
    ruis_tellers: int = 0
    laatste_soort: Optional[str] = None
    laatste_anna_vraag: str = ""
    sessie_id: int = field(default_factory=lambda: random.randint(1000, 9999))


class Flow:
    """Orkestreert de machine. Eén instance per boot."""

    def __init__(self, inhoud: dict, state_cb=None):
        self.inhoud = inhoud
        self.rng = random.Random()
        self.state: State = State.RUST
        self.sessie: Optional[Session] = None
        self.brain_client = brain.BrainClient()
        self.see_bron = see.ZieBron()
        self.recent_quote_ids: list[str] = []  # laatste 5 bon-quote-ids
        self._state_cb = state_cb or (lambda s: None)
        self._should_stop = False

    # ----- helpers -----

    def _switch(self, nieuwe: State) -> None:
        if nieuwe != self.state:
            log.info("[flow] %s → %s", self.state.value, nieuwe.value)
            self.state = nieuwe
            self._state_cb(nieuwe)

    def _random_tekst(self, lijst: list[dict], fallback: str = "") -> tuple[str, str | None]:
        """Trek willekeurig een (tekst, id) uit een lijst van {id, tekst}-dicts."""
        if not lijst:
            return fallback, None
        item = self.rng.choice(lijst)
        return item.get("tekst", fallback), item.get("id")

    def _trek_vragen(self) -> list[dict]:
        """4 vragen: 1 bekeken (voorkeur licht:true), 1 bewaard, 1 wrijving,
        1 vrij uit bewaard/wrijving. Geen dubbele."""
        alle = self.inhoud["vragen"]
        per_halte = {"bekeken": [], "bewaard": [], "wrijving": []}
        for v in alle:
            if v["halte"] in per_halte:
                per_halte[v["halte"]].append(v)

        gekozen: list[dict] = []

        # 1: bekeken, voorkeur licht:true
        licht = [v for v in per_halte["bekeken"] if v.get("licht")]
        pool = licht or per_halte["bekeken"]
        if pool:
            gekozen.append(self.rng.choice(pool))

        # 2: bewaard
        if per_halte["bewaard"]:
            gekozen.append(self.rng.choice(per_halte["bewaard"]))

        # 3: wrijving
        if per_halte["wrijving"]:
            gekozen.append(self.rng.choice(per_halte["wrijving"]))

        # 4: vrij uit bewaard/wrijving, niet dubbel
        gebruikt_ids = {v["id"] for v in gekozen}
        vrij_pool = [v for v in (per_halte["bewaard"] + per_halte["wrijving"])
                     if v["id"] not in gebruikt_ids]
        if vrij_pool:
            gekozen.append(self.rng.choice(vrij_pool))

        return gekozen

    def _check_timers(self) -> Optional[State]:
        """Return een state als een teller afloopt, anders None."""
        if not self.sessie:
            return None
        tijd = time.monotonic() - self.sessie.start_tijd
        if tijd >= MAX_GESPREK_SEC:
            log.info("[timer] gesprek > %ds — AFSLUITING", MAX_GESPREK_SEC)
            return State.AFSLUITING
        if self.sessie.zijwegen >= MAX_ZIJWEGEN:
            log.info("[timer] 2 zijwegen — AFSLUITING")
            return State.AFSLUITING
        if self.see_bron.get().is_leeg():
            # 6s plek leeg wordt in handle_* geïnterpreteerd; hier alleen
            # ruwe signalering. In droogloop komt dit via #weg event.
            return None
        return None

    # ----- state-handlers -----

    def run_tot_stop(self) -> None:
        """REPL-achtige main-loop. Draait tot KeyboardInterrupt of _should_stop."""
        self._state_cb(State.RUST)
        try:
            while not self._should_stop:
                getattr(self, f"handle_{self.state.value.lower()}")()
        except KeyboardInterrupt:
            print("\n[flow] stop.")
        except Exception:
            log.exception("[flow] onverwachte fout — terug naar RUST")
            self._switch(State.RUST)

    # --- toestanden ---

    def handle_rust(self) -> None:
        self.sessie = None
        # Lokzin af en toe (alleen als iemand in de ruimte is).
        # In droogloop keep it simple: één prompt, geen auto-lokzin-timer.
        ev = hear.luister_wake(prompt=f"[{self.state.value}] ")
        if ev.type == "wake":
            self.sessie = Session()
            self.sessie.vraag_rij = self._trek_vragen()
            self._switch(State.OPENING)
        elif ev.type == "sleep":
            # Al in rust; speel niets, blijf.
            pass
        elif ev.type == "weg":
            self.see_bron.set("leeg")
        elif ev.type == "druk":
            self.see_bron.set("meer")
        # debug / anders: negeren

    def handle_opening(self) -> None:
        # WAKE_ACK
        tekst, aid = self._random_tekst(self.inhoud["situaties"]["wake_ack"], "Hm.")
        speak.say(tekst, audio_id=aid)
        # Opening
        opening_tekst, oid = self._random_tekst(self.inhoud["openingen"], "Hé.")
        speak.say(opening_tekst, audio_id=oid)
        self._switch(State.VRAAG)

    def handle_vraag(self) -> None:
        assert self.sessie
        if self.sessie.vraag_index >= len(self.sessie.vraag_rij):
            self._switch(State.AFSLUITING)
            return
        v = self.sessie.vraag_rij[self.sessie.vraag_index]
        self.sessie.laatste_anna_vraag = v["tekst"]
        speak.say(v["tekst"], audio_id=v["id"])
        self._switch(State.LUISTEREN)

    def handle_luisteren(self) -> None:
        assert self.sessie
        # Check tijd-teller voor we luisteren — anders zouden we hier eindeloos blijven
        timer_state = self._check_timers()
        if timer_state:
            self._switch(timer_state)
            return

        ev = hear.luister_spraak(prompt=f"[{self.state.value}] ")
        self.sessie.stil_tellers = 0  # reset bij elke ontvangst
        if ev.type == "wake":
            # Herhaalde wake midden-gesprek: negeer, blijf luisteren
            log.debug("wake midden-gesprek genegeerd")
            return
        if ev.type == "sleep":
            self._switch(State.LOSLATEN)
            return
        if ev.type == "weg":
            self.see_bron.set("leeg")
            self._switch(State.LOSLATEN)
            return
        if ev.type == "druk":
            self.see_bron.set("meer")
            self._switch(State.DRUK)
            return
        if ev.type == "stilte":
            self.sessie.stil_tellers += 1
            self._switch(State.STIL)
            return
        if ev.type == "ruis":
            self._switch(State.RUIS)
            return
        if ev.type == "spraak":
            # Antwoord ontvangen — laat REAGEREN de brain call doen
            self._laatste_antwoord = ev.tekst
            self._switch(State.REAGEREN)
            return

    def handle_reageren(self) -> None:
        assert self.sessie
        antwoord = getattr(self, "_laatste_antwoord", "")
        v = self.sessie.vraag_rij[self.sessie.vraag_index]
        ctx = "AFSLUITING" if self.state == State.AFSLUITING else "VRAAG"

        # wachtzin om traag-voelen te vermijden
        if self.brain_client.beschikbaar:
            w, wid = self._random_tekst(self.inhoud["wachtzinnen"], "")
            if w:
                speak.say(w, audio_id=wid, blocking=False)

        r = self.brain_client.call(v["tekst"], antwoord, ctx)
        self.sessie.laatste_soort = r["soort"]
        if r["reactie"]:
            speak.say(r["reactie"])

        # halte-log bijwerken voor longest-halte quote-keuze later
        if r["soort"] in ("antwoord", "pas"):
            self.sessie.halte_log.append(v["halte"])
            self.sessie.vraag_index += 1
        elif r["soort"] == "zijweg":
            self.sessie.zijwegen += 1
            # zijweg: niet door naar volgende vraag, zelfde vraag niet herhalen
            # → in plaats: hergebruik huidige of door naar volgende?
            # Bron 2 impliceert: ga door naar volgende vraag.
            self.sessie.halte_log.append(v["halte"])
            self.sessie.vraag_index += 1
        elif r["soort"] == "provocatie":
            # geen vraag-voortgang — Anna heeft gereageerd, luister opnieuw
            pass
        elif r["soort"] == "verdriet":
            self._switch(State.ZACHT)
            return

        # check timer-triggers
        timer = self._check_timers()
        if timer:
            self._switch(timer)
            return
        if self.sessie.vraag_index >= len(self.sessie.vraag_rij):
            self._switch(State.AFSLUITING)
            return
        self._switch(State.VRAAG)

    def handle_stil(self) -> None:
        assert self.sessie
        sit = self.inhoud["situaties"]["pas"]
        idx = min(self.sessie.stil_tellers - 1, len(sit) - 1)
        tekst, aid = sit[idx]["tekst"], sit[idx].get("id")
        speak.say(tekst, audio_id=aid)
        # 2e stilte op zelfde vraag: ga door
        if self.sessie.stil_tellers >= 2:
            self.sessie.halte_log.append(
                self.sessie.vraag_rij[self.sessie.vraag_index]["halte"]
            )
            self.sessie.vraag_index += 1
            self.sessie.stil_tellers = 0
            if self.sessie.vraag_index >= len(self.sessie.vraag_rij):
                self._switch(State.AFSLUITING)
                return
            self._switch(State.VRAAG)
            return
        self._switch(State.LUISTEREN)

    def handle_ruis(self) -> None:
        assert self.sessie
        sit = self.inhoud["situaties"]["ruis"]
        idx = min(self.sessie.ruis_tellers, len(sit) - 1)
        tekst, aid = sit[idx]["tekst"], sit[idx].get("id")
        speak.say(tekst, audio_id=aid)
        self.sessie.ruis_tellers += 1
        if self.sessie.ruis_tellers >= 2:
            # 2e ruis → door naar volgende vraag
            self.sessie.halte_log.append(
                self.sessie.vraag_rij[self.sessie.vraag_index]["halte"]
            )
            self.sessie.vraag_index += 1
            self.sessie.ruis_tellers = 0
            if self.sessie.vraag_index >= len(self.sessie.vraag_rij):
                self._switch(State.AFSLUITING)
                return
            self._switch(State.VRAAG)
            return
        self._switch(State.LUISTEREN)

    def handle_druk(self) -> None:
        tekst, aid = self._random_tekst(self.inhoud["situaties"]["druk"], "")
        speak.say(tekst, audio_id=aid)
        # wacht 10s (gesimuleerd korter in droogloop)
        if DROOGLOOP:
            time.sleep(1.0)
        else:
            time.sleep(10.0)
        self._switch(State.KNOPMODUS)

    def handle_knopmodus(self) -> None:
        tekst, aid = self._random_tekst(self.inhoud["situaties"]["knop"], "Druk op de knop om te praten.")
        speak.say(tekst, audio_id=aid)
        # Luister met knop ingedrukt (in droogloop: zelfde input() loop)
        ev = hear.luister_spraak(prompt="[KNOPMODUS] ")
        if ev.type == "sleep" or ev.type == "weg":
            self._switch(State.LOSLATEN)
            return
        if ev.type in ("stilte",):
            # 30s rust → terug (gesimuleerd kort)
            self._switch(State.LUISTEREN)
            return
        # anders terug naar luistere pad
        self._laatste_antwoord = ev.tekst
        self._switch(State.REAGEREN)

    def handle_zacht(self) -> None:
        assert self.sessie
        # Bied aan te stoppen. Volgens bron 2 → AFSLUITING.
        tekst, aid = self._random_tekst(self.inhoud["situaties"]["pas"], "")
        # (bron 2 zegt zacht biedt afbouwen — we gebruiken 'pas' als korte warm zin
        #  tot Jolanda een specifieke 'zacht'-zin levert)
        if tekst:
            speak.say(tekst, audio_id=aid)
        self._switch(State.AFSLUITING)

    def handle_afsluiting(self) -> None:
        assert self.sessie
        tekst, aid = self._random_tekst(self.inhoud["afsluiting"], "Wil je de rekening?")
        speak.say(tekst, audio_id=aid)
        ev = hear.luister_spraak(prompt="[AFSLUITING] ")
        if ev.type == "sleep" or ev.type == "weg":
            self._switch(State.LOSLATEN)
            return

        # Mistral mag bepalen of het een ja of nee is
        r = self.brain_client.call(tekst, ev.tekst or "", context="AFSLUITING")
        if r["soort"] == "ja":
            self._switch(State.BON)
        else:
            # na_nee-zin
            nt, nid = self._random_tekst(self.inhoud["na_nee"], "Ook goed. Dag.")
            speak.say(nt, audio_id=nid)
            self._switch(State.LOSLATEN)

    def handle_bon(self) -> None:
        assert self.sessie
        img, quote = bon.maak_bon(
            inhoud=self.inhoud,
            halte_log=self.sessie.halte_log,
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
            # printer uit → geenprint-zin
            tekst, aid = self._random_tekst(self.inhoud["situaties"]["geenprint"], "")
            speak.say(tekst, audio_id=aid)

        # slotzin
        st, sid = self._random_tekst(self.inhoud["slotzinnen"], "Dag.")
        speak.say(st, audio_id=sid)
        self._switch(State.LOSLATEN)

    def handle_loslaten(self) -> None:
        # SLEEP_ACK alleen als sleep-triggered (optional; keep it simple)
        # Session wissen
        if self.sessie:
            log.info("[loslaten] gesprek %d — gewist", self.sessie.sessie_id)
        self.sessie = None
        self._switch(State.RUST)
