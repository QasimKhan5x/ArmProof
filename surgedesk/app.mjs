import {
  buildReplaySnapshot,
  createWorkspace,
  findRecordedCase,
  resolveTicket,
  selectRecordedCase,
} from "./model.mjs";


const elements = Object.fromEntries(
  [...document.querySelectorAll("[id]")].map((element) => [element.id, element]),
);

let data;
let workspace;
let replayTimer = null;


function setText(id, value) {
  elements[id].textContent = String(value);
}


function formatRps(value) {
  return `${value.toFixed(3)} r/s`;
}


function formatMs(value) {
  if (!value) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round(value)} ms`;
}


function activateView(view) {
  document.querySelectorAll("[role=tab]").forEach((tab) => {
    const selected = tab.dataset.view === view;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll(".view").forEach((panel) => {
    panel.hidden = panel.id !== `view-${view}`;
  });
  document.querySelector(`[data-view="${view}"]`)?.focus({ preventScroll: true });
}


function renderQueues() {
  elements["queue-list"].replaceChildren();
  Object.entries(workspace.queue_counts).forEach(([queue, count]) => {
    const row = document.createElement("li");
    const label = document.createElement("span");
    const number = document.createElement("strong");
    label.textContent = queue;
    number.textContent = count;
    row.append(label, number);
    elements["queue-list"].append(row);
  });
}


function renderReview() {
  const active = workspace.active;
  elements["review-panel"].hidden = !active;
  if (!active) return;
  setText("review-title", active.source_text);
  setText("suggested-intent", active.suggested_label);
  setText("suggested-queue", active.queue);
  setText("review-priority", active.priority);
  elements["review-priority"].className = `priority-badge ${active.priority.toLowerCase()}`;
  if (active.correct) {
    elements["review-warning"].textContent = "This recorded suggestion matches the benchmark label. Human approval is still required.";
    elements["correct-route"].hidden = true;
  } else {
    elements["review-warning"].textContent = `This recorded suggestion differs from the benchmark label (${active.expected_label}). Correct it before routing.`;
    elements["correct-route"].hidden = false;
  }
}


function renderReviewedTickets() {
  setText("review-count", `${workspace.resolved.length} reviewed`);
  elements["reviewed-tickets"].replaceChildren();
  if (!workspace.resolved.length) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No tickets reviewed in this demo session.";
    row.append(cell);
    elements["reviewed-tickets"].append(row);
    return;
  }
  workspace.resolved.forEach((ticket) => {
    const row = document.createElement("tr");
    const request = document.createElement("td");
    const queue = document.createElement("td");
    const status = document.createElement("td");
    const runbook = document.createElement("td");
    request.textContent = ticket.source_text;
    queue.textContent = ticket.final_queue;
    status.textContent = ticket.review_status === "confirmed" ? "Confirmed" : "Corrected";
    status.className = `review-state ${ticket.review_status}`;
    runbook.textContent = ticket.procedure;
    runbook.className = "runbook-cell";
    row.append(request, queue, status, runbook);
    elements["reviewed-tickets"].append(row);
  });
}


function renderWorkspace() {
  renderQueues();
  renderReview();
  renderReviewedTickets();
}


function loadSelectedSample() {
  const selected = data.routing_cases.find(
    (item) => item.request_id === elements["sample-select"].value,
  );
  if (selected) elements["customer-message"].value = selected.source_text;
  elements["intake-error"].hidden = true;
}


function routeSelectedMessage(event) {
  event.preventDefault();
  const recordedCase = findRecordedCase(data.routing_cases, elements["customer-message"].value);
  if (!recordedCase) {
    elements["intake-error"].textContent = "No recorded Phi-4 result exists for edited text. Select an evidence-backed BANKING77 request for this offline demo.";
    elements["intake-error"].hidden = false;
    return;
  }
  elements["intake-error"].hidden = true;
  workspace = selectRecordedCase(workspace, recordedCase);
  renderWorkspace();
  elements["review-panel"].scrollIntoView({ behavior: "smooth", block: "nearest" });
}


function review(decision) {
  workspace = resolveTicket(workspace, decision);
  renderWorkspace();
}


function populateCases() {
  data.routing_cases.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.request_id;
    option.textContent = `${item.priority} · ${item.expected_label}`;
    elements["sample-select"].append(option);
  });
  loadSelectedSample();
}


function renderMixTable() {
  elements["mix-table"].replaceChildren();
  Object.entries(data.capacity.mixes).forEach(([name, mix]) => {
    const row = document.createElement("tr");
    [
      name[0].toUpperCase() + name.slice(1),
      formatRps(mix.baseline_sustainable_rps),
      formatRps(mix.optimized_sustainable_rps),
      `${mix.ratio.toFixed(1)}×`,
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    elements["mix-table"].append(row);
  });
}


function renderEvidenceSummary() {
  const mixes = Object.values(data.capacity.mixes);
  const mixed = data.capacity.mixes.mixed;
  const maxCapacity = Math.max(
    mixed.baseline_sustainable_rps,
    mixed.optimized_sustainable_rps,
  );
  const ratios = mixes.map((mix) => mix.ratio);
  setText("capacity-title", `Same instance. ${mixed.ratio.toFixed(0)}× the capacity.`);
  setText("headline-ratio", `${mixed.ratio.toFixed(1)}×`);
  setText(
    "confirmation-count",
    `${mixed.confirmations_per_treatment} confirmations per treatment`,
  );
  setText("experiment-slo", `p95 ≤ ${(data.capacity.slo_ms / 1000).toFixed(0)} seconds`);
  setText("baseline-capacity-rps", `${mixed.baseline_sustainable_rps.toFixed(2)} requests/s`);
  setText("optimized-capacity-rps", `${mixed.optimized_sustainable_rps.toFixed(2)} requests/s`);
  elements["baseline-capacity-bar"].style.width = `${(mixed.baseline_sustainable_rps / maxCapacity) * 100}%`;
  elements["optimized-capacity-bar"].style.width = `${(mixed.optimized_sustainable_rps / maxCapacity) * 100}%`;
  setText("baseline-boundary", formatRps(mixed.baseline_sustainable_rps));
  setText("optimized-boundary", formatRps(mixed.optimized_sustainable_rps));
  setText(
    "conclusion-copy",
    `The optimized service sustained ${mixed.ratio.toFixed(0)}× mixed traffic under the same ${(data.capacity.slo_ms / 1000).toFixed(0)}-second p95 objective.`,
  );
  setText("proof-capacity", `Minimum ${Math.min(...ratios).toFixed(1)}×`);
  setText("proof-quality", `${data.quality.accuracy_delta_pp.toFixed(3)} pp`);
  setText("proof-schema", `${data.quality.schema_valid_percent.toFixed(0)}%`);
  setText(
    "proof-arm",
    data.proof.kleidiai_enabled_callchains && !data.proof.kleidiai_disabled_callchains
      ? "kai_* enabled only"
      : "Attribution unavailable",
  );
  setText(
    "proof-reproduction",
    `${data.proof.reproduction_max_relative_difference_percent.toFixed(0)}% ratio difference`,
  );
  setText("artifact-reduction", `${data.proof.artifact_reduction_percent.toFixed(2)}% smaller deployment artifact`);
  setText(
    "direct-speedup",
    `${data.proof.direct_speedup_min.toFixed(2)}–${data.proof.direct_speedup_max.toFixed(2)}× direct execution speedup`,
  );
  setText(
    "capacity-range",
    `${Math.min(...ratios).toFixed(1)}–${Math.max(...ratios).toFixed(1)}× fixed-SLO service capacity`,
  );
  setText("deployment-instance", data.proof.instance);
  setText("deployment-threads", data.proof.threads);
}


function renderRun(name, snapshot) {
  setText(`${name}-completed`, `${snapshot.completed} / ${snapshot.total}`);
  setText(`${name}-p95`, formatMs(snapshot.p95_ms));
  setText(`${name}-breaches`, snapshot.breaches);
  setText(`${name}-rps`, formatRps(snapshot.offered_rps));
  elements[`${name}-progress`].style.width = `${(snapshot.completed / snapshot.total) * 100}%`;
  elements[`${name}-status`].className = `run-status ${snapshot.slo_status}`;
  setText(`${name}-status`, snapshot.slo_status);
  const latest = snapshot.events.at(-1);
  setText(
    `${name}-event`,
    latest
      ? `#${String(latest.sequence).padStart(2, "0")} ${formatMs(latest.latency_ms)} · ${latest.source_text}`
      : "Run not started.",
  );
}


