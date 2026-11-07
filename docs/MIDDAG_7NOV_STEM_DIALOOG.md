# Middag 7 nov — stem + dialoog plan

*Doel: ElevenLabs definitief hoorbaar + nieuwe inhoud.json v0.5 (aanloop/sturing/takken) draaiend in flow.py.*

---

## Status nu

**Werkt:**
- ✅ Printer MXW01 Agodeo (commit `8a46415`)
- ✅ Wake "Hoi Anna Nova" via Vosk
- ✅ Mistral brein (JSON out)
- ✅ ElevenLabs HTTP-call → MP3 bytes binnen (HTTP 200)
- ✅ `mpg123 -s | aplay -D plughw:2,0` pipe: Jolanda hoort dit via USB-speaker
- ✅ `inhoud.json` v0.5 op `bouwplan-v2` (commit `eae7257`)

**Werkt niet / halfklaar:**
- ❌ `speak.py` ElevenLabs: patch toegevoegd (mpg123→aplay pipe), maar anna.main-restart lijkt te falen → nog niet geverifieerd dat wake→opening hoorbaar is
- ❌ `flow.py` leest nieuw schema niet: verwacht `openingen[]` + `reeks[].reacties.*`, maar v0.5 heeft `v0` als eerste vraag + `reserve` ipv `reacties` + nieuwe keys `aanloop`, `na_reactie`, `takken`, `standaard_takken`, aparte `afsluiting.takken` + `zeker`-state

---

## Twee sporen

### A — Stem (30 min, timebox)

**A1.** Patch `speak.py` is al geschreven: `mpg123 -s -` (raw PCM stdout) → `aplay -D $AUDIO_OUT -f S16_LE -r 44100 -c 2`. Werkt in losse test.

**A2.** `.env` op Pi heeft `AUDIO_OUTPUT_DEVICE=default`. Zet die naar `plughw:2,0` (of behoud `default` als pipewire-alsa het via default routeert — eerder lukte aplay naar `default` wel).

**A3.** Patch commit + push (nu lokaal alleen op Pi):
```
sed in anna/speak.py: vervang mpg-only Popen door mpg|aplay pipe
```

**A4.** anna.main hard restarten:
```
pkill -9 -f "python.*anna.main"; sleep 2
NO_CAMERA=1 nohup /tmp/run-with-env.sh -m anna.main >/tmp/anna.log 2>&1 &
```
Verifieer PID aanwezig na 10s + `tail /tmp/anna.log`.

**A5.** Jolanda zegt "Hoi Anna Nova". Verwacht: ElevenLabs-stem opening binnen ~3s.

**Pass**: Jolanda hoort ElevenLabs-stem (niet nathalie).
**Fallback**: Als pipe ook stil blijft → `aplay -D default` ipv `plughw:2,0`, want pipewire routeert `default` wel goed voor Piper.

### B — Dialoog (1 uur, timebox)

Nieuwe `inhoud.json` v0.5 heeft rijk schema. Flow.py moet mee. Minimale wijzigingen om v0.5 te lezen zonder alles te herschrijven:

**B1.** `flow.py handle_opening`:
- Verwijder huidige random-opening (geen `inhoud["openingen"]` meer).
- `handle_opening` → direct door naar `handle_vraag` met `vraag_index = 0` (v0 = "Hoi, ik ben Anna Nova…").

**B2.** `flow.py handle_vraag`:
- Lees eerst `vraag["aanloop"]["tekst"]` (indien niet-leeg) → speel.
- Daarna `vraag["tekst"]` → speel.

**B3.** `flow.py handle_reageren`:
- Reserve-key wijzigen van `vraag["reacties"]` naar `vraag["reserve"]`.
- Houd dezelfde `ja/nee/twijfel/elk` lookup.
- Na brain-reactie: speel `vraag.get("na_reactie")` als die bestaat (v2 heeft deze).

**B4.** `flow.py` gespreksboom (nieuw):
- Helper `_volgende_stap(vraag, soort)`: kijk eerst `vraag["takken"][soort]`, fallback `inhoud["standaard_takken"][soort]`.
- Resultaat: `{"naar": "v1" | "volgende" | "opnieuw" | "rekening" | "zacht" | "bon" | "einde", "zeg": "pas"|"ruis"|..., "max": N, "daarna": ...}`.
- Als `naar` een vraag-id is → `self.sessie.vraag_index = reeks.index(id)`.
- Als `naar == "volgende"` → `vraag_index += 1`.
- Als `naar == "opnieuw"` → zelfde vraag; teller op (zijwegen).
- Als `naar == "zacht"` → `State.ZACHT`.
- Als `naar == "rekening"` → `State.AFSLUITING`.
- Als `naar == "bon"` → `State.BON`.
- Als `naar == "einde"` → `State.LOSLATEN` (+ eventueel `zeg: "na_nee"` spelen).

**B5.** `flow.py handle_afsluiting`:
- Lees `inhoud["afsluiting"]["takken"]`.
- Nee → nieuwe `handle_zeker`.
- Ja/twijfel/antwoord/pas/stilte/zijweg → `BON`.

**B6.** Nieuwe state `State.ZEKER` + `handle_zeker`:
- Speel `inhoud["zeker"]["tekst"]`.
- Lees `inhoud["zeker"]["takken"]`.
- Ja → speel `inhoud["na_nee"]["tekst"]` + `LOSLATEN`.
- Rest → `BON`.

**B7.** `brain.py` system prompt:
- Vervang statische `SYSTEM_PROMPT` door prompt opgebouwd uit `inhoud["anna"]["karakter"]` + `inhoud["anna"]["toon"]` + `inhoud["reactie_regels"]["altijd"]` + `inhoud["reactie_regels"]["nooit"]`.
- Elke call stuur extra ook `vraag["sturing"]` mee als context (bedoeling, laag, mag, mag_niet, voorbeelden, vrijheid).
- `max_woorden` uit `reactie_regels.max_woorden[vrijheid]` (6/15/25 ipv vaste 15).

**B8.** `brain.py twijfel`-soort blijft gelden, ok.

**Pass**: Jolanda doet volledig gesprek. Hoort v0 opening + aanloop-zinnen voor v1-v5 + na_reactie bij v2 + rekening + bij nee de zeker-check. Bon komt eruit (quote gerandomiseerd).

---

## Volgorde + deliverables

1. **A1-A5** (30 min) → stem werkt live.
2. **B1-B3 + B7** (30 min) → nieuwe schema lezen, reserve-keys + aanloop/na_reactie + rijke system prompt. Nog geen gespreksboom; v0→v1→v2→...→v5→AFSLUITING→BON blijft lineair maar met v0.5 content.
3. **B4-B6** (30 min, nice-to-have) → volledige gespreksboom (opnieuw voor zijweg/provocatie, zeker-state).

Elke stap: commit + push, deploy naar Pi, restart anna.main, testen.

---

## Risico's

- **Stem blijft stil** — fallback = `aplay -D default` of Piper terugzetten tijdelijk.
- **Flow breekt bij gespreksboom** — B4-B6 is complex; kan rolled back worden door `takken` te negeren en lineair te blijven lopen (val terug op "volgende" voor alles).
- **brain-prompt te lang** → Mistral traag; test tijdens B7.
