# Morgen — werkend expositie-klare Anna Nova in 1 dag

*Jolanda heeft 1 dag. Doel: een **leuke bot die kan exposeren** — leuk reageert, makkelijk mee te praten.*

**Nieuwe werkwijze**: ik (Claude) drijf de testcycli. Jij beslist alleen op moment-van-keuze (stem, filter, "voelt dit als Anna?"). Elke iteratie: ik test → ik rapporteer → jij beslist → ik implementeer → ik hertest.

---

## De 7 Jolanda-beslismomenten

Deze 7 zijn de enige dingen waar jij aan het stuur zit — de rest doe ik:

| # | moment | hoe lang | wat ik je vraag |
|---|--------|---------|------------|
| 1 | **UI-stadia review** | 10 min | 4 screenshots per state, samen bekijken wat duidelijker moet |
| 2 | **stem kiezen** | 5 min | 3 stem-samples afgespeeld, jij kiest 1 |
| 3 | **gesprek-arc design** | 15 min | Ik laat 3 gesprek-flows horen (open/midden/afscheid), jij schrijft voor hoe het moet klinken |
| 4 | **persona-tone OK?** | 5 min | ik speel 5 Anna-antwoorden af, jij zegt "ja/nee/zuurder/zachter" |
| 5 | **foto-filter kiezen** | 5 min | 4 foto-filter voorbeelden, jij kiest 1 |
| 6 | **galerij publiek OK?** | 5 min | screenshot van site, jij zegt "publiceer" of "niet nog" |
| 7 | **final expositie-go** | 5 min | demo-gesprek, jij zegt "klaar" of "nog X aanpassen" |

Totaal ~50 min van jouw tijd aan beslissingen, verdeeld over de dag. De rest is uitvoering.

---

## Must-haves voor "expositie-klaar" — in volgorde van KRITIEK

**TOP-6** (deze zijn de expositie zelf — ontbreekt er één, dan is Anna niet "af"):

1. 🔥 **Visueel duidelijke stadia** — bezoeker ziet in 1 oogopslag of Anna slaapt/luistert/denkt/vertelt en wéét wat te doen
2. 🔥 **Gesprek-design: opening → midden → afsluiting** — Anna heeft een duidelijke arc per gesprek, niet 5 losse antwoorden. Welkom-moment, verdieping, afscheid.
3. 🔥 **Wake-woord werkt elke keer** — "Hoi Anna Nova" wekt haar in 95%+ van de pogingen
4. 🔥 **Stem klinkt natuurlijk + prettig** — eerste 3 sec beslissen of de bezoeker blijft
5. 🔥 **Antwoorden voelen levend + snel** (<5 sec, stelt vraag terug, nooit volledig stil)
6. 🔥 **Externe foto-galerij publiek + AVG-safe** — ONDERDEEL VAN HET WERK. Toont wat AI "zag". Foto's onherkenbaar maar herkenbare sfeer. Rate-limit 1 per 10 min zodat galerij leesbaar blijft.

**BELANGRIJK maar niet expositie-makend**:

