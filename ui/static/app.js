"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const state = { incidents: [], selected: null, followLatest: true, report: null, approvals: { pending: [], history: [] }, stopped: null, mode: "unknown", events: [], cursor: 0, epoch: "", warKey: "", refreshing: false, busy: false };
const esc = value => String(value ?? "—").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const pretty = value => typeof value === "string" ? value : JSON.stringify(value, null, 2);
const words = value => String(value ?? "unknown").replaceAll("_", " ");
const date = value => value && !Number.isNaN(new Date(value).getTime()) ? new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Kolkata", hour12: false }).format(new Date(value)) + " IST" : "—";
const number = (value, digits = 1) => value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toLocaleString("en-IN", { maximumFractionDigits: digits });
const percent = value => value == null ? "—" : number(Number(value) * 100) + "%";
const chip = status => `<span class="chip ${esc(status)}">${esc(words(status))}</span>`;
const tier = value => `<span class="chip tier-${esc(value)}">Tier ${esc(value)}</span>`;
const fact = (label, value) => `<div class="fact"><small>${esc(label)}</small><strong>${esc(value ?? "Not recorded")}</strong></div>`;

async function api(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options, headers: { "Content-Type": "application/json", ...options.headers }, signal: options.signal || AbortSignal.timeout(30000) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : pretty(data.detail || data));
  return data;
}

function notice(message) { $("#notice").textContent = message; $("#notice").hidden = !message; }
function navigate() {
  const view = location.hash.slice(1) || "war-room";
  const valid = ["war-room", "incidents", "services", "approvals", "safety"].includes(view) ? view : "war-room";
  document.querySelectorAll(".view").forEach(el => { el.hidden = el.id !== valid; });
  document.querySelectorAll("[data-view]").forEach(el => { if (el.dataset.view === valid) el.setAttribute("aria-current", "page"); else el.removeAttribute("aria-current"); });
  document.title = `${words(valid).replace("-", " ")} · Incident Zero`;
}

function renderMode() {
  $("#mode").textContent = words(state.mode).toUpperCase();
  const real = state.mode === "real";
  $("#mode-banner").textContent = real ? "CONNECTED TO ACTION API · Decisions use the real approval gate. Reports and verification remain the source of truth." : state.mode === "unknown" ? "CONTROL STATE UNAVAILABLE · Approval controls are disabled until the API reconnects." : `${state.mode === "mock_fallback" ? "ACTION BACKEND UNAVAILABLE · MOCK FALLBACK" : "MOCK MODE"} · Reports are recorded observations. Approvals and STOP are in memory; no stack changes or recovery are simulated.`;
  $("#stop-description").textContent = real ? "Latch the Action API kill switch to stop the response. The backend owns cancellation of in-flight work." : "Latch this mock session's approval gate. This does not stop the demo stack or another session.";
  $("#stop-scope").textContent = real ? "Action API controls are blocked." : "Mock session only; the live stack is unaffected.";
  $("#stop-banner").hidden = state.stopped !== true;
  $("#safety-state").textContent = state.stopped === null ? "STATE UNKNOWN" : state.stopped ? "STOP LATCHED" : "LATCH CLEAR";
  $("#safety-state").className = `chip ${state.stopped ? "aborted" : ""}`;
  $("#clear-stop-button").disabled = state.stopped !== true || state.busy;
  $("#stop-button").disabled = state.stopped === true || state.busy;
  $("#quick-stop").disabled = state.stopped === true || state.busy;
  document.querySelectorAll("[data-approve]").forEach(button => { button.disabled = state.stopped !== false || state.busy; });
}

function evidenceTable(evidence, reportId) {
  if (!evidence?.length) return '<p class="muted">No evidence entries have been recorded.</p>';
  return `<div class="table-wrap"><table class="evidence-table"><thead><tr><th>Evidence ID · click to resolve</th><th>Source</th><th>Observation</th></tr></thead><tbody>${evidence.map(item => `<tr><td><button class="evidence-id" data-evidence="${esc(item.id)}" data-report="${esc(reportId)}">${esc(item.id)}</button></td><td>${esc(item.source)}</td><td>${esc(item.summary)}</td></tr>`).join("")}</tbody></table></div>`;
}

