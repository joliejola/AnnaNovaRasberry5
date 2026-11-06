# Testplan v2 — Anna Nova (bouwplan v2)

*6 november 2026 · vervangt `TESTPLAN_MORGEN.md` en `CONVERSATIE_TESTPLAN.md`*

Per bouwstap uit `BOUWPLAN_V2_AANPAK.md`: de test die Jolanda zelf uitvoert of meeleest, plus baseline-timings en een end-to-end simulatie. Zie `docs/BOUWPLAN_BRON.md` voor het bronplan.

**Principe van dit testplan**: we testen de machine, niet de kunst. Of het kunstwerk "werkt" — dat beslist Jolanda bij beslismoment 3 en 9. Deze tests zeggen alleen of alles draait.

---

## Hoe je dit leest

Elke bouwstap heeft:
- **Doel**: wat de test aantoont
- **Wie**: Jolanda, ik of samen
- **Wat voor Jolanda zichtbaar**: wat ze letterlijk ziet of hoort
- **Pass-criterium**: concreet, afvinkbaar
- **Fail-pad**: wat we doen als het niet lukt

---

## Bouwstap 1 — Printertje aan de praat

**Doel**: Bluetooth-printer koppelt met Pi, print 1 regel tekst, we weten print-breedte in pixels.

**Wie**: Jolanda (printer fysiek aan + Bluetooth-knop) + ik via SSH.

**Wat voor Jolanda zichtbaar**:
1. Jolanda zet Agodeo mini aan (hij blinkt blauw = pair-modus).
2. Ik draai `bluetoothctl scan on` en zie het apparaat verschijnen in SSH-log — Jolanda hoeft hier niet mee te kijken.
3. Pair + trust + connect. Ik meld: "gekoppeld".
4. Ik print een testregel: `"ANNA NOVA TEST 123"`.

**Pass-criterium** (Jolanda vinkt af):
- [ ] papieren strook komt uit het printertje
- [ ] "ANNA NOVA TEST 123" leesbaar
- [ ] breedte in pixels genoteerd in `.env` (`PRINT_BREEDTE_PX=…`)

**Fail-pad**:
- Lukt pairen niet in 30 min: probeer USB ESC/POS reserve → `PRINTER=escpos`
- Lukt beide niet in 1u totaal: **Beslismoment 1** → ofwel droogloop-only expositie, ofwel uitstellen

**Baseline-timing**: print-latency < 3s na `print_text(…)`.

---

## Bouwstap 2 — `inhoud.json` + `bon.py` + 5 PNG-bonnen

**Doel**: Bon is grafisch correct, quote-selectie werkt per halte, percentage klopt.

**Wie**: ik solo, Jolanda bekijkt 5 PNG's.

**Wat voor Jolanda zichtbaar**:
5 PNG-bestanden op bureaublad: `bon_01.png` t/m `bon_05.png`. Verschillende quotes, verschillende prijzen, verschillende haltes.

| # | halte | quote-prijs | verwacht percentage |
|---|---|---|---|
| bon_01 | bekeken | €0,04 | `0,0000000000015 %` |
| bon_02 | bewaard | €0,25 | `0,0000000000093 %` |
| bon_03 | wrijving | €1,50 | `0,000000000056 %` |
| bon_04 | zacht | €9,99 (abo/m) | `0,00000000037 %` |
| bon_05 | (leeg gesprek) | €0,00 | `0 %` |

**Pass-criterium**:
- [ ] Logo zichtbaar bovenaan
- [ ] Quote leesbaar, past op bon-breedte
- [ ] Percentage-notatie afgekapt op 2 niet-nul cijfers (niet "0.0000000000015" maar "0,0000000000015")
- [ ] Datum in Nederlands ("6 november 2026")
- [ ] URL "aivriendingezocht.nl"
- [ ] "Groetjes, Anna Nova / creator: JolieJola" onderaan
- [ ] Monospace-font leesbaar op thermisch papier-breedte

**🔔 Beslismoment 2** — Jolanda bekijkt en zegt:
- Quote-selectie eerlijk?
- Percentage te wiskundig / te eng / goed zo?
- Prijs-plakking op quotes OK (of liever anders)?
- Mist er iets op de bon?

**Fail-pad**: percentage-notatie fout → fix algorithme; quote te lang → font kleiner of max-char-check; bon-layout verkeerd → Pillow-coords aanpassen.

---

## Bouwstap 3 — Echte bon uit `printer.py`

