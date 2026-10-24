// Plotly charts for the signal inspector (section 1) and the error chart (section 6).
"use strict";

MARINE.charts = (function () {
  const NORMAL_BAND = [35, 50];
  const HISTORY_S = 300;
  const PLOT_CONFIG = { responsive: true, displaylogo: false };
  const pal = () => MARINE.content.palette;
  const threshold = () => MARINE.content.tracking_threshold_dbhz;

  function draw(id, data, layout) {
    Plotly.react(id, data, layout, PLOT_CONFIG);
  }

  function baseLayout(title, height, extra) {
    return Object.assign({
      title: { text: title, font: { size: 14 }, x: 0.01 },
      height: height || 280,
      margin: { l: 50, r: 10, t: 40, b: 40 },
      legend: { orientation: "h", y: -0.28 },
      paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
    }, extra || {});
  }

  function sats(S, t) {
    return S.sats[t].map(([id, az, el, cn0, tracked]) => ({ id, az, el, cn0, tracked: !!tracked }));
  }

  function window_(S, t) {
    const start = Math.max(0, t - HISTORY_S);
    const idx = [];
    for (let i = start; i <= t; i++) idx.push(i);
    return idx;
  }

  function meanCn0(S, t) {
    const values = sats(S, t).filter((s) => s.tracked).map((s) => s.cn0);
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  }

  // ------------------------------------------------------------ snapshot

  function sky(id, S, t, N) {
    const data = [];
    if (N) {
      const h = sats(N, t);
      data.push({ type: "scatterpolar", mode: "markers", name: "healthy receiver",
        r: h.map((s) => 90 - s.el), theta: h.map((s) => s.az),
        marker: { size: 14, color: "rgba(0,0,0,0)", line: { width: 2, color: pal().healthy } } });
    }
    const now = sats(S, t);
    data.push({ type: "scatterpolar", mode: "markers+text", name: "this second",
      r: now.map((s) => 90 - s.el), theta: now.map((s) => s.az),
      text: now.map((s) => String(s.id)), textposition: "top center",
      marker: { size: 11, color: now.map((s) => (s.tracked ? pal().accent : pal().muted)),
                line: { width: 2, color: "white" } },
      hovertemplate: "Satellite %{text}<br>azimuth %{theta:.0f}°<extra></extra>" });
    draw(id, data, baseLayout("Sky plot: where the signals come from", 340, {
      polar: {
        radialaxis: { range: [0, 90], tickvals: [0, 30, 60, 90], ticktext: ["90°", "60°", "30°", "0°"],
                      angle: 225, tickangle: 0, tickfont: { size: 9 } },
        angularaxis: { direction: "clockwise", rotation: 90, tickvals: [0, 90, 180, 270],
                       ticktext: ["N", "E", "S", "W"] },
      },
    }));
  }

  function cn0Bars(id, S, t, N) {
    const now = sats(S, t);
    const data = [{ type: "bar", name: "this second", x: now.map((s) => String(s.id)),
      y: now.map((s) => s.cn0),
      marker: { color: now.map((s) => (s.tracked ? pal().accent : pal().muted)) },
      hovertemplate: "Satellite %{x}: %{y:.1f} dB-Hz<extra></extra>" }];
    if (N) {
      const h = sats(N, t);
      data.push({ type: "scatter", mode: "markers", name: "healthy receiver",
        x: h.map((s) => String(s.id)), y: h.map((s) => s.cn0),
        marker: { symbol: "line-ew", size: 26, line: { width: 3, color: pal().healthy } } });
    }
    draw(id, data, baseLayout("Signal strength (C/N0) per satellite", 340, {
      yaxis: { range: [0, 60], title: { text: "C/N0 (dB-Hz)" } },
      xaxis: { title: { text: "satellite" }, type: "category" },
      shapes: [
        { type: "rect", xref: "paper", x0: 0, x1: 1, y0: NORMAL_BAND[0], y1: NORMAL_BAND[1],
          fillcolor: "rgba(0,131,0,0.10)", line: { width: 0 }, layer: "below" },
        { type: "line", xref: "paper", x0: 0, x1: 1, y0: threshold(), y1: threshold(),
          line: { dash: "dash", color: pal().muted } },
      ],
      annotations: [
        { text: "normal band 35-50", xref: "paper", x: 0, xanchor: "left", y: NORMAL_BAND[1],
          yanchor: "bottom", showarrow: false, font: { size: 11 } },
        { text: `tracking threshold ${threshold()}`, xref: "paper", x: 1, xanchor: "right",
          y: threshold(), yanchor: "top", showarrow: false, font: { size: 11 } },
      ],
    }));
  }

  // --------------------------------------------------------- time series

  function hline(y, color, dash, label, where) {
    return {
      shape: { type: "line", xref: "paper", x0: 0, x1: 1, y0: y, y1: y,
               line: { color, dash, width: 1 } },
      annotation: label ? { text: label, xref: "paper", x: where === "right" ? 1 : 0,
        xanchor: where === "right" ? "right" : "left", y, yanchor: "bottom", showarrow: false,
        font: { size: 11 } } : null,
    };
  }

  function withLines(layout, lines) {
    layout.shapes = lines.map((l) => l.shape);
    layout.annotations = lines.filter((l) => l.annotation).map((l) => l.annotation);
    return layout;
  }

  function cn0History(id, S, t, N) {
    const idx = window_(S, t);
    const ids = [...new Set(idx.flatMap((i) => S.sats[i].map((s) => s[0])))].sort((a, b) => a - b);
    const data = ids.map((satId) => ({
      type: "scatter", mode: "lines", name: `sat ${satId}`, showlegend: false, opacity: 0.35,
      x: idx, y: idx.map((i) => { const s = S.sats[i].find((v) => v[0] === satId); return s ? s[3] : null; }),
      line: { width: 1, color: pal().accent },
      hovertemplate: `sat ${satId}: %{y:.1f}<extra></extra>` }));
    data.push({ type: "scatter", mode: "lines", name: "mean (tracked)", x: idx,
      y: idx.map((i) => meanCn0(S, i)), line: { width: 3, color: pal().accent } });
    if (N) data.push({ type: "scatter", mode: "lines", name: "healthy mean", x: idx,
      y: idx.map((i) => meanCn0(N, i)), line: { width: 2, dash: "dash", color: pal().healthy } });
    draw(id, data, withLines(baseLayout("C/N0 of every satellite, last 5 minutes", 300, {
      yaxis: { range: [0, 60], title: { text: "dB-Hz" } } }),
      [hline(threshold(), pal().muted, "dot")]));
  }

  function noiseHistory(id, S, t, N) {
    const idx = window_(S, t);
    const cfg = MARINE.content.config;
    const data = [
      { type: "scatter", mode: "lines", name: "noise floor", x: idx, y: idx.map((i) => S.agc[i]),
        line: { width: 2, color: pal().accent } },
      { type: "scatter", mode: "lines", name: "learned normal", x: idx, y: idx.map((i) => S.b_agc[i]),
        line: { width: 1, color: pal().muted } },
      { type: "scatter", mode: "lines", name: `alarm (+${cfg.agc_jump_db} dB)`, x: idx,
        y: idx.map((i) => S.b_agc[i] + cfg.agc_jump_db),
        line: { width: 1, dash: "dash", color: pal().red_path } },
    ];
    if (N) data.push({ type: "scatter", mode: "lines", name: "healthy", x: idx,
      y: idx.map((i) => N.agc[i]), line: { width: 2, dash: "dash", color: pal().healthy } });
    draw(id, data, baseLayout("Noise floor, last 5 minutes", 300, { yaxis: { title: { text: "dB" } } }));
  }

  function countHistory(id, S, t, N) {
    const idx = window_(S, t);
    const data = [{ type: "scatter", mode: "lines", name: "tracked", x: idx,
      y: idx.map((i) => S.nsat[i]), line: { width: 2, color: pal().accent, shape: "hv" } }];
    if (N) data.push({ type: "scatter", mode: "lines", name: "healthy", x: idx,
      y: idx.map((i) => N.nsat[i]), line: { width: 2, dash: "dash", color: pal().healthy, shape: "hv" } });
    draw(id, data, withLines(baseLayout("Satellites tracked, last 5 minutes", 300, {
      yaxis: { range: [0, 13], title: { text: "satellites" } } }), [
      hline(4, pal().muted, "dot", "4 = fix", "left"),
      hline(5, "#008300", "dash", "5 = checkable", "right"),
    ]));
  }

  function jumps(S, idx) {
    return idx.map((i) => {
      if (i === 0 || S.gx[i] === null || S.gx[i - 1] === null) return null;
      return Math.hypot(S.gx[i] - S.gx[i - 1], S.gy[i] - S.gy[i - 1]);
    });
  }

  function jumpHistory(id, S, t, N) {
    const idx = window_(S, t);
    const data = [{ type: "scatter", mode: "lines", name: "GNSS jump", x: idx, y: jumps(S, idx),
      line: { width: 2, color: pal().accent } }];
    if (N) data.push({ type: "scatter", mode: "lines", name: "healthy", x: idx, y: jumps(N, idx),
      line: { width: 2, dash: "dash", color: pal().healthy } });
    const speed = S.speed[t];
    draw(id, data, withLines(baseLayout("GNSS position jump per second, last 5 minutes", 300, {
      yaxis: { title: { text: "metres per second" }, rangemode: "tozero" } }),
      [hline(speed, pal().muted, "dot", `ship speed ≈ ${speed.toFixed(1)} m/s`, "right")]));
  }

  // ------------------------------------------------------------ errors

  function errorChart(id, S, t) {
    const every = S.meta.voyage ? 10 : 1;
    const idx = [];
    for (let i = 0; i < S.state.length; i += every) idx.push(i);
    const m = S.meta;
    const shapes = [{ type: "line", x0: t, x1: t, yref: "paper", y0: 0, y1: 1,
                      line: { color: pal().truth, width: 1 } }];
    const annotations = [];
    if (m.event_start !== null) {
      shapes.push({ type: "rect", x0: m.event_start, x1: m.event_end, yref: "paper", y0: 0, y1: 1,
                    fillcolor: pal().event_shade, line: { width: 0 }, layer: "below" });
      annotations.push({ text: "event", x: m.event_start, xanchor: "left", yref: "paper", y: 1,
                         showarrow: false });
    }
    draw(id, [
      { type: "scatter", mode: "lines", name: "naive GNSS (believes everything)", x: idx,
        y: idx.map((i) => Math.max(S.nerr[i], 0.1)), line: { color: pal().red_path, width: 2 } },
      { type: "scatter", mode: "lines", name: "guard", x: idx,
        y: idx.map((i) => Math.max(S.gerr[i], 0.1)), line: { color: pal().green_path, width: 2 } },
    ], baseLayout("Position error over time: guard vs naive GNSS", 320, {
      yaxis: { type: "log", title: { text: "position error (m, log scale)" } },
      xaxis: { title: { text: "time (s)" } }, hovermode: "x unified", shapes, annotations,
      legend: { orientation: "h", y: 1.15, x: 1, xanchor: "right" },
    }));
  }

  return { sky, cn0Bars, cn0History, noiseHistory, countHistory, jumpHistory, errorChart, sats };
})();
