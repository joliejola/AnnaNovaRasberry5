# Camera pose-overlay voor Anna Nova

*Aanpak voor bouwstap 9 uit `docs/BOUWPLAN_BRON.md`: stippenraster 64×48 + pose-lijnen van de bezoeker, gerenderd achter de cel op het scherm. Deze file is een plan — nog geen code — zodat de bouwer in bouwstap 9 direct kan beginnen.*

## Wat moet er op het scherm

Twee overlays op `face/index.html` canvas, achter de cel (`z-index: 0`):

1. **Stippenraster 64×48** — 3072 grijze stippen, per cel helderheid geschaald naar gemiddelde luminantie van die camerablok (de bezoeker als silhouet in halftone).
2. **Pose-lijnen** — 15-20 keypoints van de persoon vóór de camera, verbonden door lijnen (schouder-elleboog-pols, heup-knie-enkel), dun en lichtgrijs.

Privacy-concept: het echte camerabeeld verlaat `see.py` nooit. Alleen 3072 grijswaarden + ~17 (x,y)-punten gaan via websocket naar `face.html`. Dat is per frame <2 KB — een echt camerabeeld zou 50-200 KB zijn.

## Library-keuze: Hailo YOLOv8s-pose

| Optie | Pro | Con | Besluit |
|---|---|---|---|
| **A. Hailo YOLOv8s-pose** | ~27-30 fps op Pi 5, draait op Hailo-8L chip (0% Pi CPU), 17 COCO-keypoints, officieel ondersteund in `hailo-rpi5-examples` | Vereist werkende Hailo-stack (al in bouwplan v1 geïnstalleerd), HEF model (~15 MB download) | ✅ **Gebruik** |
| B. MediaPipe pose | Breed ondersteund, 33 keypoints | CPU-only op Pi 5 (geen Hailo-acceleratie beschikbaar — AlbertaBeef-Hailo-blog bevestigt dat pose-demo niet werkt). Rauwe fps op Pi 5 CPU: ~3-6 fps, te traag | ❌ Alternatief als Hailo stuk is |
| C. OpenCV HOG | Alleen person-detect, geen keypoints | Geen pose | ❌ Niet geschikt |

Dus: Hailo YOLOv8s-pose. Model via `hailo_model_zoo` of download direct uit `hailo-rpi5-examples`.

## Install-pakket (voorbeeld-commando's)

```bash
# Hailo-stack staat al op de Pi (uit bouwplan v1 install.sh).
# Pose-model halen uit officiële examples:
cd ~/anna-nova
git clone https://github.com/hailo-ai/hailo-rpi5-examples.git /tmp/hailo-examples
cp /tmp/hailo-examples/resources/yolov8s_pose.hef models/

# Python-deps die nog niet in venv zitten:
pip install hailo-platform==4.19.0 opencv-python-headless==4.10.0.84 \
            websockets==12.0 numpy==1.26.4
```

Versies gekozen op basis van compatibility-matrix oktober 2026 — pin exact of `install.sh` kan breken.

## Architectuur — data-flow

```
camera (libcamera-vid) ─> see.py ─┬─> Hailo YOLOv8s-pose ─> 17 keypoints ─┐
                                   │                                        ├─> websocket ──> achtergrond.js
                                   └─> downscale 64x48 ─> 3072 grijswaarden ┘           (face/index.html <canvas>)
```

**Websocket**: `face.py` draait al een websocket-server op `:8766` (uit commit a8b9fab). Breid het protocol uit met twee berichttypes:

```json
{"type": "stippen", "grid": [0.12, 0.08, 0.34, ...]}         // 3072 floats 0-1
{"type": "pose",    "pts": [[x,y,conf], [x,y,conf], ...]}    // 17 keypoints
```

`see.py` stuurt deze elke frame (~20 fps budget). Bij 20 fps + 2 KB payload = ~40 KB/s op localhost — triviaal.

**Alternatief voor websocket**: SSE (Server-Sent Events) is simpeler als er maar één richting data gaat (face.py → browser). Maar websocket is er al, dus hergebruik.

## Rendering in achtergrond.js

Canvas 1024×768 (of wat het Pi-scherm doet), 2 lagen:

### Laag 1 — stippenraster

```js
// 64x48 grid, elke stip = 1 cel. Cel-grootte = 1024/64 = 16 px.
function tekenStippen(ctx, grid) {
  ctx.clearRect(0, 0, 1024, 768);
  for (let y = 0; y < 48; y++) {
    for (let x = 0; x < 64; x++) {
      const v = grid[y * 64 + x];           // 0-1
      const r = 2 + v * 5;                  // kleine stip bij donker, groter bij fel
      ctx.fillStyle = `rgba(180, 180, 180, ${0.3 + v * 0.5})`;
      ctx.beginPath();
      ctx.arc(x * 16 + 8, y * 16 + 8, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}
```

### Laag 2 — pose-lijnen

COCO keypoints (17): 0 nose, 1 left_eye, 2 right_eye, 3 left_ear, 4 right_ear, 5 left_shoulder, 6 right_shoulder, 7 left_elbow, 8 right_elbow, 9 left_wrist, 10 right_wrist, 11 left_hip, 12 right_hip, 13 left_knee, 14 right_knee, 15 left_ankle, 16 right_ankle.