function renderReplay(progress) {
  const snapshot = buildReplaySnapshot(data.replay, progress);
  renderRun("baseline", snapshot.baseline);
  renderRun("optimized", snapshot.optimized);
  elements["replay-conclusion"].hidden = progress < 1;
}


function startReplay() {
  if (replayTimer) window.clearInterval(replayTimer);
  elements["replay-conclusion"].hidden = true;
  elements["run-replay"].disabled = true;
  elements["run-replay"].textContent = "Replaying evidence…";
  const started = performance.now();
  const duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 200 : 6000;
  renderReplay(0);
  replayTimer = window.setInterval(() => {
    const progress = Math.min(1, (performance.now() - started) / duration);
    renderReplay(progress);
    if (progress >= 1) {
      window.clearInterval(replayTimer);
      replayTimer = null;
      elements["run-replay"].disabled = false;
      elements["run-replay"].textContent = "Replay again";
    }
  }, 120);
}


function bindInteractions() {
  document.querySelectorAll("[role=tab]").forEach((tab) => {
    tab.addEventListener("click", () => activateView(tab.dataset.view));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const tabs = [...document.querySelectorAll("[role=tab]")];
      const current = tabs.indexOf(tab);
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(current + offset + tabs.length) % tabs.length];
      activateView(next.dataset.view);
    });
  });
  document.querySelectorAll("[data-go-proof]").forEach((button) => {
    button.addEventListener("click", () => activateView("proof"));
  });
  elements["sample-select"].addEventListener("change", loadSelectedSample);
  elements["intake-form"].addEventListener("submit", routeSelectedMessage);
  elements["confirm-route"].addEventListener("click", () => review("confirm"));
  elements["correct-route"].addEventListener("click", () => review("correct"));
  elements["run-replay"].addEventListener("click", startReplay);
}


async function main() {
  try {
    const response = await fetch("./data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    workspace = createWorkspace(data);
    setText("demo-source", `${data.provenance.experiment_id} · ${data.provenance.machine} · recorded replay`);
    setText("experiment-machine", data.proof.instance);
    setText("absolute-accuracy", `${data.quality.optimized_accuracy_percent.toFixed(2)}%`);
    populateCases();
    renderWorkspace();
    renderMixTable();
    renderEvidenceSummary();
    renderReplay(0);
    bindInteractions();
  } catch (error) {
    console.error(error);
    document.querySelectorAll(".view").forEach((view) => { view.hidden = true; });
    elements["load-error"].hidden = false;
  }
}


main();