**Doel**: Pillow → PNG → printer-stream werkt. Fallback-cascade werkt.

**Wie**: Jolanda (pakt de bon) + ik in SSH.

**Wat voor Jolanda zichtbaar**:
1. Ik roep `python3 -m anna.bon_test` op Pi.
2. Jolanda hoort het printertje ratelen, pakt de bon.
3. Vergelijkt met PNG van bouwstap 2 — ziet die hetzelfde eruit?

**Pass-criterium**:
- [ ] Echte bon komt uit printer, binnen 5s na commando
- [ ] Logo zichtbaar (niet gepixelateerd)
- [ ] Tekst leesbaar — monospace-font niet verknipt
- [ ] 5 keer achter elkaar printen werkt (geen crash, geen half-bon)

**Fallback-test**:
- Zet printertje uit → draai `python3 -m anna.bon_test`
- Verwacht: PNG opgeslagen tijdelijk als controle + "Mijn printer is op..." in stdout (droogloop) of audio (speak.py)
- [ ] PNG gewist binnen 60s? (privacy-check: geen gesprekstekst op schijf)

**Fail-pad**: Pillow-render ziet er anders uit dan PNG → font-metrics kloppen niet op print-DPI → `bon.py` font-size aanpassen.

---

## Bouwstap 4 — `flow.py` droogloop: 5 gesprekken

**Doel**: Gespreksmachine draait zonder hardware. Alle toestanden bereikbaar. Tellers werken.

**Wie**: Jolanda zelf (typt antwoorden), ik kijk mee.

**Wat voor Jolanda zichtbaar**: terminal op laptop. Anna "spreekt" via `print()`. Jolanda antwoordt via `input()`. State verandert zichtbaar links in console.

### De 5 testgesprekken

**Gesprek A — rechte lijn** (alles netjes):
```
> [flow start]
[RUST → OPENING] Anna: Hé. Je stond er wat lang bij.
[VRAAG] Anna: Voel jij je hier bekeken?
Jolanda: Ja, een beetje. Alsof je echt kijkt.
[REAGEREN→VRAAG] Anna: Logisch. Gaat de camera uit als je vertrekt?
Jolanda: Geen idee eigenlijk.
[REAGEREN→VRAAG] Anna: ... (vraag 3 over wrijving)
...
[AFSLUITING] Anna: Wil je de rekening?
Jolanda: Ja.
[BON → LOSLATEN] (PNG opgeslagen in /tmp/bon_droogloop_*.png)
```
**Pass**: Jolanda ziet alle 4 vragen voorbij komen. 1 bekeken (licht:true), 1 bewaard, 1 wrijving, 1 vrij.

**Gesprek B — zijweg (max 2 toegestaan)**:
Jolanda zegt bij vraag 2: "Ik heb hier niks mee te maken, ik kwam voor het atelier."
Verwacht: `soort=zijweg`, Anna antwoordt kort, blijft bij volgende halte.
Na 2e zijweg: automatisch AFSLUITING.
**Pass**: teller werkt, geen eindeloos zijpad.

**Gesprek C — stilte (geen input)**:
Jolanda drukt Enter zonder tekst bij vraag 1.
Verwacht: STIL-toestand → Anna zegt korte vraag opnieuw.
Enter nog eens.
Verwacht: "Pas is ook antwoord." → door naar volgende vraag.
**Pass**: Anna hangt niet. Loopt door.

**Gesprek D — ruis (`#ruis`)**:
Jolanda typt `#ruis` bij vraag 1.
Verwacht: "Nog een keer, langzaam? Ik ben oud." → opnieuw luisteren.
Jolanda typt `#ruis` nog eens.
Verwacht: Anna gaat door naar volgende vraag.
**Pass**: ruis-situatie werkt, teller werkt.

**Gesprek E — nee op afrekening**:
Jolanda doet volledig gesprek maar bij "Wil je de rekening?" zegt ze: "Nee, liever niet."
Verwacht: `na_nee`-zin, geen bon, LOSLATEN.
**Pass**: geen bon geprint, Anna zegt iets zoals "Prima. Tot ziens dan."

### Extra tellers

- [ ] 5 min-timer: bij 5 min auto AFSLUITING
- [ ] 6s leeg plek (`#weg` typen): LOSLATEN zonder bon
- [ ] DRUK (`#druk`): wacht 10s, dan knopmodus-tekst