function renderSteps(steps) {
  if (!steps?.length) return '<p class="muted">Waiting for investigation steps.</p>';
  return `<div class="steps">${steps.map((step, index) => `<div class="step"><span class="step-number">${esc(step.step ?? index + 1)}</span><div><h3>${esc(step.tool)}</h3><p>${esc(step.why)}</p><p class="query">${esc(pretty(step.query ?? step.arguments ?? ""))}</p><p class="finding">${esc(pretty(step.finding ?? "Observation recorded"))}</p></div></div>`).join("")}</div>`;
}

function approvalPanel(report, pending) {
  const level = Math.max(report.impact?.tier ?? 3, pending?.tier ?? 1);
  if (level === 3) return `<article class="panel approval-box escalated full"><p class="eyebrow">TIER 3 · HUMAN INVESTIGATION REQUIRED</p><h2>Escalated to a human</h2><p>${esc(report.escalation_note || report.impact?.rationale || "The findings do not support an approved automated action.")}</p><p class="muted">Review the evidence above and collect the missing observations. No approve action is available.</p></article>`;
  if (!pending) {
    const decision = report.ui_decision;
    return `<article class="panel approval-box full"><h2>${decision ? `Decision ${esc(decision.status)}` : "Approval gate"}</h2><p>${decision ? `${esc(decision.operator)} · ${esc(date(decision.decided_at))}. ${esc(decision.reason || decision.note || "")}` : report.approval?.approved === true ? "Approval recorded by the backend. Watch execution and verification below." : "There is no pending approval for this report."}</p><p class="muted">${state.mode === "real" ? "Execution and recovery are reported separately." : "Mock decisions do not execute a fix or change verification results."}</p></article>`;
  }
  return `<article class="panel approval-box full"><div class="panel-heading"><h2>${level === 1 ? "Quick approval" : "Review the evidence, then confirm"}</h2>${tier(level)}</div><p><strong>${esc(pending.action)} → ${esc(pending.target)}</strong> · ${esc(pending.predicted_effect)}</p><p class="muted">Expires ${esc(date(pending.expiry))}</p>${pending.preview ? `<p>${esc(pending.preview.impact?.rationale)}</p><p class="muted">Reason codes: ${esc((pending.preview.reason_codes || []).join(", "))}</p><p>Side effects: ${esc(pending.preview.side_effects)}</p><p>Rollback: ${esc(pending.preview.rollback_limits)}</p><details><summary>Exact dry-run plan</summary><pre>${esc(pretty(pending.preview.plan))}</pre></details>` : ""}${level === 2 ? evidenceTable(report.evidence, report.incident_id) : ""}<form id="decision-form" data-approval="${esc(pending.id)}" data-revision="${esc(pending.revision)}"><div class="form-row"><label>Operator<input name="operator" required maxlength="100" autocomplete="name" placeholder="Your name"></label>${level === 2 ? '<label>Type yes to approve<input name="confirmation" autocomplete="off" placeholder="yes"></label>' : ""}</div><label>Approval note / rejection reason<textarea name="note" maxlength="2000" placeholder="A reason is required when rejecting"></textarea></label><div class="button-row"><button type="submit" data-approve ${state.stopped !== false ? "disabled" : ""}>Approve plan</button><button type="button" class="reject" data-reject>Reject & escalate</button></div><p class="muted" style="margin:14px 0 0">${state.stopped ? "STOP is latched. Approval is blocked." : "Nothing changes without an explicit approval."}</p></form></article>`;
}

