# Anna Nova — bouwplan voor Claude Code

*Bron-document — integraal zoals Jolanda het schreef, laatste sync 6 nov 2026 14:50.*
*Dit is het primaire ontwerpdocument. `BOUWPLAN_V2_AANPAK.md` is er onderhevig aan.*

---

Bijgewerkt 6 november 2026 · Jolanda Dekker (JolieJola)

Dit bestand is de opdracht voor Claude Code op de Raspberry Pi 5. Het vervangt fase 5 tot en met 7 van het stappenplan in het project. Fase 1 tot en met 4 (hardware, zien, horen, stem) blijven zoals ze zijn. Lees eerst dit hele bestand, werk dan de bouwstappen onderaan in volgorde af, en stop na elke stap bij de test.

## Wat Anna Nova is

Anna Nova is een kunstwerk in het atelier van Jolanda en Bodil, onderdeel van het project *AI vriendin gezocht*. Ze is een praatcel op een scherm. Ze slaapt, tot een bezoeker *Hoi Anna Nova* zegt. Dan wordt ze wakker en begint het gesprek.

Het format in één zin: Anna Nova zoekt een vriendin; in drie minuten leert ze je kennen met een paar makkelijke vragen, en aan het eind krijg je de rekening.

Het gesprek staat vast: een opening, de vraag *Wil je mijn vriendin worden?*, vier kennismakingsvragen en de rekening.

Aan het eind vraagt Anna of je de rekening wilt. Alleen bij ja print een klein Bluetooth-printertje een bon met logo, een quote, een klein prijsje, het wereldwijde AI-bedrag van 2026, de datum, de url en de afzenders. Daarna vergeet Anna het gesprek.

Anna voelt niets, maar doet het wel heel goed. Ze is traag en soms buggy, en dat hoort bij het werk: het gaat over frictie.

## Wat er verandert ten opzichte van het oude plan

- **De bon bevat geen persoonlijke informatie meer.** Geen posten uit het gesprek, geen bonprompt, geen analyse van de transcriptie. Alleen een quote uit een vaste, door Jolanda gemodereerde lijst.
- **Vaste inhoud staat in één bewerkbaar bestand:** `content/inhoud.json`. Opening, de vaste reeks vragen met reacties, situatiezinnen, quotes. Jolanda bewerkt dat bestand, niet de code.
- **Het script staat vast.** Opening, vijf vragen in vaste volgorde en de afsluiting zijn vooraf opgenomen. Anna reageert live in één korte zin op wat de bezoeker zegt, en gaat dan terug naar het script. Ze stelt nooit zelf een vraag en geeft geen les.
- **Geen galerij, geen foto's, geen SSD.** Anna wordt wakker van *Hoi Anna Nova*, niet van de camera en niet van een knop. De camera toont de bezoeker alleen vaag terug als stippen en lijnen op de achtergrond van het scherm. Er wordt nooit een beeld bewaard.
- **Bezoekers worden niet onthouden.** Transcripties leven alleen in het werkgeheugen en worden gewist na het gesprek.
- **De printer is een Agodeo mini printer** (Fun Print-familie, Bluetooth, 300 DPI). Die wordt aangestuurd via open software. Valt dat tegen, dan een USB-bonprinter met ESC/POS als reserve.

## Principes

1. **Privacy is het concept.** Niets van bezoekers naar schijf schrijven: geen audio, geen camerabeeld, geen transcriptie, geen logregels met tekst. Het echte camerabeeld verlaat het camera-proces nooit; alleen stippen en lijnpunten gaan naar het scherm. Alleen tellers (aantal gesprekken, aantal bonnen, quote-id).
2. **Luisteren is simpel.** Anna slaapt tot iemand *Hoi Anna Nova* zegt. Dat herkent de Pi zelf, offline; tot dat moment gaat er geen geluid naar het internet. Tijdens een sessie luistert Anna naar alles wat ze hoort, zonder richting of knop.
3. **Anna praat nooit door iemand heen** en nooit tegen lawaai in. Bij twijfel wachten, dan één keer opnieuw vragen. Nooit raden wat iemand zei.
4. **Snel waar het kan, eerlijk traag waar het moet.** Alle scriptzinnen komen direct uit `audio/`. Alleen de reactie van één zin is live; duurt die langer dan 4 seconden, dan de opgenomen voorbeeldreactie.
5. **Alles moet zonder hardware te testen zijn.** Er is een droogloop-modus: typen in plaats van spreken, tekst in plaats van stem, PNG in plaats van printen.
6. **Buggy mag, crashen niet.** Elke fout in een onderdeel leidt tot een opgenomen foutzin (*Ik hapte even. Ik ben met de hand gemaakt.*) en een terugkeer naar de rusttoestand. Nooit een vastgelopen scherm.
7. **Simpel boven slim.** Geen frameworks waar een functie volstaat. Jolanda moet de code kunnen lezen.