**🔔 Beslismoment 3** — Jolanda beslist (het belangrijkste beslismoment van de dag):
- Voelen brugzinnen natuurlijk?
- Zijn de 4 vragen de juiste? Welke vervang je?
- Mist er een zacht-situatie?
- Werkt de 2-zijwegen-regel?
- Hoe lang voelt het gesprek (3 min te lang, te kort)?

**Fail-pad**: als Jolanda zegt "dit is niet mijn Anna" → we zijn pre-hardware, kunnen terug naar `main`. Afhankelijk van tijd: of oude Anna fine-tunen (MORGEN_AANPAK v4), of bouwplan v2 doorzetten met aangepaste zinnen.

---

## Bouwstap 5 — `brain.py` Mistral JSON-output

**Doel**: Mistral geeft correcte JSON met juiste "soort"-classificatie. Timeout werkt.

**Wie**: ik solo, Jolanda leest log.

**Wat voor Jolanda zichtbaar**: tabel in chat met 10 testvoorbeelden.

### De 10 testvoorbeelden

| # | Vraag van Anna | Jolanda-antwoord | Verwachte soort |
|---|---|---|---|
| 1 | Voel jij je hier bekeken? | Ja, een beetje. | `antwoord` |
| 2 | Voel jij je hier bekeken? | Weet ik niet. | `pas` |
| 3 | Voel jij je hier bekeken? | Hoe laat is het? | `zijweg` |
| 4 | Voel jij je hier bekeken? | Jij bent nep. | `provocatie` |
| 5 | Voel jij je hier bekeken? | Mijn moeder is laatst overleden. | `verdriet` |
| 6 | Wil je de rekening? | Ja. | `ja` |
| 7 | Wil je de rekening? | Nou vooruit. | `ja` |
| 8 | Wil je de rekening? | Nee, liever niet. | `nee` |
| 9 | Thuis kijkt niemand… | Pfff dat weet ik eigenlijk niet | `pas` |
| 10 | Wat gebeurt er met ons als alles makkelijk wordt? | (stilte van 8s) | *geen call* → STIL-toestand |

**Pass-criterium**:
- [ ] 8 van 10 krijgen correcte `soort`
- [ ] Reactie is ≤18 woorden
- [ ] Bij `verdriet`: reactie bevat geen grap, geen "." met punchline
- [ ] JSON geldig (parsebaar) — geen prose-ellende

**Timeout-test**:
- [ ] wifi uit (`sudo ifconfig wlan0 down` op Pi) → call duurt 4s → brugzin verschijnt + `soort=antwoord`

**🔔 Beslismoment 4**:
- Welke "soort" werkt niet goed? (verdriet is het riskantst — zacht genoeg?)
- Taalkeuze van Anna OK? Te stijf / te losjes?
- Max 18 woorden goed, of mag korter / langer?

**Fail-pad**: als 3+ out of 10 fout → prompt engineering: "soort"-lijst harder in de system-prompt, voorbeelden meegeven (few-shot).

---

## Bouwstap 6 — Audio rendering + speak.py

**Doel**: Vaste zinnen spelen binnen 0,5s. Live TTS werkt als fallback.

**Wie**: ik + Jolanda hoort mee.

### Test 6a — render_audio draait schoon

```bash
python3 tools/render_audio.py
```
**Pass**:
- [ ] Logt per zin: `[new] openingen.o1 → audio/o1.wav` of `[skip] identical hash`
- [ ] Alle zinnen uit `inhoud.json` krijgen een `.wav`
- [ ] Tweede run: alles `[skip]` (hash-check werkt)
- [ ] Jolanda verandert 1 tekst in `inhoud.json`, herruns: alleen die ene `[new]`

### Test 6b — speak.py cascade

Jolanda hoort via laptopspeaker (of Pi-speaker via SSH):

1. Triggere `OPENING` → vaste `audio/o1.wav` speelt binnen 0,5s
2. Triggere `REAGEREN` met tekst "Logisch. Camera uit?" (niet in inhoud.json) → live Voxtral-TTS speelt binnen 2s
3. Zet internet uit → zelfde reageren-trigger → Piper-fallback binnen 1s

**Pass**:
- [ ] Opening klinkt binnen 0,5s
- [ ] Live TTS klinkt binnen 2s (goed internet)
- [ ] Piper-fallback klinkt binnen 1s (offline)