Verbindingen om te tekenen:

```js
const EDGES = [
  [5, 7], [7, 9],   [6, 8], [8, 10],   // armen
  [5, 6], [11, 12],                     // schouder-lijn, heup-lijn
  [5, 11], [6, 12],                     // romp-zijden
  [11, 13], [13, 15], [12, 14], [14, 16], // benen
  [0, 5], [0, 6]                        // nek (globaal)
];

function tekenPose(ctx, pts) {
  ctx.strokeStyle = 'rgba(200, 200, 200, 0.6)';
  ctx.lineWidth = 2;
  for (const [a, b] of EDGES) {
    if (pts[a][2] < 0.3 || pts[b][2] < 0.3) continue;  // conf-threshold
    ctx.beginPath();
    ctx.moveTo(pts[a][0] * 1024, pts[a][1] * 768);
    ctx.lineTo(pts[b][0] * 1024, pts[b][1] * 768);
    ctx.stroke();
  }
}
```

### Stijl

- Kleur: `rgba(200, 200, 200, 0.6)` (lichtgrijs, semi-transparant — laat de rust/luistert-vignet er doorheen schijnen)
- Lijndikte: 2 px (dun genoeg om niet dominant te zijn, dik genoeg om zichtbaar op 1024 px)
- Geen schaduwen, geen fillcolors op de pose — alleen contouren
- Bij RUST: pose en stippen aan (anders is het scherm dood). Bij SPREEKT: optioneel dimmen naar 30% alpha zodat de tekst leesbaar blijft.

## Performance-budget

| Stap | Tijd per frame | Loc |
|---|---|---|
| libcamera capture 720p | ~15 ms | Pi CPU (I/O) |
| Hailo YOLOv8s-pose | ~30-40 ms | Hailo-8L chip (0% Pi CPU) |
| Downscale 720p → 64×48 | ~2 ms | NumPy, Pi CPU |
| JSON serialize + ws send | ~1 ms | Pi CPU |
| Browser render (canvas) | ~5-10 ms | Pi GPU (Chromium) |
| **Totaal** | **~55 ms/frame = ~18 fps** | |

Dus **~18 fps werkbaar**. Bron 2 vraagt niet om 30 fps — pose + stippen op 15 fps is vloeiend genoeg voor een kunstwerk, zonder dat de Pi CPU volloopt met andere taken (wake, flow, speak, brain).

Als het haperig blijkt: laat stippen op 20 fps draaien (goedkoop), pose op 10 fps (duur).

## Privacy-check

Per frame verlaat `see.py`:
- 3072 floats (stippen) = ~24 KB uncompressed, ~2 KB als JSON-compacte floats
- 17 × 3 floats (pose) = ~400 bytes

**Nooit** het ruwe camerabeeld. **Nooit** een afbeelding op schijf (SSD is weg in bron 2). **Nooit** persoon-ID. Alleen anonieme grijstonen en skelet-punten die een halfseconde later weg zijn.

`see.py` zelf houdt 1 frame in RAM voor Hailo-inference, dan weg. Geen buffer, geen log.

## Test bij bouwstap 9

```bash
# Op de Pi, met echte camera + persoon vóór de lens:
cd ~/anna-nova && python3 -m anna.see --test-overlay
# → opent /tmp/overlay-preview.png met één frame stippen+pose op een 1024x768 canvas
```

Visuele check: zie je het silhouet in stippen? Lopen de pose-lijnen door schouders/heupen? Werkt het met 2 personen (pose multi-detect)?

## Timebox

Bron 2 bouwstap 9 geeft geen expliciete tijd, maar **~2 uur** is realistisch:
- Hailo model downloaden + opsetten: 30 min
- see.py uitbreiden met downscale + pose-extract: 45 min
- achtergrond.js tekenen: 30 min
- integratie-test: 15 min

Als Hailo faalt → pose-overlay overslaan, alleen stippenraster uit grijsframe (MediaPipe-vrij, puur OpenCV, 25 fps haalbaar).

## Sources

- [hailo-ai/hailo-rpi5-examples (basic pipelines doc)](https://github.com/hailo-ai/hailo-rpi5-examples/blob/main/doc/basic-pipelines.md)
- [Pose Estimation deepwiki Hailo](https://deepwiki.com/hailo-ai/hailo-rpi5-examples/3.3-pose-estimation)
- [YOLOv8 Pose on reComputer with Hailo-8L — Seeed benchmark](https://wiki.seeedstudio.com/yolov8_pose_estimation_on_recomputer_r1000_with_hailo_8l/)
- [Pi 5 + Hailo8L AI Fall Detection (~30 fps claim)](https://www.elektormagazine.com/labs/pi-5hailo8l-ai-powered-fall-identification-recording-project)
- [AlbertaBeef: Accelerating MediaPipe models on Pi 5 AI Kit](https://www.hackster.io/AlbertaBeef/accelerating-the-mediapipe-models-on-raspberry-pi-5-ai-kit-1698fe) *(bevestigt dat pose-demo nog niet werkt op Pi 5 CPU)*
- [DataRoot Labs: Hailo AI Kit Pi 5 setup](https://datarootlabs.com/blog/hailo-ai-kit-raspberry-pi-5-setup-and-computer-vision-pipelines)