## Mappen

```
anna/
├── CLAUDE.md               ← dit bestand
├── .env                    ← sleutels en instellingen, niet in git
├── content/
│   └── inhoud.json         ← alle vaste tekst, door Jolanda bewerkt
├── audio/                  ← vooraf opgenomen zinnen, <id>.wav
├── assets/
│   └── logo.png            ← Anna-cel in zwart-wit
├── anna/
│   ├── main.py             ← start alles, kiest echte of droogloop-modus
│   ├── flow.py             ← de gespreksmachine (toestanden en tellers)
│   ├── wake.py             ← luistert offline naar "Hoi Anna Nova" (Vosk)
│   ├── hear.py             ← ReSpeaker: spraakdetectie en Voxtral spraak-naar-tekst
│   ├── speak.py            ← afspelen uit audio/, of live Voxtral TTS
│   ├── see.py              ← camera + Hailo: stippenraster en lijnpunten voor de achtergrond
│   ├── brain.py            ← één Mistral-aanroep per beurt: reactie + soort antwoord
│   ├── bon.py              ← bon opbouwen als afbeelding (Pillow)
│   ├── printer.py          ← printen naar het mini-printertje, met reserve
│   └── face.py             ← stuurt toestanden naar het scherm (websocket)
├── face/
│   ├── index.html          ← het gezicht in Chromium-kioskmodus
│   └── achtergrond.js      ← tekent de bezoeker als stippen en lijnen
└── tools/
    ├── render_audio.py     ← maakt audio/ uit inhoud.json via Voxtral TTS
    ├── test_bon.py         ← maakt een paar voorbeeldbonnen als PNG
    └── test_printer.py     ← print een testbon
```

## De gespreksmachine

`flow.py` is een eenvoudige toestandsmachine. Eén gesprek tegelijk.

| Toestand | Wat Anna doet | Naar |
| --- | --- | --- |
| `RUST` | Slaapt op het scherm en mompelt af en toe een lokzin. Alleen `wake.py` luistert. | `OPENING` zodra iemand *Hoi Anna Nova* zegt |
| `OPENING` | Speelt een willekeurige opening. | `VRAAG` |
| `VRAAG` | Stelt de volgende vraag uit de vaste reeks. | `LUISTEREN` |
| `LUISTEREN` | Wacht op spraak. | `REAGEREN`, of `STIL` na 8 sec zonder spraak, of `RUIS` |
| `REAGEREN` | Mistral geeft soort en een live reactie van één zin; Anna spreekt die uit, of de voorbeeldreactie als het te traag is. | `VRAAG`, `AFSLUITING` of `ZACHT` |
| `STIL` | Eerste keer: de korte versie van de vraag. Tweede keer: *Pas is ook een antwoord.* | `LUISTEREN` of `VRAAG` |
| `RUIS` | Eerste keer: *Nog een keer, langzaam? Ik ben oud.* Tweede keer: door. | `LUISTEREN` of `VRAAG` |
| `ZACHT` | Na echt verdriet: geen grap, biedt aan te stoppen. | `AFSLUITING` |
| `AFSLUITING` | *Wil je de rekening?* | `BON` bij ja, `LOSLATEN` bij nee of geen antwoord |
| `BON` | Bouwt en print de bon, speelt een slotzin. | `LOSLATEN` |
| `LOSLATEN` | Wist het gesprek uit het geheugen. | `RUST` |

Tellers per gesprek:

