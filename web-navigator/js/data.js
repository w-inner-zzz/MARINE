// Data registry and loader for the bridge view. Everything this page needs is
// inside the web-navigator/ folder, so it works opened from disk or served alone.
"use strict";

window.NAV = {
  raw: {},          // id -> packed text, filled by data/scenarios/*.js
  scenarios: {},    // id -> decoded scenario
  rawContent: null, // packed text, filled by data/content.js
  content: null,

  registerScenario(id, packed) { this.raw[id] = packed; },
  registerContent(packed) { this.rawContent = packed; },
};

// Show a problem at the top of the page instead of failing silently.
NAV.fail = function (message) {
  const box = document.getElementById("error");
  if (!box) return;
  box.hidden = false;
  box.textContent = message;
};

window.addEventListener("error", (e) => NAV.fail(`Something went wrong: ${e.message}`));
window.addEventListener("unhandledrejection", (e) =>
  NAV.fail(`Something went wrong: ${e.reason && e.reason.message ? e.reason.message : e.reason}`));

// base64 -> gzip -> JSON (written by export_web.py).
NAV.unpack = async function (packed) {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("This browser is too old to open the data. Please use a current Chrome, " +
                    "Edge, Firefox or Safari.");
  }
  const bytes = Uint8Array.from(atob(packed), (c) => c.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
};

NAV.loadScript = function (src) {
  return new Promise((resolve, reject) => {
    const tag = document.createElement("script");
    tag.src = src;
    tag.onload = resolve;
    tag.onerror = () => reject(new Error(`Could not load ${src}. Keep the web-navigator folder ` +
      "complete (with its data/ folder), or run `python export_web.py` to recreate it."));
    document.head.appendChild(tag);
  });
};

NAV.getContent = async function () {
  if (!this.content) {
    if (!this.rawContent) {
      throw new Error("The data files are missing (web-navigator/data/content.js). " +
                      "Run `python export_web.py` to create them.");
    }
    this.content = await this.unpack(this.rawContent);
  }
  return this.content;
};

NAV.getScenario = async function (mode, key) {
  const id = `${mode}/${key}`;
  if (!this.scenarios[id]) {
    if (!this.raw[id]) await this.loadScript(`data/scenarios/${mode}_${key}.js`);
    this.scenarios[id] = await this.unpack(this.raw[id]);
    delete this.raw[id];
  }
  return this.scenarios[id];
};

NAV.escape = function (text) {
  return String(text).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
};

NAV.fmtLatLon = function (lat, lon) {
  return `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? "N" : "S"}, ` +
         `${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? "E" : "W"}`;
};