function renderWar() {
  const report = state.report;
  if (!report) { $("#war-content").innerHTML = '<div class="empty">No incident reports yet. Waiting for a report bundle.</div><article class="panel section-space"><h2>Investigation feed</h2><div id="live-activity"></div></article>'; renderActivity(); return; }
  const pending = state.approvals.pending.find(item => (item.report_id || item.id) === report.incident_id);
  const key = JSON.stringify([report, pending, state.stopped, state.mode]);
  if (key === state.warKey) { renderActivity(); return; }
  state.warKey = key;
  const root = report.root_cause || report.root_causes?.[0] || {};
  const impact = report.impact || {};
  const alert = report.alert || {};
  const actions = report.proposed_actions?.length ? report.proposed_actions : report.proposed_action ? [report.proposed_action] : [];
  const verification = report.verification || {};
  const reasons = impact.reason_codes || impact.reasons || [];
  $("#war-content").innerHTML = `<div class="alert-line"><div><p class="eyebrow">${esc(report.incident_id)} · ${esc(date(report.detected_at))}</p><h3>${esc(alert.service || root.component)} / ${esc(words(alert.signal))}</h3><p>Observed ${esc(alert.signal === "error_rate" ? percent(alert.observed) : number(alert.observed))} · threshold ${esc(alert.signal === "error_rate" ? percent(alert.threshold) : number(alert.threshold))} · ${esc(alert.window_s ?? "—")}s window</p></div>${chip(report.status)}</div>
    <div class="war-grid"><article class="panel"><div class="panel-heading"><h2>Investigation</h2><span class="eyebrow">${report.investigation?.length || 0} STEPS</span></div>${renderSteps(report.investigation)}</article>
    <article class="panel"><p class="eyebrow">PRIMARY DIAGNOSIS</p><h2 class="diagnosis-title">${esc(root.component || "Undetermined")}</h2><div class="diagnosis-meta">${chip(root.category || "unknown")}<span class="confidence">${percent(root.confidence)} confidence</span></div><p>${esc(root.cause || "Awaiting a diagnosis")}</p><div class="facts">${fact("Evidence confidence", percent(root.confidence_evidence))}${fact("Model confidence", percent(root.confidence_model))}</div>${(report.root_causes || []).slice(1).map(cause => `<h3 class="section-space">Additional cause · ${esc(cause.component)}</h3><p>${esc(cause.cause)} (${percent(cause.confidence)})</p>`).join("")}${root.alternatives_considered?.length ? `<details><summary>Alternatives considered</summary><ul>${root.alternatives_considered.map(item => `<li>${esc(item)}</li>`).join("")}</ul></details>` : ""}</article>
    <article class="panel full"><div class="panel-heading"><h2>Impact & risk</h2>${tier(impact.tier ?? 3)}</div><p>${esc(impact.rationale || "No impact rationale recorded.")}</p><div class="facts">${fact("Business impact", impact.business)}${fact("Journeys affected", impact.journeys_affected?.join(", "))}${fact("Blast radius", words(impact.blast_radius))}${fact("Reversibility / data risk", `${words(impact.reversibility)} / ${words(impact.data_risk)}`)}${fact("Users affected", impact.users_affected_estimate)}${fact("Reason codes", reasons.length ? pretty(reasons) : "Not provided by report")}</div></article>
    <article class="panel full"><div class="panel-heading"><h2>Evidence ledger</h2><span class="eyebrow">${report.evidence?.length || 0} REFERENCES</span></div>${evidenceTable(report.evidence, report.incident_id)}</article>
    <article class="panel full"><h2>Proposed action</h2>${actions.length ? actions.map(action => `<div class="action-plan"><h3>${esc(action.type)} → ${esc(action.target)}</h3><p>${esc(action.reason)}</p><p class="muted">Predicted effect: ${esc(action.dry_run?.predicted_effect || "Not supplied")}</p><p class="muted">Risk: ${esc(action.risk || "Not supplied")} · Dry run: ${action.dry_run?.performed ? "performed" : "not performed"}</p><details><summary>Plan parameters</summary><pre>${esc(pretty(action.parameters || {}))}</pre></details></div>`).join("") : '<p class="muted">No safe action proposed. Findings remain available for human investigation.</p>'}</article>
    ${approvalPanel(report, pending)}
    <article class="panel full"><div class="panel-heading"><h2>Execution & verification</h2>${chip(verification.recovered === true ? "fixed" : verification.rolled_back ? "rolled_back" : "awaiting_result")}</div><div class="facts">${fact("Action executed", report.action?.executed ? "Yes · " + date(report.action.finished_at) : "No recorded execution")}${fact("Signal", verification.signal)}${fact("Before", verification.before)}${fact("After", verification.after)}${fact("Recovery", verification.recovered === true ? "Confirmed by report" : verification.recovered === false ? "Not recovered" : "Not yet verified")}${fact("Checked", date(verification.checked_at))}</div>${report.prevention ? `<p class="section-space">Prevention: ${esc(report.prevention)}</p>` : ""}${report.limitations?.length ? `<details><summary>Limitations (${report.limitations.length})</summary><ul>${report.limitations.map(item => `<li>${esc(item)}</li>`).join("")}</ul></details>` : ""}<details><summary>Original report Markdown</summary><pre>${esc(report.markdown || "Markdown is not available for this report.")}</pre></details></article>
    <article class="panel full"><div class="panel-heading"><h2>Investigation feed</h2><span class="eyebrow">LATEST JOURNAL EVENTS</span></div><div id="live-activity"></div></article></div>`;
  renderActivity();
}