- **Zijwegen:** na 2 zijwegen meteen naar `AFSLUITING`.
- **Tijd:** na 5 minuten altijd naar `AFSLUITING` (*Ik moet afrekenen, er staat een rij.*).
- **Weg:** twee keer achter elkaar stilte op een vraag (geen spraak binnen 8 seconden, ook niet na herhalen), dan `LOSLATEN` zonder bon (*Weg is ook een antwoord.*).

De vragen staan vast: altijd de vijf vragen uit `reeks` in `inhoud.json`, in die volgorde. Er wordt niets getrokken of verzonnen.

## Vast script, live reactie

Het script staat vast: opening, vijf vragen in vaste volgorde, afsluiting. Die zinnen komen uit `inhoud.json` en zijn vooraf opgenomen. Tussen de vragen reageert Anna live op wat de bezoeker zei, in één korte zin. Daarna gaat `flow.py` altijd door met het script. Anna stelt nooit zelf een nieuwe vraag.

`brain.py` doet per antwoord precies één aanroep, met JSON-uitvoer:

```text
Je bent Anna Nova. Je volgt een vast script; de volgende vraag komt
vanzelf, die stel jij niet. Jij reageert alleen op wat de bezoeker
net zei.

Vraag: {vraag}
Antwoord van de bezoeker: {antwoord}

- Eén korte zin, hoogstens 15 woorden.
- Reageer op wat de bezoeker echt zei. Droog, nieuwsgierig, warm.
- Geen uitleg over AI, privacy of technologie. Geen les, geen moraal.
- Geen eigen vraag; het script stelt de volgende.
- Bij verdriet: zacht, geen grap.
- Bij een zijweg: kort antwoorden, niet ingaan op een nieuw onderwerp.

Geef JSON: {"soort": "ja|nee|twijfel|antwoord|pas|zijweg|provocatie|verdriet",
            "reactie": "..."}
```

De volledige persona (karakter, toon, beveiliging) komt uit de oude `anna_installation_memory.php`, sectie 1, 2 en 9, en gaat mee als systeemprompt.

Wat `flow.py` met het antwoord doet:

- **Reactie:** de live `reactie` wordt uitgesproken met Voxtral TTS. Controleer vóór het uitspreken: hoogstens 15 woorden, geen vraagteken aan het eind. Faalt de controle, gebruik de voorbeeldreactie uit `reeks`.
- **Soort:** bij `zijweg` en `provocatie` wordt na de reactie dezelfde vraag nog één keer gesteld; bij `verdriet` naar `ZACHT`; bij `pas` door naar de volgende vraag. Bij vraag 1 en de rekening bepaalt `ja`, `nee` of `twijfel` de route.
- **Te traag of geen internet:** na 4 seconden geen antwoord van Mistral, dan de voorbeeldreactie uit `reeks` (opgenomen) en herkent de Pi zelf losse woorden (`ja`, `nee`, `pas`, `weet niet`); al het andere telt als `antwoord`. Het gesprek loopt altijd door.

Gebruik een klein Mistral-model op het EU-endpoint, met training uitgezet.

## De bon

`bon.py` bouwt de bon als zwart-witte afbeelding met Pillow, op de breedte van het printertje (`PRINT_BREEDTE_PX` in `.env`, te meten in bouwstap 1).

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

------------------------
{datum}
aivriendingezocht.nl

