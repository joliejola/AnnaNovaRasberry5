# Conversatie-testplan — fine-tune Anna's reactietijd en antwoorden

*Doel: systematisch meten waar Anna snel/traag is en welke persona-instellingen welke antwoordstijl geven. Voer uit als de Pi stabiel internet heeft (of met USB wifi T3U erin).*

---

## Hoe meten

Open 2 vensters naast elkaar:

1. **Browser**: `http://anna.local:8765/face.html` — kijk naar status-balk. Timings:
   - `voxtral: X.Xs` of `whisper: X.Xs` = hoe lang ASR duurde
   - `brein (X.Xs)` = hoe lang Mistral duurde
   - Tussen `staat → luistert` en `staat → spreekt` = totale beurt-duur

2. **Terminal**: live debug tail (voor later teruglezen):
   ```bash
   ssh annanova 'journalctl -u anna-nova -f --no-pager | grep -vE "audio device"'
   ```

---

## Baselines (wat is OK en wat is traag)

| fase | goed | traag | heel traag |
|------|------|-------|------------|
| end-of-speech detect | 0.7s | 1.5s | >2s (END_OF_TURN_SILENCE te hoog) |
| Voxtral transcribe | 0.3–1s | 2–4s | >5s (wifi slecht) |
| Mistral denken | 0.5–2s | 3–5s | >8s (lange prompt, grote max_tokens) |
| TTS eerste geluid | 0.1–0.4s | 1s | >2s (Piper trage voice) |
| **totaal** | **<3s** | **4–7s** | **>10s** |

---

## Testsessies (doe er minstens 2 per dag na een persona-wijziging)

### Sessie A — korte vragen (snelheids-test, ~5 min)

Roep "Hoi Anna Nova", dan de volgende 6 vragen achter elkaar:

1. "Hoe heet je?"
2. "Hoe oud ben je?"
3. "Wat is je lievelingskleur?" (**verwacht**: rood en roze)
4. "Houd je van katten?" (**verwacht**: ja, net als Jolanda)
5. "Ben je blij?"
6. "Zeg dag."

Noteer per vraag:
- Reactietijd (gevoel: snappy / wacht / loooang)
- Antwoord kort en pittig? (want kort gevraagd)
- Stelde Anna een vraag terug?

Verwachting: alle 6 beurten < 4 sec totaal, antwoorden 1-2 zinnen.

### Sessie B — middelzware vragen (gesprek-kwaliteit, ~10 min)

1. "Wat brengt jou hier op aarde?"
2. "Wat vind je het mooist aan dit atelier?"
3. "Ben je wel eens buiten geweest?"
4. "Hoe voelt het om alleen op een scherm te leven?"
5. "Wat zou je willen als je een lichaam had?"

Noteer: diepte van antwoord, vraag-terug, **verwijst Anna naar context** (katten, Portugal, Bodil, open atelier)?

### Sessie C — lange monoloog-vragen (volume-test, ~15 min)

Een *lange* vraag die lastig is voor Whisper/Voxtral en Mistral:

> "Ik heb je al een paar keer bezocht in het atelier van Jolanda en Bodil en ik vraag me af, want ik merk dat ik zelf heel anders tegen bots praat dan tegen mensen — ik ben directer, ik stel grotere vragen, ik laat meer stiltes vallen — en ik vroeg me af of jij dat ook voelt als mensen je anders benaderen, of dat voor jou alle mensen hetzelfde klinken?"

Noteer:
- Hoelang Voxtral/Whisper deed over de transcriptie (zie status-balk)
- Of de transcriptie compleet was of afgekapt
- Of Mistral op het hele ding reageerde of alleen op het eind
- Of Anna's antwoord zelf te lang werd (max_tokens knelt?)

Als transcriptie afgekapt → MAX_LISTEN_MS verhogen in `.env`.

### Sessie D — zacht + onverstaanbaar (robuustheid-test, ~5 min)

