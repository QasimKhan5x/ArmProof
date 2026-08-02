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
let inferenceMode = "recorded";

const VIEW_TO_HASH = {
  workspace: "triage",
  surge: "surge",
  proof: "proof",
};
const HASH_TO_VIEW = Object.fromEntries(
  Object.entries(VIEW_TO_HASH).map(([view, hash]) => [hash, view]),
);


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


function activateView(view, { focus = true, updateHash = true } = {}) {
  if (!(view in VIEW_TO_HASH)) return;
  document.querySelectorAll("[role=tab]").forEach((tab) => {
    const selected = tab.dataset.view === view;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll(".view").forEach((panel) => {
    panel.hidden = panel.id !== `view-${view}`;
  });
  if (updateHash) history.replaceState(null, "", `#${VIEW_TO_HASH[view]}`);
  if (focus) document.querySelector(`[data-view="${view}"]`)?.focus({ preventScroll: true });
}


function labelResponsiveTable(table) {
  const labels = [...table.querySelectorAll("thead th")].map((header) => header.textContent.trim());
  table.querySelectorAll("tbody tr").forEach((row) => {
    [...row.cells].forEach((cell, index) => {
      if (labels[index]) cell.dataset.label = labels[index];
    });
  });
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
  setText("llm-queue", active.llm_queue);
  setText("suggested-queue", active.queue);
  setText(
    "inference-source",
    active.mode === "live_model_output"
      ? `${active.backend} · ${formatMs(active.inference_ms)}`
      : "Recorded Phi-4 Mini INT4",
  );
  setText("review-priority", active.priority);
  elements["review-priority"].className = `priority-badge ${active.priority.toLowerCase()}`;
  if (active.mode === "live_model_output") {
    elements["review-warning"].textContent = active.guard_overrode
      ? `The queue guard changed the live LLM route from ${active.llm_queue} to ${active.guard_queue}. Human validation is required.`
      : "This is a live two-stage suggestion with no benchmark label. Human validation is required.";
    elements["correct-route"].hidden = true;
  } else if (!active.queue_correct) {
    elements["review-warning"].textContent = `The guarded queue differs from the benchmark queue (${active.expected_queue}). Correct it before routing.`;
    elements["correct-route"].hidden = false;
  } else if (active.guard_overrode) {
    elements["review-warning"].textContent = `The queue guard changed the LLM route from ${active.llm_queue} to ${active.guard_queue}, matching the held-out benchmark. Human approval is still required.`;
    elements["correct-route"].hidden = true;
  } else {
    elements["review-warning"].textContent = "The two-stage route matches the held-out benchmark. Human approval is still required.";
    elements["correct-route"].hidden = true;
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
    labelResponsiveTable(elements["reviewed-tickets"].closest("table"));
    elements["review-complete"].hidden = true;
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
  labelResponsiveTable(elements["reviewed-tickets"].closest("table"));
  elements["review-complete"].hidden = Boolean(workspace.active);
  const latest = workspace.resolved[0];
  setText(
    "review-complete-title",
    latest.review_status === "corrected"
      ? `Corrected to ${latest.final_queue}`
      : `Routed to ${latest.final_queue}`,
  );
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
  document.querySelectorAll("[data-case-id]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.caseId === selected?.request_id));
  });
  elements["intake-error"].hidden = true;
}


function selectScenario(requestId) {
  elements["sample-select"].value = requestId;
  loadSelectedSample();
}


async function routeSelectedMessage(event) {
  event.preventDefault();
  if (inferenceMode === "live") {
    elements["route-request"].disabled = true;
    elements["route-request"].textContent = "Routing on Graviton…";
    try {
      const response = await fetch("/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: elements["customer-message"].value }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      workspace = selectRecordedCase(workspace, payload);
      elements["intake-error"].hidden = true;
      renderWorkspace();
      elements["review-panel"].scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      elements["intake-error"].textContent = `Live route failed: ${error.message}`;
      elements["intake-error"].hidden = false;
    } finally {
      elements["route-request"].disabled = false;
      elements["route-request"].textContent = "Run live route";
    }
    return;
  }
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


function setInferenceMode(mode) {
  inferenceMode = mode;
  const live = mode === "live";
  elements["sample-select"].disabled = live;
  elements["scenario-picker"].hidden = live;
  setText("environment-label", live ? "Live Graviton endpoint" : "Recorded Graviton evidence");
  elements["workspace-mode"].textContent = live ? "Live Graviton inference" : "BANKING77 recorded output";
  elements["intake-note"].textContent = live
    ? "This message is sent through the configured Graviton inference endpoint and local queue guard."
    : "Select an evidence-backed request to replay its recorded model output.";
  elements["route-request"].textContent = live ? "Run live route" : "Load model suggestion";
  elements["customer-message"].readOnly = false;
  if (live) {
    elements["customer-message"].value = "";
    elements["customer-message"].placeholder = "Enter a support request for the live Graviton service";
    elements["customer-message"].focus();
  } else {
    elements["customer-message"].placeholder = "";
    loadSelectedSample();
  }
  elements["intake-error"].hidden = true;
  workspace = { ...workspace, active: null };
  renderWorkspace();
}


async function configureLiveMode() {
  try {
    const response = await fetch("./live-status.json", { cache: "no-store" });
    if (!response.ok) return;
    const status = await response.json();
    if (!status.live_available) return;
    elements["live-mode"].disabled = false;
    elements["live-mode-hint"].textContent = "Connected to the configured Arm inference endpoint.";
    elements["live-mode-label"].classList.add("available");
  } catch {
    // Static hosting intentionally remains in recorded-evidence mode.
  }
}


function review(decision) {
  workspace = resolveTicket(workspace, decision);
  renderWorkspace();
  elements["tab-workspace"].classList.add("completed");
  elements["review-complete"].querySelector("button").focus();
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
  labelResponsiveTable(elements["mix-table"].closest("table"));
}


function renderEvidenceSummary() {
  const mixes = Object.values(data.capacity.mixes);
  const mixed = data.capacity.mixes.mixed;
  const maxCapacity = Math.max(
    mixed.baseline_sustainable_rps,
    mixed.optimized_sustainable_rps,
  );
  const ratios = mixes.map((mix) => mix.ratio);
  setText("capacity-title", `Same instance. ${mixed.ratio.toFixed(0)}× higher confirmed tested traffic.`);
  setText("headline-ratio", `${mixed.ratio.toFixed(1)}×`);
  setText("guard-accuracy", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText("guard-gain", `+${data.quality.guard_queue_gain_pp.toFixed(2)} pp`);
  setText(
    "guard-split",
    `${data.quality.guard_training_cases} train / ${data.quality.guard_evaluation_cases} held out`,
  );
  setText("schema-valid", `${data.quality.schema_valid_percent.toFixed(0)}%`);
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
    "reveal-cycle-share",
    `${data.proof.kleidiai_cycle_callchain_share_percent.toFixed(2)}%`,
  );
  setText("reveal-baseline-p95", formatMs(data.replay.baseline.p95_ms));
  setText("reveal-optimized-p95", formatMs(data.replay.optimized.p95_ms));
  setText("reveal-baseline-rps", formatRps(mixed.baseline_sustainable_rps));
  setText("reveal-optimized-rps", formatRps(mixed.optimized_sustainable_rps));
  setText(
    "conclusion-copy",
    `KleidiAI sustained ${mixed.ratio.toFixed(0)}× higher confirmed tested mixed traffic under the same ${(data.capacity.slo_ms / 1000).toFixed(0)}-second p95 objective.`,
  );
  setText("proof-capacity", `Minimum ${Math.min(...ratios).toFixed(1)}×`);
  setText("proof-quality", `${data.quality.accuracy_delta_pp.toFixed(3)} pp`);
  setText("proof-macro-f1", `${data.quality.macro_f1_delta_pp.toFixed(3)} pp`);
  setText("proof-queue-quality", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText("proof-schema", `${data.quality.schema_valid_percent.toFixed(0)}%`);
  setText(
    "proof-arm",
    data.proof.kleidiai_enabled_callchains && !data.proof.kleidiai_disabled_callchains
      ? `${data.proof.kleidiai_cycle_callchain_share_percent.toFixed(2)}% of sampled cycles`
      : "Attribution unavailable",
  );
  setText(
    "proof-reproduction",
    `${data.proof.reproduction_max_relative_difference_percent.toFixed(0)}% ratio difference`,
  );
  setText(
    "proof-decision-detail",
    `${data.proof.verified_claims} required claims passed after raw evidence verification and derivation.`,
  );
  setText(
    "proof-evidence-count",
    `${data.provenance.evidence.total_checksummed_files} files verified`,
  );
  setText(
    "proof-derived-claims",
    `${data.proof.verified_claims} contract claims evaluated from derived evidence; missing or inconsistent inputs block release.`,
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
  setText("queue-accuracy", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText("queue-gain", `+${data.quality.guard_queue_gain_pp.toFixed(2)} percentage points`);
}


function renderRun(name, snapshot) {
  setText(`${name}-completed`, `${snapshot.completed} / ${snapshot.total}`);
  setText(`${name}-p95`, formatMs(snapshot.p95_ms));
  setText(`${name}-breaches`, snapshot.breaches);
  setText(`${name}-rps`, formatRps(snapshot.offered_rps));
  elements[`${name}-progress`].style.width = `${(snapshot.completed / snapshot.total) * 100}%`;
  elements[`${name}-status`].className = `run-status ${snapshot.slo_status}`;
  setText(`${name}-status`, snapshot.slo_status);
  const requestStrip = elements[`${name}-request-strip`];
  requestStrip.replaceChildren();
  snapshot.events.filter((event) => [4, 5, 7].includes(event.sequence)).forEach((event) => {
    const tile = document.createElement("span");
    tile.className = `request-tile ${event.within_slo ? "within-slo" : "late"}`;
    const request = document.createElement("span");
    request.className = "request-copy";
    request.textContent = event.source_text;
    const outcome = document.createElement("strong");
    outcome.className = "request-outcome";
    outcome.textContent = `${formatMs(event.latency_ms)} · ${event.within_slo ? "on time" : "missed SLO"}`;
    tile.append(request, outcome);
    tile.title = `Request ${event.sequence}: ${formatMs(event.latency_ms)}`;
    tile.setAttribute(
      "aria-label",
      `Request ${event.sequence}, ${formatMs(event.latency_ms)}, ${event.within_slo ? "within SLO" : "SLO breach"}`,
    );
    requestStrip.append(tile);
  });
  const latest = snapshot.events.at(-1);
  setText(
    `${name}-event`,
    latest
      ? `#${String(latest.sequence).padStart(2, "0")} ${formatMs(latest.latency_ms)} · ${latest.source_text}`
      : "Accepted run not loaded.",
  );
}


function renderReplay(progress) {
  const snapshot = buildReplaySnapshot(data.replay, progress);
  renderRun("baseline", snapshot.baseline);
  renderRun("optimized", snapshot.optimized);
  elements["replay-conclusion"].hidden = progress < 1;
}


function loadVerifiedExperiment() {
  renderReplay(1);
  elements["experiment-results"].hidden = false;
  elements["load-experiment"].disabled = true;
  elements["load-experiment"].textContent = "Verified experiment loaded";
  elements["evidence-load-note"].textContent =
    `Loaded ${data.provenance.evidence.total_checksummed_files} verified files across the primary and fresh-instance confirmation bundles; metrics recomputed from accepted evidence.`;
  elements["evidence-loader"].classList.add("loaded");
  elements["tab-surge"].classList.add("completed");
}


function bindInteractions() {
  document.querySelectorAll("[role=tab]").forEach((tab) => {
    tab.addEventListener("click", () => activateView(tab.dataset.view));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
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
  document.querySelectorAll("[data-go-surge]").forEach((button) => {
    button.addEventListener("click", () => activateView("surge"));
  });
  document.querySelectorAll("[data-case-id]").forEach((button) => {
    button.addEventListener("click", () => selectScenario(button.dataset.caseId));
  });
  elements["sample-select"].addEventListener("change", loadSelectedSample);
  elements["intake-form"].addEventListener("submit", routeSelectedMessage);
  elements["confirm-route"].addEventListener("click", () => review("confirm"));
  elements["correct-route"].addEventListener("click", () => review("correct"));
  elements["load-experiment"].addEventListener("click", loadVerifiedExperiment);
  document.querySelectorAll('input[name="inference-mode"]').forEach((radio) => {
    radio.addEventListener("change", () => setInferenceMode(radio.value));
  });
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        elements["copy-status"].textContent = "Command copied to clipboard.";
      } catch {
        elements["copy-status"].textContent = "Clipboard access is unavailable; select the command text above.";
      }
    });
  });
  window.addEventListener("hashchange", () => {
    const view = HASH_TO_VIEW[location.hash.slice(1)];
    if (view) activateView(view, { focus: false, updateHash: false });
  });
}


async function main() {
  try {
    const response = await fetch("./data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    workspace = createWorkspace(data);
    setText("demo-source", `${data.provenance.experiment_id} · ${data.provenance.machine} · accepted evidence`);
    setText("evidence-experiment-id", data.provenance.experiment_id);
    setText(
      "evidence-checksum-status",
      `${data.provenance.evidence.total_checksummed_files} files · ${data.provenance.evidence.checksum_verified && data.provenance.evidence.reproduction_checksum_verified ? "both SHA-256 ledgers verified" : "verification failed"}`,
    );
    setText(
      "evidence-comparison",
      data.provenance.evidence.comparison === "matched_control"
        ? "Matched INT4 control · only KleidiAI changes"
        : "Comparison unavailable",
    );
    setText("experiment-machine", data.proof.instance);
    setText("absolute-accuracy", `${data.quality.optimized_accuracy_percent.toFixed(2)}%`);
    populateCases();
    renderWorkspace();
    renderMixTable();
    renderEvidenceSummary();
    renderReplay(0);
    bindInteractions();
    document.querySelectorAll("table[data-mobile-cards]").forEach(labelResponsiveTable);
    const initialView = HASH_TO_VIEW[location.hash.slice(1)] ?? "workspace";
    activateView(initialView, { focus: false });
    await configureLiveMode();
  } catch (error) {
    console.error(error);
    document.querySelectorAll(".view").forEach((view) => { view.hidden = true; });
    elements["load-error"].hidden = false;
  }
}


main();