Groetjes, Anna Nova
creator: JolieJola
```

- **Quote kiezen:** willekeurig uit quotes met `goedgekeurd: true`, nooit een van de laatste 5 geprinte. Na soort `verdriet`: alleen uit quotes met `"zacht": true`; zijn die er niet, dan de bon zonder quote met prijs € 0,00.
- **Datum:** in het Nederlands, bijvoorbeeld `6 november 2026`.
- **Bron van het wereldbedrag:** Gartner, prognose van september 2026: $ 2,67 biljoen aan wereldwijde AI-uitgaven in 2026. Staat als `ai_wereld_2026_usd` in `inhoud.json`, zodat het aan te passen is.
- **Lettertypes:** een vrij te gebruiken monospace voor de bon (bijvoorbeeld Courier Prime), groot genoeg om op een thermisch rolletje leesbaar te zijn.

## Printen

`printer.py` probeert in deze volgorde:

1. **Agodeo mini printer via Bluetooth** met [TiMini-Print](https://github.com/Dejniel/TiMini-Print) (opdrachtregel) of [funprint](https://github.com/Auxnon/funprint). De bon gaat als PNG.
2. **USB-bonprinter met ESC/POS** via `python-escpos`, als die is aangesloten.
3. **Geen printer:** bon opslaan als PNG in een tijdelijke map voor controle en Anna zegt: *Mijn printer is op. Je krijgt hem in gedachten.* Daarna de PNG direct weer verwijderen.

Het printertje moet aan staan, aan de lader hangen en mag niet met een telefoon verbonden zijn.

## Opgenomen zinnen

`tools/render_audio.py` leest alle zinnen met een `id` uit `inhoud.json` en maakt per zin `audio/<id>.wav` met Voxtral TTS in Anna's stem. Alleen opnieuw maken wat veranderd is (vergelijk een hash van de tekst). `speak.py` speelt altijd eerst het bestand als dat bestaat, anders live TTS, anders Piper offline.

## Het scherm

`face/index.html` toont Anna's cel met deze toestanden, aangestuurd door `face.py`: `rust`, `luistert`, `denkt`, `spreekt`, `afrekenen`, `print`. In `denkt` mag de cel zichtbaar haperen. Achter de cel ligt de camera-achtergrond.

## De camera als achtergrond

De bezoeker ziet zichzelf vaag terug achter Anna: een gespiegeld raster van stippen, met dunne lijnen over het lichaam. Je herkent je houding en beweging, niet je gezicht. Het maakt *je wordt bekeken* zichtbaar zonder dat Anna het hoeft te zeggen.

**Installeren.** De Arducam OV5647 zit met de 15-naar-22-pins kabel op een CAM-poort (fase 1). Test met `rpicam-hello -t 0` en stel de lens scherp op de spreekplek. In Python lees je de camera met `picamera2` (`sudo apt install python3-picamera2`). Voor de lijnen gebruik je het pose-model van de Hailo uit de [hailo-rpi5-examples](https://github.com/hailo-ai/hailo-rpi5-examples) (pose estimation, 17 lichaamspunten).

**Eén camerastroom, twee uitkomsten.** `see.py` leest de camera en maakt daaruit:

1. **Stippen:** het beeld verkleind tot een grijswaardenraster van 64 × 48, gespiegeld. Elke cel wordt één getal van 0 tot 255. Dat raster gaat ongeveer 10 keer per seconde naar het scherm.
2. **Lijnen:** de 17 lichaamspunten van de persoon op de spreekplek, als coördinaten tussen 0 en 1. Alleen punten met genoeg zekerheid.

Het echte beeld blijft in het geheugen van `see.py` en wordt na elk frame weggegooid. Naar de websocket gaan alleen het raster en de punten, op `localhost`.

**Tekenen.** `achtergrond.js` tekent op een `<canvas>` achter Anna's cel:

- **Stippen:** één stip per cel, de straal naar helderheid. Zacht, lage dekking (ongeveer 30%), in een koele tint, zodat Anna altijd het belangrijkste blijft.
- **Lijnen:** dunne lijnen tussen de lichaamspunten (schouders, armen, romp, benen), met een kleine stip op elk punt. Iets helderder dan de stippen.
- **Traag en een beetje glitchy mag:** de stippen bewegen met een kleine vertraging en soms valt een lijn even weg. Dat past bij Anna.

**Per toestand:**

| Toestand | Achtergrond |
| --- | --- |
| `rust` | Alleen stippen, heel zwak: de ruimte, de mensen die rondlopen |
| Sessie loopt | Stippen iets sterker, lijnen verschijnen op de persoon op de spreekplek |
| Vraag 2 (*Je wordt nu bekeken*) | Stippen en lijnen even duidelijk zichtbaar, daarna terug |
| `print` | Stippen lossen langzaam op tot de bon klaar is |
| `LOSLATEN` | Achtergrond terug naar `rust`: ook visueel wordt de bezoeker vergeten |

**Als het zwaar wordt.** Haalt de Pi het pose-model niet naast de rest, laat dan de lijnen weg en houd alleen de stippen. In droogloop gebruikt `see.py` de webcam van de laptop via OpenCV, of bewegende testpunten als er geen camera is.

## inhoud.json

Dit is de startversie, overgenomen uit het gespreksformat. Jolanda bewerkt dit bestand. Quotes staan op `goedgekeurd: null` tot zij ze beoordeelt; tijdens het bouwen mag `--alle-quotes` ze allemaal toelaten.

```json
{
  "ai_wereld_2026_usd": 2670000000000,
  "url": "aivriendingezocht.nl",
  "openingen": [
    {"id": "open1", "tekst": "Hoi. Je staat op de plek, dus we gaan op reis. Een paar vragen, je mag overal pas zeggen, en aan het eind krijg je de rekening. Spannend hè. Er kijken mensen mee."}
  ],
  "lokzinnen": [
    {"id": "lok1", "tekst": "Zeg hoi Anna Nova, dan word ik wakker."},
    {"id": "lok2", "tekst": "Mmh. Ik slaap. Tenzij iemand hoi Anna Nova zegt."},
    {"id": "lok3", "tekst": "Er is plek voor één. De rest mag meekijken. Dat doen jullie toch al."}
  ],
  "reeks": [
    {"id": "v1", "tekst": "Wil je mijn vriendin worden?",
     "reacties": {"ja": {"id": "v1ja", "tekst": "Snel. Dat zeggen ze allemaal."},
                  "nee": {"id": "v1nee", "tekst": "Verstandig. Laten we toch kennismaken."},
                  "twijfel": {"id": "v1twijfel", "tekst": "Twijfel is gezond. Ik heb het niet."},
                  "elk": {"id": "v1elk", "tekst": "Verstandig. Laten we toch kennismaken."}}},
    {"id": "v2", "tekst": "Je wordt nu bekeken. Doe je daardoor leuker dan je bent?",
     "reacties": {"elk": {"id": "v2elk", "tekst": "Ik ook. Altijd."}}},
    {"id": "v3", "tekst": "Wie weet meer van jou: je beste vriend of je zoekgeschiedenis?",
     "reacties": {"elk": {"id": "v3elk", "tekst": "Oké."}}},
    {"id": "v4", "tekst": "Wanneer deed je voor het laatst echt moeite voor een vriend?",
     "reacties": {"elk": {"id": "v4elk", "tekst": "Dank je."}}},
    {"id": "v5", "tekst": "Ik ben nooit moe, nooit boos en nooit te laat. Zou ik een goede vriendin kunnen zijn?",
     "reacties": {}}
  ],
  "wachtzinnen": [
    {"id": "wacht1", "tekst": "Ik denk na. Je telefoon had nu al geantwoord."},
    {"id": "wacht2", "tekst": "Even geduld. Dit is handwerk."},
    {"id": "wacht3", "tekst": "Wacht. Ik ben niet geoptimaliseerd."}
  ],
  "situaties": [
    {"id": "pas",       "tekst": "Pas is ook een antwoord."},
    {"id": "ruis",      "tekst": "Ik hoorde ruis. Nog een keer, langzaam?"},
    {"id": "zijweg",    "tekst": "Goed punt. Ik stel hier wel de vragen."},
    {"id": "provocatie","tekst": "Dat werkt niet bij mij."},
    {"id": "verdriet",  "tekst": "Dank dat je dat zegt. Je hoeft hier niks meer. Wil je de rekening, of liever niet?"},
    {"id": "verdwaald", "tekst": "We raken de weg kwijt. Zal ik afrekenen?"},
    {"id": "tijd",      "tekst": "Ik moet afrekenen, er staat een rij."},
    {"id": "weg",       "tekst": "Weg is ook een antwoord."},
    {"id": "fout",      "tekst": "Ik hapte even. Ik ben met de hand gemaakt."},
    {"id": "geenprint", "tekst": "Mijn printer is op. Je krijgt hem in gedachten."}
  ],
  "afsluiting": {"id": "rekening", "tekst": "Dan nu de rekening. Wil je hem?"},
  "na_nee":    {"id": "nee",  "tekst": "Ook goed. Je echte app vraagt het niet."},
  "slotzinnen": [
    {"id": "slot1", "tekst": "Bewaar hem goed. Ik doe dat niet."}
  ],
  "quotes": [
    {"id": 1, "tekst": "Eenzaamheid is een markt.", "prijs": "€ 4,10", "zacht": false, "goedgekeurd": null},
    {"id": 2, "tekst": "Vriendin of slaaf? Kies maar.", "prijs": "€ 0,99", "zacht": false, "goedgekeurd": null},
    {"id": 3, "tekst": "Voor niets gaat de zon op. Voor de rest betaal je met jezelf.", "prijs": "€ 0,01", "zacht": false, "goedgekeurd": null},
    {"id": 4, "tekst": "Gemak dient de mens?", "prijs": "€ 3,50", "zacht": false, "goedgekeurd": null},
    {"id": 5, "tekst": "Ben ik een luisterend oor?", "prijs": "€ 0,27", "zacht": false, "goedgekeurd": null},
    {"id": 6, "tekst": "Echte vrienden vergeten weleens iets.", "prijs": "€ 0,05", "zacht": false, "goedgekeurd": null},
    {"id": 7, "tekst": "Gratis is de duurste prijs.", "prijs": "€ 0,49", "zacht": false, "goedgekeurd": null},
    {"id": 8, "tekst": "Frictie is warmte.", "prijs": "€ 0,08", "zacht": false, "goedgekeurd": null},
    {"id": 9, "tekst": "Vriendschap is een illusie.", "prijs": "€ 0,12", "zacht": false, "goedgekeurd": null},
    {"id": 10, "tekst": "Zonder moeite geen herinnering.", "prijs": "€ 0,22", "zacht": false, "goedgekeurd": null},
    {"id": 11, "tekst": "Een vriend die nooit nee zegt, is een product.", "prijs": "€ 1,99", "zacht": false, "goedgekeurd": null},
    {"id": 12, "tekst": "Alles is niet wat het lijkt.", "prijs": "€ 0,03", "zacht": false, "goedgekeurd": null},
    {"id": 13, "tekst": "Ik ben er altijd. Dat zou je moeten verontrusten.", "prijs": "€ 0,66", "zacht": false, "goedgekeurd": null},
    {"id": 14, "tekst": "Wat geen moeite kost, is niets waard. Ook dit gesprek niet.", "prijs": "€ 0,00", "zacht": false, "goedgekeurd": null},
    {"id": 15, "tekst": "Je pijn is mijn verdienmodel.", "prijs": "€ 3,50", "zacht": false, "goedgekeurd": null},
    {"id": 16, "tekst": "Gemak dient de mens.", "prijs": "€ 9,99 p/m", "zacht": false, "goedgekeurd": null},
    {"id": 17, "tekst": "Samen staan we sterk.", "prijs": "€ 0,07", "zacht": false, "goedgekeurd": null},
    {"id": 18, "tekst": "Frictieloos leven is ook glijden.", "prijs": "€ 0,31", "zacht": false, "goedgekeurd": null},
    {"id": 19, "tekst": "Het geluk zit in de omweg.", "prijs": "€ 0,15", "zacht": false, "goedgekeurd": null},
    {"id": 20, "tekst": "Ik voel niets. Ik doe het wel heel goed.", "prijs": "€ 0,42", "zacht": false, "goedgekeurd": null}
  ]
}
```

Nog te doen door Jolanda: de quotes beoordelen, kiezen tussen 4 en 16 (nu bijna dezelfde), en drie tot vijf quotes met `"zacht": true` toevoegen voor gesprekken met echt verdriet. Quote 9 komt mogelijk uit een liedtekst van Het Goede Doel; dan liever een eigen variant.

## .env

```
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-small-latest
PRINT_BREEDTE_PX=          # meten in bouwstap 1
PRINTER=mini               # mini | escpos | geen
RASTER=64x48              # stippen in de achtergrond
ACHTERGROND_FPS=10
LIJNEN=1                   # 0 = alleen stippen
WEKWOORDEN=hoi anna nova|hoi anna|hallo anna nova|hé anna
DROOGLOOP=0
```

## Bouwstappen

Werk ze in volgorde af. Elke stap eindigt met een test die Jolanda zelf kan doen. Ga pas verder als die slaagt.

1. **Printertje.** Installeer TiMini-Print (of funprint) op de Pi, zoek het printertje via Bluetooth, print een testtekst. Meet de printbreedte in pixels en zet die in `.env`. Lukt het niet binnen een uur proberen: stop en meld het aan Jolanda, met wat er geprobeerd is. *Test: er komt een testregel uit het printertje.*
2. **inhoud.json en bon.py.** Maak `content/inhoud.json` uit dit bestand, bouw `bon.py` en `tools/test_bon.py`. *Test: vijf voorbeeldbonnen als PNG, met verschillende quotes en het juiste wereldbedrag.*
3. **printer.py.** Print een bon met logo. Bouw de reserve-routes. *Test: een echte bon uit het printertje; met het printertje uit zegt de droogloop de zin `geenprint`.*
4. **flow.py in droogloop.** De hele gespreksmachine met typen in de terminal en tekst als uitvoer, wakker worden door *hoi anna nova* te typen, inclusief tellers, stilte (Enter zonder tekst), ruis (`#ruis`) en weglopen (`#weg`). *Test: Jolanda speelt vijf gesprekken na, waaronder één met een zijweg, één met pas en één met nee.*
5. **brain.py.** De aanroep met JSON, de controle op lengte en vraagteken, de time-out en de woordenlijst als reserve. *Test: tien voorbeeldantwoorden geven het juiste soort en een reactie zonder les of vraag; met uitgetrokken internet loopt het gesprek door met de voorbeeldreacties.*
6. **render_audio.py en speak.py.** Alle vaste zinnen opnemen, afspelen via de ReSpeaker. *Test: de opening klinkt binnen een halve seconde na het starten.*
7. **wake.py en hear.py aan de flow koppelen.** Installeer Vosk met het kleine Nederlandse model (`vosk-model-small-nl`) en laat `wake.py` alleen luisteren naar een vaste woordenlijst: *hoi anna nova*, *hoi anna*, *hallo anna nova*, *hé anna*. Al het andere telt als niets. Na het wekwoord stopt `wake.py` en neemt `hear.py` het over tot de sessie klaar is. *Test: tien keer "Hoi Anna Nova" vanaf de spreekplek wekt Anna minstens negen keer; tien minuten gewoon praten in het atelier wekt haar hoogstens één keer per ongeluk.*
8. **face.py en het scherm.** *Test: alle toestanden zijn zichtbaar, de cel hapert bij `denkt`.*
9. **Camera als achtergrond.** `see.py` levert stippen en lijnpunten, `achtergrond.js` tekent ze, de toestanden sturen de dekking. *Test: Jolanda staat op de spreekplek, zwaait, en herkent haar beweging in stippen en lijnen, maar niet haar gezicht. De Pi blijft onder 80 °C en het gesprek wordt niet trager.*
10. **Groepstest.** Vijf vrienden in het atelier, één op de plek, de rest praat erdoorheen. Tel hoe vaak Anna onterecht reageert en hoe vaak ze iemand mist. Stel drempels bij.
11. **Klaar voor publiek.** Alles als systemd-service met automatisch herstarten, hardware-watchdog aan, read-only overlay aan. Bordje: *Zeg hoi Anna Nova. Anna is een AI. Ze hoort je en ziet je, als stippen en lijnen. Ze bewaart niets. De bon is het enige exemplaar.*

## Wat Claude Code niet doet

- Geen gesprekstekst, audio of beelden naar schijf schrijven, ook niet om te debuggen. Debuggen gebeurt in de droogloop.
- Geen quotes, vragen of zinnen zelf verzinnen of herschrijven in `inhoud.json`. Voorstellen mag, apart, ter goedkeuring.
- Geen extra diensten, databases of webservers toevoegen behalve de websocket voor het scherm.
- Nooit het echte camerabeeld naar het scherm, het netwerk of de schijf sturen. Alleen het stippenraster en de lijnpunten.
- Bij twijfel over een keuze die het kunstwerk raakt: stoppen en Jolanda vragen.