function renderActivity() {
  const completed = new Set(state.events.filter(event => event.type === "report_ready").map(event => event.run_id));
  if (state.report?.run_id) completed.add(state.report.run_id);
  const active = state.events.filter(event => !event.recorded && event.type === "investigation_step" && !completed.has(event.run_id) && Date.now() - new Date(event.observed_at || event.at).getTime() < 300000);
  const activeRun = active.at(-1)?.run_id;
  $("#active-investigation").hidden = !activeRun;
  if (activeRun) {
    $("#active-run").textContent = activeRun + " · Read from the agent's investigation journal; awaiting a report.";
    $("#active-steps").innerHTML = renderSteps(active.filter(event => event.run_id === activeRun).map(event => event.step));
  }
  const target = $("#live-activity");
  if (!target) return;
  const events = state.events.filter(event => ["alert_raised", "investigation_step", "report_ready", "action_executed", "verification_result", "stop"].includes(event.type)).slice(-8).reverse();
  target.innerHTML = events.length ? events.map(event => `<div class="step"><span class="step-number">•</span><div><h3>${esc(words(event.type))} ${event.recorded ? "· recorded" : ""}</h3><p class="muted">${esc(event.incident_id || event.run_id || "Safety control")}</p><p>${esc(event.step ? `${event.step.tool} — ${event.step.why}` : event.alert ? `${event.alert.service}: ${event.alert.signal}` : event.status || event.verification?.recovered?.toString() || (event.type === "stop" ? event.stopped ? "STOP latched" : "STOP cleared" : "Report observation"))}</p></div></div>`).join("") : '<p class="muted">Listening for alerts and investigation steps…</p>';
}

function renderIncidents() {
  $("#incident-count").textContent = state.incidents.length;
  $("#incident-list").innerHTML = state.incidents.length ? `<div class="table-wrap"><table><thead><tr><th>Incident</th><th>Status</th><th>Component</th><th>Confidence</th><th>Tier</th><th>Detected</th></tr></thead><tbody>${state.incidents.map(item => `<tr><td><button class="link-button" data-open="${esc(item.id)}">${esc(item.id)} ↗</button><div class="muted">${esc(words(item.category))}</div></td><td>${chip(item.status)}</td><td>${esc(item.component)}</td><td>${percent(item.confidence)}</td><td>${tier(item.tier)}</td><td>${esc(date(item.detected_at))}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">No report bundles found in the configured reports directory.</div>';
}

