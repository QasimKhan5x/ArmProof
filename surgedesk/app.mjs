import {
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
let matchedSurgeAvailable = false;
let auditAvailable = false;
let proofState = "recorded";

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


function formatMs(value) {
  if (!value) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round(value)} ms`;
}


function formatClaimValue(metric, value) {
  if (["accuracy_delta_pp", "macro_f1_delta_pp"].includes(metric)) return `${value.toFixed(3)} pp`;
  if (["schema_valid_rate", "enabled_kai_cycle_callchain_share"].includes(metric)) return `${(value * 100).toFixed(2)}%`;
  if (metric === "minimum_capacity_ratio") return `${value.toFixed(1)}×`;
  if (metric === "enabled_kai_callchains_observed") return value === 1 ? "Observed" : "Absent";
  return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
}


function renderProofClaims() {
  const tbody = elements["proof-claims"];
  tbody.replaceChildren();
  const operators = { gte: "≥", lte: "≤", gt: ">", lt: "<", eq: "=" };
  data.proof.claims.forEach((claim) => {
    const row = document.createElement("tr");
    const values = [
      claim.label,
      formatClaimValue(claim.metric, claim.observed),
      `${operators[claim.operator]} ${formatClaimValue(claim.metric, claim.threshold)}`,
    ];
    values.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    const status = document.createElement("td");
    const mark = document.createElement("span");
    if (proofState === "recorded" && claim.status === "pass") {
      mark.className = "recorded-label";
      mark.textContent = "Recorded pass";
    } else if (proofState === "failed") {
      mark.className = "unknown-label";
      mark.textContent = "Not reverified";
    } else {
      mark.className = claim.status === "pass" ? "pass-label" : "fail-label";
      mark.textContent = claim.status[0].toUpperCase() + claim.status.slice(1);
    }
    status.append(mark);
    row.append(status);
    tbody.append(row);
  });
  labelResponsiveTable(tbody.closest("table"));
}


function renderProofDecision(state, detail = "") {
  proofState = state;
  const header = elements["proof-decision-title"].closest(".proof-decision");
  const mark = header.querySelector(".decision-mark");
  header.classList.toggle("failed", state === "failed");
  if (state === "fresh") {
    setText("proof-decision-source", "Verified during this session");
    setText("proof-decision-title", "Fresh audit approved the conservative Graviton boundary");
    setText("proof-decision-detail", detail);
    setText("proof-decision-status", "VERIFIED NOW");
    setText(
      "environment-label",
      `${inferenceMode === "live" ? "Live matched Arm64 endpoint" : "Recorded inference"} · fresh audit`,
    );
    mark.textContent = "✓";
  } else if (state === "failed") {
    setText("proof-decision-source", "Current ArmProof audit");
    setText("proof-decision-title", "Fresh audit blocked the release");
    setText("proof-decision-detail", detail);
    setText("proof-decision-status", "BLOCKED");
    setText("environment-label", "Current evidence audit blocked");
    mark.textContent = "×";
  } else {
    setText("proof-decision-source", "Checked-in ArmProof receipt");
    setText("proof-decision-title", "Checked-in conservative release receipt");
    setText(
      "proof-decision-detail",
      `${data.proof.verified_claims} required claims passed when this recorded receipt was generated. `
      + "Run the measured experiment audit to recompute the decision in this session.",
    );
    setText("proof-decision-status", "RECORDED PASS");
    mark.textContent = "✓";
  }
  renderProofClaims();
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
      : `Recorded ${data.provenance.model} INT4`,
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
    elements["route-request"].textContent = "Routing on Arm64…";
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
    elements["intake-error"].textContent = `No recorded ${data.provenance.model} result exists for edited text. Select an evidence-backed ${data.provenance.dataset} request for this offline demo.`;
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
  setText("environment-label", live ? "Live matched Arm64 endpoint" : "Recorded Graviton evidence");
  elements["workspace-mode"].textContent = live
    ? "Live matched Arm64 inference"
    : `${data.provenance.dataset} recorded output`;
  elements["intake-note"].textContent = live
    ? "This message is sent through the identity-checked Arm64 inference endpoint and local queue guard."
    : "Select an evidence-backed request to load its recorded model output.";
  elements["route-request"].textContent = live ? "Run live route" : "Load model suggestion";
  elements["customer-message"].readOnly = false;
  if (live) {
    elements["customer-message"].value = "";
    elements["customer-message"].placeholder = "Enter a support request for the live Arm64 service";
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
    if (status.live_available) {
      elements["live-mode"].disabled = false;
      elements["live-mode-hint"].textContent = "Connected to the configured Arm inference endpoint.";
      elements["live-mode-label"].classList.add("available");
    }
    matchedSurgeAvailable = Boolean(status.matched_surge_available);
    auditAvailable = Boolean(status.audit_available);
    elements["tamper-check"].disabled = !auditAvailable;
    if (status.lanes) {
      setText("baseline-live-cores", `Cores ${status.lanes.baseline.core_group}`);
      setText("optimized-live-cores", `Cores ${status.lanes.optimized.core_group}`);
    }
    if (matchedSurgeAvailable && status.matched_identity) {
      const identity = status.matched_identity;
      setText(
        "live-match-proof",
        `Runtime-verified match: model ${identity.model_identity.slice(0, 12)}… · `
        + `${identity.runtime} ${identity.runtime_version} · ${identity.threads_per_lane} threads per lane · `
        + `${identity.architecture} · compared runtime control ${identity.changed_control}: `
        + `${identity.baseline_control} → ${identity.optimized_control}.`,
      );
    } else {
      setText(
        "live-match-proof",
        `Matched run unavailable: ${status.matched_status || "endpoint identity was not verified"}.`,
      );
    }
    setText(
      "surge-live-status",
      matchedSurgeAvailable ? "Matched Arm endpoints connected" : "Matched endpoints not connected",
    );
    elements["run-live-surge"].disabled = !matchedSurgeAvailable;
    if (!auditAvailable) {
      elements["load-experiment"].textContent = "Open checked-in evidence";
      elements["evidence-load-note"].textContent =
        "This public page can inspect the repository receipt. Run the local demo to hash and re-derive the archive.";
    }
  } catch {
    // Static hosting intentionally remains in recorded-evidence mode.
    setText("surge-live-status", "Matched endpoints unavailable");
    setText("live-match-proof", "Runtime identity probes are unavailable on this static page.");
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


function populateScenarios() {
  const labels = {
    "straight-through": ["Straight-through", "Model and guard agree"],
    "guard-intervention": ["Guard intervention", "Guard rescues the LLM route"],
    "human-correction": ["Human correction", "Operator catches a guard error"],
  };
  elements["scenario-options"].replaceChildren();
  Object.entries(labels).forEach(([role, [title, description]], index) => {
    const scenario = data.routing_cases.find((item) => item.scenario_role === role);
    if (!scenario) return;
    const button = document.createElement("button");
    const strong = document.createElement("strong");
    const small = document.createElement("small");
    button.type = "button";
    button.dataset.caseId = scenario.request_id;
    button.setAttribute("aria-pressed", String(index === 0));
    strong.textContent = title;
    small.textContent = description;
    button.append(strong, small);
    elements["scenario-options"].append(button);
  });
}


async function loadVerifiedExperiment() {
  if (!auditAvailable) {
    elements["load-experiment"].disabled = true;
    showRepositoryEvidence();
    return;
  }
  const expected = data.provenance.evidence;
  elements["load-experiment"].disabled = true;
  elements["load-experiment"].textContent =
    `Verifying ${expected.sustained_raw_confirmation_samples.toLocaleString()} outcomes…`;
  elements["evidence-load-note"].textContent =
    "Reading the archive, recomputing all long windows, and evaluating the contract.";
  resetAuditProgress();
  try {
    const response = await fetch("/api/audit-stream", { method: "POST" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const receipt = await readAuditStream(response);
    const valid =
      receipt.passed
      && receipt.experiment_id === data.provenance.experiment_id
      && receipt.claims_verified === data.proof.verified_claims
      && receipt.raw_request_outcomes === expected.sustained_raw_confirmation_samples
      && receipt.confirmation_files === expected.sustained_raw_confirmation_files
      && receipt.archive_sha256 === expected.sustained_archive_sha256
      && receipt.matched_control;
    if (!valid) throw new Error("audit receipt does not match the loaded release data");
    renderAuditResult(receipt);
    renderProofDecision(
      "fresh",
      `${receipt.claims_verified} required claims passed after ${receipt.raw_request_outcomes.toLocaleString()} outcomes were re-derived in ${receipt.elapsed_ms.toFixed(0)} ms.`,
    );
    setText(
      "audit-archive-result",
      `${receipt.archive_sha256.slice(0, 12)}… · ${receipt.elapsed_ms.toFixed(0)} ms total`,
    );
    setText(
      "audit-request-result",
      `${receipt.raw_request_outcomes.toLocaleString()} outcomes across ${receipt.confirmation_files} files`,
    );
    setText("audit-control-result", "Matched identities; declared treatment control verified");
    setText("audit-claim-result", `${receipt.claims_verified}/${receipt.claims_verified} required claims passed`);
    elements["experiment-results"].hidden = false;
    elements["load-experiment"].textContent = "Measured experiment verified";
    elements["evidence-load-note"].textContent =
      `${receipt.adapter} recomputed the release decision from the immutable archive in ${receipt.elapsed_ms.toFixed(0)} ms.`;
    elements["evidence-loader"].classList.add("loaded");
    elements["tab-surge"].classList.add("completed");
    elements["experiment-results"].scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    elements["load-experiment"].disabled = false;
    elements["load-experiment"].textContent = "Retry measured experiment";
    elements["evidence-load-note"].textContent = `Verification blocked: ${error.message}`;
    elements["evidence-loader"].classList.add("failed");
    renderProofDecision("failed", `The current audit did not approve: ${error.message}`);
  }
}


function resetAuditProgress() {
  elements["audit-progress"].hidden = false;
  const rows = [...elements["audit-progress"].querySelectorAll("li")];
  rows.forEach((row, index) => {
    row.className = index === 0 ? "active" : "";
    row.querySelector("small").textContent = "Waiting…";
  });
  elements["audit-archive-result"].textContent = "Hashing the archive…";
}


function updateAuditStage(stage, detail) {
  const order = ["archive", "requests", "controls", "contract"];
  const index = order.indexOf(stage);
  if (index < 0) throw new Error(`unknown audit stage: ${stage}`);
  const row = elements["audit-progress"].querySelector(`[data-audit-stage="${stage}"]`);
  row.className = "complete";
  if (stage === "archive") {
    setText("audit-archive-result", `${detail.archive_sha256.slice(0, 12)}… · ${detail.checksummed_files} files`);
  } else if (stage === "requests") {
    setText("audit-request-result", `${detail.raw_request_outcomes.toLocaleString()} outcomes across ${detail.confirmation_files} files`);
  } else if (stage === "controls") {
    setText("audit-control-result", detail.matched_control ? `Matched; treatment control ${detail.only_changed_control} verified` : "Control mismatch");
  } else {
    setText("audit-claim-result", `${detail.claims_verified}/${detail.claims_verified} required claims passed`);
  }
  const next = elements["audit-progress"].querySelector(`[data-audit-stage="${order[index + 1]}"]`);
  if (next) next.className = "active";
}


async function readAuditStream(response) {
  if (!response.body) throw new Error("audit stream is unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receipt = null;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "stage") updateAuditStage(event.stage, event.detail);
      if (event.type === "result") receipt = event.receipt;
      if (event.type === "error") throw new Error(event.error);
    }
    if (done) break;
  }
  if (!receipt) throw new Error("audit finished without a result receipt");
  return receipt;
}


function showRepositoryEvidence() {
  const mixed = data.capacity.mixes.mixed;
  const evidence = data.provenance.evidence;
  elements["audit-progress"].hidden = false;
  elements["audit-progress"].querySelectorAll("li").forEach((row) => {
    row.className = "complete";
  });
  renderAuditResult({
    passed: data.proof.decision === "PASS",
    claims_verified: data.proof.verified_claims,
    capacity: {
      trial_matrix: mixed.trial_matrix,
      optimized_pass_rps: mixed.optimized_sustainable_rps,
      baseline_fail_rps: mixed.baseline_fail_rps,
      minimum_ratio: mixed.minimum_capacity_ratio,
      confirmations: mixed.confirmations_per_treatment,
      confirmation_seconds: mixed.confirmation_seconds,
    },
    original_gate: {
      passed: data.provenance.original_gate_passed,
      required_probe_failures: mixed.confirmations_per_treatment,
      observed_probe_failures: mixed.optimized_probe_failures,
      observed_probe_passes: mixed.optimized_probe_passes,
      probe_rps: mixed.optimized_probe_rps,
      exact_lower_ratio: mixed.minimum_capacity_ratio,
      exact_upper_ratio: mixed.optimized_probe_rps / mixed.baseline_sustainable_rps,
    },
    arm: {
      performix_disabled_sample_share_percent: data.proof.performix.disabled_kai_sample_share_percent,
      performix_enabled_sample_share_percent: data.proof.performix.enabled_kai_sample_share_percent,
      linux_perf_cycle_share_percent: data.proof.kleidiai_cycle_callchain_share_percent,
      kernel: data.proof.performix.kernel_family,
    },
  });
  setText("audit-archive-result", `${evidence.sustained_archive_sha256.slice(0, 12)}… · repository receipt`);
  setText("audit-request-result", `${evidence.sustained_raw_confirmation_samples.toLocaleString()} recorded outcomes across ${evidence.sustained_raw_confirmation_files} files`);
  setText("audit-control-result", "Matched identities; declared treatment control verified");
  setText("audit-claim-result", `${data.proof.verified_claims}/${data.proof.verified_claims} claims in the checked-in decision`);
  elements["experiment-results"].hidden = false;
  elements["load-experiment"].textContent = "Repository evidence opened";
  elements["evidence-load-note"].textContent =
    "GitHub Pages loaded the checked-in audit receipt. The local runbook recomputes the archive during the demo.";
  elements["evidence-loader"].classList.add("loaded");
  renderProofDecision("recorded");
}


function renderTrialMatrix(trials) {
  const body = elements["trial-matrix-body"];
  body.replaceChildren();
  trials.forEach((trial) => {
    const row = document.createElement("tr");
    const treatment = document.createElement("td");
    treatment.textContent = trial.treatment;
    const rate = document.createElement("td");
    rate.textContent = `${trial.rate_rps.toFixed(2)} r/s`;
    row.append(treatment, rate);
    trial.outcomes.forEach((outcome, index) => {
      const cell = document.createElement("td");
      const mark = document.createElement("span");
      mark.className = `trial-outcome ${outcome}`;
      mark.textContent = outcome === "pass" ? "Pass" : "Fail";
      mark.title = `${formatMs(trial.p95_ms[index])} p95`;
      cell.append(mark);
      row.append(cell);
    });
    const interpretation = document.createElement("td");
    const passCount = trial.outcomes.filter((outcome) => outcome === "pass").length;
    interpretation.textContent = `${passCount}/5 passed · ${trial.boundary}`;
    row.append(interpretation);
    body.append(row);
  });
  labelResponsiveTable(body.closest("table"));
}


function renderAuditResult(receipt) {
  const capacity = receipt.capacity;
  const arm = receipt.arm;
  const originalGate = receipt.original_gate;
  setText(
    "confirmation-count",
    `${capacity.confirmations} trials × 4 boundaries × ${capacity.confirmation_seconds}s`,
  );
  setText("equation-treatment", `${capacity.optimized_pass_rps.toFixed(2)} r/s optimized pass`);
  setText("equation-baseline", `${capacity.baseline_fail_rps.toFixed(2)} r/s baseline fail`);
  setText("headline-ratio", `≥${capacity.minimum_ratio.toFixed(2)}×`);
  setText("original-gate-status", originalGate.passed ? "PASSED" : "REJECTED");
  setText(
    "original-gate-explanation",
    `The exact ${originalGate.exact_lower_ratio.toFixed(1)}×–${originalGate.exact_upper_ratio.toFixed(1)}× bracket required all `
    + `${originalGate.required_probe_failures} optimized windows at ${originalGate.probe_rps.toFixed(2)} r/s to fail. `
    + `${originalGate.observed_probe_passes} passed, so that preregistered claim was rejected. `
    + "The release below evaluates a separate, narrower lower-bound claim supported by every confirmation window.",
  );
  setText(
    "capacity-explanation",
    `KleidiAI enabled passed all five windows at ${capacity.optimized_pass_rps.toFixed(2)} r/s. `
    + `KleidiAI disabled failed all five at ${capacity.baseline_fail_rps.toFixed(2)} r/s. `
    + "Using the failing baseline probe makes the published ratio a lower bound.",
  );
  setText("reveal-disabled-sample-share", `${arm.performix_disabled_sample_share_percent.toFixed(0)}%`);
  setText("reveal-enabled-sample-share", `${arm.performix_enabled_sample_share_percent.toFixed(2)}%`);
  setText("reveal-cycle-share", `${arm.linux_perf_cycle_share_percent.toFixed(2)}%`);
  setText("reveal-kernel", arm.kernel);
  setText("surge-release-decision", receipt.passed ? "PASS" : "BLOCK");
  setText(
    "conclusion-copy",
    `${receipt.claims_verified} required claims passed: capacity, quality, evidence volume, matched Arm execution, and profiler integrity.`,
  );
  renderTrialMatrix(capacity.trial_matrix);
}


function initializeLiveSlots() {
  ["baseline", "optimized"].forEach((lane) => {
    const container = elements[`${lane}-live-slots`];
    container.replaceChildren();
    for (let sequence = 1; sequence <= 3; sequence += 1) {
      const tile = document.createElement("div");
      tile.className = "live-request waiting";
      tile.dataset.sequence = String(sequence);
      const number = document.createElement("span");
      number.textContent = `Request ${sequence}`;
      const result = document.createElement("strong");
      result.textContent = "Waiting";
      const detail = document.createElement("small");
      detail.textContent = "—";
      tile.append(number, result, detail);
      container.append(tile);
    }
  });
}


function updateLiveTile(lane, result) {
  const tile = elements[`${lane}-live-slots`].querySelector(
    `[data-sequence="${result.sequence}"]`,
  );
  tile.className = "live-request complete";
  tile.querySelector("strong").textContent = formatMs(result.gateway_latency_ms);
  tile.querySelector("small").textContent =
    `${result.backend} · ${result.core_group} · ${result.suggested_label}`;
  tile.title = `${result.request_id} started ${result.gateway_started_at}`;
}


function updateLiveFailure(lane, sequence, message) {
  const tile = elements[`${lane}-live-slots`].querySelector(
    `[data-sequence="${sequence}"]`,
  );
  tile.className = "live-request failed";
  tile.querySelector("strong").textContent = "Failed";
  tile.querySelector("small").textContent = message;
}


async function runLiveMiniSurge(event) {
  event.preventDefault();
  if (!matchedSurgeAvailable) return;
  const text = elements["surge-message"].value.trim();
  if (!text) return;
  initializeLiveSlots();
  elements["live-surge-result"].hidden = true;
  elements["run-live-surge"].disabled = true;
  elements["run-live-surge"].textContent = "Sending six live requests…";
  setText("baseline-live-summary", "Three requests in flight");
  setText("optimized-live-summary", "Three requests in flight");
  const runId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const started = performance.now();
  const outcomes = { baseline: [], optimized: [] };
  const tasks = ["baseline", "optimized"].flatMap((lane) =>
    [1, 2, 3].map(async (sequence) => {
      const response = await fetch(`/api/surge/${lane}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, run_id: runId, sequence }),
      });
      const result = await response.json();
      if (!response.ok) throw Object.assign(new Error(result.error || `HTTP ${response.status}`), { lane, sequence });
      outcomes[lane].push(result);
      updateLiveTile(lane, result);
    }),
  );
  const settled = await Promise.allSettled(tasks);
  settled.filter((result) => result.status === "rejected").forEach((result) => {
    updateLiveFailure(result.reason.lane, result.reason.sequence, result.reason.message);
  });
  const elapsed = performance.now() - started;
  ["baseline", "optimized"].forEach((lane) => {
    const rows = outcomes[lane];
    setText(
      `${lane}-live-summary`,
      `${rows.length}/3 completed${rows.length === 3 ? " · runtime identity verified" : ""}`,
    );
  });
  const complete = outcomes.baseline.length === 3 && outcomes.optimized.length === 3;
  if (complete) {
    elements["live-surge-result"].textContent =
      `Live run ${runId}: all six matched requests completed in ${formatMs(elapsed)}. `
      + "Per-request latency is shown above; capacity is evaluated by the long-window audit below.";
  } else {
    elements["live-surge-result"].textContent =
      `Live run ${runId} finished with ${settled.filter((result) => result.status === "rejected").length} failed gateway calls.`;
  }
  elements["live-surge-result"].hidden = false;
  elements["run-live-surge"].disabled = false;
  elements["run-live-surge"].textContent = "Run matched request check again";
}


