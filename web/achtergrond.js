// achtergrond.js — stippenraster 64×48 + pose-lijnen achter Anna's cel.
//
// Leest websocket data uit face.py op :8766. Twee berichttypes:
//   {"type": "stippen", "grid": [3072 floats 0-1]}
//   {"type": "pose",    "pts": [[x,y,conf], ...]}  // 17 COCO keypoints
//
// Koppel aan face/index.html:
//   <canvas id="achtergrond"></canvas>
//   <script src="achtergrond.js"></script>
//
// Demo-modus: zet DEMO=1 in URL (?demo=1) → genereer mock-data lokaal, geen ws.
//
// Privacy: ontvangt alleen grijswaarden + keypoints, nooit beeld.

(function () {
  "use strict";

  const COLS = 64, ROWS = 48;
  const EDGES = [
    [5, 7], [7, 9],   [6, 8], [8, 10],      // armen
    [5, 6], [11, 12],                        // schouder/heup-lijn
    [5, 11], [6, 12],                        // romp-zijden
    [11, 13], [13, 15], [12, 14], [14, 16],  // benen
    [0, 5], [0, 6],                          // nek (globaal)
  ];
  const DEMO = new URLSearchParams(location.search).has("demo");

  let canvas, ctx, cellW, cellH;
  let latestStippen = null, latestPose = null;

  function init() {
    canvas = document.getElementById("achtergrond");
    if (!canvas) {
      console.warn("[achtergrond] geen <canvas id='achtergrond'> gevonden");
      return;
    }
    resize();
    window.addEventListener("resize", resize);

    if (DEMO) {
      startDemo();
    } else {
      connectWs();
    }

    tekenLus();
  }

  function resize() {
    const r = canvas.getBoundingClientRect();
    canvas.width = r.width;
    canvas.height = r.height;
    cellW = canvas.width / COLS;
    cellH = canvas.height / ROWS;
    ctx = canvas.getContext("2d");
  }

  function connectWs() {
    const url = (location.protocol === "https:" ? "wss" : "ws") +
                "://" + location.hostname + ":8766";
    const ws = new WebSocket(url);
    ws.onmessage = (e) => {
      try {
        const m = JSON.parse(e.data);
        if (m.type === "stippen" && Array.isArray(m.grid)) latestStippen = m.grid;
        if (m.type === "pose" && Array.isArray(m.pts))    latestPose    = m.pts;
      } catch (err) {
        console.error("[achtergrond] bad msg", err);
      }
    };
    ws.onclose = () => setTimeout(connectWs, 2000);
    ws.onerror = () => ws.close();
  }

  // --- demo: random stippen-noise + "ademende" pose in het midden ----------
  function startDemo() {
    console.info("[achtergrond] DEMO-modus — mock pose + stippen");
    const t0 = performance.now();
    setInterval(() => {
      const t = (performance.now() - t0) / 1000;
      // Stippen: random noise met een "blob" in het midden die beweegt
      const grid = new Array(COLS * ROWS);
      const cx = COLS / 2 + Math.sin(t * 0.3) * 12;
      const cy = ROWS / 2 + Math.cos(t * 0.5) * 4;
      for (let y = 0; y < ROWS; y++) {
        for (let x = 0; x < COLS; x++) {
          const dx = x - cx, dy = y - cy;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const blob = Math.max(0, 1 - dist / 14);
          const noise = Math.random() * 0.15;
          grid[y * COLS + x] = Math.min(1, blob * 0.8 + noise);
        }
      }
      latestStippen = grid;
      // Pose: een "staand persoon" die subtiel heen-en-weer deint
      const cx2 = 0.5 + Math.sin(t * 0.4) * 0.05;
      const sh = 0.18, hp = 0.12;  // schouder-offset, heup-offset
      latestPose = [
        [cx2,            0.18, 0.9],   // 0 nose
        [cx2 - 0.015,    0.16, 0.9],   // 1 left_eye
        [cx2 + 0.015,    0.16, 0.9],   // 2 right_eye
        [cx2 - 0.025,    0.17, 0.9],   // 3 left_ear
        [cx2 + 0.025,    0.17, 0.9],   // 4 right_ear
        [cx2 - sh,       0.28, 0.9],   // 5 left_shoulder
        [cx2 + sh,       0.28, 0.9],   // 6 right_shoulder
        [cx2 - sh - 0.02 + Math.sin(t*1.2)*0.03, 0.40, 0.9],  // 7 left_elbow
        [cx2 + sh + 0.02 - Math.sin(t*1.2)*0.03, 0.40, 0.9],  // 8 right_elbow
        [cx2 - sh - 0.05,0.52, 0.85],  // 9 left_wrist
        [cx2 + sh + 0.05,0.52, 0.85],  // 10 right_wrist
        [cx2 - hp,       0.55, 0.9],   // 11 left_hip
        [cx2 + hp,       0.55, 0.9],   // 12 right_hip
        [cx2 - hp,       0.72, 0.85],  // 13 left_knee
        [cx2 + hp,       0.72, 0.85],  // 14 right_knee
        [cx2 - hp,       0.92, 0.8],   // 15 left_ankle
        [cx2 + hp,       0.92, 0.8],   // 16 right_ankle
      ];
    }, 100);  // 10 fps mock
  }

  // --- render loop (requestAnimationFrame, ~60 fps draw, data update eigen tempo)
  function tekenLus() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (latestStippen) tekenStippen(latestStippen);
    if (latestPose)    tekenPose(latestPose);
    requestAnimationFrame(tekenLus);
  }

  function tekenStippen(grid) {
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) {
        const v = grid[y * COLS + x] || 0;
        if (v < 0.02) continue;
        const r = 1 + v * 4;
        ctx.fillStyle = `rgba(200, 200, 200, ${0.2 + v * 0.55})`;
        ctx.beginPath();
        ctx.arc(x * cellW + cellW / 2, y * cellH + cellH / 2, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  function tekenPose(pts) {
    // Geen lijnen tussen keypoints — alleen de gouden stippen zelf.
    // (Skelet-visualisatie oogde als een "poppetje" wat te letterlijk was.)
    ctx.fillStyle = "rgba(244, 184, 96, 0.85)";  // goud-accent
    for (const p of pts) {
      if (!p || (p[2] || 0) < 0.3) continue;
      ctx.beginPath();
      ctx.arc(p[0] * canvas.width, p[1] * canvas.height, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
