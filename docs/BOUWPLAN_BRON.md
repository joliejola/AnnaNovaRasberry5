# Anna Nova — bouwplan voor Claude Code

*Bron-document — integraal zoals Jolanda het schreef op 6 november 2026.*
*Dit is het primaire ontwerpdocument. `BOUWPLAN_V2_AANPAK.md` is er onderhevig aan.*

---

Bijgewerkt 6 november 2026 · Jolanda Dekker (JolieJola)

Dit bestand is de opdracht voor Claude Code op de Raspberry Pi 5. Het vervangt fase 5 tot en met 7 van het stappenplan in het project. Fase 1 tot en met 4 (hardware, zien, horen, stem) blijven zoals ze zijn. Lees eerst dit hele bestand, werk dan de bouwstappen onderaan in volgorde af, en stop na elke stap bij de test.

## Wat Anna Nova is

Anna Nova is een kunstwerk in het atelier van Jolanda en Bodil, onderdeel van het project *AI vriendin gezocht*. Ze is een praatcel op een scherm. Eén bezoeker tegelijk staat op een gemarkeerde spreekplek. Anna neemt die bezoeker in ongeveer drie minuten mee op een korte reis van vier vragen langs drie haltes:

1. **Bekeken:** je voelt je hier bekeken.
2. **Bewaard:** thuis kijkt niemand, maar alles wordt opgeslagen.
3. **Wrijving:** wat gebeurt er met ons als alles makkelijk wordt?

Aan het eind vraagt Anna of je de rekening wilt. Alleen bij ja print een klein Bluetooth-printertje een bon met logo, een quote, een klein prijsje, het wereldwijde AI-bedrag van 2026, jouw aandeel daarin als percentage, de datum, de url en de afzenders. Daarna vergeet Anna het gesprek.

Anna voelt niets, maar doet het wel heel goed. Ze is traag en soms buggy, en dat hoort bij het werk: het gaat over frictie.

## Wat er verandert

- Bon bevat GEEN persoonlijke info — alleen quote uit vaste lijst
- Vaste inhoud in `content/inhoud.json`, Jolanda bewerkt dat
- Vaste zinnen vooraf opgenomen, live-TTS alleen voor reactie
- GEEN galerij, GEEN foto's, GEEN SSD
- Bezoekers NIET onthouden — transcript leeft alleen in werkgeheugen
- Printer: Agodeo mini (Bluetooth 300DPI) of USB ESC/POS reserve

## Principes

1. Privacy is het concept — niks naar schijf behalve tellers
2. Nooit door iemand heen praten, nooit raden wat gezegd werd
3. Snel waar kan, eerlijk traag waar moet — >4s live → brugzin
4. Zonder hardware testen via droogloop-modus
5. Buggy mag, crashen niet — foutzin + terug naar rust
6. Simpel boven slim

## Mappen

```
anna/
├── CLAUDE.md               ← dit bestand
├── .env
├── content/inhoud.json     ← alle vaste tekst
├── audio/<id>.wav          ← vooraf opgenomen zinnen
├── assets/logo.png
├── anna/
│   ├── main.py             flow.py           hear.py         speak.py
│   ├── see.py              brain.py          bon.py          printer.py    face.py
├── face/index.html
└── tools/
    ├── render_audio.py     ← audio uit inhoud.json via Voxtral TTS
    ├── test_bon.py         ← voorbeeldbonnen als PNG
    └── test_printer.py
```

## Gespreksmachine (flow.py)

| Toestand | Wat Anna doet | Naar |
|---|---|---|
| RUST | Slaapt, roept lokzin als mensen in ruimte maar niet op plek | OPENING na 2s iemand op plek |
| OPENING | Speelt willekeurige opening | VRAAG |
| VRAAG | Stelt volgende vraag uit getrokken reeks | LUISTEREN |
| LUISTEREN | Wacht spraak van plek | REAGEREN, STIL na 8s, of RUIS |
| REAGEREN | Mistral-call, speelt reactie/brugzin | VRAAG, AFSLUITING of ZACHT |
| STIL | 1e keer: korte vraag. 2e: "Pas is ook antwoord." | LUISTEREN/VRAAG |
| RUIS | 1e: "Nog een keer, langzaam? Ik ben oud." 2e: door | LUISTEREN/VRAAG |
| DRUK | Te veel stemmen: wacht 10s dan knopmodus | LUISTEREN |
| ZACHT | Na echt verdriet: geen grap, biedt afbouwen | AFSLUITING |
| AFSLUITING | "Wil je de rekening?" | BON bij ja, LOSLATEN bij nee |
| BON | Bouwt en print bon, speelt slotzin | LOSLATEN |
| LOSLATEN | Wist gesprek | RUST |

Tellers: 2 zijwegen → AFSLUITING. 5 min totaal → AFSLUITING. 6s leeg plek → LOSLATEN zonder bon.

Vragen trekken bij OPENING: 1 bekeken (voorkeur licht:true), 1 bewaard, 1 wrijving, 1 vrij uit bewaard/wrijving. Geen dubbele.

## Wie er spreekt

- ReSpeaker DoA ± 30° + see.py bevestigt 1 persoon op plek
- Meer dan 1 persoon of overlappende stemmen → DRUK
- Knopmodus: Anna luistert alleen zolang USB-knop ingedrukt. Terug naar normaal na 30s rust.

## Mistral brain.py

