/* HoloEnergy web client. It edits robot and mission documents (the same YAML schema as the
   files) and renders what the Python API returns. It computes no energy, grade or verdict. */
"use strict";

const S = {
  catalog: null, templates: null, robot: null, mission: null, summary: null,
  preflight: null, mode: "energy-only", lastRun: null, runs: [], libFilter: {},
};
const SOURCE_TYPES = [
  ["datasheet", "Manufacturer datasheet"], ["measurement", "Own laboratory measurement"],
  ["paper", "Peer-reviewed paper"], ["dataset", "Experimental dataset"],
  ["assumption", "Engineering assumption"], ["unknown", "Unknown"],
];
const MODES = [
  ["energy-only", "Energy-only", "Prescribed thrust, no vehicle dynamics"],
  ["holoocean", "HoloOcean", "Simulator dynamics drive the thrusters"],
  ["holoocean+desert", "HoloOcean + DESERT", "Adds observed network activity"],
];

/* ---------- utilities ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clone = (x) => JSON.parse(JSON.stringify(x));
function fmt(v, digits = 3) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (typeof v !== "number") return esc(v);
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.001 || a >= 1e6)) return v.toExponential(2);
  return Number(v.toPrecision(digits)).toLocaleString("en-US", { maximumFractionDigits: 6 });
}
const range = (r) => (!r ? "" : r[0] === r[1] ? `${fmt(r[0])} W` : `${fmt(r[0])}–${fmt(r[1])} W`);
const fullName = (c) => (!c ? "" : c.manufacturer && !String(c.model).startsWith(c.manufacturer) ? `${c.manufacturer} ${c.model}` : c.model);
const val = (v, unit, digits) => `${fmt(v, digits)}<span class="unit">${esc(unit)}</span>`;
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), 3500); }
function save() { try { localStorage.setItem("he.robot", JSON.stringify(S.robot)); localStorage.setItem("he.mission", JSON.stringify(S.mission)); } catch (e) { /* storage optional */ } }
function load(key) { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch (e) { return null; } }

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({ error: { summary: `HTTP ${r.status}`, technical: "" } }));
  if (!r.ok) { const err = new Error(data.error?.summary || `HTTP ${r.status}`); err.payload = data.error; throw err; }
  return data;
}
function errorBox(err) {
  const p = err.payload || { summary: err.message };
  return `<div class="issue error" role="alert"><span class="icon" aria-hidden="true">×</span><div>
    <p class="msg">${esc(p.summary)}</p>${p.fix ? `<p class="small">${esc(p.fix)}</p>` : ""}
    ${p.technical ? `<details><summary class="small">Technical detail</summary><code>${esc(p.technical)}</code></details>` : ""}</div></div>`;
}
function gradeBadge(g, extra = "") {
  if (!g) return `<span class="badge info">no grade</span>`;
  const words = { A: "A · measured/exact", B: "B · representative", C: "C · proxy", D: "D · assumption" };
  return `<span class="badge grade-${esc(g)}" title="Evidence grade ${esc(words[g] || g)}">${esc(g)}${extra}</span>`;
}
function download(name, text, type = "text/yaml") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function bars(rows, unit) {
  const max = Math.max(...rows.map((r) => Math.abs(r[1] || 0)), 1e-12);
  return `<div class="bars">${rows.map(([n, v, note]) => `<div class="bar"><span class="name">${esc(n)}${note ? ` <span class="muted small">${esc(note)}</span>` : ""}</span><span>${val(v, unit)}</span>
    <span class="track" aria-hidden="true"><span class="fill" style="width:${(100 * Math.abs(v || 0) / max).toFixed(1)}%;display:block"></span></span></div>`).join("")}</div>`;
}
function lineChart(series, keys, labels, unit, title, zero = true) {
  const t = series.time_s || [];
  if (t.length < 2) return `<p class="muted">No samples.</p>`;
  // Draw at about the rendered width so 12 px axis labels stay 12 px on phones.
  const W = Math.max(300, Math.min(640, (document.querySelector("main")?.clientWidth || 640) - 64));
  const H = Math.round(W * 0.42), L = 48, R = 12, T = 12, B = 30;
  const ys = keys.flatMap((k) => (series[k] || []).filter((v) => v !== null));
  let lo = zero ? Math.min(0, ...ys) : Math.min(...ys), hi = Math.max(...ys);
  if (hi - lo < 1e-9) { hi += 1; lo -= zero ? 0 : 1; }
  const x = (v) => L + (W - L - R) * (v - t[0]) / (t[t.length - 1] - t[0] || 1);
  const y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  const ticks = [lo, (lo + hi) / 2, hi];
  const paths = keys.map((k, i) => {
    const d = (series[k] || []).map((v, j) => (v === null ? "" : `${j ? "L" : "M"}${x(t[j]).toFixed(1)},${y(v).toFixed(1)}`)).join("");
    return `<path d="${d}" fill="none" stroke="var(--series-${i + 1})" stroke-width="2"/>`;
  }).join("");
  const summary = keys.map((k, i) => { const v = (series[k] || []).filter((q) => q !== null); return `${labels[i]}: ${fmt(Math.min(...v))}–${fmt(Math.max(...v))} ${unit}`; }).join("; ");
  return `<figure><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}. ${esc(summary)}">
    <g class="axis">${ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`).join("")}
    <text x="${L}" y="${H - 8}">${fmt(t[0])} s</text><text x="${W - R}" y="${H - 8}" text-anchor="end">${fmt(t[t.length - 1])} s</text></g>${paths}</svg>
    <div class="legend">${keys.map((k, i) => `<span><i style="background:var(--series-${i + 1})"></i>${esc(labels[i])}</span>`).join("")}</div>
    <figcaption>${esc(summary)}</figcaption></figure>`;
}

/* ---------- documents ---------- */
async function refreshSummary() {
  try { S.summary = await api("/api/robot/summary", { robot: S.robot }); S.summaryError = null; }
  catch (e) { S.summary = null; S.summaryError = e; }
}
async function refreshPreflight() {
  try { S.preflight = await api("/api/preflight", { robot: S.robot, mission: S.mission, mode: S.mode }); }
  catch (e) { S.preflight = { ok: false, errors: [e.payload || { summary: e.message }], issues: [], counts: { errors: 1 } }; }
}
function setRobot(doc) { S.robot = doc; save(); }

/* ---------- views ---------- */
const views = {};

views.overview = async () => {
  const s = S.summary, r = S.lastRun?.report;
  const pf = S.preflight;
  return `<div class="page-head"><h1>Overview</h1><p>Evidence-aware energy for configurable marine robots</p></div>
  <div class="grid cols-3">
    <section class="block"><div class="block-head"><h2>Robot</h2><a class="button" href="#/robot">Edit</a></div>
      ${s ? `<p class="item-title">${esc(s.name || "Unnamed robot")}</p><div class="item-meta"><span><b>${s.actuator_count}</b> actuators</span><span><b>${s.components.length}</b> components</span><span><b>${s.rails.length}</b> rails</span><span>Battery <b>${fmt(s.battery.nominal_voltage_V)} V</b></span></div>` : errorBox(S.summaryError || new Error("No robot"))}
    </section>
    <section class="block"><div class="block-head"><h2>Mission</h2><a class="button" href="#/mission">Edit</a></div>
      <p class="item-title">${esc(S.mission.name)}</p><div class="item-meta"><span><b>${S.mission.phases.length}</b> phases</span><span><b>${fmt(S.mission.phases.reduce((a, p) => a + Number(p.duration_s || 0), 0))}</b> s</span></div>
      <div class="timeline" style="margin-top:10px" aria-hidden="true">${S.mission.phases.map((p) => `<div style="flex:${Number(p.duration_s) || 1}">${esc(p.name)}</div>`).join("")}</div>
    </section>
    <section class="block"><div class="block-head"><h2>Pre-flight</h2><a class="button" href="#/run">Review</a></div>
      ${pf ? `<p>${pf.ok ? `<span class="badge ok">✓ runnable</span>` : `<span class="badge bad">× cannot run</span>`}</p><div class="item-meta"><span><b>${pf.counts?.attention || 0}</b> need attention</span><span><b>${pf.counts?.interpretation || 0}</b> affect interpretation</span></div>` : `<p class="muted">Not checked.</p>`}
    </section>
  </div>
  <section class="block"><div class="block-head"><h2>Last result</h2>${r ? `<a class="button" href="#/results">Open</a>` : ""}</div>
    ${r ? kpis(r) : `<div class="empty">No run yet. Build a robot, define a mission, then run it.</div>`}
  </section>
  <section class="block"><h2>Modes</h2><div class="mode-cards" style="margin-top:10px">${MODES.map(([k, n, d]) => `<div class="item"><p class="item-title">${esc(n)}</p><p class="small muted">${esc(d)}</p></div>`).join("")}</div></section>`;
};

function kpis(r) {
  const iv = r.intervals?.terminal_energy_Wh || {};
  const hi = (iv.open_high || []).length ? "open" : fmt(iv.high);
  const ev = r.evidence?.share_percent || {};
  const ab = (ev.A || 0) + (ev.B || 0);
  return `<div class="kpis">
    <div class="kpi primary"><div class="label">Terminal energy</div><div class="value">${val(r.terminal_energy_Wh, "Wh")}</div><div class="sub">evidence range ${fmt(iv.low)} – ${esc(hi)}</div></div>
    <div class="kpi"><div class="label">SOC used</div><div class="value">${val(100 * ((r.soc_initial ?? 0) - (r.soc_final ?? 0)), "%")}</div><div class="sub">${fmt(100 * (r.soc_final ?? 0))} % left</div></div>
    <div class="kpi"><div class="label">Minimum voltage</div><div class="value">${val(r.minimum_voltage_V, "V")}</div><div class="sub">peak ${fmt(r.peak_current_A)} A</div></div>
    <div class="kpi"><div class="label">Grade A–B share</div><div class="value">${val(ab, "%")}</div><div class="sub">electrical models only</div></div>
  </div>`;
}

/* Robot builder */
views.robot = async () => {
  const s = S.summary, t = S.templates, cat = S.catalog;
  const comps = cat.cards.filter((c) => c.kind === "component");
  const acts = cat.profiles.actuators;
  const bats = cat.profiles.batteries;
  const isTemplateVehicle = Boolean(S.robot.profile);
  const actuators = S.robot.actuators || [];
  return `<div class="page-head"><h1>Robot</h1><p>Same schema as the YAML files and the Python builder</p></div>
  <section class="block"><div class="block-head"><h2>Start from</h2>
    <div class="row"><button id="export-robot">Export YAML</button><label class="button" for="import-file">Import</label><input class="sr-only" type="file" id="import-file" accept=".yaml,.yml,.json"></div></div>
    <div class="fields two"><div class="field"><label for="tpl">Template</label><select id="tpl">${Object.entries(t.robots).map(([k, v]) => `<option value="${esc(k)}" ${S.templateKey === k ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select></div>
    <div class="field"><label for="robot-name">Name</label><input id="robot-name" value="${esc(S.robot.vehicle?.name || s?.name || "")}" ${isTemplateVehicle ? "disabled" : ""}></div></div>
    <div class="row" style="margin-top:10px"><button id="apply-tpl">Load template</button><span class="hint">Replaces the current robot.</span></div>
    ${S.summaryError ? errorBox(S.summaryError) : ""}
  </section>
  <div class="split">
  <div>
  <section class="block"><div class="block-head"><h2>Actuators <span class="badge info">${s?.actuator_count ?? 0}</span></h2>${isTemplateVehicle ? `<span class="hint">Packaged vehicle geometry</span>` : `<button id="add-act">Add actuator</button>`}</div>
    ${isTemplateVehicle ? actTable(s?.actuators || []) : `<div class="items">${actuators.map((a, i) => actEditor(a, i, acts)).join("") || `<div class="empty">No actuators.</div>`}</div>`}
  </section>
  <section class="block"><div class="block-head"><h2>Components <span class="badge info">${s?.components.length ?? 0}</span></h2>
    <div class="row"><button id="add-custom">Custom hardware</button></div></div>
    <div class="fields two"><div class="field"><label for="add-comp">Add from library</label><select id="add-comp"><option value="">Choose…</option>${comps.filter((c) => c.energy_model === "available").map((c) => `<option value="${esc(c.id)}">${esc(c.manufacturer || "")} ${esc(c.model)} (${esc(c.type)})</option>`).join("")}</select></div>
    <div class="field"><label for="add-comp-rail">On rail</label><select id="add-comp-rail">${railOptions("")}</select></div></div>
    <div class="items" style="margin-top:10px">${(S.robot.components || []).map((c, i) => compRow(c, i)).join("") || `<div class="empty">No components.</div>`}</div>
  </section>
  </div>
  <div>
  <section class="block"><h2>Layout</h2><div style="margin-top:10px">${schematic(s?.actuators || [])}</div></section>
  <section class="block"><div class="block-head"><h2>Battery</h2></div>
    <div class="field"><label for="battery">Pack</label><select id="battery">${bats.map((b) => `<option value="${esc(b)}" ${String(S.robot.battery?.profile || "").includes(b.replace(/-/g, "_").replace("4s_18ah", "4s18ah")) ? "selected" : ""}>${esc(b)}</option>`).join("")}<option value="__custom">Custom battery…</option></select></div>
    ${s ? `<div class="item-meta" style="margin-top:8px"><span><b>${fmt(s.battery.nominal_voltage_V)}</b> V nominal</span><span><b>${fmt(s.battery.capacity_Ah ?? s.battery.capacity_Wh)}</b> ${s.battery.capacity_Ah ? "Ah" : "Wh"}</span><span>cutoff <b>${fmt(s.battery.cutoff_voltage_V)}</b> V</span><span>max <b>${fmt(s.battery.max_current_A)}</b> A</span></div><p class="hint">${esc(s.battery.chemistry || "Chemistry not stated")} — chemistry is metadata, not a model.</p>` : ""}
  </section>
  <section class="block"><div class="block-head"><h2>Rails</h2><button id="add-rail">Add rail</button></div>
    <div class="items">${(S.robot.rails || []).map((r, i) => railRow(r, i)).join("") || `<div class="empty small">No named rails: loads use the legacy payload rail.</div>`}</div>
  </section>
  </div></div>`;
};
function actTable(rows) {
  return `<div class="table-wrap"><table><caption class="sr-only">Actuator geometry</caption><thead><tr><th>ID</th><th>Position (m)</th><th>Direction</th></tr></thead><tbody>${rows.map((a) => `<tr><td>${esc(a.id)}</td><td class="mono">${(a.position_m || []).map((v) => fmt(v)).join(", ")}</td><td class="mono">${(a.direction || []).map((v) => fmt(v)).join(", ")}</td></tr>`).join("")}</tbody></table></div>`;
}
function actEditor(a, i, acts) {
  const model = String(a.profile || "").split("/").pop().replace(".yaml", "").replace(/_/g, "-");
  const xyz = (k, label) => `<fieldset><legend>${label}</legend><div class="xyz">${[0, 1, 2].map((j) => `<input aria-label="${label} ${"xyz"[j]} of ${esc(a.id)}" inputmode="decimal" data-act="${i}" data-k="${k}" data-j="${j}" value="${esc(a[k]?.[j] ?? 0)}">`).join("")}</div></fieldset>`;
  const v3 = (q) => (q || []).map((x) => fmt(x)).join(", ");
  return `<div class="item"><details><summary><span class="item-title">${esc(a.id)}</span> <span class="small muted">${esc(model)} · (${v3(a.position_m)}) m · dir (${v3(a.direction)})</span></summary>
    <div class="fields two"><div class="field"><label for="act-id-${i}">ID</label><input id="act-id-${i}" data-act="${i}" data-k="id" value="${esc(a.id)}"></div>
    <div class="field"><label for="act-model-${i}">Model</label><select id="act-model-${i}" data-act="${i}" data-k="profile">${acts.map((m) => `<option value="${esc(m)}" ${m === model ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></div>
    ${xyz("position_m", "Position (m)")}${xyz("direction", "Direction")}</div>
    <div class="row" style="margin-top:8px"><button class="quiet danger" data-del-act="${i}" aria-label="Remove actuator ${esc(a.id)}">Remove</button></div></details></div>`;
}
function schematic(rows) {
  if (!rows.length) return `<div class="empty small">No geometry.</div>`;
  const W = 320, H = 240, pad = 30;
  const xs = rows.map((a) => a.position_m?.[0] || 0), ys = rows.map((a) => a.position_m?.[1] || 0);
  const span = Math.max(0.2, ...xs.map(Math.abs), ...ys.map(Math.abs));
  const px = (y) => W / 2 + (W / 2 - pad) * y / span, py = (x) => H / 2 - (H / 2 - pad) * x / span;
  const items = rows.map((a) => {
    const [x, y] = a.position_m || [0, 0]; const [dx, dy, dz] = a.direction || [0, 0, 0];
    const cx = px(y), cy = py(x), vert = Math.abs(dz) > 0.7;
    return `<g><circle cx="${cx}" cy="${cy}" r="${vert ? 7 : 5}" fill="${vert ? "var(--series-2)" : "var(--series-1)"}"/>
      ${vert ? "" : `<line x1="${cx}" y1="${cy}" x2="${cx + 22 * dy}" y2="${cy - 22 * dx}" stroke="var(--series-1)" stroke-width="2"/>`}
      <text x="${cx + 9}" y="${cy - 8}" font-size="12" fill="var(--ink-2)">${esc(a.id)}</text></g>`;
  }).join("");
  return `<figure><svg class="schematic" viewBox="0 0 ${W} ${H}" role="img" aria-label="Top view of ${rows.length} actuators; forward is up">
    <line x1="${W / 2}" y1="${pad / 2}" x2="${W / 2}" y2="${H - pad / 2}" stroke="var(--line)"/><line x1="${pad / 2}" y1="${H / 2}" x2="${W - pad / 2}" y2="${H / 2}" stroke="var(--line)"/>
    <text x="${W / 2 + 4}" y="14" font-size="12" fill="var(--muted)">+x forward</text>${items}</svg>
    <figcaption>Top view. Copper: mostly vertical thrust; teal line: horizontal thrust direction.</figcaption></figure>`;
}
function railOptions(sel) {
  const rails = (S.robot.rails || []).map((r) => r.name);
  return [`<option value="" ${!sel ? "selected" : ""}>payload (legacy rail)</option>`, ...rails.map((r) => `<option value="${esc(r)}" ${r === sel ? "selected" : ""}>${esc(r)}</option>`)].join("");
}
function compRow(c, i) {
  const card = S.catalog.cards.find((k) => c.profile && c.profile.endsWith("/" + k.id.replace(/-/g, "_") + ".yaml"));
  const sumc = S.summary?.components.find((x) => x.name === c.name);
  const name = card ? fullName(card) : (c.name || "component");
  return `<div class="item"><div class="item-head"><div><div class="item-title">${esc(c.name)}</div><div class="small muted">${esc(name)}</div></div>
    <button class="quiet danger" data-del-comp="${i}" aria-label="Remove ${esc(c.name)}">Remove</button></div>
    <div class="item-meta">${card?.power_range_W ? `<span><b>${range(card.power_range_W)}</b></span>` : ""}
      ${card ? gradeBadge(card.grade) : ""}${sumc?.status === "unconfigured" ? `<span class="badge bad">unknown power</span>` : ""}
      <span>HoloOcean: <b>${esc(sumc?.simulation_sensor || "not mapped")}</b></span></div>
    <div class="field" style="margin-top:8px"><label for="comp-rail-${i}">Rail</label><select id="comp-rail-${i}" data-comp-rail="${i}">${railOptions(c.rail || "")}</select></div></div>`;
}
function railRow(r, i) {
  return `<div class="item"><div class="item-head"><span class="item-title">${esc(r.name)}</span><button class="quiet danger" data-del-rail="${i}" aria-label="Remove rail ${esc(r.name)}">Remove</button></div>
    <div class="fields two" style="margin-top:8px">
    <div class="field"><label for="rail-kind-${i}">Kind</label><select id="rail-kind-${i}" data-rail="${i}" data-k="kind"><option value="direct" ${r.kind === "direct" ? "selected" : ""}>Pack direct</option><option value="converter" ${r.kind !== "direct" ? "selected" : ""}>Converter</option></select></div>
    ${r.kind === "direct" ? "" : `<div class="field"><label for="rail-v-${i}">Output (V)</label><input id="rail-v-${i}" inputmode="decimal" data-rail="${i}" data-k="output_V" value="${esc(r.output_V ?? "")}"></div>
    <div class="field"><label for="rail-e-${i}">Efficiency (0–1)</label><input id="rail-e-${i}" inputmode="decimal" data-rail="${i}" data-k="efficiency" value="${esc(r.efficiency ?? "")}" placeholder="unknown"><p class="hint">Leave empty if unknown: charged at 1.0 and reported as a lower bound.</p></div>
    <div class="field"><label for="rail-ev-${i}">Evidence record</label><input id="rail-ev-${i}" data-rail="${i}" data-k="efficiency_evidence" value="${esc(r.efficiency_evidence ?? "")}" placeholder="record id"></div>`}
    </div></div>`;
}

function customDialog() {
  const d = $("#dialog");
  d.innerHTML = `<form method="dialog" id="custom-form"><div class="dialog-body stack"><h2 id="dialog-title">Custom hardware</h2>
    <div class="fields two"><div class="field"><label for="c-name">Name</label><input id="c-name" required pattern="[A-Za-z0-9_]+" aria-describedby="c-name-h"><p class="hint" id="c-name-h">Letters, digits, underscores.</p></div>
    <div class="field"><label for="c-cat">Category</label><select id="c-cat"><option>sensors</option><option>compute</option><option>communications</option><option>auxiliaries</option></select></div>
    <div class="field"><label for="c-state">State</label><input id="c-state" value="ACTIVE"></div>
    <div class="field"><label for="c-power">Power (W)</label><input id="c-power" inputmode="decimal" placeholder="empty = unknown"></div>
    <div class="field"><label for="c-src">Source</label><select id="c-src">${SOURCE_TYPES.map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join("")}</select></div>
    <div class="field"><label for="c-cite">Citation</label><input id="c-cite" placeholder="title, DOI or notebook"></div>
    <div class="field"><label for="c-loc">Page / table</label><input id="c-loc"></div>
    <div class="field"><label for="c-rail">Rail</label><select id="c-rail">${railOptions("")}</select></div></div>
    <p class="hint">The grade follows the source type (Python rule): datasheet or own measurement A, paper or dataset B, assumption D, unknown excluded.</p>
    <div id="c-err"></div></div>
    <div class="dialog-foot"><button value="cancel" formnovalidate>Cancel</button><button class="primary" id="c-ok" value="ok">Add</button></div></form>`;
  d.showModal();
  $("#c-ok").addEventListener("click", async (ev) => {
    ev.preventDefault();
    try {
      const out = await api("/api/component/custom", {
        name: $("#c-name").value, category: $("#c-cat").value, states: { [$("#c-state").value || "ACTIVE"]: $("#c-power").value },
        source_type: $("#c-src").value, citation: $("#c-cite").value, locator: $("#c-loc").value, rail: $("#c-rail").value,
      });
      const robot = clone(S.robot);
      robot.components = [...(robot.components || []), out.component];
      robot.evidence = robot.evidence || {};
      robot.evidence.sources = [...(robot.evidence.sources || []), ...out.sources];
      robot.evidence.records = [...(robot.evidence.records || []), ...out.records];
      setRobot(robot); d.close(); toast(`Added ${out.component.name}${out.grade ? ` (grade ${out.grade})` : " (unknown power)"}`); route();
    } catch (e) { $("#c-err").innerHTML = errorBox(e); }
  });
}

function bindRobot() {
  $("#apply-tpl")?.addEventListener("click", () => { S.templateKey = $("#tpl").value; setRobot(clone(S.templates.robots[S.templateKey].robot)); route(); });
  $("#robot-name")?.addEventListener("change", (e) => { const r = clone(S.robot); r.vehicle = { ...(r.vehicle || {}), name: e.target.value }; setRobot(r); route(); });
  $("#export-robot")?.addEventListener("click", async () => { const out = await api("/api/export", { kind: "robot", document: S.robot }); download("robot.yaml", out.yaml); });
  $("#import-file")?.addEventListener("change", importFile);
  $("#add-custom")?.addEventListener("click", customDialog);
  $("#add-act")?.addEventListener("click", () => {
    const r = clone(S.robot); const n = (r.actuators || []).length + 1;
    r.actuators = [...(r.actuators || []), { id: `T${n}`, position_m: [0, 0, 0], direction: [1, 0, 0], profile: "package:actuators/bluerobotics_t200.yaml" }];
    r.actuation = { ...(r.actuation || {}), backend: { mapping: "direct", backend_index: r.actuators.map((_, i) => i) } };
    setRobot(r); route();
  });
  document.querySelectorAll("[data-del-act]").forEach((b) => b.addEventListener("click", () => {
    const r = clone(S.robot); r.actuators.splice(Number(b.dataset.delAct), 1);
    r.actuation = { ...(r.actuation || {}), backend: { mapping: "direct", backend_index: r.actuators.map((_, i) => i) } };
    setRobot(r); route();
  }));
  document.querySelectorAll("[data-act]").forEach((el) => el.addEventListener("change", () => {
    const r = clone(S.robot), a = r.actuators[Number(el.dataset.act)], k = el.dataset.k;
    if (k === "profile") a.profile = `package:actuators/${el.value.replace(/-/g, "_")}.yaml`;
    else if (k === "id") a.id = el.value.trim();
    else a[k][Number(el.dataset.j)] = Number(el.value);
    setRobot(r); route();
  }));
  $("#add-comp")?.addEventListener("change", (e) => {
    if (!e.target.value) return;
    const card = S.catalog.cards.find((c) => c.id === e.target.value);
    const r = clone(S.robot); let name = card.profile_name || card.id.replace(/-/g, "_"); const names = new Set((r.components || []).map((c) => c.name));
    for (let k = 2; names.has(name); k++) name = `${card.profile_name}_${k}`;
    const entry = { profile: `package:components/${card.id.replace(/-/g, "_")}.yaml`, name };
    if ($("#add-comp-rail").value) entry.rail = $("#add-comp-rail").value;
    r.components = [...(r.components || []), entry]; setRobot(r); toast(`Added ${card.model}`); route();
  });
  document.querySelectorAll("[data-del-comp]").forEach((b) => b.addEventListener("click", () => { const r = clone(S.robot); r.components.splice(Number(b.dataset.delComp), 1); setRobot(r); route(); }));
  document.querySelectorAll("[data-comp-rail]").forEach((el) => el.addEventListener("change", () => { const r = clone(S.robot); const c = r.components[Number(el.dataset.compRail)]; if (el.value) c.rail = el.value; else delete c.rail; setRobot(r); route(); }));
  $("#add-rail")?.addEventListener("click", () => { const r = clone(S.robot); const n = (r.rails || []).length + 1; r.rails = [...(r.rails || []), { name: `rail${n}`, kind: "converter", output_V: 5.0 }]; setRobot(r); route(); });
  document.querySelectorAll("[data-del-rail]").forEach((b) => b.addEventListener("click", () => { const r = clone(S.robot); r.rails.splice(Number(b.dataset.delRail), 1); setRobot(r); route(); }));
  document.querySelectorAll("[data-rail]").forEach((el) => el.addEventListener("change", () => {
    const r = clone(S.robot), rail = r.rails[Number(el.dataset.rail)], k = el.dataset.k, v = el.value.trim();
    if (k === "kind") { rail.kind = v; if (v === "direct") { delete rail.output_V; delete rail.efficiency; delete rail.efficiency_evidence; } else rail.output_V = rail.output_V ?? 5; }
    else if (v === "") delete rail[k]; else rail[k] = k === "efficiency_evidence" ? v : Number(v);
    setRobot(r); route();
  }));
  $("#battery")?.addEventListener("change", (e) => {
    if (e.target.value === "__custom") { batteryDialog(); return; }
    const r = clone(S.robot); r.battery = { profile: `package:batteries/${batteryFile(e.target.value)}` }; setRobot(r); route();
  });
}
function batteryFile(name) {
  const map = { "bluerobotics-4s-18ah": "bluerobotics_4s18ah_v2.yaml", "bluerobotics-4s-18ah-v0.1": "bluerobotics_4s18ah.yaml", "bluerobotics-4s-18ah-30q-proxy": "bluerobotics_4s18ah_30q_proxy.yaml", "demo-24v30ah": "demo_24v30ah.yaml" };
  return map[name] || `${name.replace(/-/g, "_")}.yaml`;
}
function batteryDialog() {
  const d = $("#dialog");
  d.innerHTML = `<form method="dialog"><div class="dialog-body stack"><h2 id="dialog-title">Custom battery</h2>
    <div class="fields two">${[["b-v", "Nominal voltage (V)"], ["b-ah", "Capacity (Ah)"], ["b-cut", "Cutoff voltage (V)"], ["b-i", "Max current (A)"], ["b-r", "Resistance (ohm)"]].map(([id, l]) => `<div class="field"><label for="${id}">${l}</label><input id="${id}" inputmode="decimal"></div>`).join("")}
    <div class="field"><label for="b-chem">Chemistry (metadata)</label><input id="b-chem" placeholder="e.g. Li-ion NMC"></div></div>
    <div class="field"><label for="b-ocv">OCV curve: one "SOC, V" pair per line</label><textarea id="b-ocv" placeholder="0, 12.0&#10;0.5, 14.8&#10;1, 16.8"></textarea><p class="hint">Without a source this curve is graded D. Chemistry names do not supply a model.</p></div><div id="b-err"></div></div>
    <div class="dialog-foot"><button value="cancel">Cancel</button><button class="primary" id="b-ok">Use battery</button></div></form>`;
  d.showModal();
  $("#b-ok").addEventListener("click", async (ev) => {
    ev.preventDefault();
    const num = (id) => ($(id).value.trim() === "" ? null : Number($(id).value));
    const ocv = $("#b-ocv").value.trim().split(/\n+/).filter(Boolean).map((l) => l.split(/[,;\s]+/).map(Number));
    const battery = { model: "rint", nominal_voltage_V: num("#b-v"), capacity_Ah: num("#b-ah"), cutoff_voltage_V: num("#b-cut"), max_current_A: num("#b-i"), internal_resistance_ohm: num("#b-r"), initial_soc: 1.0, chemistry: $("#b-chem").value || undefined, ocv_curve: ocv };
    const r = clone(S.robot); r.battery = battery;
    try { await api("/api/robot/summary", { robot: r }); setRobot(r); d.close(); route(); } catch (e) { $("#b-err").innerHTML = errorBox(e); }
  });
}
async function importFile(e) {
  const file = e.target.files[0]; if (!file) return;
  try {
    const out = await api("/api/import", { text: await file.text() });
    if (out.kind === "mission") { S.mission = out.document; } else { S.robot = out.document; }
    save(); toast(`Imported ${out.kind}`); route();
  } catch (err) { $("#main").insertAdjacentHTML("afterbegin", errorBox(err)); }
}

/* Mission builder */
views.mission = async () => {
  const s = S.summary, m = S.mission;
  const wrench = s?.action_mode === "wrench";
  const n = wrench ? 6 : s?.actuator_count || 0;
  const names = wrench ? ["Fx", "Fy", "Fz", "Mx", "My", "Mz"] : (s?.actuators || []).map((a) => a.id);
  const env = Object.fromEntries((S.preflight?.environment || []).map((r) => [`${r.phase}|${r.quantity}`, r.status]));
  return `<div class="page-head"><h1>Mission</h1><p>${m.phases.length} phases · ${fmt(m.phases.reduce((a, p) => a + Number(p.duration_s || 0), 0))} s</p></div>
  <section class="block"><div class="fields two"><div class="field"><label for="m-name">Mission name</label><input id="m-name" value="${esc(m.name)}"></div>
    <div class="row" style="align-self:end"><button id="add-phase">Add phase</button><button id="export-mission">Export YAML</button><label class="button" for="import-file">Import</label><input class="sr-only" type="file" id="import-file" accept=".yaml,.yml,.json"></div></div>
    <div class="timeline" style="margin-top:12px" aria-hidden="true">${m.phases.map((p) => `<div style="flex:${Number(p.duration_s) || 1}">${esc(p.name)}</div>`).join("")}</div></section>
  <div class="items" style="margin-top:12px">${m.phases.map((p, i) => phaseEditor(p, i, n, names, wrench, env)).join("")}</div>`;
};
function phaseEditor(p, i, n, names, wrench, env) {
  const key = wrench ? "wrench_N" : "thrust_N";
  const values = p.propulsion?.[key] || Array(n).fill(0);
  const comps = S.summary?.components || [];
  const envField = (k, label, unit) => {
    const v = p[k]; const status = env[`${p.name}|${k}`];
    const input = k === "current_m_s" ? `<div class="xyz">${[0, 1, 2].map((j) => `<input aria-label="Current ${"xyz"[j]} (m/s), ${esc(p.name)}" inputmode="decimal" data-ph="${i}" data-env="${k}" data-j="${j}" value="${esc(v?.[j] ?? "")}">`).join("")}</div>`
      : `<input id="ph-${k}-${i}" inputmode="decimal" data-ph="${i}" data-env="${k}" value="${esc(v ?? "")}">`;
    return `<div class="field">${k === "current_m_s" ? `<fieldset><legend>${label} (${unit})</legend>${input}</fieldset>` : `<label for="ph-${k}-${i}">${label} (${unit})</label>${input}`}${status ? `<p class="hint">${esc(status)}</p>` : ""}</div>`;
  };
  return `<section class="block" aria-labelledby="ph-title-${i}"><div class="block-head"><h2 id="ph-title-${i}">${i + 1}. ${esc(p.name)} <span class="badge info">${fmt(p.duration_s)} s</span></h2>
    <div class="row"><button class="quiet" data-up="${i}" ${i ? "" : "disabled"} aria-label="Move ${esc(p.name)} up">Up</button><button class="quiet" data-dup="${i}" aria-label="Duplicate ${esc(p.name)}">Duplicate</button><button class="quiet danger" data-del-ph="${i}" aria-label="Remove ${esc(p.name)}">Remove</button></div></div>
    <div class="fields three"><div class="field"><label for="ph-name-${i}">Name</label><input id="ph-name-${i}" data-ph="${i}" data-k="name" value="${esc(p.name)}"></div>
    <div class="field"><label for="ph-dur-${i}">Duration (s)</label><input id="ph-dur-${i}" inputmode="decimal" data-ph="${i}" data-k="duration_s" value="${esc(p.duration_s)}"></div>
    <div class="field"><label for="ph-act-${i}">Target / action</label><input id="ph-act-${i}" data-ph="${i}" data-k="action" value="${esc(p.action ?? "")}"></div></div>
    <details style="margin-top:8px"><summary>Propulsion <span class="muted small">${wrench ? "wrench" : "thrust per actuator"} · energy-only</span></summary>
      <div class="fields three">${values.slice(0, n).map((v, j) => `<div class="field"><label for="ph-p-${i}-${j}">${esc(names[j] || j)} (${wrench && j > 2 ? "N·m" : "N"})</label><input id="ph-p-${i}-${j}" inputmode="decimal" data-ph="${i}" data-prop="${key}" data-j="${j}" value="${esc(v)}"></div>`).join("")}</div>
      <p class="hint">Prescribed, not simulated. In HoloOcean modes the controller and the simulator produce the thrust.</p></details>
    <details><summary>Component states <span class="muted small">${Object.keys(p.component_states || {}).length} set</span></summary>
      <div class="fields three">${comps.map((c) => `<div class="field"><label for="ph-s-${i}-${esc(c.name)}">${esc(c.name)}</label><select id="ph-s-${i}-${esc(c.name)}" data-ph="${i}" data-state="${esc(c.name)}"><option value="">unchanged</option>${[...new Set(c.states)].map((st) => `<option ${p.component_states?.[c.name] === st ? "selected" : ""}>${esc(st)}</option>`).join("")}</select></div>`).join("") || `<p class="muted">No components.</p>`}</div></details>
    <details><summary>Environment</summary><div class="fields three">${envField("water_temperature_C", "Water temperature", "°C")}${envField("current_m_s", "Current", "m/s")}${envField("water_density_kg_m3", "Water density", "kg/m³")}</div></details>
  </section>`;
}
function bindMission() {
  const m = () => clone(S.mission);
  const set = (x) => { S.mission = x; save(); route(); };
  $("#m-name")?.addEventListener("change", (e) => { const x = m(); x.name = e.target.value; set(x); });
  $("#add-phase")?.addEventListener("click", () => { const x = m(); x.phases.push({ name: `phase${x.phases.length + 1}`, duration_s: 60 }); set(x); });
  $("#export-mission")?.addEventListener("click", async () => { try { const out = await api("/api/export", { kind: "mission", document: S.mission }); download("mission.yaml", out.yaml); } catch (e) { $("#main").insertAdjacentHTML("afterbegin", errorBox(e)); } });
  $("#import-file")?.addEventListener("change", importFile);
  document.querySelectorAll("[data-del-ph]").forEach((b) => b.addEventListener("click", () => { const x = m(); if (x.phases.length > 1) { x.phases.splice(Number(b.dataset.delPh), 1); set(x); } }));
  document.querySelectorAll("[data-dup]").forEach((b) => b.addEventListener("click", () => { const x = m(); const i = Number(b.dataset.dup); const c = clone(x.phases[i]); c.name = `${c.name}_copy`; x.phases.splice(i + 1, 0, c); set(x); }));
  document.querySelectorAll("[data-up]").forEach((b) => b.addEventListener("click", () => { const x = m(); const i = Number(b.dataset.up); [x.phases[i - 1], x.phases[i]] = [x.phases[i], x.phases[i - 1]]; set(x); }));
  document.querySelectorAll("[data-ph]").forEach((el) => el.addEventListener("change", () => {
    const x = m(), p = x.phases[Number(el.dataset.ph)], v = el.value.trim();
    if (el.dataset.k) { if (el.dataset.k === "duration_s") p.duration_s = Number(v); else if (v === "") delete p[el.dataset.k]; else p[el.dataset.k] = v; }
    else if (el.dataset.prop) { const k = el.dataset.prop; const n = S.summary?.action_mode === "wrench" ? 6 : S.summary?.actuator_count || 0; p.propulsion = { [k]: (p.propulsion?.[k] || Array(n).fill(0)).slice(0, n) }; p.propulsion[k][Number(el.dataset.j)] = Number(v || 0); if (p.propulsion[k].every((q) => q === 0)) delete p.propulsion; }
    else if (el.dataset.state !== undefined) { p.component_states = p.component_states || {}; if (v) p.component_states[el.dataset.state] = v; else delete p.component_states[el.dataset.state]; if (!Object.keys(p.component_states).length) delete p.component_states; }
    else if (el.dataset.env) { const k = el.dataset.env; if (k === "current_m_s") { const c = p.current_m_s || [0, 0, 0]; c[Number(el.dataset.j)] = Number(v || 0); p.current_m_s = c; } else if (v === "") delete p[k]; else p[k] = Number(v); }
    set(x);
  }));
}

/* Run (pre-flight + launch + live) */
views.run = async () => {
  await refreshPreflight();
  const pf = S.preflight;
  const groups = [["attention", "Needs attention", "!"], ["interpretation", "Affects interpretation", "i"], ["info", "Information", "·"]];
  return `<div class="page-head"><h1>Run</h1><p>Pre-flight check, then run</p></div>
  <section class="block"><h2>Mode</h2><div class="mode-cards" role="radiogroup" aria-label="Experiment mode" style="margin-top:10px">${MODES.map(([k, n, d]) => `<label class="mode-card" data-checked="${S.mode === k}"><input type="radio" name="mode" value="${k}" ${S.mode === k ? "checked" : ""}><b>${esc(n)}</b><span class="scope"><span class="sr-only">. </span>${esc(d)}</span></label>`).join("")}</div>
    ${pf.scope ? `<details style="margin-top:8px"><summary>What this mode can and cannot establish</summary><div class="cols-2 grid"><div class="scope"><b>Can</b><ul>${pf.scope.establishes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div><div class="scope"><b>Cannot</b><ul>${pf.scope.cannot_establish.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div></details>` : ""}
  </section>
  <section class="block"><div class="block-head"><h2>Pre-flight check</h2>${pf.ok ? `<span class="badge ok">✓ runnable</span>` : `<span class="badge bad">× cannot run</span>`}</div>
    <p class="small">${pf.counts?.errors || 0} errors · ${pf.counts?.attention || 0} need attention · ${pf.counts?.interpretation || 0} affect interpretation. Exploratory runs are allowed with warnings.</p>
    <div class="issues" style="margin-top:10px">${(pf.errors || []).map((e) => errorBox({ payload: e })).join("")}</div>
    ${groups.map(([sev, title, icon]) => { const list = (pf.issues || []).filter((i) => i.severity === sev); return list.length ? `<details ${sev === "attention" ? "open" : ""} style="margin-top:8px"><summary>${title} <span class="badge ${sev === "attention" ? "warn" : "info"}">${list.length}</span></summary><div class="issues">${list.map((i) => `<div class="issue ${sev}"><span class="icon" aria-hidden="true">${icon}</span><div><p class="msg">${esc(i.message)}</p><p class="kind">${esc(i.kind.replace(/_/g, " "))} · ${esc(i.subject)}</p></div></div>`).join("")}</div></details>` : ""; }).join("")}
    ${pf.backend ? `<p class="small" style="margin-top:10px"><b>Backend:</b> ${esc(pf.backend.status)} — ${esc(pf.backend.message)}</p>` : ""}
  </section>
  <section class="block"><div class="block-head"><h2>Launch</h2></div>
    ${S.mode === "energy-only" ? `<div class="fields two"><div class="field"><label for="run-label">Run label</label><input id="run-label" value="${esc(S.mission.name)}"></div><div class="row" style="align-self:end"><button class="primary" id="run-btn" ${pf.ok ? "" : "disabled"}>Run energy-only</button></div></div><div id="run-out" aria-live="polite"></div>`
      : `<p>HoloOcean runs need the simulator process. Export the robot and mission, then start a runner; this page shows its live telemetry.</p><pre class="mono small" style="white-space:pre-wrap;overflow-wrap:anywhere">python examples/realtime_energy_demo.py --backend holoocean --holoocean-binary &lt;patched Holodeck.exe&gt; --dashboard-port 8765 --telemetry-port 8766</pre><p class="hint">The packaged runner drives the BlueROV2 profile. Other robots need a robot-to-agent mapping.</p>`}
  </section>
  <section class="block"><div class="block-head"><h2>Live</h2><span id="live-badge" class="badge info">waiting</span></div><div id="live"></div></section>`;
};
function bindRun() {
  document.querySelectorAll("input[name=mode]").forEach((el) => el.addEventListener("change", () => { S.mode = el.value; route(); }));
  $("#run-btn")?.addEventListener("click", async () => {
    const b = $("#run-btn"); b.disabled = true; b.textContent = "Running…";
    try { S.lastRun = await api("/api/run", { robot: S.robot, mission: S.mission, label: $("#run-label").value }); toast("Run complete"); location.hash = "#/results"; }
    catch (e) { $("#run-out").innerHTML = errorBox(e); b.disabled = false; b.textContent = "Run energy-only"; }
  });
  pollLive();
}
async function pollLive() {
  if (!$("#live")) return;
  try {
    const st = await api("/api/state"); const r = st.latest;
    $("#live-badge").textContent = st.status; $("#live-badge").className = `badge ${st.status === "live" ? "ok" : "info"}`;
    $("#live").innerHTML = r ? `<div class="kpis">
      <div class="kpi"><div class="label">Phase</div><div class="value" style="font-size:1.1rem">${esc(r.phase || "—")}</div></div>
      <div class="kpi primary"><div class="label">Total power</div><div class="value">${val(r.power_total_W, "W")}</div></div>
      <div class="kpi"><div class="label">SOC</div><div class="value">${val(100 * r.soc, "%")}</div></div>
      <div class="kpi"><div class="label">Voltage · current</div><div class="value">${val(r.voltage_V, "V")}</div><div class="sub">${fmt(r.current_A)} A</div></div>
      <div class="kpi"><div class="label">Propulsion</div><div class="value">${val(r.power_propulsion_W, "W")}</div></div>
      <div class="kpi"><div class="label">Payload</div><div class="value">${val(r.power_payload_W, "W")}</div></div>
      <div class="kpi"><div class="label">Communications</div><div class="value">${val(r.power_communications_W ?? 0, "W")}</div></div>
      <div class="kpi"><div class="label">Limits</div><div class="value" style="font-size:1rem">${esc(r.battery_state || "—")}</div><div class="sub">action factor ${fmt(r.derating_factor)}</div></div></div>
      <details><summary>Actuators and components</summary>${bars(Object.entries(r.sensor_power_W || {}).map(([k, v]) => [k, v]), "W")}${bars((r.thruster_power_W || []).map((v, i) => [`actuator ${i + 1}`, v]), "W")}</details>
      ${st.history?.length > 1 ? lineChart({ time_s: st.history.map((h) => h.time_s), p: st.history.map((h) => h.power_total_W) }, ["p"], ["Total power"], "W", "Live total power") : ""}`
      : `<p class="muted">No telemetry. Live data appear when a runner publishes to this dashboard.</p>`;
    const ls = $("#live-status"); ls.dataset.state = st.status; ls.lastChild.textContent = st.status === "live" ? "Live run" : st.status === "ended" ? "Run ended" : "No live run";
  } catch (e) { /* keep last view */ }
  setTimeout(pollLive, 1000);
}

/* Results */
views.results = async () => {
  const run = S.lastRun;
  if (!run) return `<div class="page-head"><h1>Results</h1></div><div class="empty">No result in this session. Run a mission, or open a saved run in Compare.</div>`;
  const r = run.report, sr = run.series;
  const cat = Object.entries(r.category_energy_Wh || {}).filter(([, v]) => v > 1e-12).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k.replace(/_/g, " "), v]);
  const phases = Object.entries(r.phases || {}).map(([k, v]) => [k, v.terminal_energy_Wh, `${fmt(v.duration_s)} s`]);
  const devices = Object.entries(r.device_energy_Wh || {}).filter(([, v]) => v > 1e-12).sort((a, b) => b[1] - a[1]);
  const warnings = r.evidence?.scientific_warnings || [];
  const dyn = r.evidence?.dynamics_evidence || r.evidence?.dynamics || {};
  const shares = r.evidence?.share_percent || {};
  return `<div class="page-head"><h1>Results</h1><p>${esc(r.label || run.run_id)} · ${esc(r.mode || "energy-only")}</p>
    <div class="row"><button id="dl-report">Report JSON</button><button id="dl-robot">Robot YAML</button><button id="dl-mission">Mission YAML</button></div></div>
  ${kpis(r)}
  <div class="grid cols-2" style="margin-top:12px">
    <section class="block"><h2>Power</h2>${lineChart(sr, ["power_total_W", "power_propulsion_W", "power_payload_W"], ["Total", "Propulsion", "Payload"], "W", "Power over the mission")}</section>
    <section class="block"><h2>State of charge and voltage</h2>${lineChart({ time_s: sr.time_s, soc: sr.soc.map((v) => (v === null ? null : 100 * v)) }, ["soc"], ["SOC (%)"], "%", "State of charge", false)}${lineChart({ time_s: sr.time_s, v: sr.voltage_V }, ["v"], ["Voltage (V)"], "V", "Battery voltage", false)}</section>
    <section class="block"><h2>By category</h2>${bars(cat, "Wh")}</section>
    <section class="block"><h2>By phase</h2>${bars(phases, "Wh")}</section>
    <section class="block"><h2>By device</h2>${bars(devices.slice(0, 16), "Wh")}${devices.length > 16 ? `<p class="hint">${devices.length - 16} more in the report JSON.</p>` : ""}</section>
    <section class="block"><h2>Evidence</h2>
      <div class="row">${["A", "B", "C", "D"].map((g) => `${gradeBadge(g)} <span class="small">${fmt(shares[g] || 0)} %</span>`).join(" ")}</div>
      <p class="small" style="margin-top:8px">Shares of terminal energy by the grade of its electrical model. ${dyn.status ? `Dynamics: <b>${esc(dyn.status)}</b>.` : ""} Battery losses ${fmt(r.category_energy_Wh?.battery_losses)} Wh.</p>
      <p class="small">Uncertainty: ${fmt(r.intervals?.terminal_energy_Wh?.low)} – ${(r.intervals?.terminal_energy_Wh?.open_high || []).length ? "open (unknown contributions)" : fmt(r.intervals?.terminal_energy_Wh?.high)} Wh.</p>
    </section>
  </div>
  <section class="block"><details ${warnings.length ? "" : ""}><summary>Scientific warnings <span class="badge warn">${warnings.length}</span></summary>
    <div class="issues">${warnings.map((w) => `<div class="issue attention"><span class="icon" aria-hidden="true">!</span><div><p class="msg">${esc(w.effect)}</p><p class="kind">${esc(String(w.kind).replace(/_/g, " "))} · ${esc(w.subject)} · ${fmt(w.energy_Wh)} Wh${w.share_percent != null ? ` (${fmt(w.share_percent)} %)` : ""}</p></div></div>`).join("")}</div></details></section>
  <section class="block"><details><summary>Environment in this run</summary><div class="issues">${(run.environment || []).map((e) => `<div class="issue"><span class="icon" aria-hidden="true">·</span><div><p class="msg">${esc(e.phase)}: ${esc(e.quantity)} = ${esc(JSON.stringify(e.value))}</p><p class="kind">${esc(e.status)}</p></div></div>`).join("") || `<p class="muted">No environment settings.</p>`}</div></details></section>`;
};
function bindResults() {
  const r = S.lastRun; if (!r) return;
  $("#dl-report")?.addEventListener("click", () => download(`${r.run_id}.json`, JSON.stringify(r.report, null, 1), "application/json"));
  $("#dl-robot")?.addEventListener("click", async () => download("robot.yaml", (await api("/api/export", { kind: "robot", document: r.report.robot })).yaml));
  $("#dl-mission")?.addEventListener("click", async () => download("mission.yaml", (await api("/api/export", { kind: "mission", document: r.report.mission })).yaml));
}

/* Compare */
views.compare = async () => {
  S.runs = (await api("/api/runs")).runs;
  const opts = (sel) => S.runs.map((r) => `<option value="${esc(r.file)}" ${r.file === sel ? "selected" : ""}>${esc(r.file.replace(".json", ""))} · ${fmt(r.terminal_energy_Wh)} Wh</option>`).join("");
  if (S.runs.length < 2) return `<div class="page-head"><h1>Compare</h1></div><div class="empty">Two saved runs are needed (${S.runs.length} available). Run two configurations of the same mission.</div>`;
  const a = S.cmpA || S.runs[S.runs.length - 2].file, b = S.cmpB || S.runs[S.runs.length - 1].file;
  return `<div class="page-head"><h1>Compare</h1><p>Paired comparison on the bus side</p></div>
  <section class="block"><div class="fields two"><div class="field"><label for="cmp-a">Run A</label><select id="cmp-a">${opts(a)}</select></div><div class="field"><label for="cmp-b">Run B</label><select id="cmp-b">${opts(b)}</select></div></div>
  <div class="row" style="margin-top:10px"><button class="primary" id="cmp-go">Compare</button></div></section><div id="cmp-out"></div>`;
};
function verdictText(v) {
  return { A_LOWER_SUPPORTED: ["ok", "✓ A lower — supported"], B_LOWER_SUPPORTED: ["ok", "✓ B lower — supported"], RANKING_NOT_SUPPORTED: ["warn", "! Ranking not supported"] }[v] || ["info", v];
}
function bindCompare() {
  $("#cmp-a")?.addEventListener("change", (e) => { S.cmpA = e.target.value; });
  $("#cmp-b")?.addEventListener("change", (e) => { S.cmpB = e.target.value; });
  $("#cmp-go")?.addEventListener("click", async () => {
    try {
      const c = await api("/api/compare", { a: $("#cmp-a").value, b: $("#cmp-b").value });
      $("#cmp-out").innerHTML = `<section class="block"><div class="kpis">
        <div class="kpi"><div class="label">A terminal</div><div class="value">${val(c.a.terminal_energy_Wh, "Wh")}</div></div>
        <div class="kpi"><div class="label">B terminal</div><div class="value">${val(c.b.terminal_energy_Wh, "Wh")}</div></div>
        <div class="kpi"><div class="label">A − B</div><div class="value">${val(c.nominal.difference_Wh, "Wh")}</div></div>
        <div class="kpi"><div class="label">Relative to B</div><div class="value">${val(c.nominal.difference_percent, "%")}</div></div></div>
        ${c.same_mission ? "" : `<div class="issue attention" style="margin-top:10px"><span class="icon" aria-hidden="true">!</span><p class="msg">The runs use different missions: a paired comparison assumes the same mission.</p></div>`}
        <div class="items" style="margin-top:12px"><div class="item"><div class="item-head"><span class="item-title">Nominal</span><span class="badge info">${c.nominal.lower === "tie" ? "tie" : `${c.nominal.lower.toUpperCase()} lower`}</span></div><p class="small muted">Point values only; no evidence considered.</p></div>
        ${c.policies.map((p) => { const [cls, txt] = verdictText(p.verdict); return `<div class="item"><div class="item-head"><span class="item-title">${esc(p.policy)}</span><span class="badge ${cls}">${esc(txt)}</span></div>
          <p class="small">Supported difference A − B: ${p.difference_low_Wh == null ? "open" : fmt(p.difference_low_Wh)} to ${p.difference_high_Wh == null ? "open" : fmt(p.difference_high_Wh)} Wh · ${p.differing.length} differing contributions</p>
          ${p.assumptions.length ? `<ul class="small">${p.assumptions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div>`; }).join("")}</div></section>`;
    } catch (e) { $("#cmp-out").innerHTML = errorBox(e); }
  });
}

/* Hardware library */
views.library = async () => {
  const cards = S.catalog.cards, f = S.libFilter;
  const uniq = (k) => [...new Set(cards.map((c) => c[k]).filter(Boolean))].sort();
  const shown = cards.filter((c) => (!f.q || `${c.model} ${c.manufacturer} ${c.type} ${c.id}`.toLowerCase().includes(f.q.toLowerCase()))
    && (!f.type || c.type === f.type) && (!f.maker || c.manufacturer === f.maker) && (!f.grade || c.grade === f.grade)
    && (!f.sim || (f.sim === "mapped" ? c.simulation && c.kind === "component" : !c.simulation)) && (!f.kind || c.kind === f.kind)
    && (!f.volt || !c.supply_V || (c.supply_V[0] <= Number(f.volt) && Number(f.volt) <= c.supply_V[1])));
  const sel = (id, label, key, values) => `<div class="field"><label for="${id}">${label}</label><select id="${id}" data-f="${key}"><option value="">All</option>${values.map((v) => `<option ${f[key] === v ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></div>`;
  return `<div class="page-head"><h1>Hardware</h1><p>${shown.length} of ${cards.length} items · every number from the evidence registry</p></div>
  <section class="block"><div class="field"><label for="f-q">Search</label><input id="f-q" type="search" data-f="q" value="${esc(f.q || "")}" placeholder="model, maker, type"></div>
    <details ${Object.entries(f).some(([k, v]) => k !== "q" && v) || window.innerWidth >= 1024 ? "open" : ""}><summary>Filters <span class="badge info">${Object.entries(f).filter(([k, v]) => k !== "q" && v).length} active</span></summary><div class="fields three">
    ${sel("f-kind", "Kind", "kind", uniq("kind"))}${sel("f-type", "Type", "type", uniq("type"))}${sel("f-maker", "Manufacturer", "maker", uniq("manufacturer"))}${sel("f-grade", "Evidence grade", "grade", ["A", "B", "C", "D"])}
    <div class="field"><label for="f-sim">HoloOcean mapping</label><select id="f-sim" data-f="sim"><option value="">All</option><option value="mapped" ${f.sim === "mapped" ? "selected" : ""}>mapped</option><option value="none" ${f.sim === "none" ? "selected" : ""}>not mapped</option></select></div>
    <div class="field"><label for="f-volt">Runs from supply (V)</label><input id="f-volt" inputmode="decimal" data-f="volt" value="${esc(f.volt || "")}" placeholder="e.g. 16"></div></div></details></section>
  <div class="items cards" style="margin-top:12px">${shown.map(hwCard).join("") || `<div class="empty">No hardware matches.</div>`}</div>`;
};
function hwCard(c) {
  const power = c.power_range_W ? range(c.power_range_W) : (c.kind === "battery" ? "" : "no published power");
  const src = c.sources?.[0]?.kind || (c.kind === "actuator" ? "Manufacturer dataset / literature" : "");
  return `<article class="item"><div class="item-head"><div><h3 class="item-title">${esc(c.model)}</h3><p class="small muted">${esc(c.manufacturer || "")} · ${esc(c.type)}</p></div>${gradeBadge(c.grade)}</div>
    <div class="item-meta">${power ? `<span>Power <b>${esc(power)}</b>${c.upper_bound ? " <span class=\"badge warn\">max used</span>" : ""}</span>` : ""}
      ${c.supply_V ? `<span>Supply <b>${fmt(c.supply_V[0])}–${fmt(c.supply_V[1])} V</b></span>` : c.kind === "component" ? `<span>Supply <b>not recorded</b></span>` : ""}
      <span>Energy model <b>${c.energy_model === "available" ? "available" : "unknown power"}</b></span>
      <span>HoloOcean <b>${esc(c.kind === "component" ? (c.simulation || "not mapped") : (c.simulation || "—"))}</b></span>
      ${src ? `<span>${esc(src)}</span>` : ""}</div>
    <div class="row" style="margin-top:8px"><button class="quiet" data-hw="${esc(c.kind)}|${esc(c.id)}" aria-label="Evidence for ${esc(c.model)}">Evidence</button>
    ${c.kind === "component" && c.energy_model === "available" ? `<button class="quiet" data-add-hw="${esc(c.id)}" aria-label="Add ${esc(c.model)} to robot">Add to robot</button>` : ""}</div></article>`;
}
async function hwDetail(kind, id) {
  const d = await api(`/api/catalog/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`);
  const dlg = $("#dialog");
  dlg.innerHTML = `<div class="dialog-body stack"><h2 id="dialog-title">${esc(fullName(d))}</h2>
    ${(d.states || []).length ? `<div class="table-wrap"><table><caption class="sr-only">Power states</caption><thead><tr><th>State</th><th class="num">Used (W)</th><th class="num">Range (W)</th><th>Bound</th><th>Grade</th></tr></thead><tbody>${d.states.map((s) => `<tr><td>${esc(s.state)}</td><td class="num">${fmt(s.power_W)}</td><td class="num">${s.min_W != null || s.max_W != null ? `${fmt(s.min_W)}–${fmt(s.max_W)}` : "—"}</td><td>${esc(s.bound || "—")}</td><td>${gradeBadge(s.grade)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    ${(d.fields || []).length ? `<div class="table-wrap"><table><thead><tr><th>Field</th><th>Value</th><th>Grade</th></tr></thead><tbody>${d.fields.map((x) => `<tr><td>${esc(x.field)}</td><td class="mono">${x.points ? `${x.points} points` : fmt(x.value)}</td><td>${gradeBadge(x.grade)}</td></tr>`).join("")}</tbody></table></div>` : ""}
    ${(d.records || []).map((r) => `<details><summary>${esc(r.id)} ${gradeBadge(r.grade)}</summary><div class="small stack">
      <p><b>Relation</b> ${esc(r.relation)} · <b>bound</b> ${esc(r.bound)} · <b>value</b> ${fmt(r.value)} ${esc(r.unit || "")}${r.value_min != null || r.value_max != null ? ` (range ${fmt(r.value_min)}–${fmt(r.value_max)})` : ""}</p>
      ${r.location && Object.keys(r.location).length ? `<p><b>Location</b> ${esc(Object.entries(r.location).map(([k, v]) => `${k} ${v}`).join("; "))}</p>` : ""}
      ${r.conditions && Object.keys(r.conditions).length ? `<p><b>Conditions</b> ${esc(Object.entries(r.conditions).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join("; "))}</p>` : ""}
      ${r.derivation ? `<p><b>Derivation</b> ${esc(r.derivation)}</p>` : ""}
      ${(r.source_details || []).map((s) => `<p><b>Source</b> ${esc(s.kind)}: ${esc(s.title || s.id)}${s.doi ? ` · doi ${esc(s.doi)}` : ""}${/^https?:\/\//.test(s.url || "") ? ` · <a href="${esc(s.url)}" rel="noopener noreferrer" target="_blank">link</a>` : ""}</p>`).join("")}
      ${r.notes ? `<p class="muted">${esc(r.notes)}</p>` : ""}</div></details>`).join("")}
    ${d.notes ? `<p class="small muted">${esc(d.notes)}</p>` : ""}</div>
    <div class="dialog-foot"><button id="dlg-close">Close</button></div>`;
  dlg.showModal(); $("#dlg-close").addEventListener("click", () => dlg.close());
}
function bindLibrary() {
  document.querySelectorAll("[data-f]").forEach((el) => el.addEventListener(el.type === "search" || el.dataset.f === "volt" ? "change" : "change", () => { S.libFilter = { ...S.libFilter, [el.dataset.f]: el.value }; route(); }));
  document.querySelectorAll("[data-hw]").forEach((b) => b.addEventListener("click", () => { const [k, id] = b.dataset.hw.split("|"); hwDetail(k, id).catch((e) => toast(e.message)); }));
  document.querySelectorAll("[data-add-hw]").forEach((b) => b.addEventListener("click", () => {
    const card = S.catalog.cards.find((c) => c.id === b.dataset.addHw); const r = clone(S.robot);
    let name = card.profile_name; const names = new Set((r.components || []).map((c) => c.name)); for (let k = 2; names.has(name); k++) name = `${card.profile_name}_${k}`;
    r.components = [...(r.components || []), { profile: `package:components/${card.id.replace(/-/g, "_")}.yaml`, name }]; setRobot(r); toast(`Added ${card.model} to the robot`);
  }));
}

/* Evidence */
views.evidence = async () => {
  await refreshPreflight();
  const pf = S.preflight, r = S.lastRun?.report;
  const byKind = {};
  (pf.issues || []).forEach((i) => { (byKind[i.kind] = byKind[i.kind] || []).push(i); });
  const rows = r?.intervals?.contributions || [];
  return `<div class="page-head"><h1>Evidence</h1><p>What the numbers rest on</p></div>
  <section class="block"><h2>Grades</h2><div class="items cards" style="margin-top:10px">
    ${[["A", "Measured or exact for this device (datasheet, own measurement)"], ["B", "Representative: published data for the device under related conditions"], ["C", "Proxy: a related device or a scaled cell-level value"], ["D", "Assumption or placeholder: no published evidence"]].map(([g, t]) => `<div class="item">${gradeBadge(g)}<p class="small" style="margin-top:6px">${esc(t)}</p></div>`).join("")}</div>
    <p class="hint" style="margin-top:8px">A grade is capped by the relation between the evidence and the configured device (exact, representative, proxy, user).</p></section>
  <section class="block"><h2>Current robot</h2>${Object.entries(byKind).map(([k, list]) => `<details><summary>${esc(k.replace(/_/g, " "))} <span class="badge info">${list.length}</span></summary><ul class="small">${list.map((i) => `<li>${esc(i.message)}</li>`).join("")}</ul></details>`).join("") || `<p class="muted">No issues.</p>`}</section>
  <section class="block"><h2>Last run: contributions with evidence</h2>${rows.length ? `<div class="items">${rows.map((x) => `<div class="item"><div class="item-head"><span class="item-title">${esc(x.device)} · ${esc(x.state)}</span>${gradeBadge(x.grade)}</div>
    <div class="item-meta"><span><b>${fmt(x.energy_Wh)}</b> Wh</span><span>rail ${esc(x.rail)}</span><span>range ×${x.ratio ? `${x.ratio[0] == null ? "open" : fmt(x.ratio[0])}–${x.ratio[1] == null ? "open" : fmt(x.ratio[1])}` : "open"}</span></div>
    <details><summary class="small">Record</summary><p class="small mono">${esc(x.record)}</p></details></div>`).join("")}</div>` : `<div class="empty">Run a mission to see per-contribution evidence.</div>`}</section>`;
};

/* ---------- router ---------- */
const binders = { robot: bindRobot, mission: bindMission, run: bindRun, results: bindResults, compare: bindCompare, library: bindLibrary };
async function route() {
  const name = (location.hash.replace(/^#\/?/, "") || "overview").split("?")[0];
  const view = views[name] ? name : "overview";
  document.querySelectorAll("nav.tabs a").forEach((a) => a.setAttribute("aria-current", a.getAttribute("href") === `#/${view}` ? "page" : "false"));
  const y = window.scrollY;
  if (["overview", "robot", "mission"].includes(view)) { await refreshSummary(); }
  if (view === "overview" || view === "mission") await refreshPreflight();
  const main = $("#main");
  try { main.innerHTML = await views[view](); } catch (e) { main.innerHTML = errorBox(e); }
  document.title = `${view[0].toUpperCase()}${view.slice(1)} · HoloEnergy`;
  binders[view]?.();
  // Move focus to the new content on navigation, but not on the first load (keeps the skip link first).
  if (route.last === undefined) { /* initial load */ } else if (route.last !== view) { main.focus({ preventScroll: true }); window.scrollTo(0, 0); } else window.scrollTo(0, y);
  route.last = view;
}

async function init() {
  [S.catalog, S.templates] = await Promise.all([api("/api/catalog"), api("/api/templates")]);
  S.templateKey = "four-thruster-rov";
  S.robot = load("he.robot") || clone(S.templates.robots[S.templateKey].robot);
  S.mission = load("he.mission") || clone(S.templates.mission);
  window.addEventListener("hashchange", route);
  await route();
}
init().catch((e) => { $("#main").innerHTML = errorBox(e); });
