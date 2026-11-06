# Pi-test — bouwplan v2 op Raspberry Pi 5

*Doel: Anna op Pi laten draaien met echte mic, scherm en nathalie-stem.
Geen printer, geen Vosk-wake nog. Puur: kan ik "Hoi Anna Nova" zeggen en Anna loopt door de 5 vragen?*

## 1 — Pull + install (±5 min)

SSH naar de Pi, dan:

```bash
cd ~/anna-nova
git fetch
git checkout bouwplan-v2
git pull
bash scripts/pi-setup.sh
```

Het script doet:
- `sudo apt install portaudio19-dev libsndfile1`
- venv aanmaken + `pip install -r requirements.txt`
- 32 WAV-bestanden renderen via Piper nathalie-medium
- Toont audio-devices

Verwacht eind-output: lijst van audio-devices. Noteer het nummer of de naam van de ReSpeaker.

## 2 — .env instellen

```bash
cp .env.sample .env
nano .env
```

Zet minimaal:
```
MISTRAL_API_KEY=...    # jouw sleutel voor brain + Voxtral-ASR
PIPER_VOICE=/home/anna/anna-nova/assets/voices/nl_BE-nathalie-medium.onnx
AUDIO_INPUT_DEVICE=ReSpeaker   # of index uit sounddevice-lijst
```

Alle andere vars kunnen default blijven.

## 3 — Scherm (parallel terminal)

Op de Pi, apart venster:

```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:8765/
```

Of open 'm handmatig in een reguliere browser. Je ziet RUST (rood pulserend) + de hint *"zeg 'Hoi Anna Nova'"*.

## 4 — Live draaien

```bash
cd ~/anna-nova
.venv/bin/python -m anna.main
```

Output in terminal zou moeten tonen:
```
── Anna Nova ──
Scherm: http://localhost:8765/
Typ 'Hoi Anna Nova' om wakker te maken. Enter = stilte.
```

**NB** — in live-mode is dat "typ" misleidend, de werkelijke input gaat via de mic. Niks typen.

Sta ongeveer 1 m voor de Pi (binnen DoA-range).

## 5 — De test

1. **Zeg**: "Hoi Anna Nova."
   - Verwacht: binnen ~3s hoor je de opening-zin uit de speaker. Scherm → spreekt (oranje puls).
2. **Luister** naar vraag 1: "Wil je mijn vriendin worden?"
3. **Zeg** je antwoord (ja/nee/misschien).
4. Anna reageert + stelt vraag 2, enzovoort t/m vraag 5.
5. **Laatste**: "Dan nu de rekening. Wil je hem?"
   - Zeg "ja" → Anna zegt `situaties.geenprint` ("Mijn printer is op…") en slotzin, want er is nog geen printer.
   - Zeg "nee" → na_nee-zin, geen bon.

## 6 — Wat terug te sturen

Bij problemen kopieer in de chat (of stuur bestanden):

```bash
journalctl -u anna-nova --since "10 min ago" 2>/dev/null \
  || tail -n 200 ~/.cache/anna-nova.log 2>/dev/null
```

Of terminal-output na Ctrl-C.

## Mogelijke problemen en snelle fixes

| Symptoom | Vermoedelijke oorzaak | Fix |
|---|---|---|
| "No module named sounddevice" | pip install miste | `source .venv/bin/activate && pip install -r requirements.txt` |
| sounddevice PortAudio error | apt dep ontbreekt | `sudo apt install portaudio19-dev` |
| Geen geluid uit speaker | ALSA default fout | `aplay -L` en zet `AUDIO_OUTPUT_DEVICE=plughw:...` in .env |
| Anna reageert niet op wake | ReSpeaker niet default input | zet `AUDIO_INPUT_DEVICE=ReSpeaker` of de index |
| Anna wordt direct wakker op niks | VAD te gevoelig | iets te laat problemen voor — kan in volgende iteratie |
| Mistral timeout | wifi slecht | Voxtral valt terug op Whisper lokaal (iets trager); check `faster-whisper` is geinstalleerd |
| Scherm blijft op RUST | websocket-connectie niet | check browser-console (F12) voor /tick fouten |
| Piper rendert niks | voice-file ontbreekt | `ls assets/voices/` moet nl_BE-nathalie-medium.onnx tonen; anders `git lfs pull` of handmatig downloaden |

## Beoordelingscriterium

Minimum voor BM4 (wake-test):
- [ ] Anna wordt in ≥8 van 10 pogingen wakker bij "Hoi Anna Nova"
- [ ] Doorloopt alle 5 vragen zonder vastlopen
- [ ] Reageert op minstens 1 ja-antwoord met iets levends (niet alleen script)
- [ ] Sleep-phrase "slaap lekker" in LUISTEREN laat Anna direct stil

Als dat lukt: wake.py Vosk is dan het logische volgende blok (offline wake = meer privacy + onafhankelijk van wifi).