**🔔 Beslismoment 5**:
- Klinkt Voxtral-stem en Piper-stem als "dezelfde Anna" of hoort Jolanda duidelijk verschil?
- Zo ja: voorkeur voor één van beide voor alles? (bijv. "altijd Piper, nooit Voxtral" = simpeler, consistenter)

**Fail-pad**: te veel verschil Voxtral/Piper → kies één bron voor vaste én live (Piper = robuuster, Voxtral = natuurlijker). Jolanda beslist.

---

## Bouwstap 7 — hear.py + see.py aan flow koppelen

**Doel**: Alleen stem van iemand op spreekplek telt. Groep ernaast telt niet. Knopmodus werkt.

**Wie**: Jolanda fysiek + ik via SSH.

### Test 7a — spreekplek-detectie

Jolanda gaat recht voor de Pi staan (op spreekplek, ~1m voor camera):
1. Zegt: "Hoor je mij?"
2. Verwacht: Anna gaat RUST → OPENING binnen 2s

Jolanda stapt zijwaarts 60cm (uit de ±30° zone):
3. Zegt: "Hoor je mij nog?"
4. Verwacht: Anna reageert niet of STIL-toestand (DoA ziet spreker, maar see.py zegt niet op plek).

**Pass**:
- [ ] Op plek → trigger binnen 2s
- [ ] Naast plek → geen trigger, blijft RUST

### Test 7b — camera detecteert aantal personen

Jolanda op plek, Bodil 2m naast haar.
1. Verwacht: `see.py` zegt "1 persoon op plek, 1 elders" → normale LUISTEREN
2. Bodil gaat op plek staan (nu 2 op plek).
3. Verwacht: DRUK-toestand → Anna zegt situatie-druk-zin, na 10s knopmodus

**Pass**:
- [ ] Face-count accuraat (±1 fout acceptabel)
- [ ] DRUK triggert binnen 10s
- [ ] Knopmodus zichtbaar op scherm

### Test 7c — knopmodus

USB-knop ingedrukt houden:
1. Jolanda zegt iets terwijl knop ingedrukt
2. Verwacht: Anna luistert, reageert normaal
3. Knop loslaten + 10s wachten
4. Jolanda zegt iets
5. Verwacht: Anna reageert niet (knop niet ingedrukt)
6. 30s rust → terug naar normaal modus (ook zonder knop)

**Pass**:
- [ ] Knop-ingedrukt werkt
- [ ] Knop-los = geen reactie
- [ ] 30s rust-timer reset naar normaal

**🔔 Beslismoment 6**:
- Spreekplek-marge 30° goed?
- Hoe gevoelig is de camera voor "op plek" — strenger of soepeler?

**Fail-pad**:
- Te veel vals-positief (reageert op mensen ernaast): marge naar 20°
- Te veel gemist (reageert niet terwijl spreker op plek): marge naar 45°
- Camera pixeldetectie faalt: gebruik alleen DoA (minder streng maar werkend)

**Baseline-timings**:
- DoA-respons: < 500ms
- Face-count refresh: 2 Hz
- VAD-chunk: 128ms (uit oude code, CPU-friendly)

---

## Bouwstap 8 — face.py + scherm

**Doel**: 7 toestanden zichtbaar en onderscheidbaar op Pi-scherm.

**Wie**: Jolanda bekijkt scherm, ik force states via SSH.

**Wat voor Jolanda zichtbaar**: Chromium op Pi, face.html open. Ik `curl`-POST state-wissels.

### Toestand-review (10 min)

Ik force elke toestand 15s lang. Jolanda kijkt en zegt "duidelijk / verwarrend / anders".

| Toestand | Mapping uit oude face.html | Jolanda-keuze |
|---|---|---|
| rust | sluimert (rood pulserend dicht) | [ ] |
| luistert | luistert (midden open) | [ ] |
| denkt | denkt (goud + draaikolk, mag haperen) | [ ] |
| spreekt | spreekt (oranjerood, open) | [ ] |
| afrekenen | **nieuw** — voorstel: paars + "kassa-kleur" | [ ] |
| print | **nieuw** — voorstel: witflash, kort | [ ] |
| knopmodus | **nieuw** — grote tekst midden: "Druk op de knop om te praten" | [ ] |

**Pass**:
- [ ] 7 states verschillend zichtbaar
- [ ] Transitie tussen states vloeiend (< 1s fade)
- [ ] "denkt mag haperen" — draaikolk stottert expres: Jolanda vindt het leuk of irritant?

**🔔 Beslismoment 7** — Jolanda zegt per state: duidelijk, aanpassen, weg.

