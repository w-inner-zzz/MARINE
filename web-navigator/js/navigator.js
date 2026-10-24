// Bridge view: status, instructions, vital readings, checks, map and GPS signal at a
// glance, with a choice of navigation aid (none, pseudolites, nearby ships).
// Uses only files inside web-navigator/ (data/ is written by export_web.py).
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const C = () => NAV.content;
  const pal = () => NAV.content.palette;
  const M_PER_DEG = 111195;
  const SEA_SCALE = [[0, "#d6eaf8"], [1, "#1b4f72"]];
  const KNOT_MPS = 0.514444;
  const TICK_MS = 250;
  const SPEEDS = {
    voyage: [[10, "10×"], [60, "60× (1 min/s)"], [240, "240× (4 min/s)"], [600, "600× (10 min/s)"]],
    short: [[1, "1× real time"], [5, "5×"], [10, "10×"], [30, "30×"]],
  };
  const HARD = ["LOST", "JAMMING", "SPOOFING"];
  const SIGNAL_WINDOW_S = 300;

  // Plain-language status of the received GPS signal, from the raw verdict.
  const SIGNAL_STATUS = {
    OK: ["NORMAL", "#008300"],
    DEGRADED: ["NOISY", "#eda100"],
    LOST: ["WEAK", "#e34948"],
    JAMMING: ["WEAK", "#e34948"],
    SPOOFING: ["TAMPERED", "#6250d6"],
  };

  // Extra instruction while the chosen aid is navigating for us.
  const AID_INSTRUCTION = {
    pseudolites: "Position from shore stations (pseudolites)",
    peers: "Position from nearby ships: unverified, cross-check radar",
    seabed: "Position from seabed matching (sounder + chart)",
  };
  const SEABED_LOOKBACK_S = 1800;

  // One short line per state, shown under the big status word.
  const STATE_LINE = {
    TRUSTED: "GNSS position OK",
    DEGRADED: "GNSS noisy: blended with dead reckoning",
    RECOVERING: "GNSS clean again: waiting before trusting it",
    LOST: "No satellite position: backup navigation",
    JAMMING: "Signals jammed: backup navigation",
    SPOOFING: "Fake position: GNSS ignored",
  };

  // Tile label, unit, and whether the value must stay above ("min") or below ("max") the limit.
  const CHECK_TILES = {
    "Noise floor": ["Noise", "dB", "max", 1, true],
    "Satellite count": ["Satellites", "", "min", 0],
    "Signal strength drop": ["Signal drop", "dB", "max", 1],
    "Signal spread": ["Signal spread", "dB", "min", 1],
    "Signal strength rise": ["Signal rise", "dB", "max", 1, true],
    "Clock consistency": ["Clock", "s", "max", 3],
    "Position vs dead reckoning": ["Position jump", "m", "max", 0],
    "Position on water": ["On water", "", null, 0],
    "Depth vs chart": ["Depth match", "m", "max", 1],
    "Position agreement": ["Agreement", "m", "max", 1],
  };

  const view = { mode: "voyage", key: "normal", solution: "none", t: 0, S: null, timer: null,
                 transitions: [], mapView: "ship", showTruth: false, pending: false };

  const stateAt = (t) => C().states[view.S.state[t]];

  // ------------------------------------------------------------ formatting

  function clock(seconds) {
    const s = Math.round(seconds);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
  }

  function bits(mask) {
    let n = 0;
    for (let m = mask; m; m &= m - 1) n++;
    return n;
  }

  function confidence(uncertaintyM) {
    if (uncertaintyM <= 10) return "HIGH";
    if (uncertaintyM <= 50) return "MEDIUM";
    return "LOW";
  }


  // ------------------------------------------------------------- panels

  function renderStatus(S, t) {
    const state = stateAt(t);
    const color = pal().states[state];
    document.documentElement.style.setProperty("--state", color);
    $("status").classList.toggle("alarm", HARD.includes(state));
    $("state").textContent = state;
    $("state-line").textContent = state === "RECOVERING"
      ? `GNSS clean ${S.clean[t]}/${S.need[t]} s: still on backup`
      : STATE_LINE[state];
    $("confidence").innerHTML = `${confidence(S.unc[t])}<small style="display:block;font-weight:500;` +
      `font-size:0.85rem;color:var(--muted)">±${S.unc[t].toFixed(0)} m</small>`;
    const cn0 = S.cn0[t];
    const vitals = [
      ["Position", NAV.fmtLatLon(S.lat[t], S.lon[t]), true],
      ["Heading", `${((S.heading[t] % 360) + 360) % 360 | 0}°`],
      ["Speed", `${(S.speed[t] / KNOT_MPS).toFixed(1)} kn`],
      ["Satellites", `${S.nsat[t]}`],
      ["Signal", cn0 === null ? "none" : `${cn0.toFixed(0)} dB-Hz`],
      ["Noise", `${S.agc[t].toFixed(1)} dB`],
      ["Aid", aidStatus(S, t)],
    ];
    $("vitals").innerHTML = vitals.map(([k, v, wide]) =>
      `<div class="vital${wide ? " wide" : ""}"><span>${k}</span><b>${NAV.escape(v)}</b></div>`).join("");
  }

  // e.g. "6 stations · in use", "2/4 ships used", "Off".
  function aidStatus(S, t) {
    const solution = S.meta.solution;
    if (solution === "none") return "Off";
    const inUse = S.aid_used[t] > 0;
    const standby = stateAt(t) === "TRUSTED" || stateAt(t) === "DEGRADED";
    if (solution === "pseudolites") {
      const heard = bits(S.stations[t]);
      if (!S.aid_offered[t]) return `${heard} stations · no fix`;
      return `${heard} stations · ${inUse ? "in use" : standby ? "standby" : "rejected"}`;
    }
    if (solution === "seabed") {
      if (standby) return "standby";
      const last = lastSeabed(S, t);
      if (!last) return "collecting soundings";
      if (last.fix === 0) return "no clear match";
      const [, , east, north, used] = last.fix;
      const fmt = (v) => (v === null ? "?" : `±${v}`);
      return `fix ${fmt(east)}/${fmt(north)} m · ${used ? "used" : "rejected"}`;
    }
    const inRadar = S.peers[t].filter((p) => p[2]).length;
    if (standby) return `${inRadar} ships · standby`;
    return `${bits(S.peers_used[t])}/${inRadar} ships used`;
  }

  // Latest seabed match attempt at or before t: { t, fix } or null.
  function lastSeabed(S, t) {
    for (let i = t; i >= Math.max(0, t - SEABED_LOOKBACK_S); i--) {
      if (S.seabed[i] !== null) return { t: i, fix: S.seabed[i] };
    }
    return null;
  }

  function computeTransitions(S) {
    const out = [];
    S.state.forEach((code, t) => {
      if (t === 0 || code !== S.state[t - 1]) out.push({ t, state: C().states[code] });
    });
    return out;
  }

  function instructionLines(state) {
    const a = C().actions[state];
    const lines = [a.autopilot_mode, `Speed: ${a.recommended_speed_kn}`, a.crew_instructions[0]];
    const aid = AID_INSTRUCTION[view.solution];
    if (aid && state !== "TRUSTED" && state !== "DEGRADED") lines.push(aid);
    return lines;
  }

  function renderInstructions(t) {
    const shown = view.transitions.filter((x) => x.t <= t).slice(-6).reverse();
    $("instructions").innerHTML = shown.map((x, i) => {
      const color = pal().states[x.state];
      return `<li class="${i === 0 ? "now" : ""}" style="border-left-color:${color};--entry:${color}">
        <span class="when">${clock(x.t)}</span><span class="chip" style="background:${color}">${x.state}</span>
        <ul>${instructionLines(x.state).map((l) => `<li>${NAV.escape(l)}</li>`).join("")}</ul></li>`;
    }).join("");
  }

  function reading(name, value, threshold, passed) {
    const [, unit, kind, digits, signed] = CHECK_TILES[name];
    if (kind === null) return passed === null ? "no data" : passed ? "yes" : "NO";
    if (value === null) return "no data";
    if (unit === "m" && Math.abs(value) >= 1000) {
      return `${(value / 1000).toFixed(1)} km · ${kind} ${threshold.toFixed(digits)} m`;
    }
    const v = (signed && value >= 0 ? "+" : "") + value.toFixed(digits);
    return `${v}${unit ? " " + unit : ""} · ${kind} ${threshold.toFixed(digits)}`;
  }

  function renderChecks(S, t) {
    $("checks").innerHTML = S.checks[t].map(([passed, value, threshold], i) => {
      const name = C().checks[i].name;
      const cls = passed === null ? "skip" : passed ? "ok" : "bad";
      return `<div class="check ${cls}" title="${NAV.escape(C().checks[i].if_fails)}">
        <span>${CHECK_TILES[name][0]}</span>
        <span class="reading">${NAV.escape(reading(name, value, threshold, passed))}</span></div>`;
    }).join("");
  }

  // ---------------------------------------------------------------- map

  function circle(lat, lon, radiusM) {
    const x = [], y = [];
    for (let k = 0; k <= 60; k++) {
      const a = 2 * Math.PI * k / 60;
      x.push(lon + radiusM * Math.cos(a) / (M_PER_DEG * Math.cos(lat * Math.PI / 180)));
      y.push(lat + radiusM * Math.sin(a) / M_PER_DEG);
    }
    return { x, y };
  }

  // A view around the points, widened to roughly the shape of the plot.
  function bounds(points, marginDeg, minSpanDeg, widthToHeight) {
    const lats = points.map((p) => p[0]), lons = points.map((p) => p[1]);
    const latC = (Math.min(...lats) + Math.max(...lats)) / 2;
    const lonC = (Math.min(...lons) + Math.max(...lons)) / 2;
    const shrink = Math.cos(latC * Math.PI / 180);
    let latHalf = Math.max((Math.max(...lats) - Math.min(...lats)) / 2 + marginDeg, minSpanDeg / 2);
    let lonHalf = Math.max((Math.max(...lons) - Math.min(...lons)) / 2 + marginDeg / shrink, minSpanDeg);
    lonHalf = Math.max(lonHalf, latHalf * widthToHeight / shrink);
    latHalf = Math.max(latHalf, lonHalf * shrink / widthToHeight);
    return [[latC - latHalf, latC + latHalf], [lonC - lonHalf, lonC + lonHalf]];
  }

  // Sea depth (smoothed) and land from the chart grid, cropped to the view.
  function depthBackground(latRange, lonRange) {
    const g = C().route_grid;
    const pick = (n, origin, step, lo, hi) => [...Array(n).keys()]
      .filter((i) => origin + i * step >= lo - 0.02 && origin + i * step <= hi + 0.02);
    const rows = pick(g.depth.length, g.lat0, g.dlat, ...latRange);
    const cols = pick(g.depth[0].length, g.lon0, g.dlon, ...lonRange);
    if (!rows.length || !cols.length) return [];
    const every = Math.max(1, Math.ceil(Math.max(rows.length, cols.length) / 200));
    const R = rows.filter((_, i) => i % every === 0), Cs = cols.filter((_, i) => i % every === 0);
    const lats = R.map((r) => g.lat0 + r * g.dlat), lons = Cs.map((c) => g.lon0 + c * g.dlon);
    const isLand = (r, c) => g.depth[r][c] === 255;
    return [
      { type: "heatmap", x: lons, y: lats, zsmooth: "best", showscale: false, hoverinfo: "skip",
        z: R.map((r) => Cs.map((c) => (isLand(r, c) ? null : g.depth[r][c]))),
        colorscale: SEA_SCALE, zmin: 0, zmax: 100 },
      { type: "heatmap", x: lons, y: lats, showscale: false, hoverinfo: "skip",
        z: R.map((r) => Cs.map((c) => (isLand(r, c) ? 1 : null))),
        colorscale: [[0, pal().land], [1, pal().land]] },
    ];
  }

  function segment(S, t0, t1, latKey, lonKey, keep) {
    const x = [], y = [];
    const step = S.meta.voyage ? 5 : 1;
    for (let t = t0; t <= t1; t += step) {
      if (keep(t) && S[latKey][t] !== null) { x.push(S[lonKey][t]); y.push(S[latKey][t]); }
      else if (y.length && y[y.length - 1] !== null) { x.push(null); y.push(null); }
    }
    return { x, y };
  }

  // "ship": a few km around the ship. "route": everything drawn so far, including
  // the rejected GNSS positions (which may be far away).
  function mapRange(S, t) {
    const lat = S.lat[t], lon = S.lon[t];
    if (view.mapView === "route") {
      const pts = [[lat, lon]];
      for (let i = 0; i <= t; i += 30) {
        pts.push([S.lat[i], S.lon[i]]);
        if (stateAt(i) !== "TRUSTED" && S.glat[i] !== null) pts.push([S.glat[i], S.glon[i]]);
        if (view.showTruth) pts.push([S.tlat[i], S.tlon[i]]);
      }
      if (S.peers) S.peers[t].forEach(([plat, plon]) => pts.push([plat, plon]));
      return bounds(pts, 0.01, 0.02, 2.2);
    }
    let halfM = S.meta.solution === "peers" ? 9000 : 3000;  // keep nearby ships in view
    if (view.showTruth) halfM = Math.max(halfM, 1.4 * S.gerr[t]);  // keep the true ship in view
    const dLat = halfM / 111195, dLon = dLat / Math.cos(lat * Math.PI / 180);
    return [[lat - dLat * 0.45, lat + dLat * 0.45], [lon - dLon, lon + dLon]];
  }

  function renderMap(S, t) {
    const [latRange, lonRange] = mapRange(S, t);
    const trusted = (i) => stateAt(i) === "TRUSTED";
    const start = view.mapView === "route" ? 0 : Math.max(0, t - 1800);
    const traces = S.meta.voyage ? depthBackground(latRange, lonRange) : [];
    const track = segment(S, start, t, "lat", "lon", trusted);
    const backup = segment(S, start, t, "lat", "lon", (i) => !trusted(i));
    const gnss = segment(S, start, t, "glat", "glon", (i) => !trusted(i));
    const ring = circle(S.lat[t], S.lon[t], S.unc[t]);
    const color = pal().states[stateAt(t)];
    traces.push(
      { type: "scatter", mode: "lines", x: track.x, y: track.y, line: { color: pal().ship_track, width: 3 } },
      { type: "scatter", mode: "lines", x: backup.x, y: backup.y, line: { color: pal().green_path, width: 3 } },
      { type: "scatter", mode: "lines", x: gnss.x, y: gnss.y, line: { color: pal().red_path, width: 2, dash: "dot" } },
      { type: "scatter", mode: "lines", x: ring.x, y: ring.y, fill: "toself", hoverinfo: "skip",
        line: { color, width: 1 }, fillcolor: "rgba(0,0,0,0.08)" },
    );
    traces.push(...aidTraces(S, t));
    if (view.showTruth) traces.push(...truthTraces(S, start, t));
    traces.push(
      { type: "scatter", mode: "markers", x: [S.lon[t]], y: [S.lat[t]], hoverinfo: "skip",
        marker: { symbol: "arrow", size: 30, angle: S.heading[t], color, line: { width: 2, color: "white" } } },
    );
    const layout = {
      height: 380, margin: { l: 55, r: 10, t: 10, b: 40 }, showlegend: false,
      paper_bgcolor: "#ffffff", plot_bgcolor: "#d6eaf8",
      xaxis: { range: lonRange, title: { text: "longitude (° E)" }, constrain: "domain" },
      yaxis: { range: latRange, title: { text: "latitude (° N)" }, constrain: "domain", scaleanchor: "x",
               scaleratio: 1 / Math.cos(S.lat[t] * Math.PI / 180) },
    };
    if (!S.meta.voyage) {
      layout.shapes = [{ type: "rect", x0: lonRange[0], x1: lonRange[1], y0: C().coast_lat_short,
                         y1: latRange[1] + 1, fillcolor: pal().land, line: { width: 0 }, layer: "below" }];
    }
    Plotly.react("map", traces, layout, { responsive: true, displaylogo: false });
  }

  // Shore stations (with ranging lines to the ones heard) or nearby ships at
  // their broadcast positions (green = used, red = rejected, grey = out of radar).
  function aidTraces(S, t) {
    const solution = S.meta.solution;
    const lat = S.lat[t], lon = S.lon[t];
    if (solution === "pseudolites") {
      const heard = C().stations.map((_, i) => !!(S.stations[t] & (1 << i)));
      const inUse = S.aid_used[t] > 0;
      const lines = { x: [], y: [] };
      C().stations.forEach((st, i) => {
        if (heard[i]) { lines.x.push(lon, st.lon, null); lines.y.push(lat, st.lat, null); }
      });
      return [
        { type: "scatter", mode: "lines", x: lines.x, y: lines.y, hoverinfo: "skip",
          line: { color: inUse ? "#1b4f72" : "#8a8986", width: 1, dash: "dot" } },
        { type: "scatter", mode: "markers+text", x: C().stations.map((s) => s.lon),
          y: C().stations.map((s) => s.lat), text: C().stations.map((s) => s.name),
          textposition: "top center", textfont: { size: 11 }, hoverinfo: "text",
          marker: { symbol: "triangle-up", size: 13, line: { width: 2, color: "#1b4f72" },
                    color: heard.map((h) => (h ? "#1b4f72" : "#ffffff")) } },
      ];
    }
    if (solution === "peers") {
      const peers = S.peers[t];
      const colour = peers.map(([, , inRadar], i) =>
        !inRadar ? "#8a8986" : S.peers_used[t] & (1 << i) ? "#008300" : "#e34948");
      const lines = { x: [], y: [] };
      peers.forEach(([plat, plon, inRadar]) => {
        if (inRadar) { lines.x.push(lon, plon, null); lines.y.push(lat, plat, null); }
      });
      return [
        { type: "scatter", mode: "lines", x: lines.x, y: lines.y, hoverinfo: "skip",
          line: { color: "#8a8986", width: 1, dash: "dot" } },
        { type: "scatter", mode: "markers+text", x: peers.map((p) => p[1]), y: peers.map((p) => p[0]),
          text: C().peers, textposition: "top center", textfont: { size: 11 }, hoverinfo: "text",
          marker: { symbol: "circle", size: 13, color: colour, line: { width: 2, color: "white" } } },
      ];
    }
    if (solution === "seabed") {
      const fixes = [];
      for (let i = Math.max(0, t - SEABED_LOOKBACK_S); i <= t; i++) {
        if (Array.isArray(S.seabed[i])) fixes.push(S.seabed[i]);
      }
      return [{ type: "scatter", mode: "markers", x: fixes.map((f) => f[1]), y: fixes.map((f) => f[0]),
        hovertemplate: "seabed fix<extra></extra>",
        marker: { symbol: "diamond", size: 12, line: { width: 2, color: "white" },
                  color: fixes.map((f) => (f[4] ? "#1baf7a" : "#e34948")) } }];
    }
    return [];
  }

  // ------------------------------------------------------------ accuracy

  // Whole-run error curves, built once per loaded scenario.
  function accuracySeries(S) {
    const every = S.meta.voyage ? 10 : 1;
    const t = [], err = [], claimed = [];
    for (let i = 0; i < S.gerr.length; i += every) {
      t.push(i); err.push(Math.max(S.gerr[i], 0.1)); claimed.push(S.unc[i]);
    }
    return { t, err, claimed };
  }

  function renderAccuracy(S, t) {
    const err = S.gerr[t], claimed = S.unc[t];
    const fmt = (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)} km` : `${v.toFixed(0)} m`);
    $("acc-error").textContent = fmt(err);
    $("acc-claimed").textContent = `±${fmt(claimed)}`;
    $("acc-method").textContent = C().solutions.find((x) => x.key === S.meta.solution).title;
    const [label, colour] = err <= claimed ? ["WITHIN ESTIMATE", "#008300"]
      : err <= 2 * claimed ? ["SLIGHTLY OFF", "#eda100"] : ["WORSE THAN IT THINKS", "#e34948"];
    $("accuracy-badge").textContent = label;
    $("accuracy-badge").style.background = colour;

    const series = view.accuracy;
    const m = S.meta;
    const shapes = [{ type: "line", x0: t, x1: t, yref: "paper", y0: 0, y1: 1,
                      line: { color: "#1d2733", width: 2 } }];
    if (m.event_start !== null) {
      shapes.push({ type: "rect", x0: m.event_start, x1: m.event_end, yref: "paper", y0: 0, y1: 1,
                    fillcolor: "rgba(150,150,150,0.18)", line: { width: 0 }, layer: "below" });
    }
    Plotly.react("accuracy-chart", [
      { type: "scatter", mode: "lines", name: "ship's own estimate (±)", x: series.t, y: series.claimed,
        line: { color: "#8a8986", width: 2, dash: "dash" } },
      { type: "scatter", mode: "lines", name: "actual error", x: series.t, y: series.err,
        line: { color: "#2a78d6", width: 2 } },
    ], {
      height: 240, margin: { l: 50, r: 10, t: 10, b: 35 }, shapes,
      legend: { orientation: "h", y: 1.12, x: 0 }, paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
      xaxis: { title: { text: "time (s)" } },
      yaxis: { type: "log", title: { text: "metres" }, tickvals: [0.1, 1, 10, 100, 1000, 10000],
               ticktext: ["0.1", "1", "10", "100", "1 km", "10 km"] },
    }, { responsive: true, displaylogo: false });

    const rows = C().accuracy[view.mode][view.key];
    $("accuracy-table").innerHTML = `<table><caption>All 4 methods, this scenario
      (${m.event_start === null ? "whole run" : "during the event"})</caption>
      <tr><th>Method</th><th>Average</th><th>Worst</th><th>Within estimate</th></tr>
      ${C().solutions.map((sol) => {
        const a = rows[sol.key];
        return `<tr class="${sol.key === S.meta.solution ? "current" : ""}"><td>${NAV.escape(sol.title)}</td>
          <td>${fmt(a.mean_m)}</td><td>${fmt(a.worst_m)}</td><td>${a.within_pct}%</td></tr>`;
      }).join("")}</table>`;
  }

  // Simulation only: where the ship really is (a real crew cannot see this).
  function truthTraces(S, start, t) {
    const truth = segment(S, start, t, "tlat", "tlon", () => true);
    const err = S.gerr[t];
    const label = err >= 1000 ? `${(err / 1000).toFixed(1)} km` : `${err.toFixed(0)} m`;
    return [
      { type: "scatter", mode: "lines", x: truth.x, y: truth.y, hoverinfo: "skip",
        line: { color: "#111111", width: 2, dash: "dot" } },
      { type: "scatter", mode: "markers+text", x: [S.tlon[t]], y: [S.tlat[t]], hoverinfo: "skip",
        text: [`true position · off by ${label}`], textposition: "bottom center",
        textfont: { size: 12, color: "#111111" },
        marker: { symbol: "arrow", size: 26, angle: S.heading[t], color: "rgba(255,255,255,0.6)",
                  line: { width: 2, color: "#111111" } } },
    ];
  }

  // ---------------------------------------------------------- GPS signal

  function signalClass(S, i) {
    const verdict = C().verdicts[S.verdict[i]];
    if (S.sig[i].every((v) => v === null)) return ["NO SIGNAL", "#e34948"];
    return SIGNAL_STATUS[verdict];
  }

  function renderSignal(S, t) {
    const start = Math.max(0, t - SIGNAL_WINDOW_S);
    const idx = [];
    for (let i = start; i <= t; i++) idx.push(i);
    const ago = idx.map((i) => i - t);
    const traces = [];
    for (let k = 0; k < S.sig[0].length; k++) {
      traces.push({ type: "scatter", mode: "lines", x: ago, y: idx.map((i) => S.sig[i][k]),
        line: { width: 1, color: "#2a78d6" }, opacity: 0.35, hoverinfo: "skip" });
    }
    traces.push({ type: "scatter", mode: "lines", x: ago, y: idx.map((i) => S.cn0[i]),
      line: { width: 3, color: "#1d2733" }, hovertemplate: "%{y:.0f} dB-Hz<extra></extra>" });

    // Shade the stretches where the signal was not normal.
    const shapes = [
      { type: "rect", xref: "paper", x0: 0, x1: 1, y0: 35, y1: 50, fillcolor: "rgba(0,131,0,0.10)",
        line: { width: 0 }, layer: "below" },
      { type: "line", xref: "paper", x0: 0, x1: 1, y0: 28, y1: 28, line: { color: "#8a8986", dash: "dash", width: 1 } },
    ];
    let runStart = 0;
    for (let j = 1; j <= idx.length; j++) {
      const label = signalClass(S, idx[runStart])[0];
      if (j < idx.length && signalClass(S, idx[j])[0] === label) continue;
      if (label !== "NORMAL") {
        shapes.push({ type: "rect", yref: "paper", y0: 0, y1: 1, x0: ago[runStart] - 0.5,
          x1: ago[j - 1] + 0.5, fillcolor: signalClass(S, idx[runStart])[1], opacity: 0.18,
          line: { width: 0 }, layer: "below" });
      }
      runStart = j;
    }
    Plotly.react("signal", traces, {
      height: 380, margin: { l: 45, r: 10, t: 10, b: 40 }, showlegend: false,
      paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", shapes,
      xaxis: { range: [-SIGNAL_WINDOW_S, 0], title: { text: "seconds ago" } },
      yaxis: { range: [0, 60], title: { text: "signal strength (dB-Hz)" } },
    }, { responsive: true, displaylogo: false });

    const [label, colour] = signalClass(S, t);
    $("signal-status").textContent = label;
    $("signal-status").style.background = colour;
  }

  function renderSignalLegend() {
    const swatch = (colour, label) =>
      `<i style="background:${colour};height:0.8rem;opacity:0.6"></i>${label}`;
    $("signal-legend").innerHTML =
      `<i style="background:#1d2733"></i>average <i style="background:#2a78d6;opacity:0.5"></i>each satellite` +
      `<br>${swatch("#008300", "normal range")}${swatch("#eda100", "noisy")}` +
      `${swatch("#e34948", "weak / lost")}${swatch("#6250d6", "tampered")}`;
  }

  function renderMapLegend() {
    const item = (color, label, dotted) =>
      `<i style="background:${dotted ? "none" : color};border-top:${dotted ? `3px dotted ${color}` : "none"}"></i>${label}`;
    const dot = (color, label, shape) =>
      `<span style="color:${color};margin-left:0.8rem">${shape}</span> ${label}`;
    const aid = view.solution === "pseudolites" ? dot("#1b4f72", "shore station", "▲")
      : view.solution === "peers" ? dot("#008300", "ship used", "●") + dot("#e34948", "ship rejected", "●")
      : view.solution === "seabed" ? dot("#1baf7a", "seabed fix used", "◆") + dot("#e34948", "rejected", "◆")
      : "";
    $("map-legend").innerHTML =
      item(pal().ship_track, "GNSS track") + item(pal().green_path, "backup track") +
      item(pal().red_path, "GNSS reported (rejected)", true) + aid +
      ` <button id="map-view" type="button" style="margin-left:1rem">${view.mapView === "ship" ? "Show whole route" : "Follow ship"}</button>` +
      ` <label style="margin-left:0.6rem"><input id="show-truth" type="checkbox"${view.showTruth ? " checked" : ""}>` +
      ` show true position (simulation)</label>`;
    $("show-truth").addEventListener("change", () => {
      view.showTruth = $("show-truth").checked;
      render();
    });
    $("map-view").addEventListener("click", () => {
      view.mapView = view.mapView === "ship" ? "route" : "ship";
      renderMapLegend();
      render();
    });
  }

  // ---------------------------------------------------------- controls

  function render() {
    const { S, t } = view;
    if (!S) return;
    $("clock").textContent = clock(t);
    $("time").value = t;
    renderStatus(S, t);
    renderInstructions(t);
    renderChecks(S, t);
    renderMap(S, t);
    renderSignal(S, t);
    renderAccuracy(S, t);
  }

  function requestRender() {
    if (view.pending) return;
    view.pending = true;
    requestAnimationFrame(() => { view.pending = false; render(); });
  }

  function setTime(t) {
    view.t = Math.max(0, Math.min(Math.round(t), view.S.state.length - 1));
    requestRender();
  }

  function stop() {
    clearInterval(view.timer);
    view.timer = null;
    $("play").textContent = "▷ Play";
  }

  function togglePlay() {
    if (view.timer) { stop(); return; }
    $("play").textContent = "❚❚ Pause";
    view.timer = setInterval(() => {
      const perTick = Math.max(1, Number($("speed").value) * TICK_MS / 1000);
      setTime(view.t + perTick);
      if (view.t >= view.S.state.length - 1) stop();
    }, TICK_MS);
  }

  function fillControls() {
    $("scenario").innerHTML = C().scenarios[view.mode]
      .map((s) => `<option value="${s.key}">${NAV.escape(s.title)}</option>`).join("");
    $("scenario").value = view.key;
    $("solution").innerHTML = C().solutions
      .map((s) => `<option value="${s.key}">${NAV.escape(s.title)}</option>`).join("");
    $("solution").value = view.solution;
    $("speed").innerHTML = SPEEDS[view.mode].map(([v, label]) => `<option value="${v}">${label}</option>`).join("");
    $("speed").selectedIndex = 1;
  }

  async function load(keepTime) {
    stop();
    $("loading").hidden = false;
    try {
      view.S = await NAV.getScenario(view.mode, view.key, view.solution);
    } catch (err) {
      $("loading").hidden = true;
      NAV.fail(err.message);
      return;
    }
    $("loading").hidden = true;
    view.transitions = computeTransitions(view.S);
    view.accuracy = accuracySeries(view.S);
    $("time").max = view.S.state.length - 1;
    renderMapLegend();
    setTime(keepTime ? view.t : 0);
  }

  async function start() {
    try {
      if (typeof Plotly === "undefined") {
        throw new Error("The map library is missing (web-navigator/vendor/plotly.min.js).");
      }
      await NAV.getContent();
    } catch (err) {
      $("loading").hidden = true;
      NAV.fail(err.message);
      return;
    }
    view.mode = $("mode").value;  // the browser may restore the last selection on reload
    fillControls();
    renderSignalLegend();
    $("mode").addEventListener("change", () => {
      view.mode = $("mode").value; view.key = $("scenario").value || "normal";
      fillControls(); load();
    });
    $("scenario").addEventListener("change", () => { view.key = $("scenario").value; load(); });
    // Same moment, different solution: easy to compare.
    $("solution").addEventListener("change", () => { view.solution = $("solution").value; load(true); });
    $("play").addEventListener("click", togglePlay);
    $("time").addEventListener("input", () => { stop(); setTime(Number($("time").value)); });
    await load();
  }

  start();
})();