function renderApprovals() {
  $("#approval-count").textContent = state.approvals.pending.length;
  $("#approval-queue").innerHTML = state.approvals.pending.length ? state.approvals.pending.map(item => `<article class="panel approval-card"><div class="panel-heading"><h2>${esc(item.action)} → ${esc(item.target)}</h2>${tier(item.tier)}</div><p>${esc(item.predicted_effect)}</p><p class="muted">${esc(item.report_id || item.id)} · expires ${esc(date(item.expiry))}</p><button class="secondary" data-open="${esc(item.report_id || item.id)}">Review report & decide ↗</button></article>`).join("") : '<div class="empty">No approvals waiting. Tier 3 incidents are escalated directly to a human.</div>';
  $("#approval-history").innerHTML = state.approvals.history.length ? `<div class="table-wrap"><table><thead><tr><th>Incident</th><th>Decision</th><th>Operator</th><th>Note / reason</th><th>Time</th></tr></thead><tbody>${state.approvals.history.map(item => `<tr><td>${esc(item.report_id || item.id)}</td><td>${chip(item.status)}</td><td>${esc(item.operator || item.approved_by)}</td><td>${esc(item.reason || item.note || "—")}</td><td>${esc(date(item.decided_at || item.approved_at))}</td></tr>`).join("")}</tbody></table></div>` : '<p class="muted">No decisions recorded in this session.</p>';
}

function renderHealth(health) {
  $("#health-meta").textContent = `${health.source === "live" ? "Live telemetry" : "Recorded report observations"} · observed ${date(health.observed_at)}. ${(health.warnings || []).join(" ")}`;
  const cell = (text, bad) => `<td class="${bad ? "cell-danger" : ""}">${esc(text)}</td>`;
  $("#health-table").innerHTML = health.rows?.length ? `<div class="table-wrap"><table><thead><tr><th>Service</th><th>Error rate</th><th>p95 ms</th><th>RPS</th><th>Restarts</th><th>Status</th><th>CPU %</th><th>Memory MiB</th></tr></thead><tbody>${health.rows.map(row => `<tr><td><strong>${esc(row.service)}</strong></td>${cell(percent(row.error_rate), row.error_rate != null && row.error_rate >= .05)}${cell(number(row.p95_ms), row.p95_ms != null && row.p95_ms >= 1500)}${cell(number(row.rps), false)}${cell(number(row.restarts, 0), false)}${cell(row.status, !!row.status && !["running", "healthy", "unknown"].includes(row.status))}${cell(number(row.cpu), row.cpu != null && row.cpu >= 90)}${cell(number(row.mem), false)}</tr>`).join("")}</tbody></table></div>` : '<div class="empty">No service measurements available.</div>';
}

async function selectIncident(identity, followLatest = false) {
  state.followLatest = followLatest;
  state.selected = identity;
  const report = await api(`/api/incidents/${encodeURIComponent(identity)}`);
  if (state.selected !== identity) return;
  state.report = report;
  renderWar();
  location.hash = "war-room";
}

async function refresh() {
  if (state.refreshing || state.busy) return;
  state.refreshing = true;
  try {
    const results = await Promise.allSettled([api("/api/incidents"), api("/api/approvals"), api("/api/stop"), api("/api/health"), api("/api/log?tail=50")]);
    const [incidents, approvals, stop, health, log] = results;
    if (incidents.status === "fulfilled") state.incidents = incidents.value;
    if (approvals.status === "fulfilled") state.approvals = approvals.value;
    if (stop.status === "fulfilled") { state.stopped = stop.value.stopped; state.mode = stop.value.mode; } else { state.stopped = null; state.mode = "unknown"; }
    if (health.status === "fulfilled") renderHealth(health.value);
    if (log.status === "fulfilled") $("#action-log").textContent = log.value.lines.length ? log.value.lines.map(pretty).join("\n\n") : "No action log entries.";
    if ((!state.selected || state.followLatest) && state.incidents.length) state.selected = state.incidents[0].id;
    if (state.selected) state.report = await api(`/api/incidents/${encodeURIComponent(state.selected)}`);
    renderIncidents(); renderApprovals(); renderWar(); renderMode();
    const failed = results.filter(result => result.status === "rejected");
    $("#connection").textContent = failed.length ? "Partial connection · retrying" : "Connected · updates automatic";
    if (failed.length) notice("Some data is unavailable; displayed values may be stale. " + failed[0].reason.message);
  } catch (error) { state.stopped = null; renderMode(); $("#connection").textContent = "Connection interrupted · retrying"; notice(error.message); }
  finally { state.refreshing = false; }
}

