// Maps on latitude/longitude axes, drawn from the real land mask and the depth
// chart exported by export_web.py (no internet map tiles needed).
//   red   - what GNSS reported while it was not trusted
//   green - the guard's backup track while GNSS was not trusted
//   grey dotted - ground truth (only a simulation knows it)
"use strict";

MARINE.maps = (function () {
  const PLOT_CONFIG = { responsive: true, displaylogo: false };
  const SEA_SCALE = [[0, "#d6eaf8"], [1, "#1b4f72"]];
  const M_PER_DEG = 111195;
  const pal = () => MARINE.content.palette;
  const stateName = (S, t) => MARINE.content.states[S.state[t]];
  const notTrusted = (S, t) => stateName(S, t) !== "TRUSTED";

  function range(start, stop, step) {
    const out = [];
    for (let i = start; i < stop; i += step) out.push(i);
    if (out[out.length - 1] !== stop - 1 && stop > start) out.push(stop - 1);
    return out;
  }

  function equalAxes(layout, lat, latRange, lonRange, height) {
    return Object.assign(layout, {
      height,
      margin: { l: 60, r: 10, t: 40, b: 50 },
      plot_bgcolor: "#d6eaf8", paper_bgcolor: "#ffffff",
      xaxis: { range: lonRange, title: { text: "longitude (° E)" }, constrain: "domain" },
      yaxis: { range: latRange, title: { text: "latitude (° N)" }, constrain: "domain",
               scaleanchor: "x", scaleratio: 1 / Math.cos(lat * Math.PI / 180) },
      legend: { orientation: "h", y: -0.15 },
    });
  }

  function note(lat, lon, text, color, ax, ay) {
    return { x: lon, y: lat, text: MARINE.escape(text), ax, ay, showarrow: true,
             arrowcolor: color, font: { size: 11, color }, bgcolor: "rgba(255,255,255,0.88)",
             bordercolor: color, borderpad: 3 };
  }

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

  // Lon/lat lists of the seconds where keep(t), with gaps between segments.
  function path(S, idx, latKey, lonKey, keep) {
    const x = [], y = [];
    for (const t of idx) {
      const ok = keep(t) && S[latKey][t] !== null;
      if (!ok) {
        if (y.length && y[y.length - 1] !== null) { x.push(null); y.push(null); }
        continue;
      }
      x.push(S[lonKey][t]); y.push(S[latKey][t]);
    }
    return { x, y };
  }

  function circle(lat, lon, radiusM) {
    const x = [], y = [];
    for (let k = 0; k <= 60; k++) {
      const a = 2 * Math.PI * k / 60;
      const dLat = radiusM * Math.sin(a) / M_PER_DEG;
      const dLon = radiusM * Math.cos(a) / (M_PER_DEG * Math.cos(lat * Math.PI / 180));
      x.push(lon + dLon); y.push(lat + dLat);
    }
    return { x, y };
  }

  function chartBackground(chart, latRange, lonRange) {
    const g = chart.route;
    const rows = [], cols = [];
    g.depth.forEach((_, r) => { const lat = g.lat0 + r * g.dlat;
      if (lat >= latRange[0] - 0.02 && lat <= latRange[1] + 0.02) rows.push(r); });
    g.depth[0].forEach((_, c) => { const lon = g.lon0 + c * g.dlon;
      if (lon >= lonRange[0] - 0.02 && lon <= lonRange[1] + 0.02) cols.push(c); });
    if (!rows.length || !cols.length) return [];
    const step = Math.max(1, Math.ceil(Math.max(rows.length, cols.length) / 250));
    const R = rows.filter((_, i) => i % step === 0), Cc = cols.filter((_, i) => i % step === 0);
    const lats = R.map((r) => g.lat0 + r * g.dlat), lons = Cc.map((c) => g.lon0 + c * g.dlon);
    const depth = R.map((r) => Cc.map((c) => (g.depth[r][c] === 255 ? null : g.depth[r][c])));
    const land = R.map((r) => Cc.map((c) => (g.depth[r][c] === 255 ? 1 : null)));
    const label = g.synthetic ? "SYNTHETIC depth (m)" : "depth (m), EMODnet";
    return [
      { type: "heatmap", x: lons, y: lats, z: depth, colorscale: SEA_SCALE, zmin: 0, zmax: 100,
        name: "depth chart", colorbar: { title: { text: label }, len: 0.6 },
        hovertemplate: "depth %{z:.0f} m<extra></extra>" },
      landLayer(lats, lons, land),
    ];
  }

  function landLayer(lats, lons, z) {
    return { type: "heatmap", x: lons, y: lats, z, colorscale: [[0, pal().land], [1, pal().land]],
             showscale: false, hoverinfo: "skip", name: "land" };
  }

  function tracks(S, idx) {
    const traces = [];
    const truth = path(S, idx, "tlat", "tlon", () => true);
    traces.push({ type: "scatter", mode: "lines", name: "ground truth (visible only in the simulation)",
                  x: truth.x, y: truth.y, line: { color: pal().truth, width: 1.5, dash: "dot" } });
    const ship = path(S, idx, "lat", "lon", (t) => !notTrusted(S, t));
    traces.push({ type: "scatter", mode: "lines", name: "ship track (GNSS trusted)",
                  x: ship.x, y: ship.y, line: { color: pal().ship_track, width: 2.5 } });
    const red = path(S, idx, "glat", "glon", (t) => notTrusted(S, t));
    if (red.y.some((v) => v !== null)) traces.push({ type: "scatter", mode: "lines",
      name: "RED: what GNSS reported (where a GNSS autopilot would think it is)",
      x: red.x, y: red.y, line: { color: pal().red_path, width: 2.5 } });
    const green = path(S, idx, "lat", "lon", (t) => notTrusted(S, t));
    if (green.y.some((v) => v !== null)) traces.push({ type: "scatter", mode: "lines",
      name: "GREEN: guard backup track (dead reckoning + radar + depth)",
      x: green.x, y: green.y, line: { color: pal().green_path, width: 2.5 } });
    for (const [bit, kind, symbol] of [[1, "radar", "triangle-down"], [2, "depth", "diamond"]]) {
      const fixes = idx.filter((t) => S.fixes[t] & bit);
      if (fixes.length) traces.push({ type: "scatter", mode: "markers", name: `${kind} fix applied`,
        x: fixes.map((t) => S.lon[t]), y: fixes.map((t) => S.lat[t]),
        marker: { symbol, size: 8, color: pal().fix, line: { width: 1, color: "white" } } });
    }
    return traces;
  }

  function uncertainty(S, t, showLegend) {
    const c = circle(S.lat[t], S.lon[t], S.unc[t]);
    return { type: "scatter", mode: "lines", fill: "toself", x: c.x, y: c.y,
             name: `uncertainty ±${S.unc[t].toFixed(0)} m`, showlegend: showLegend,
             line: { color: pal().green_path, width: 1 }, fillcolor: "rgba(0,131,0,0.2)" };
  }

  function shipMarker(S, t, traces, annotations) {
    const color = pal().states[stateName(S, t)];
    traces.push({ type: "scatter", mode: "markers", name: "ship (guard position)",
      x: [S.lon[t]], y: [S.lat[t]],
      marker: { symbol: "arrow", size: 22, angle: S.heading[t], color, line: { width: 1, color: "white" } } });
    annotations.push(note(S.lat[t], S.lon[t], "ship " + MARINE.fmtLatLon(S.lat[t], S.lon[t]), "#222222", 60, 35));
  }

  function events(S, t, traces, annotations) {
    const shown = S.detections.filter((d) => d.t <= t);
    if (shown.length) {
      traces.push({ type: "scatter", mode: "markers", name: "detection",
        x: shown.map((d) => d.lon), y: shown.map((d) => d.lat),
        marker: { symbol: "star", size: 14, color: shown.map((d) => pal().states[d.state]),
                  line: { width: 1, color: "white" } } });
      shown.slice(-3).forEach((d, i) => annotations.push(note(d.lat, d.lon,
        `⚑ ${d.state} at ${d.t.toFixed(0)} s: ${d.reason}`, pal().states[d.state], -40, -40 - 28 * i)));
    }
    const danger = S.danger;
    if (danger && danger.t <= t) {
      traces.push({ type: "scatter", mode: "markers", name: "grounding risk if GNSS had been trusted",
        x: [danger.lon], y: [danger.lat],
        marker: { symbol: "x", size: 16, color: pal().red_path, line: { width: 2 } } });
      annotations.push(note(danger.lat, danger.lon,
        `⚠ grounding risk if GNSS had been trusted (${danger.what})`, pal().red_path, 0, 40));
    }
  }

  function placeLabels(places, latRange, lonRange) {
    const inside = places.filter(([, lat, lon]) => lat >= latRange[0] && lat <= latRange[1] &&
                                                     lon >= lonRange[0] && lon <= lonRange[1]);
    if (!inside.length) return [];
    return [{ type: "scatter", mode: "markers+text", name: "places", showlegend: false,
      x: inside.map((p) => p[2]), y: inside.map((p) => p[1]), text: inside.map((p) => p[0]),
      textposition: inside.map((p) => p[3]), marker: { size: 7, color: "#333333" }, hoverinfo: "text" }];
  }

  function shortModeCoast(latRange, lonRange) {
    const coast = MARINE.content.coast_lat_short;
    return { shapes: [{ type: "rect", x0: lonRange[0], x1: lonRange[1], y0: coast, y1: latRange[1] + 1,
                        fillcolor: pal().land, line: { width: 0 }, layer: "below" }],
             annotations: [{ x: lonRange[0], xanchor: "left", y: coast, yanchor: "top",
                             text: "synthetic straight coast", showarrow: false }] };
  }

  function routeMap(id, S, chart, t, every) {
    const idx = range(0, t + 1, every);
    const drawn = [];
    for (const i of idx) {
      drawn.push([S.tlat[i], S.tlon[i]], [S.lat[i], S.lon[i]]);
      if (notTrusted(S, i) && S.glat[i] !== null) drawn.push([S.glat[i], S.glon[i]]);
    }
    const [latRange, lonRange] = bounds(drawn, 0.03, 0.08, 1.8);
    const traces = S.meta.voyage ? chartBackground(chart, latRange, lonRange) : [];
    const annotations = [];
    traces.push(...tracks(S, idx), uncertainty(S, t, false));
    events(S, t, traces, annotations);
    shipMarker(S, t, traces, annotations);
    traces.push(...placeLabels(pal().places, latRange, lonRange));
    const layout = equalAxes({ title: { text: "Route map (zoomed)", font: { size: 14 }, x: 0.01 } },
                             S.tlat[t], latRange, lonRange, 560);
    layout.annotations = annotations;
    if (!S.meta.voyage) {
      const coast = shortModeCoast(latRange, lonRange);
      layout.shapes = coast.shapes; layout.annotations.push(...coast.annotations);
    }
    Plotly.react(id, traces, layout, PLOT_CONFIG);
  }

  function closeupMap(id, S, t) {
    const idx = range(Math.max(0, t - 600), t + 1, 1);
    const halfM = Math.max(800, 3 * S.unc[t]);
    const lat = S.lat[t], lon = S.lon[t];
    const dLat = halfM / 6371000 * 180 / Math.PI, dLon = dLat / Math.cos(lat * Math.PI / 180);
    const latRange = [lat - dLat * 0.7, lat + dLat * 0.7], lonRange = [lon - dLon, lon + dLon];
    const traces = tracks(S, idx), annotations = [];
    traces.push(uncertainty(S, t, true));
    events(S, t, traces, annotations);
    shipMarker(S, t, traces, annotations);
    const layout = equalAxes({ title: { text: `Close-up: ±${(halfM / 1000).toFixed(1)} km around the ship`,
                                        font: { size: 14 }, x: 0.01 }, showlegend: false },
                             lat, latRange, lonRange, 420);
    layout.annotations = annotations;
    Plotly.react(id, traces, layout, PLOT_CONFIG);
  }

  function overviewMap(id, S, chart, t) {
    const o = chart.overview;
    const lats = o.land.map((_, r) => o.lat0 + r * o.step);
    const lons = [...o.land[0]].map((_, c) => o.lon0 + c * o.step);
    const z = o.land.map((row) => [...row].map((v) => (v === "1" ? 1 : null)));
    const route = range(0, S.tlat.length, 300);
    const traces = [
      landLayer(lats, lons, z),
      { type: "scatter", mode: "lines", name: "voyage", x: route.map((i) => S.tlon[i]),
        y: route.map((i) => S.tlat[i]), line: { color: pal().ship_track, width: 3 } },
      { type: "scatter", mode: "markers", name: "ship", x: [S.tlon[t]], y: [S.tlat[t]],
        marker: { size: 10, color: pal().states[stateName(S, t)], line: { width: 1, color: "white" } } },
    ];
    const latRange = [53.5, 66.0], lonRange = [9.0, 31.0];
    traces.push(...placeLabels(pal().overview_places, latRange, lonRange));
    const layout = equalAxes({ title: { text: "Overview: the Baltic Sea", font: { size: 14 }, x: 0.01 },
                               showlegend: false }, 59.0, latRange, lonRange, 420);
    layout.annotations = pal().area_labels.map(([name, lat, lon, ax, ay]) => ({
      x: lon, y: lat, text: `<i>${name}</i>`, showarrow: !!(ax || ay), ax, ay,
      arrowcolor: "#1b4f72", font: { color: "#1b4f72", size: 12 } }));
    Plotly.react(id, traces, layout, PLOT_CONFIG);
  }

  return { routeMap, closeupMap, overviewMap, chartBackground, circle, bounds };
})();
