// Shared helpers: data registry, decompression, formatting, Markdown + maths.
// Plain script (no ES modules) so the site also works when opened from disk.
"use strict";

window.MARINE = {
  content: null,      // set by data/content.js
  rawScenarios: {},   // id -> packed text, filled by data/scenarios/*.js
  rawChart: null,     // packed text, filled by data/chart.js
  scenarios: {},      // id -> decoded scenario
  chart: null,        // decoded chart

  registerScenario(id, packed) { this.rawScenarios[id] = packed; },
  registerChart(packed) { this.rawChart = packed; },
};

// base64 -> gzip -> JSON (the reverse of export_web.py's packed()).
MARINE.unpack = async function (packed) {
  const bytes = Uint8Array.from(atob(packed), (c) => c.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
};

MARINE.loadScript = function (src) {
  return new Promise((resolve, reject) => {
    const tag = document.createElement("script");
    tag.src = src;
    tag.onload = resolve;
    tag.onerror = () => reject(new Error("Could not load " + src +
      ". Run `python export_web.py` to generate the data."));
    document.head.appendChild(tag);
  });
};

MARINE.getScenario = async function (mode, key) {
  const id = `${mode}/${key}`;
  if (!this.scenarios[id]) {
    if (!this.rawScenarios[id]) await this.loadScript(`data/scenarios/${mode}_${key}.js`);
    this.scenarios[id] = await this.unpack(this.rawScenarios[id]);
    delete this.rawScenarios[id];
  }
  return this.scenarios[id];
};

MARINE.getChart = async function () {
  if (!this.chart) this.chart = await this.unpack(this.rawChart);
  return this.chart;
};

// ------------------------------------------------------------ formatting

MARINE.escape = function (text) {
  return String(text).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
};

// Fill a Python-style template such as "{value:+.1f} of {threshold:.0f}".
MARINE.pyFormat = function (template, values) {
  return template.replace(/\{(\w+)(?::(\+?)\.(\d+)f)?\}/g, (whole, name, plus, digits) => {
    const v = values[name];
    if (v === undefined || v === null) return whole;
    if (digits === undefined) return String(v);
    const text = Number(v).toFixed(Number(digits));
    return plus && v >= 0 ? "+" + text : text;
  });
};

MARINE.fmtLatLon = function (lat, lon) {
  return `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? "N" : "S"}, ` +
         `${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? "E" : "W"}`;
};

MARINE.fmtNumber = function (v) {
  if (v === null || v === undefined) return "-";
  return Math.abs(v) < 1 ? v.toFixed(3) : v.toFixed(1);
};

// Distance in metres between two lat/lon points (local flat approximation).
MARINE.distanceM = function (lat1, lon1, lat2, lon2) {
  const R = 6371000, rad = Math.PI / 180;
  const dy = (lat2 - lat1) * rad * R;
  const dx = (lon2 - lon1) * rad * R * Math.cos(lat1 * rad);
  return Math.hypot(dx, dy);
};

// ----------------------------------------------------- Markdown + maths

// Render Markdown that may contain $inline$ and $$display$$ maths. Maths is
// cut out first so Markdown cannot mangle its backslashes and underscores.
MARINE.markdown = function (text) {
  const maths = [];
  const protectedText = text.replace(/\$\$([\s\S]+?)\$\$|\$([^$]+?)\$/g, (m, display, inline) => {
    maths.push({ tex: display !== undefined ? display : inline, display: display !== undefined });
    return `@@MATH${maths.length - 1}@@`;
  });
  const html = marked.parse(protectedText);
  return html.replace(/@@MATH(\d+)@@/g, (m, i) =>
    katex.renderToString(maths[i].tex, { displayMode: maths[i].display, throwOnError: false }));
};

MARINE.latex = function (tex) {
  return katex.renderToString(tex, { displayMode: true, throwOnError: false });
};

// Render a list of content blocks (see teaching/blocks.py) to HTML.
MARINE.renderBlocks = function (blocks) {
  return blocks.map((b) => {
    if (b.type === "md") return `<div class="md">${MARINE.markdown(b.text)}</div>`;
    if (b.type === "latex") return `<div class="math">${MARINE.latex(b.text)}</div>`;
    if (b.type === "diagram") return `<div class="diagram">${b.svg}</div>`;
    return "";
  }).join("");
};
