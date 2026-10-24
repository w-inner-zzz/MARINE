// HTML sections of the Monitor tab: numbers, check cards, decision, playbook.
// The wording comes from content.js (exported from the Python teaching/ package).
"use strict";

MARINE.sections = (function () {
  const esc = MARINE.escape;
  const C = () => MARINE.content;
  const pal = () => MARINE.content.palette;
  const stateName = (S, t) => C().states[S.state[t]];
  const STATUS = { 1: ["✅", "passed"], 0: ["❌", "failed"], null: ["➖", "skipped"] };

  // ---------------------------------------------------------- the checks

  function checks(S, t) {
    return S.checks[t].map(([passed, value, threshold, skipText], i) => ({
      name: C().checks[i].name, verdictIfFailed: C().checks[i].verdict_if_failed,
      passed, value, threshold, skipText,
    }));
  }

  function explain(check) {
    const texts = C().check_explanations[check.name];
    if (check.passed === null) {
      return { measured: check.skipText, means: C().skipped_meaning, ifFails: texts.if_fails };
    }
    let measured = texts.measured;
    if (check.value !== null && check.threshold !== null) {
      measured = MARINE.pyFormat(measured, { value: check.value, threshold: check.threshold });
    }
    return { measured, means: check.passed ? texts.means_ok : texts.means_bad, ifFails: texts.if_fails };
  }

  function renderChecks(el, S, t) {
    const list = checks(S, t);
    const deciding = list.find((c) => c.passed === 0);
    const color = pal().states[stateName(S, t)];
    el.innerHTML = list.map((c, i) => {
      const [icon, word] = STATUS[c.passed];
      const texts = explain(c);
      const isDeciding = c === deciding;
      const style = isDeciding ? `border:3px solid ${color};background:${color}14;` : "";
      const badge = isDeciding ? `<span class="badge" style="background:${color}">decided the verdict</span>` : "";
      return `<div class="card" style="${style}">
        <div class="head">${i + 1}. ${icon} ${esc(c.name)}
          <span class="meta"> · ${word} · value ${MARINE.fmtNumber(c.value)} / threshold
          ${MARINE.fmtNumber(c.threshold)} · if it fails: ${c.verdictIfFailed}</span>${badge}</div>
        <div><b>What we measured:</b> ${esc(texts.measured)}</div>
        <div><b>What it means:</b> ${esc(texts.means)}</div>
        <div><b>If it fails, what that suggests:</b> ${esc(texts.ifFails)}</div>
      </div>`;
    }).join("");
  }

  // -------------------------------------------------------- the decision

  function whatIsHappening(S, t) {
    const state = stateName(S, t);
    const a = C().actions[state];
    const base = `${state}: ${C().state_meaning[state]}`;
    if (state === "TRUSTED") return `${base} Autopilot: ${a.autopilot_mode}.`;
    if (state === "RECOVERING") {
      return `${base} Clean for ${S.clean[t]} of ${S.need[t]} seconds; position from ${a.position_source}.`;
    }
    return `${base} Position from ${a.position_source}; autopilot ${a.autopilot_mode}.`;
  }

  function why(S, t) {
    const list = checks(S, t);
    const failed = list.filter((c) => c.passed === 0);
    const skipped = list.filter((c) => c.passed === null).length;
    const skippedText = skipped ? ` (${skipped} could not run)` : "";
    if (!failed.length) return `All checks that could run passed${skippedText}. ${S.reason[t]}`;
    return `${failed.length} of ${list.length} checks failed (${failed.map((c) => c.name).join(", ")})` +
           `${skippedText}. The first failure decides: ${S.reason[t]}`;
  }

  function renderDecision(el, S, t) {
    const state = stateName(S, t);
    const color = pal().states[state];
    el.innerHTML = `<div class="banner" style="border-left-color:${color};background:${color}1f">
      <div class="state" style="color:${color}">${state}
        <small>&nbsp;t = ${t} s · position ${S.lat[t].toFixed(4)}° N, ${S.lon[t].toFixed(4)}° E
        ± ${S.unc[t].toFixed(0)} m</small></div>
      <div><b>What is happening:</b> ${esc(whatIsHappening(S, t))}</div>
      <div><b>Why:</b> ${esc(why(S, t))}</div></div>`;
  }

  // ---------------------------------------------------------- playbook

  function sourceLink(key, text) {
    const s = C().sources[key];
    return `<a href="${s.url}" target="_blank" rel="noopener">${esc(text || s.title)}</a>`;
  }

  function ruleWithLink(rule) {
    for (const [prefix, key] of Object.entries(C().rule_sources)) {
      if (rule.startsWith(prefix)) return `${esc(rule)} (${sourceLink(key, "IMO")})`;
    }
    return esc(rule);
  }

  function renderPlaybook(el, S, t) {
    const state = stateName(S, t);
    const a = C().actions[state];
    const color = pal().states[state];
    const progress = state === "RECOVERING"
      ? `<p>Clean for ${S.clean[t]} of ${S.need[t]} seconds</p><div class="progress">
         <div style="width:${(100 * S.clean[t] / S.need[t]).toFixed(0)}%"></div></div>` : "";
    el.innerHTML = `
      <p><span style="color:${color};font-weight:700;font-size:1.2rem">${state}</span>
        &nbsp; position from <b>${esc(a.position_source)}</b> · autopilot <b>${esc(a.autopilot_mode)}</b>
        · speed <b>${esc(a.recommended_speed_kn)}</b> · look-out <b>${esc(a.lookout_level)}</b></p>
      ${a.alerts.map((x) => `<div class="note warn">${esc(x)}</div>`).join("")}
      ${progress}
      <div class="playbook">
        <div>
          <p><b>Why it matters.</b> ${esc(a.why_it_matters)}</p>
          <p><b>Steps for the bridge team</b></p>
          <ol>${a.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
        </div>
        <div>
          <div class="rules"><p><b>Rules that still apply when GNSS fails</b></p>
            <ul>${a.rules.map((r) => `<li>${ruleWithLink(r)}</li>`).join("")}</ul></div>
          <p><b>Sources for the steps:</b>
            ${C().playbook_sources.map(([key, text]) => sourceLink(key, text)).join("; ")}.</p>
        </div>
      </div>
      <div class="note info">${esc(C().disclaimer)}</div>`;
  }

  // ------------------------------------------------- inspector: numbers

  function renderSatTable(el, S, t) {
    const sats = MARINE.charts.sats(S, t);
    if (!sats.length) {
      el.innerHTML = `<div class="note info">The receiver reports no satellites at all this second.</div>`;
      return;
    }
    el.innerHTML = `<table><thead><tr><th>Satellite</th><th>Azimuth (°)</th><th>Elevation (°)</th>
      <th>C/N0 (dB-Hz)</th><th>Tracked</th></tr></thead><tbody>${sats.map((s) => `<tr>
      <td class="num">${s.id}</td><td class="num">${Math.round(s.az)}</td>
      <td class="num">${Math.round(s.el)}</td><td class="num">${s.cn0.toFixed(1)}</td>
      <td>${s.tracked ? "yes" : "no"}</td></tr>`).join("")}</tbody></table>`;
  }

  function metric(label, value, delta, bad, captionKey) {
    return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div>
      ${delta ? `<span class="delta${bad ? " bad" : ""}">${delta}</span>` : ""}
      <p class="caption"><b>How to read this:</b> ${esc(C().captions[captionKey])}</p></div>`;
  }

  function renderMetrics(el, noteEl, S, t, N) {
    const cfg = C().config;
    const rise = S.agc[t] - S.b_agc[t];
    const n = S.nsat[t];
    const verdict = n >= 5 ? "enough" : n >= 4 ? "position only, no cross-check" : "no position";
    const hdop = S.hdop[t];
    const quality = hdop === null ? "-" : hdop < 2 ? "good" : hdop > 5 ? "poor" : "fair";
    const clock = S.clock[t];
    el.innerHTML = [
      metric("Noise floor", `${S.agc[t].toFixed(1)} dB`,
             `${rise >= 0 ? "+" : ""}${rise.toFixed(1)} dB vs learned normal ${S.b_agc[t].toFixed(1)}`,
             rise > cfg.agc_jump_db, "noise_floor"),
      metric("Satellites tracked", n, `need 4 for a fix, 5 to check: ${verdict}`, n < 5, "satellite_count"),
      metric("HDOP", hdop === null ? "none" : hdop.toFixed(1), quality, hdop !== null && hdop > 5, "hdop"),
      metric("GNSS time error", clock === null ? "-" : `${(clock * 1000).toFixed(1)} ms`,
             clock === null ? "" : `${((clock - S.b_clock[t]) * 1000).toFixed(1)} ms vs normal`,
             false, "time_error"),
      metric("GNSS position", S.glat[t] === null ? "none" : `${S.glat[t].toFixed(4)}° N`,
             S.glat[t] === null ? "" : `${S.glon[t].toFixed(4)}° E`, false, "gnss_position"),
    ].join("");
    noteEl.textContent = N
      ? `Healthy receiver at the same second: noise floor ${N.agc[t].toFixed(1)} dB, ${N.nsat[t]} ` +
        `satellites, HDOP ${N.hdop[t] === null ? "none" : N.hdop[t].toFixed(1)}, GNSS ` +
        MARINE.fmtLatLon(N.glat[t], N.glon[t]) + "."
      : "";
  }

  // ------------------------------------------------------------ others

  function renderDataLabel(el, S, chart) {
    if (!S.meta.voyage) {
      el.innerHTML = `<div class="note info">Short test run: synthetic straight coast and synthetic
        seabed, the same world the automated tests use.</div>`;
    } else if (chart.route.synthetic) {
      el.innerHTML = `<div class="note warn"><b>Depth chart: SYNTHETIC.</b> Real bathymetry (EMODnet)
        could not be downloaded, so the seabed depths are generated and are NOT real survey data.
        Run <code>python -m sim.bathymetry download</code> with internet access, then
        <code>python export_web.py</code>, to use real data. The coastline and land come from a
        real land mask (global-land-mask, about 1 km resolution).</div>`;
    } else {
      el.innerHTML = `<div class="note ok">Depth chart: real EMODnet bathymetry. Land: real land mask
        (global-land-mask, about 1 km resolution).</div>`;
    }
  }

  function keyMoments(S) {
    const m = S.meta, moments = [];
    if (m.event_start !== null) moments.push(["Event starts", m.event_start]);
    S.detections.slice(0, 2).forEach((d) => moments.push([`Detected: ${d.state}`, d.t]));
    if (m.event_end !== null) {
      moments.push(["Event ends", m.event_end]);
      if (S.summary.back_to_trusted_s !== null) {
        moments.push(["Trusted again", m.event_end + S.summary.back_to_trusted_s]);
      }
    }
    return moments;
  }

  function renderStatus(el, S, t) {
    const state = stateName(S, t);
    el.innerHTML = `At <b>t = ${t} s</b> the guard says <b style="color:${pal().states[state]}">${state}</b>.
      Below: what the receiver reports, how each check judges it, the decision, and what the boat
      should do.`;
  }

  function renderDanger(el, S, t) {
    const d = S.danger;
    el.innerHTML = d && d.t <= t
      ? `<div class="note error">⚠ Grounding risk if GNSS had been trusted: at t = ${d.t.toFixed(0)} s
         the reported (red) position was ${esc(d.what)}, while the real ship was
         ${(d.off_by_m / 1000).toFixed(1)} km away in open water.</div>` : "";
  }

  function renderComparison(el, mode) {
    const rows = C().comparison[mode];
    const head = Object.keys(rows[0]);
    el.innerHTML = `<table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${head.map((h) =>
        `<td class="${typeof r[h] === "number" ? "num" : ""}">${esc(r[h])}</td>`).join("")}</tr>`).join("")}
      </tbody></table>`;
  }

  return { renderChecks, renderDecision, renderPlaybook, renderSatTable, renderMetrics,
           renderDataLabel, keyMoments, renderStatus, renderDanger, renderComparison };
})();
