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

  // State-palette: elke toestand krijgt eigen kleur + animatie-stijl.
  // Komt uit document.body.className (face.html zet 'state-xxx').
  const THEMES = {
    sluimert:  { stip: "180, 60, 80",    key: "220, 90, 100",  puls: 0.08, draai: 0 },
    luistert:  { stip: "180, 220, 190",  key: "200, 230, 200", puls: 0.02, draai: 0 },
    denkt:     { stip: "200, 180, 140",  key: "244, 184, 96",  puls: 0.04, draai: 0.9 },
    spreekt:   { stip: "244, 160, 96",   key: "250, 190, 120", puls: 0.18, draai: 0 },
    afrekenen: { stip: "240, 230, 200",  key: "250, 240, 210", puls: 0.05, draai: 0 },
    print:     { stip: "240, 230, 200",  key: "250, 240, 210", puls: 0.10, draai: 0 },
    knopmodus: { stip: "180, 180, 190",  key: "220, 220, 230", puls: 0.03, draai: 0 },
    offline:   { stip: "120, 50, 50",    key: "160, 70, 70",   puls: 0.0,  draai: 0 },
  };
  const DEFAULT_THEME = THEMES.sluimert;

  function currentTheme() {
    const cls = (document.body && document.body.className) || "";
    for (const key in THEMES) {
      if (cls.indexOf("state-" + key) !== -1) return THEMES[key];
    }
    return DEFAULT_THEME;
  }

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

  // --- render loop ---------------------------------------------------------
  function tekenLus(ts) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const theme = currentTheme();
    // Puls: zacht sinusoidaal rond 1.0, amplitude uit theme
    const t = (ts || 0) / 1000;
    const pulse = 1 + Math.sin(t * 2.4) * theme.puls;
    if (latestStippen) tekenStippen(latestStippen, theme, pulse);
    if (latestPose)    tekenPose(latestPose, theme, t);
    requestAnimationFrame(tekenLus);
  }

  function tekenStippen(grid, theme, pulse) {
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) {
        const v = grid[y * COLS + x] || 0;
        if (v < 0.02) continue;
        const r = (1 + v * 4) * pulse;
        ctx.fillStyle = `rgba(${theme.stip}, ${(0.2 + v * 0.55) * pulse})`;
        ctx.beginPath();
        ctx.arc(x * cellW + cellW / 2, y * cellH + cellH / 2, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  function tekenPose(pts, theme, t) {
    // Keypoint-stippen in theme-kleur. Bij 'denkt' draaien ze in cirkel om
    // het zwaartepunt van de persoon (= het "nadenken" animeert).
    const draai = theme.draai;
    let cx = 0, cy = 0, n = 0;
    if (draai) {
      for (const p of pts) {
        if (!p || (p[2] || 0) < 0.3) continue;
        cx += p[0]; cy += p[1]; n++;
      }
      if (n) { cx /= n; cy /= n; }
    }
    const spin = draai ? t * draai : 0;
    const pulseAlpha = 0.85 + Math.sin(t * 3) * theme.puls * 2;
    ctx.fillStyle = `rgba(${theme.key}, ${Math.min(1, pulseAlpha)})`;
    for (const p of pts) {
      if (!p || (p[2] || 0) < 0.3) continue;
      let px = p[0], py = p[1];
      if (draai && n) {
        // Roteer elk keypoint om zwaartepunt (zachte orbit)
        const dx = px - cx, dy = py - cy;
        const cs = Math.cos(spin), sn = Math.sin(spin);
        px = cx + dx * cs - dy * sn;
        py = cy + dx * sn + dy * cs;
      }
      const r = 4 * (1 + theme.puls * 0.5);
      ctx.beginPath();
      ctx.arc(px * canvas.width, py * canvas.height, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