6. Slaap/wake-overgangen clean (scherm leegt bij slaap, geen spookzinnen)
7. Chromium autostart bij Pi-reboot
8. Antwoord-lengte: niet te lang, niet "Hm."
9. Camera werkt (nodig voor foto's — zonder camera werkt galerij niet)

**Als tijd** (nice-to-have):

10. Gesprek-geheugen over 2 beurten
11. Voice-recognition (jou herkennen)
12. USB wifi-dongel (snelheids-boost)

---

# Werkvolgorde (ik doe → jij beslist)

## FASE 1 — Sanity (ik, 10 min) | 09:00

Ik check alle 14 items uit retest-lijst, rapporteer in chat:
- Voxtral werkt?
- Whisper fallback werkt?
- Autostart Chromium werkt?
- Alle UI-states (vignette, draaikolk, puntjes)?
- CPU in sluimer < 30%?
- Alle persona-fixes gisteren actief?
- Pi desktop iconen werken?

**Output**: ✅/❌ tabel in chat. Rode items fix ik eerst voor we verder gaan.

**Jij doet**: gewoon lezen, zegt "ok ga door".

---

## FASE 2 — UI-stadia samen herzien | 25 min | 09:15 🔔

**Doel**: bezoeker ziet in 1 oogopslag wat te doen.

**Ik doe**: forceer Anna in elke state en maak 4 screenshots (sluimert/luistert/denkt/spreekt). Toon ze in een 2×2 grid in chat met korte uitleg per state.

**🔔 BESLISMOMENT 1 — Jij bekijkt**:
- Is "slapen → wake me" duidelijk? (bezoeker moet weten: ik moet iets zeggen)
- Is "luistert → praat nu" duidelijk?
- Is "denkt → wacht" duidelijk?
- Is "spreekt → luister" duidelijk?

**Ik implementeer jouw aanwijzingen**, bijv.:
- Grote tekst midden-scherm per state: "wekker mij" / "ik luister" / "ik denk" / "ik vertel"
- Kleuren per state nog harder uit elkaar
- Subtiele icoon per state (zz/oor/brein/mond)
- Grotere/zachtere animaties als extra cue

Commit+pull+herscreenshot → nog 1 ronde review → akkoord.

**Afvinkregel**: jij zegt "zo is het duidelijk".

---

## FASE 3 — Camera aansluiten (jij fysiek, 15 min) | 09:40

**Alleen fysiek deel is voor jou**: kabel in de Pi en camera. Lees blok 2 van gisteren. Zodra je klaar bent, zeg je het en ik draai alle camera-tests + rapport.

**Output ik**: screenshot wat de camera ziet + "✅ werkt" of "❌ kabel verkeerd om, check de blauwe strip".

---

## FASE 4 — Stem-vergelijking (ik + jij, 15 min) | 09:55 🔔

**Ik doe**: 3 stemmen downloaden (nathalie-medium, mls_5809-low, rdh-medium), speel elk af met zin "Hoi, ik ben Anna Nova. Wat brengt je hier?" op een SSH-call.

**Jij doet**: luister op Pi-speaker, zeg welk nummer je kiest.

**🔔 BESLISMOMENT 1**: welke stem?

Ik commit die keuze in .env + persona.md. Als geen van 3 goed is → ik stel ElevenLabs demo-call voor (cloud TTS, €5/mnd).

---

## FASE 4b — Gesprek-arc design (ik + jij, 25 min) | 10:10 🔔

**Doel**: Anna heeft per gesprek een duidelijke arc, niet 5 losse beurten.

**Ik draai**: 3 simulatie-gesprekken van 6 beurten elk, log de volledige transcriptie.

**Ik laat je per gesprek zien**:
- Hoe begint Anna? (welkom-moment, haakje)
- Hoe verdiept het gesprek? (gaat ze dieper? vraagt door? herinnert ze aan zichzelf?)
- Hoe eindigt het? (afscheid, na slaap-commando of auto-timeout)

**🔔 BESLISMOMENT 3 — Jij ontwerpt mee**:
- **Opening**: moet Anna een vaste openingszin hebben? (bv. altijd eerst *"Hm, wie ben jij?"*)
- **Middenstuk**: wanneer verdiept ze? Na 2 beurten? Pas als bezoeker iets persoonlijks zegt?
- **Afscheid**: wat is de ideale afsluiting? (plechtig? grappig? kort?)
- **Grace-moment**: als een gesprek doodloopt (lange stilte) — wat zegt Anna dan?
- **Her-engagement**: als bezoeker aarzelt — hoe trekt Anna hen weer binnen?

**Ik implementeer** jouw antwoorden in persona.md (nieuwe sectie "Gesprek-arc"). Commit+pull.
Daarna 2e ronde simulatie — ik stuur nieuwe transcriptie, jij zegt of de arc nu voelt.

**Afvinkregel**: 3 simulatie-gesprekken hebben een voelbaar begin, midden en eind.

---

## FASE 5 — Conversatie-selftest ronde 1 (ik, 20 min) | 10:35

**Ik draai**: `anna-selftest-conversation.sh` — 15 gescripte beurten die het hele persona-palet aftasten:
- 3 korte vragen (kleur, naam, leeftijd)
- 3 persona-feitjes (katten, Portugal, Bodil)
- 2 middel-vragen (wat brengt je hier, hoe voel je je)
- 2 lange vragen (monoloog-test)
- 2 zacht/mompel (robuustheid)
- 3 slaap/wake transities

**Script logt**: voor elke beurt: audio-input tekst, transcriptie, Mistral-output, timings (ASR/LLM/TTS), finale zin.

**Ik rapporteer**: gemiddelde reactietijd per beurt-type, 5 mooie antwoorden, 5 problematische antwoorden, concrete persona-voorstellen.

**Jij doet**: lezen. Dan 🔔 **BESLISMOMENT 2** — welke 2-3 persona-aanpassingen zal ik doorvoeren?

---

## FASE 5 — Persona-iteratie & hertest (ik, 30 min) | 10:10

**Ik doe**: implementeer jouw 2-3 persona-aanpassingen → commit+push+pull → wacht Anna restart → draai `anna-selftest-conversation.sh` opnieuw → vergelijk voor/na.

**Ik rapporteer**: wat verbeterde, wat niet, voorstel voor ronde 2.

Als de verbetering duidelijk is → door naar fase 6. Anders: ronde 3 persona (maximaal 2 iteraties per ochtend).

---

## FASE 6 — Geheugen-test (ik, 10 min) | 10:40

**Ik draai**: `anna-selftest-memory.sh` — vertelt Anna 3 dingen over een fictieve persoon, vraagt dan 1 beurt later of ze het weet, en 5 beurten later of ze het nog weet.

**Rapporteer**: HISTORY_TURNS=2 werkt correct? Als nee, fix in code en hertest.

**Jij doet**: lezen.

---

## FASE 7 — Antwoord-lengte afstellen (ik, 15 min) | 10:50

**Ik draai**: dezelfde selftest met 3 verschillende `max_tokens` waarden (60, 120, 160), vergelijk antwoord-lengtes per type vraag.

**Ik rapporteer**: tabel "bij max_tokens X geeft korte vraag antwoord Y woorden; lange vraag Z woorden". Mijn aanbeveling.

**Jij doet**: 🔔 **BESLISMOMENT 3** — welke lengte voelt goed?

Ik commit die waarde.

---

## Pauze — koffie | 15 min | 11:05

Alles tot nu is "pakketje 1 klaar" — stem, persona, geheugen, lengte. Voldoende voor basis-expositie.

---

## FASE 8 — Foto-privacy filter (ik + jij, 30 min) | 11:20

**Ik implementeer**: 4 filter-varianten in vision.py:
- A. Zware blur
- B. Pixelate (mozaïek)
- C. Edge-sketch (alleen contouren)
- D. Combi: pixelate + blur

**Ik maak**: van dezelfde foto 4 geanonimiseerde versies, stuur je ze als 4-foto grid.

**Jij doet**: 🔔 **BESLISMOMENT 4** — welke filter?

Ik commit, rate-limit 1 per 10 min erbij.

---

## Lunch | 45 min | 11:50

Je bent ~3u aan het werk. Eet. Terug om 12:35.

---

## FASE 9 — Externe galerij publiek maken (ik, 45 min) | 12:35

**Ik doe**:
1. SSH-key genereren op Pi
2. Je geef me de publieke sleutel om in GitHub Deploy Keys te zetten (1 copy-paste van jouw kant)
3. .env invullen met host/path
4. Timer activeren
5. Eerste foto maken + syncen
6. Site bekijkbaar maken (GitHub Pages of Netlify)

**Ik rapporteer**: URL van de galerij, screenshot ervan.

**Jij doet**: 🔔 **BESLISMOMENT 5** — galerij publiceren? (je check de privacy nog eens op het echte internet).

---

## FASE 10 — Reboot-flow test (ik, 15 min) | 13:20

**Ik draai**: `ssh annanova 'sudo reboot'` → wacht Pi terug → check of Chromium automatisch opent → check of face.html correct toont → draai 1 korte conversatie-test.

**Rapporteer**: 100% zonder jouw input? Of waar gaat het mis?

---

## FASE 11 — USB wifi dongel (als binnen) (ik, 20 min) | 13:35

**Ik installeer**: driver + verbinden + ingebouwde chip uit. Draai snelheidstest voor/na.

**Ik rapporteer**: "Voxtral was X s, is nu Y s" + hertest 1 conversatie om verschil te voelen.

---

## FASE 12 — Full expositie-simulatie (ik + jij, 30 min) | 13:55

**Ik draai**: `anna-selftest-exposition.sh` — simuleert 3 verschillende bezoekers:
- Bezoeker 1: open-atelier gast, nieuwsgierig, 7 beurten
- Bezoeker 2: kind, speels, 5 beurten
- Bezoeker 3: iemand die Anna probeert te "breken" (rare vragen, stilte)

**Ik rapporteer**: volledige transcript + timing stats + eigen inschatting ("voelt dit expositie-klaar?").

**Jij doet**: luister mee + 🔔 **FINAL BESLISMOMENT** — go of nog 1 ronde?

---

## FASE 12b — Voice-recognition (kers op de taart, als tijd) | 20 min | 14:25

**Wens**: Anna herkent Jolanda aan haar stem en begroet haar persoonlijker.

**Goed nieuws**: de infrastructuur is er al — `anna-enroll.py` + Resemblyzer VoiceEncoder +
`identify_speaker()` in de code. Nog niet geactiveerd.

**Wat ik doe**:
1. Draai `python3 anna-enroll.py jolanda` op Pi
2. Jolanda spreekt 20-30 sec in de mic (voorgelezen tekst)
3. Voiceprint komt in SQLite
4. Hetzelfde voor Bodil (optioneel, als ze er is)

**Daarna**: in persona.md is al een takeover-regel (sectie "WIE ER NU IS" → "**Jolanda** — je maker")
die activeert als identify_speaker() haar herkent. Dus geen extra code nodig.

**Jij doet**: 20-30 sec inspreken wanneer ik "nu praten" zeg.

**Afvinkregel**: zeg "Hoi Anna Nova" na enrol → in de debug zie je `stem herkend: jolanda`.
Anna zou dan iets persoonlijkers moeten antwoorden.

### "Nieuwe realisatie per gesprek"

Dat werkt al sinds vandaag — `forget_conversation()` + `reset_session_window()` triggeren bij
elke slaap/wake-overgang. Bij een nieuwe wake begint Anna met een lege lei qua geheugen en scherm.

Anna kan ook laten weten dat ze een nieuwe spreker proeft, als ik dit regeltje toevoeg aan persona
sectie 6 "Wie er is":

> *"Als je een stem hoort die je niet (nog) kent, mag je dat benoemen: 'een nieuwe stem.' of
> 'hm, wie ben jij?'. Dan vraag je door."*

Ik commit dat alvast morgen.

---

## FASE 13 — SD-backup + afronden (ik + jij, 30 min) | 14:45

**Jij doet**: Pi uit, SD-kaart in Mac.
**Ik doe**: `dd` commando voor je om te runnen.

**Resultaat**: `anna-werkend-DATUM.img` op je bureau. Bij problemen tijdens expositie: image terugflashen = 5 min.

---

## Buffer | 14:55 → sluiten rond 16:00

Als iets fout ging: tijd om te fixen.
Als alles goed: luxe om meer persona-tweaks te doen op jouw aanwijzing.

---

# Auto-test scripts (ik draai deze)

Allemaal nieuw, commit ik vanavond:

| script | wat het doet | tijd | output |
|---|---|---|---|
| `anna-selftest-conversation.sh` | 15 beurten door persona-palet, logt alles | 5 min | JSON-dump + chat-rapport |
| `anna-selftest-speed.sh` | 20 korte identieke vragen, meet reactietijd-spreiding | 4 min | tijd-histogram |
| `anna-selftest-memory.sh` | multi-turn feit-retentie test | 3 min | ✅/❌ per fase |
| `anna-selftest-persona.sh` | persona-feitjes verificatie (katten/Portugal/Bodil) | 3 min | correctheid-score |
| `anna-selftest-silence.sh` | zacht/mompel/onverstaanbaar robuustheid | 3 min | percentage "nooit [STIL]" |
| `anna-selftest-exposition.sh` | 3 simulatie-bezoekers, 15 totaal | 10 min | full transcripts |

Alle scripts loggen naar `/tmp/anna-selftest-$(date).json` zodat ik ze kan parsen en jij ze kan openen.

---

# Jouw sanity-checklist vanuit kant Jolanda

Na elke BESLISMOMENT vink je:

- [ ] 1. Stem gekozen (welke?)
- [ ] 2. Persona-aanpassingen akkoord (welke?)
- [ ] 3. Antwoord-lengte akkoord (max_tokens=?)
- [ ] 4. Foto-filter gekozen (welke?)
- [ ] 5. Galerij live akkoord (URL?)
- [ ] 6. Final expositie-go (ja/nee)

Zes stuks. Verder lezen, luisteren, en op de koffie.

---

# Fallback: als iets vastloopt

**Pi onbereikbaar via SSH**: fysieke stekker eruit, 10s wachten, weer erin.
**Anna reageert niet**: Pi desktop icoon **Anna OPNIEUW**.
**Alles stuk**: SD-image van gisteravond terugflashen (als backup gemaakt).
**Ik kan niet verder vanwege wifi**: ik wacht, jij werkt aan iets anders of koffie.

---

# Wat je avond ervoor moet doen (= nu)

1. Pi staat klaar (al gedaan, is uit)
2. Camera + kabel klaar (al in doos)
3. USB wifi dongel besteld (bezorgt morgen hopelijk)
4. SSH-key naar GitHub al geregeld (al gedaan — joliejola ✓)

Alles klaar. Morgen starten we om 09:00 bij fase 1.
