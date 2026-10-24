// Bridge view: status, instructions, vital readings, checks and map at a glance.
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

  const view = { mode: "voyage", key: "normal", t: 0, S: null, chart: null, timer: null,
                 transitions: [], mapView: "ship", pending: false };

  const stateAt = (t) => C().states[view.S.state[t]];

  // ------------------------------------------------------------ formatting

  function clock(seconds) {
    const s = Math.round(seconds);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
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
      ["Position", NAV.fmtLatLon(S.lat[t], S.lon[t])],
      ["Heading", `${((S.heading[t] % 360) + 360) % 360 | 0}°`],
      ["Speed", `${(S.speed[t] / KNOT_MPS).toFixed(1)} kn`],
      ["Satellites", `${S.nsat[t]}`],
      ["Signal", cn0 === null ? "none" : `${cn0.toFixed(0)} dB-Hz`],
      ["Noise", `${S.agc[t].toFixed(1)} dB`],
    ];
    $("vitals").innerHTML = vitals.map(([k, v]) =>
      `<div class="vital"><span>${k}</span><b>${NAV.escape(v)}</b></div>`).join("");
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
    return [a.autopilot_mode, `Speed: ${a.recommended_speed_kn}`, a.crew_instructions[0]];
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
      }
      return bounds(pts, 0.01, 0.02, 2.2);
    }
    const halfM = 3000;
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

  function renderMapLegend() {
    const item = (color, label, dotted) =>
      `<i style="background:${dotted ? "none" : color};border-top:${dotted ? `3px dotted ${color}` : "none"}"></i>${label}`;
    $("map-legend").innerHTML =
      item(pal().ship_track, "GNSS track") + item(pal().green_path, "backup track") +
      item(pal().red_path, "GNSS reported (rejected)", true) +
      ` <button id="map-view" type="button" style="margin-left:1rem">${view.mapView === "ship" ? "Show whole route" : "Follow ship"}</button>`;
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
    $("speed").innerHTML = SPEEDS[view.mode].map(([v, label]) => `<option value="${v}">${label}</option>`).join("");
    $("speed").selectedIndex = 1;
  }

  async function load() {
    stop();
    $("loading").hidden = false;
    try {
      view.S = await NAV.getScenario(view.mode, view.key);
    } catch (err) {
      $("loading").hidden = true;
      NAV.fail(err.message);
      return;
    }
    $("loading").hidden = true;
    view.transitions = computeTransitions(view.S);
    $("time").max = view.S.state.length - 1;
    setTime(0);
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
    renderMapLegend();
    $("mode").addEventListener("change", () => {
      view.mode = $("mode").value; view.key = $("scenario").value || "normal";
      fillControls(); load();
    });
    $("scenario").addEventListener("change", () => { view.key = $("scenario").value; load(); });
    $("play").addEventListener("click", togglePlay);
    $("time").addEventListener("input", () => { stop(); setTime(Number($("time").value)); });
    await load();
  }

  start();
})();
