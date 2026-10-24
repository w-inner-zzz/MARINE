// Page controller: controls, tabs, playback and rendering of every section.
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const C = () => MARINE.content;
  const STEPS = { voyage: [1, 10, 30, 60, 120], short: [1, 2, 5, 10, 20] };
  const PLAY_INTERVAL_MS = 400;

  const view = { mode: "voyage", key: "normal", t: 0, S: null, N: null, chart: null,
                 compare: false, timer: null, pending: false };

  // ------------------------------------------------------------ static text

  function renderStaticText() {
    $("briefing").innerHTML = MARINE.renderBlocks(C().briefing);
    $("further-reading").innerHTML = C().further_reading
      .map(([title, url]) => `<li><a href="${url}" target="_blank" rel="noopener">${MARINE.escape(title)}</a></li>`)
      .join("");
    $("tab-simple").innerHTML = MARINE.renderBlocks(C().simple);
    const ex = C().derivation_example;
    $("derivations-intro").innerHTML = "Each derivation goes step by step, defines every symbol and " +
      `ends with a worked example. Worked examples that use live numbers take them from the ` +
      `<b>${MARINE.escape(ex.scenario)}</b> Baltic voyage at <b>t = ${ex.t} s</b>.`;
    $("derivations").innerHTML = C().derivations.map((d) =>
      `<details class="deriv"><summary>${MARINE.escape(d.title)}</summary>${MARINE.renderBlocks(d.blocks)}</details>`
    ).join("");
    document.querySelectorAll("[data-caption]").forEach((el) => {
      el.innerHTML = `<b>How to read this:</b> ${MARINE.escape(C().captions[el.dataset.caption])}`;
    });
    document.querySelectorAll("[data-section]").forEach((el) => {
      el.innerHTML = MARINE.markdown(C().section_text[el.dataset.section]);
    });
    const cfg = C().config;
    $("start-info").innerHTML = `<b>Start:</b> ${cfg.origin_lat_deg.toFixed(2)}° N, ` +
      `${cfg.origin_lon_deg.toFixed(2)}° E, heading east at 12 knots.`;
  }

  function setupTabs() {
    document.querySelectorAll(".tabs button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach((b) =>
          b.setAttribute("aria-selected", String(b === button)));
        document.querySelectorAll(".tab").forEach((tab) => {
          tab.hidden = tab.id !== `tab-${button.dataset.tab}`;
        });
        if (button.dataset.tab === "monitor") render();  // charts need a visible size
      });
    });
  }

  // --------------------------------------------------------------- controls

  function fillScenarioControls() {
    $("scenario").innerHTML = C().scenarios[view.mode]
      .map((s) => `<option value="${s.key}">${MARINE.escape(s.title)}</option>`).join("");
    if (!C().scenarios[view.mode].some((s) => s.key === view.key)) view.key = "normal";
    $("scenario").value = view.key;
    $("step").innerHTML = STEPS[view.mode].map((s) => `<option>${s}</option>`).join("");
    $("step").value = String(STEPS[view.mode][2]);
    describeScenario();
  }

  function describeScenario() {
    const s = C().scenarios[view.mode].find((x) => x.key === view.key);
    $("scenario-description").textContent = `${s.description} (${s.event_text})`;
  }

  function setTime(t) {
    view.t = Math.max(0, Math.min(t, view.S.state.length - 1));
    $("time").value = view.t;
    requestRender();
  }

  function stopPlaying() {
    clearInterval(view.timer);
    view.timer = null;
    $("play").textContent = "▶ Play";
  }

  function togglePlay() {
    if (view.timer) { stopPlaying(); return; }
    $("play").textContent = "⏸ Pause";
    view.timer = setInterval(() => {
      const last = view.S.state.length - 1;
      setTime(view.t + Number($("step").value));
      if (view.t >= last) stopPlaying();
    }, PLAY_INTERVAL_MS);
  }

  function renderMoments() {
    $("moments").innerHTML = "";
    for (const [label, t] of MARINE.sections.keyMoments(view.S)) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${label} (${t.toFixed(0)} s)`;
      button.addEventListener("click", () => { stopPlaying(); setTime(t); });
      $("moments").appendChild(button);
    }
  }

  async function loadScenario() {
    stopPlaying();
    $("loading").hidden = false;
    try {
      view.S = await MARINE.getScenario(view.mode, view.key);
      view.N = view.compare && view.key !== "normal" ? await MARINE.getScenario(view.mode, "normal") : null;
    } catch (err) {
      $("loading").textContent = err.message;
      return;
    }
    $("loading").hidden = true;
    $("time").max = view.S.state.length - 1;
    MARINE.sections.renderDataLabel($("data-label"), view.S, view.chart);
    MARINE.sections.renderComparison($("comparison"), view.mode);
    renderMoments();
    setTime(Math.min(view.t, view.S.state.length - 1));
  }

  function setupControls() {
    $("mode").addEventListener("change", () => {
      view.mode = $("mode").value; view.t = 0;
      fillScenarioControls(); loadScenario();
    });
    $("scenario").addEventListener("change", () => {
      view.key = $("scenario").value; view.t = 0;
      describeScenario(); loadScenario();
    });
    $("compare").addEventListener("change", () => { view.compare = $("compare").checked; loadScenario(); });
    $("play").addEventListener("click", togglePlay);
    $("time").addEventListener("input", () => { stopPlaying(); setTime(Number($("time").value)); });
  }

  // -------------------------------------------------------------- rendering

  // Coalesce rapid slider moves into one render per animation frame.
  function requestRender() {
    if (view.pending) return;
    view.pending = true;
    requestAnimationFrame(() => { view.pending = false; render(); });
  }

  function render() {
    const { S, N, t, chart } = view;
    if (!S || $("tab-monitor").hidden) return;
    const sec = MARINE.sections, ch = MARINE.charts, maps = MARINE.maps;
    $("time-value").textContent = t;
    sec.renderStatus($("status-line"), S, t);
    ch.sky("sky", S, t, N);
    ch.cn0Bars("cn0", S, t, N);
    sec.renderSatTable($("sat-table"), S, t);
    sec.renderMetrics($("metrics"), $("healthy-note"), S, t, N);
    ch.cn0History("h-cn0", S, t, N);
    ch.noiseHistory("h-noise", S, t, N);
    ch.countHistory("h-count", S, t, N);
    ch.jumpHistory("h-jump", S, t, N);
    sec.renderChecks($("check-cards"), S, t);
    sec.renderDecision($("decision"), S, t);
    sec.renderPlaybook($("playbook"), S, t);
    maps.routeMap("route-map", S, chart, t, S.meta.voyage ? 10 : 2);
    sec.renderDanger($("danger-note"), S, t);
    maps.closeupMap("closeup", S, t);
    maps.overviewMap("overview", S, chart, t);
    ch.errorChart("error-chart", S, t);
  }

  async function start() {
    if (!MARINE.content || !MARINE.rawChart) {
      $("loading").textContent = "The data files are missing. Run `python export_web.py` first.";
      return;
    }
    if (typeof DecompressionStream === "undefined") {
      $("loading").textContent = "This browser is too old (no DecompressionStream). Please use a " +
        "current Chrome, Edge, Firefox or Safari.";
      return;
    }
    view.chart = await MARINE.getChart();
    renderStaticText();
    setupTabs();
    fillScenarioControls();
    setupControls();
    await loadScenario();
  }

  start();
})();