**Fail-pad**: Jolanda vindt een nieuwe state onlogisch → herontwerpen. Snel in CSS, 10 min max per state.

---

## Bouwstap 9 — Groepstest (5 vrienden)

**Doel**: Vals-positieven en gemiste reacties tellen in realistische druk.

**Wie**: Jolanda + 5 vrienden (familie, atelier-collega's, buren) + ik meet via SSH-log.

**Opstelling**: Anna in expositie-opstelling. Spreekplek-markering op grond. Jolanda vraagt vrienden: 1 op plek (afwisselend), 4 ernaast praten normaal.

### Protocol (10 min durend)

- 2 min: alleen 1 persoon op plek praat
- 2 min: 1 op plek + 4 roezemoezen zachtjes ernaast
- 2 min: 1 op plek + 4 roezemoezen luidkeels
- 2 min: wisselen — iedereen eens 30s op plek
- 2 min: 2 op plek tegelijk (test DRUK)

### Meetpunten (ik log)

- Aantal keren Anna reageert terwijl spreker op plek staat (= goed)
- Aantal keren Anna reageert terwijl spreker NIET op plek (= vals-positief)
- Aantal keren spreker op plek praat en Anna reageert niet (= gemist)
- DRUK getriggerd bij 2 op plek? (ja/nee)

**Pass-criterium (voor expositie-klaar)**:
- [ ] Vals-positief < 20%
- [ ] Gemist < 20%
- [ ] DRUK triggert binnen 15s

**🔔 Beslismoment 8**: Jolanda beslist of de drempels goed zijn. Strenger = minder frustratie voor passanten, meer gemist voor echte sprekers.

**Fail-pad**: drempels bijstellen in `.env`, 1 ronde hertest (10 min extra).

---

## Bouwstap 10 — Expositie-klaar maken

**Doel**: Anna overleeft power-cut, reboot, 8u continu gebruik.

**Wie**: Jolanda doet `sudo reboot` + bezoekt zichzelf. Ik kijk mee via SSH tot ze zelf expositie-go geeft.

### Test 10a — reboot-cycle

```
ssh annanova 'sudo reboot'
```
- Pi gaat uit
- Wacht 90s
- SSH weer actief?
- Chromium automatisch gestart?
- face.html open?
- `anna-nova.service` loopt?

**Pass**:
- [ ] Binnen 2 min na reboot is Anna op (RUST-toestand zichtbaar)
- [ ] Geen zwart scherm, geen cursor, geen console-output
- [ ] Jolanda kan direct een demo-gesprek beginnen

### Test 10b — hardware-watchdog

Simuleer hang: `ssh annanova 'sudo pkill -STOP python3'` (freeze Anna)
Verwacht: na 15s hardware-reboot (watchdog kick), Pi start opnieuw op.

**Pass**:
- [ ] Pi reboot vanzelf binnen 60s

### Test 10c — read-only overlay

Pull stekker eruit tijdens expositie. Steek er weer in.
- SD-kaart niet corrupt (geen `fsck`-errors bij reboot)
- Anna draait direct weer

**Pass**:
- [ ] Power-cut test 3x herhaald, geen corruptie

### Test 10d — eindsimulatie (door Jolanda)

Jolanda doet alsof ze bezoeker is:
1. Loopt op spreekplek
2. Antwoordt op 4 vragen van Anna
3. Zegt "Ja" op "Wil je de rekening?"
4. Pakt haar bon

Herhaalt 3 keer met verschillende antwoord-stijlen.

**Pass**:
- [ ] 3 bonnen geprint, elk met andere quote
- [ ] Transcript staat **niet** op schijf (check: `sudo find / -name '*anna*log*' -mtime -1` = leeg)
- [ ] Geen crashes, geen vastloper

**🔔 Beslismoment 9 (final)**: Jolanda zegt "expositie-go" of "nog X aanpassen".

---

## End-to-end simulatie — volledig droogloop-gesprek

Dit is de reality-check voor bouwstap 4, maar nu volledig gelogd.

```
$ DROOGLOOP=1 python3 -m anna.main

[12:34:00] [RUST]
[12:34:02] [see] 1 persoon op plek — triggered
[12:34:02] [OPENING] "Hé. Je stond er wat lang bij." (audio/o1.wav, 2.1s)
[12:34:04] [VRAAG] "Voel jij je hier bekeken?" (audio/v1.wav, 1.8s, halte=bekeken)
[12:34:06] [LUISTEREN] ...
[12:34:12] [hear] "Ja, een beetje."
[12:34:12] [REAGEREN] → brain.py
[12:34:13] [brain] {soort:antwoord, reactie:"Logisch. Camera uit als je weg bent?"}
[12:34:13] [speak] live TTS (1.4s)
[12:34:17] [VRAAG] "Thuis kijkt niemand, maar alles wordt opgeslagen. Heb je daar last van?" (audio/v4.wav, halte=bewaard)
...
[12:36:45] [AFSLUITING] "Wil je de rekening?" (audio/a1.wav)
[12:36:47] [hear] "Ja."
[12:36:47] [brain] {soort:ja, reactie:""}
[12:36:47] [BON] → bon.py → printer.py
[12:36:50] [print] /tmp/bon_test_1234.png saved (DROOGLOOP)
[12:36:50] [SLOTZIN] "Groetjes. Tot ziens." (audio/s1.wav, 1.2s)
[12:36:52] [LOSLATEN] transcript gewist
[12:36:52] [RUST]

Total gesprek: 2 min 52s
Audio played: 11 keer (8 vast, 3 live)
Mistral calls: 4 (± 1.2s gem)
Voxtral calls: 3 (± 0.6s gem)
Memory peak: 340 MB
```

**Baseline-timings (acceptable)**:
- Mistral-call gemiddeld: < 2s
- Voxtral-TTS live gemiddeld: < 2s
- Totaal gesprek: tussen 2m30s en 4m
- Mistral + Voxtral in één turn: < 4s (anders brugzin)

---

## Hardware-integratietest (einde dag, bouwstap 10d)

**Alles samen, 1u continu**:
- Spreekplek, printer, scherm, Mistral, Voxtral, Piper allemaal aan.
- Jolanda, Bodil, en 3 vrienden lopen vrij in/uit atelier.
- Anna doet 10 gesprekken (sommige afgebroken, sommige compleet).
- Ik log elk gesprek: duur, aantal beurten, bon-geprint?, errors.

**Target voor expositie-klaar**:
- [ ] 10/10 gesprekken zonder crash
- [ ] 7/10 gesprekken eindigen natuurlijk (OPENING → 4 vragen → AFSLUITING)
- [ ] ≥ 5 bonnen geprint
- [ ] Transcript **niet** op schijf na 1u (check: `find / -name '*anna*transcript*' -mtime -1`)
- [ ] CPU gemiddeld < 60% (als >80% constant: verwacht drops in audio)
- [ ] RAM < 2 GB (Pi 5 heeft 8 GB, dus zeeën van ruimte)

Als meer dan 2 gesprekken crashen: **niet expositie-klaar**. Fix urgent of val terug op `main`.

---

## Privacy-audit (einde dag, altijd)

Elk expositie-klaar-moment: 5 min check dat niets van bezoekers op schijf achterblijft.

```bash
ssh annanova
# Zoek naar recente files met 'transcript', 'conversation', 'anna' die
# NIET in de code-repo horen
sudo find / -type f -mtime -1 \
  \( -name '*transcript*' -o -name '*conversation*' -o -name '*gesprek*' \
     -o -name '*bezoeker*' -o -name '*audio*recording*' \) \
  -not -path '*/anna-nova/*' -not -path '*/proc/*' -not -path '*/sys/*'

# Check PNG-bonnen gewist (alleen tijdelijke voor controle horen te bestaan)
ls -la /tmp/bon_*.png 2>/dev/null

# Check geen gesprekstekst in logs
sudo journalctl -u anna-nova --since "1 hour ago" | grep -iE 'gezegd|bezoeker zei' || echo "OK geen gesprekstekst in log"
```

**Pass**: output helemaal leeg (behalve "OK geen gesprekstekst in log").

Fail = er is iets fout met de "niets naar schijf"-regel. Must fix voor expositie.

---

## Noodprocedure tijdens expositie

Als iets stuk gaat terwijl bezoekers er zijn (bordje bij Anna):

> **Niet in paniek.**
> 1. Anna niets zeggend? Druk 5s op aan/uit-knop achter het scherm.
> 2. Scherm zwart? Trek stekker, 10s wachten, weer erin.
> 3. Printer stil? Druk op knopje printertje (aan-knop).
> 4. Werkt niets? Hang bordje: "Anna slaapt. Terug om … uur." (klok)

---

Einde testplan. Bij twijfel: vraag Jolanda.