Één call per beurt, JSON output:
```json
{"soort": "antwoord|pas|zijweg|provocatie|verdriet|ja|nee", "reactie": "..."}
```
Max 18 woorden. Bij zijweg: beantwoord kort, geen vraag terug. Provocatie: "Dat werkt niet bij mij." Verdriet: zacht, geen grap.

EU endpoint, training uit. Timeout 4s → brugzin "Daar denk ik nog over na. Volgende halte." + soort=antwoord.

## Bon (bon.py via Pillow)

```
      [ logo.png ]
     AI VRIENDIN GEZOCHT
------------------------
   {quote}
------------------------
Dit gesprek       {prijs}

Wereldwijd in AI
gestoken in 2026:
$ 2.670.000.000.000

Jouw aandeel:
{percentage} %
------------------------
{datum}
aivriendingezocht.nl

Groetjes, Anna Nova
creator: JolieJola
```

Quote: willekeurig uit goedgekeurde quotes met matching halte (longest-halte van gesprek), nooit 1 van laatste 5. Na soort=verdriet: alleen halte "zacht". Leeg → willekeurig goedgekeurd.

Percentage: `prijs_eur / 2_670_000_000_000 * 100`, decimale notatie, afgekapt op eerste 2 niet-nul cijfers. €0,04 → `0,0000000000015`. €0,00 → `0 %`. Abo €9,99 p/m → reken met 9,99.

Datum Nederlands. Bron $2.67T: Gartner sept 2026 — staat als `ai_wereld_2026_usd` in inhoud.json.

Font: vrije monospace (Courier Prime), groot genoeg voor thermisch papier.

## Printen (printer.py)

Volgorde:
1. Agodeo mini via TiMini-Print of funprint (Bluetooth PNG)
2. USB ESC/POS via python-escpos
3. Geen printer: PNG opslaan tijdelijk voor controle + Anna zegt "Mijn printer is op..." + PNG weg

Printertje: aan, aan lader, niet met telefoon verbonden.

## Audio (tools/render_audio.py + speak.py)

render_audio: alle zinnen met id uit inhoud.json → audio/<id>.wav via Voxtral TTS in Anna's stem. Hash-check, alleen nieuw/gewijzigd regenereren.

speak.py: eerst audio/<id>.wav als bestaat, anders live TTS, anders Piper offline.

## Scherm (face/index.html + face.py)

Toestanden: rust / luistert / denkt / spreekt / afrekenen / print / knopmodus. Denkt mag haperen. Knopmodus toont groot: "Druk op de knop om te praten."

Aangestuurd via websocket uit face.py.

## inhoud.json (startversie)

Bevat:
- `ai_wereld_2026_usd`: 2670000000000
- `url`: aivriendingezocht.nl
- `openingen` (3)
- `lokzinnen` (1+)
- `vragen` (10: v1-v10, met halte/licht/tekst/kort)
- `brugzinnen` (4)
- `wachtzinnen` (3)
- `situaties` (pas/ruis/druk/knop/verdwaald/tijd/weg/fout/geenprint)
- `afsluiting`, `na_nee`, `slotzinnen` (2)
- `quotes` (20: id/tekst/prijs/halte/goedgekeurd=null)

Jolanda voegt 3-5 "halte:zacht" quotes toe.

## .env

```
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-small-latest
PRINT_BREEDTE_PX=          # meten in bouwstap 1
PRINTER=mini               # mini|escpos|geen
SPREEKPLEK_HOEK=0          # graden
SPREEKPLEK_MARGE=30
DROOGLOOP=0
```

## Bouwstappen (stop na elke test)

1. **Printertje**: TiMini-Print, testtekst, print-breedte meten in .env. Max 1u proberen, anders stop. **Test**: testregel uit printertje.
2. **inhoud.json + bon.py + tools/test_bon.py**. **Test**: 5 PNG-bonnen met verschillende quotes + correct percentage.
3. **printer.py**: bon met logo + reserve-routes. **Test**: echte bon uit printer; met printer uit → droogloop zegt `geenprint`.
4. **flow.py droogloop**: hele machine via typen, inclusief tellers, stilte (Enter), ruis (#ruis), druk (#druk), weg (#weg). **Test**: Jolanda speelt 5 gesprekken na (incl zijweg, pas, nee).
5. **brain.py**: Mistral JSON + timeout. **Test**: 10 voorbeelden → juiste soort; internet uit → brugzin.
6. **render_audio.py + speak.py**: alle vaste zinnen opgenomen. **Test**: opening binnen 0,5s na start.
7. **hear.py + see.py aan flow koppelen**: spreekplek, richting, knopmodus. **Test**: stem op plek telt, erachter niet.
8. **face.py + scherm**: toestanden zichtbaar, denkt hapert. **Test**: alle toestanden werken.
9. **Groepstest**: 5 vrienden, 1 op plek, rest praat erdoorheen. Tel vals-positief + gemist, stel drempels bij.
10. **Klaar voor publiek**: systemd + auto-restart + hardware-watchdog + read-only overlay. Bordje: "Anna is AI. Ze hoort je en ziet dat je er bent. Ze bewaart niets. De bon is het enige exemplaar."

## Wat Claude Code NIET doet

- Geen gesprekstekst/audio/beelden naar schijf (ook niet debug)
- Geen eigen quotes/vragen verzinnen in inhoud.json
- Geen extra services/databases/webservers behalve websocket voor scherm
- Bij twijfel kunstwerk → stop + Jolanda vragen