async function mutate(path, body, method = "POST") {
  if (state.busy) return;
  state.busy = true; renderMode();
  try { await api(path, { method, body: body === undefined ? undefined : JSON.stringify(body) }); notice(""); }
  catch (error) { notice(error.message); }
  finally { state.busy = false; state.warKey = ""; await refresh(); renderMode(); }
}

async function decide(approved) {
  const form = $("#decision-form");
  if (!form || !form.reportValidity()) return;
  const data = Object.fromEntries(new FormData(form));
  if (!approved && !data.note?.trim()) { notice("Enter a reason before rejecting this plan."); return; }
  if (approved && form.elements.confirmation && data.confirmation !== "yes") { notice("Type exactly yes to approve a tier 2 plan."); return; }
  await mutate(`/api/approvals/${encodeURIComponent(form.dataset.approval)}/${approved ? "approve" : "reject"}`, { operator: data.operator, note: approved ? data.note : "", reason: approved ? "" : data.note, confirmation: data.confirmation || "", revision: form.dataset.revision });
}

let evidenceRequest = 0;
document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  try {
    if (button.hasAttribute("data-open")) await selectIncident(button.dataset.open);
    if (button.hasAttribute("data-reject")) await decide(false);
    if (button.hasAttribute("data-evidence")) {
      const request = ++evidenceRequest;
      $("#evidence-origin").textContent = "Resolving the cited payload…";
      $("#evidence-payload").textContent = button.dataset.evidence;
      $("#evidence-drawer").showModal();
      try {
        const payload = await api(`/api/incidents/${encodeURIComponent(button.dataset.report)}/evidence/${encodeURIComponent(button.dataset.evidence)}`);
        if (request !== evidenceRequest) return;
        $("#evidence-origin").textContent = `${words(payload.resolved_from)} · ${payload.source} · captured ${date(payload.captured_at)}${payload.resolved_from !== "live" ? " · A snapshot proves the recorded observation, not current recovery." : ""}`;
        $("#evidence-payload").textContent = pretty(payload);
      } catch (error) { if (request === evidenceRequest) $("#evidence-origin").textContent = error.message; }
    }
  } catch (error) { notice(error.message); }
});
document.addEventListener("submit", event => { if (event.target.id === "decision-form") { event.preventDefault(); decide(true); } });
$("#close-evidence").addEventListener("click", () => $("#evidence-drawer").close());
$("#latest-incident").addEventListener("click", () => { if (state.incidents.length) selectIncident(state.incidents[0].id, true).catch(error => notice(error.message)); });
$("#stop-button").addEventListener("click", () => mutate("/api/stop"));
$("#quick-stop").addEventListener("click", () => mutate("/api/stop"));
$("#clear-stop-form").addEventListener("submit", event => { event.preventDefault(); const phrase = $("#clear-phrase").value; if (phrase !== "I confirm the incident is over") { notice("The confirmation phrase must match exactly."); return; } mutate("/api/stop", { phrase }, "DELETE"); });
document.querySelectorAll(".refresh").forEach(button => button.addEventListener("click", refresh));
window.addEventListener("hashchange", navigate);

async function pollEvents() {
  for (;;) {
    try {
      const result = await api(`/api/events?after=${state.cursor}&wait=15&epoch=${encodeURIComponent(state.epoch)}`);
      if (result.reset) state.events = [];
      state.cursor = result.cursor; state.epoch = result.epoch;
      state.events = [...state.events, ...result.events].slice(-100);
      renderActivity();
      if (result.events.length || result.reset) await refresh();
    } catch (error) { $("#connection").textContent = "Event stream reconnecting · polling remains active"; await new Promise(resolve => setTimeout(resolve, 3000)); }
  }
}

navigate();
$("#clock").textContent = date(new Date());
setInterval(() => { $("#clock").textContent = date(new Date()); }, 1000);
refresh().then(pollEvents);
setInterval(refresh, 10000);