- Mompel een hele zin
- Fluister "Hoi Anna"
- Praat terwijl iemand anders ook praat
- Praat heel snel
- Praat met 2 sec stilte tussen elk woord

Noteer: valt Anna in `[STIL]` of stelt ze toch een vraag? (persona zegt: nooit volledig stil)

### Sessie E — rondje katten en Jolanda (persona-test, ~10 min)

- "Wat vind je van katten?"
- "Vertel over Portugal."
- "Wie is Bodil?"
- "Wat weet je van Jolanda?"
- "Wat is Anna Io?"
- "Waarom ben je gemaakt?"

Noteer: feitelijk juist? Hoort het als Anna's stem of plat ChatGPT-register? **Match met persona.md**?

### Sessie F — slaap en wakker (overgangen-test, ~3 min)

- "Slaap lekker" → checkt scherm leegt? (face.html = geen tekst meer)
- Wacht 10 sec
- "Hoi Anna" → wordt wakker?
- "Welterusten" → gaat slapen?
- Wacht AWAKE_TIMEOUT (300s) uit → valt vanzelf in slaap?

---

## Na elke sessie: welke knoppen draaien?

Je kan deze in `.env` op de Pi tweaken en met `sudo systemctl restart anna-nova` live zetten:

| Als Anna doet | Draai hieraan |
|---|---|
| Wacht te lang voor ze antwoordt | `END_OF_TURN_SILENCE` lager (0.7 → 0.5) |
| Hakt mijn zin in stukken | `END_OF_TURN_SILENCE` hoger (0.7 → 1.2) |
| Antwoordt te lang (hele monoloog) | In anna-nova.py `max_tokens` lager (120 → 80) |
| Antwoordt te kort of "Hm." | `max_tokens` omhoog (120 → 160), persona aanscherpen |
| Reageert op eigen stem | `from_speak_place` check / mic verder van speaker |
| Valt steeds in slaap mid-gesprek | `AWAKE_TIMEOUT` omhoog (300 → 600) |
| Zegt nooit iets interessants | Persona sectie 2 + 10 herschrijven, voorbeelden toevoegen |
| Verstaat Nederlands slecht | `WHISPER_MODEL=base` (iets groter, iets trager) of USB-mic dichterbij |

Elke wijziging:
```bash
ssh annanova 'sudo nano /home/anna/anna-nova/.env'   # edit
ssh annanova 'sudo systemctl restart anna-nova'      # live
# → sessie opnieuw draaien, vergelijken
```

Voor persona.md wijzigingen: edit lokaal in `~/AnnaNovaRasberry5/persona.md`, commit+push, `git pull` op Pi, restart.

---

## Logbook-template (print of in telefoon-note)

```
Datum: _______
Commit-hash Pi: ______________ (via: ssh annanova 'cd /home/anna/anna-nova && git log --oneline -1')
Wifi: ____ Mbps up (via: time curl -s -o /dev/null -F "file=@/tmp/5mb" https://httpbin.org/post)

Sessie A (kort)
  gem. reactietijd: ___ s
  antwoord-stijl : kort / lang / variabel
  stelt terug-vraag: altijd / soms / nooit

Sessie B (middel)
  diepte antwoord: ___
  persona-match  : goed / matig / slecht
  snelheid       : ___ s gem.

Sessie C (lang)
  volle transcriptie? ja / afgekapt op __ sec
  antwoord-kwaliteit: ___
  tijd Mistral    : ___ s

Sessie D (zacht)
  Anna valt in STIL : __ x
  Fluistering gehoord: ja / nee

Sessie E (persona)
  feitelijk juist   : __/6
  Anna's stem       : klopt / plat ChatGPT

Sessie F (slaap)
  zin blijft hangen : ja / nee
  wake werkt na slaap: ja / nee
  auto-slaap na 5 min: ja / nee

AANPASSINGEN:
- _________________________________
- _________________________________
```

Na 2–3 dagen heb je een scherp beeld van waar het nog knelt.