async function previewScaffold() {
  elements["preview-scaffold"].disabled = true;
  elements["preview-scaffold"].textContent = "Generating…";
  try {
    const response = await fetch("/api/scaffold-preview", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    elements["scaffold-preview"].textContent =
      `$ ${payload.command}\n\n${payload.files.map((file) => `created  ${file}`).join("\n")}\n\nBLOCK until evidence exists\nNext: ${payload.next}`;
    elements["scaffold-preview"].hidden = false;
    elements["preview-scaffold"].textContent = "Preview ready";
  } catch (error) {
    elements["scaffold-preview"].textContent = `Generation failed: ${error.message}`;
    elements["scaffold-preview"].hidden = false;
    elements["preview-scaffold"].disabled = false;
    elements["preview-scaffold"].textContent = "Retry starter kit preview";
  }
}


async function runTamperCheck() {
  elements["tamper-check"].disabled = true;
  elements["tamper-check"].textContent = "Changing a temporary copy…";
  elements["tamper-result"].hidden = true;
  try {
    const response = await fetch("/api/tamper-check", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    elements["tamper-result"].textContent =
      `${payload.decision}  ${payload.reason}\n`
      + `expected  ${payload.expected_sha256.slice(0, 16)}…\n`
      + `observed  ${payload.observed_sha256.slice(0, 16)}…\n`
      + `${payload.mutation} · ${payload.elapsed_ms.toFixed(0)} ms`;
    elements["tamper-result"].hidden = false;
    elements["tamper-check"].textContent = "Altered evidence blocked";
  } catch (error) {
    elements["tamper-result"].textContent = `Tamper test failed: ${error.message}`;
    elements["tamper-result"].hidden = false;
    elements["tamper-check"].disabled = false;
    elements["tamper-check"].textContent = "Retry one-byte evidence test";
  }
}


function renderRedesignEvidence() {
  const mixed = data.capacity.mixes.mixed;
  const proof = data.proof;
  const evidence = data.provenance.evidence;
  setText("guard-accuracy", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText("guard-evaluation-size", `Held out, ${data.quality.guard_evaluation_cases.toLocaleString()} requests`);
  setText("guard-gain", `+${data.quality.guard_queue_gain_pp.toFixed(2)} pp`);
  setText("guard-split", `${data.quality.guard_training_cases} train / ${data.quality.guard_evaluation_cases} held out`);
  setText("schema-valid", `${data.quality.schema_valid_percent.toFixed(0)}%`);
  setText("evidence-experiment-id", data.provenance.experiment_id);
  setText("evidence-checksum-status", `${evidence.sustained_checksummed_files} checksummed files · ${evidence.sustained_raw_confirmation_samples.toLocaleString()} outcomes`);
  setText("evidence-comparison", "Matched INT4 treatments; one runtime flag differs");
  setText("experiment-machine", proof.instance);
  setText("experiment-model", `${data.provenance.model} INT4`);
  setText("experiment-slo", `p95 ≤ ${(data.capacity.slo_ms / 1000).toFixed(0)} seconds`);
  setText("experiment-control", evidence.only_changed_control);
  setText("arm-reveal-threads", proof.threads);
  setText("arm-reveal-control", evidence.only_changed_control);
  setText("proof-evidence-count", `${evidence.sustained_checksummed_files} sustained + ${evidence.performix_checksummed_files} Performix checksums`);
  setText("proof-derived-claims", `${proof.verified_claims} contract claims evaluated from ${evidence.sustained_raw_confirmation_samples.toLocaleString()} request outcomes; missing inputs block release.`);
  setText("artifact-reduction", `${proof.artifact_reduction_percent.toFixed(2)}% smaller`);
  setText("memory-reduction", `${proof.peak_pss_reduction_percent.toFixed(2)}% lower peak PSS`);
  setText(
    "migration-quality",
    `${proof.migration_quality_delta_pp >= 0 ? "+" : ""}${proof.migration_quality_delta_pp.toFixed(2)} pp (${proof.migration_int4_quality_correct}/${proof.migration_quality_total} vs ${proof.migration_bf16_quality_correct}/${proof.migration_quality_total})`,
  );
  setText("capacity-range", `≥${mixed.minimum_capacity_ratio.toFixed(2)}× sustainable capacity under the fixed SLO`);
  setText("deployment-instance", proof.instance);
  setText("deployment-threads", proof.threads);
  setText("deployment-runtime", data.provenance.runtime);
  setText("deployment-optimization", data.provenance.optimization);
  setText("stack-model", data.provenance.model);
  setText("stack-runtime", data.provenance.runtime);
  setText("stack-machine", data.provenance.machine.split(" / ")[0].replace("AWS ", ""));
  setText("intent-count", data.quality.intent_count);
  setText("release-adapter-id", proof.adapter_id);
  setText("release-action", data.provenance.release_action);
  setText("release-contract-sha", data.provenance.contract_sha256);
  elements["release-link"].href = data.provenance.release_url;
  const performix = proof.performix;
  setText("performix-version", `Arm Performix ${performix.engine_version} · ${performix.cpu}`);
  setText("performix-disabled-share", `${performix.disabled_kai_sample_share_percent.toFixed(0)}%`);
  setText("performix-enabled-share", `${performix.enabled_kai_sample_share_percent.toFixed(2)}%`);
  setText("performix-sample-count", `${performix.enabled_function_samples.toLocaleString()} measured function samples`);
  setText("performix-linux-share", `${performix.linux_perf_cycle_share_percent.toFixed(2)}%`);
  setText("performix-kernel", performix.kernel_family);
  setText("performix-scope-note", performix.scope_note);
  setText("performix-capability-note", performix.pmu_capability_note);
  setText("queue-accuracy", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText("queue-gain", `+${data.quality.guard_queue_gain_pp.toFixed(2)} percentage points`);
  setText("absolute-accuracy", `${data.quality.optimized_accuracy_percent.toFixed(2)}%`);
  setText("reuse-action", `uses: ${data.provenance.release_action}`);
  elements["reuse-action-copy"].dataset.copy = `uses: ${data.provenance.release_action}`;
  setText(
    "evidence-chain-counts",
    `Verify ${evidence.sustained_checksummed_files} sustained and ${evidence.performix_checksummed_files} Performix checksummed evidence files.`,
  );
  initializeLiveSlots();
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
  elements["surge-form"].addEventListener("submit", runLiveMiniSurge);
  elements["preview-scaffold"].addEventListener("click", previewScaffold);
  elements["tamper-check"].addEventListener("click", runTamperCheck);
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
    setText("demo-source", `${data.provenance.experiment_id} · ${data.provenance.machine} · sustained audit`);
    setText("workspace-mode", `${data.provenance.dataset} recorded output`);
    setText("rail-model", data.provenance.model);
    setText("intent-model-label", `${data.provenance.model} intent`);
    populateCases();
    populateScenarios();
    renderWorkspace();
    renderRedesignEvidence();
    renderProofDecision("recorded");
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
