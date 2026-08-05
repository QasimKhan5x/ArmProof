import {
  createWorkspace,
  findRecordedCase,
  resolveTicketToQueue,
  selectRecordedCase,
} from "./model.mjs";


const elements = Object.fromEntries(
  [...document.querySelectorAll("[id]")].map((element) => [element.id, element]),
);

let data;
let workspace;
let inferenceMode = "recorded";
let matchedLanesAvailable = false;
let auditAvailable = false;
let proofState = "recorded";
let proofClaims = [];
let deploymentStatus = {
  active_lane: null,
  release_ready: false,
  audit_experiment_id: null,
  promoted_at: null,
};

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


function liveServiceLabel(lane) {
  return lane === "optimized"
    ? "Optimized service · KleidiAI on"
    : "Standard service · KleidiAI off";
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
  proofClaims.forEach((claim) => {
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
  if (state === "recorded") proofClaims = data.proof.claims;
  const header = elements["proof-decision-title"].closest(".proof-decision");
  const mark = header.querySelector(".decision-mark");
  header.classList.toggle("failed", state === "failed");
  elements["environment-status"].classList.toggle("failed", state === "failed");
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


function activateView(view, { focus = true, updateHash = true, focusHeading = false, scroll = true } = {}) {
  if (!(view in VIEW_TO_HASH)) return;
  document.querySelectorAll("[role=tab]").forEach((tab) => {
    const selected = tab.dataset.view === view;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll(".view").forEach((panel) => {
    panel.hidden = panel.id !== `view-${view}`;
  });
  const nextHash = `#${VIEW_TO_HASH[view]}`;
  if (updateHash && location.hash !== nextHash) history.pushState(null, "", nextHash);
  const panel = elements[`view-${view}`];
  if (scroll) panel.scrollIntoView({ block: "start" });
  if (focusHeading) {
    const heading = panel.querySelector("h1, h2");
    heading?.setAttribute("tabindex", "-1");
    heading?.focus({ preventScroll: true });
  } else if (focus) {
    document.querySelector(`[data-view="${view}"]`)?.focus({ preventScroll: true });
  }
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
      ? `${liveServiceLabel(active.deployment_lane)} · `
        + `${formatMs(active.inference_ms)} inference · ${formatMs(active.gateway_latency_ms)} end to end`
        + (active.release_audit_id ? ` · activated by ${active.release_audit_id}` : "")
      : `Recorded ${data.provenance.model} INT4`,
  );
  setText("review-priority", active.priority);
  elements["review-priority"].className = `priority-badge ${active.priority.toLowerCase()}`;
  const runtime = active.runtime_identity;
  const liveReceipt = active.mode === "live_model_output" && runtime;
  elements["live-request-receipt"].hidden = !liveReceipt;
  if (liveReceipt) {
    const observed = new Date(active.observed_at);
    setText("live-request-id", active.request_id);
    setText(
      "live-observed-at",
      Number.isNaN(observed.getTime()) ? active.observed_at : observed.toLocaleTimeString([], { hour12: false }),
    );
    setText("live-arm-runtime", `${runtime.architecture} · ${runtime.threads} threads · ${runtime.runtime_version}`);
    setText("live-control", `mlas.disable_kleidiai=${runtime.optimization_control["mlas.disable_kleidiai"]}`);
  }
  if (active.mode === "live_model_output") {
    elements["review-warning"].textContent = active.guard_overrode
      ? `The routing guard changed the live model route from ${active.llm_queue} to ${active.guard_queue}. Human validation is required.`
      : "This is a live two-stage suggestion with no benchmark label. Human validation is required.";
  } else if (!active.queue_correct) {
    elements["review-warning"].textContent = `The guarded queue differs from the benchmark queue (${active.expected_queue}). Correct it before routing.`;
  } else if (active.guard_overrode) {
    elements["review-warning"].textContent = `The routing guard changed the model route from ${active.llm_queue} to ${active.guard_queue}, matching the held-out benchmark. Human approval is still required.`;
  } else {
    elements["review-warning"].textContent = "The two-stage route matches the held-out benchmark. Human approval is still required.";
  }
  elements["final-queue"].value = active.queue;
}


function renderReviewedTickets() {
  setText("review-count", `${workspace.resolved.length} reviewed`);
  elements["reviewed-tickets"].replaceChildren();
  if (!workspace.resolved.length) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 5;
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
    const served = document.createElement("td");
    const queue = document.createElement("td");
    const status = document.createElement("td");
    const runbook = document.createElement("td");
    request.textContent = ticket.source_text;
    if (ticket.mode === "live_model_output" && ticket.runtime_identity) {
      const label = document.createElement("strong");
      label.textContent = `${liveServiceLabel(ticket.deployment_lane)} · ${formatMs(ticket.gateway_latency_ms)} observed`;
      const receipt = document.createElement("small");
      const observed = new Date(ticket.observed_at);
      const observedAt = Number.isNaN(observed.getTime())
        ? ticket.observed_at
        : observed.toLocaleTimeString([], { hour12: false });
      receipt.className = "ticket-receipt";
      receipt.textContent = `${ticket.request_id} · ${observedAt} · `
        + `${ticket.runtime_identity.architecture}/${ticket.runtime_identity.threads} threads · `
        + `mlas.disable_kleidiai=${ticket.runtime_identity.optimization_control["mlas.disable_kleidiai"]}`
        + (ticket.release_audit_id ? ` · ${ticket.release_audit_id}` : "");
      served.append(label, receipt);
    } else {
      served.textContent = "Recorded evidence";
    }
    queue.textContent = ticket.final_queue;
    status.textContent = ticket.review_status === "confirmed" ? "Confirmed" : "Corrected";
    status.className = `review-state ${ticket.review_status}`;
    runbook.textContent = ticket.procedure;
    runbook.className = "runbook-cell";
    row.append(request, served, queue, status, runbook);
    elements["reviewed-tickets"].append(row);
  });
  labelResponsiveTable(elements["reviewed-tickets"].closest("table"));
  elements["review-complete"].hidden = Boolean(workspace.active);
  const latest = workspace.resolved[0];
  const optimizedTicket = workspace.resolved.some(
    (ticket) => ticket.deployment_lane === "optimized" && ticket.release_audit_id,
  );
  elements["adoption-handoff"].hidden = !optimizedTicket;
  setText(
    "review-complete-title",
    latest.review_status === "corrected"
      ? `Corrected to ${latest.final_queue}`
      : `Routed to ${latest.final_queue}`,
  );
}


function revealVerifiedProof() {
  for (const id of ["optimization-summary", "performix-proof", "proof-details", "release-gate"]) {
    elements[id].hidden = false;
  }
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
      elements["review-title"].setAttribute("tabindex", "-1");
      elements["review-title"].focus({ preventScroll: true });
    } catch (error) {
      elements["intake-error"].textContent = `Live route failed: ${error.message}`;
      elements["intake-error"].hidden = false;
      elements["intake-error"].setAttribute("tabindex", "-1");
      elements["intake-error"].focus();
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
  elements["review-title"].setAttribute("tabindex", "-1");
  elements["review-title"].focus({ preventScroll: true });
}


function setInferenceMode(mode) {
  inferenceMode = mode;
  const live = mode === "live";
  elements["sample-select"].disabled = live;
  elements["scenario-picker"].hidden = live;
  setText(
    "environment-label",
    live
      ? `${deploymentStatus.active_lane === "optimized" ? "Optimized service · KleidiAI on" : "Standard service · KleidiAI off"}`
      : "Recorded Graviton evidence",
  );
  elements["workspace-mode"].textContent = live
    ? "Live matched Arm64 inference"
    : `${data.provenance.dataset} recorded output`;
  elements["intake-note"].textContent = live
    ? "This message is sent through the identity-checked Arm64 inference endpoint and local queue guard."
    : "Select an evidence-backed request to load its recorded model output.";
  elements["route-request"].textContent = live ? "Run live route" : "Inspect stored output";
  elements["customer-message"].readOnly = !live;
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
    if (status.live_available && status.matched_lanes_available) {
      elements["live-mode"].disabled = false;
      elements["live-mode-hint"].textContent = "Connected to the configured Arm inference endpoint.";
      elements["live-mode-label"].classList.add("available");
    }
    matchedLanesAvailable = Boolean(status.matched_lanes_available);
    auditAvailable = Boolean(status.audit_available);
    deploymentStatus = { ...deploymentStatus, ...(status.deployment || {}) };
    if (status.lanes?.baseline && status.lanes?.optimized) {
      setText(
        "promotion-candidate-lane",
        `${status.lanes.optimized.backend} · cores ${status.lanes.optimized.core_group}`,
      );
      const activeConfig = status.lanes[deploymentStatus.active_lane];
      if (activeConfig) {
        deploymentStatus.backend = activeConfig.backend;
        deploymentStatus.core_group = activeConfig.core_group;
      }
    }
    renderDeploymentStatus();
    if (!auditAvailable) {
      elements["load-experiment"].textContent = "Open checked-in evidence";
      elements["evidence-load-note"].textContent =
        "This public page can inspect the repository receipt. Run the local demo to hash and re-derive the archive.";
    }
  } catch {
    // Static hosting intentionally remains in recorded-evidence mode.
  }
}


function renderDeploymentStatus() {
  const active = deploymentStatus.active_lane;
  const connected = matchedLanesAvailable && Boolean(active);
  const optimized = active === "optimized";
  const freshAudit = proofState === "fresh" && deploymentStatus.release_ready;
  const publicEvidence = !matchedLanesAvailable && !auditAvailable;
  setText("promotion-eyebrow", "Live release action");
  setText("promotion-current-label", "Serving now");
  setText("promotion-candidate-label", "Candidate");
  setText("promotion-audit-label", "Required evidence");
  elements["promote-route"].hidden = false;
  elements["open-required-audit"].textContent = "Open required capacity audit";
  setText(
    "workspace-serving",
    !connected
      ? "Recorded model result"
      : optimized
        ? "Optimized service · KleidiAI on"
        : "Standard service · KleidiAI off",
  );
  setText(
    "workspace-candidate",
    connected
      ? "Optimized service · KleidiAI on"
      : publicEvidence
        ? "Optimized treatment · measured"
        : "Connect both matched Arm64 services",
  );
  setText(
    "workspace-release-status",
    optimized
      ? `${deploymentStatus.audit_experiment_id} approved and active`
      : freshAudit
        ? `${deploymentStatus.audit_experiment_id} approved; ready to activate`
      : publicEvidence
        ? `${data.provenance.experiment_id} passed the checked-in release policy`
        : "Waiting for the measured release check",
  );
  setText(
    "promotion-current-lane",
    !connected
      ? "No matched live route connected"
      : `${deploymentStatus.backend} · cores ${deploymentStatus.core_group}`,
  );
  setText(
    "promotion-audit-status",
    freshAudit
      ? `${deploymentStatus.audit_experiment_id} verified now`
      : "Fresh audit required",
  );
  if (publicEvidence) {
    setText("promotion-eyebrow", "Recorded release decision");
    setText("promotion-current-label", "Baseline");
    setText("promotion-current-lane", "KleidiAI disabled · measured");
    setText("promotion-candidate-label", "Released candidate");
    setText("promotion-candidate-lane", "KleidiAI enabled · measured");
    setText("promotion-audit-label", "Release evidence");
    setText("promotion-audit-status", `${data.provenance.experiment_id} · 10/10 claims passed`);
    setText("promotion-title", "The optimized candidate cleared the checked-in release policy");
    setText(
      "promotion-detail",
      "The repository receipt binds the matched Graviton treatments, sustained traffic outcomes, quality rows and Arm profiles. Live routing remains unavailable on this public page.",
    );
    elements["promote-route"].hidden = true;
    elements["open-required-audit"].hidden = false;
    elements["open-required-audit"].textContent = "Inspect capacity evidence";
    elements["route-next-request"].hidden = true;
  } else if (optimized) {
    setText("promotion-title", "The verified optimized service is handling live requests");
    setText(
      "promotion-detail",
      "The gateway changed its active route only after the measured release check passed and both service identities were checked again.",
    );
    elements["promote-route"].disabled = true;
    elements["promote-route"].textContent = "Optimized service active";
    elements["route-next-request"].hidden = false;
    elements["open-required-audit"].hidden = true;
  } else if (freshAudit && matchedLanesAvailable) {
    setText("promotion-title", "The measured optimized service is ready for live traffic");
    setText(
      "promotion-detail",
      "The release check passed. Activation will recheck both Arm service identities, then switch traffic from the standard service to the optimized service.",
    );
    elements["promote-route"].disabled = false;
    elements["promote-route"].textContent = "Activate verified optimized service";
    elements["route-next-request"].hidden = true;
    elements["open-required-audit"].hidden = true;
  } else {
    setText("promotion-title", connected
      ? "The standard service is handling support requests"
      : "Connect both matched Arm64 lanes to activate a release");
    setText(
      "promotion-detail",
      connected
        ? "Run the measured release check before routing live requests to the optimized service."
        : "The public evidence remains inspectable, but changing the live route requires both identity-checked endpoints and a fresh local audit.",
    );
    elements["promote-route"].disabled = true;
    elements["promote-route"].textContent = connected
      ? "Verify the measured experiment first"
      : "Matched live lanes required";
    elements["route-next-request"].hidden = true;
    elements["open-required-audit"].hidden = false;
  }
}


function review() {
  workspace = resolveTicketToQueue(workspace, elements["final-queue"].value);
  renderWorkspace();
  setText(
    "review-complete-detail",
    inferenceMode === "live" && deploymentStatus.active_lane !== "optimized"
      ? "This ticket used the standard service. Review the measured optimized release before switching traffic."
      : "Decision recorded in the audit trail.",
  );
  elements["tab-workspace"].classList.add("completed");
  if (workspace.resolved.length > 1) {
    elements["recent-title"].setAttribute("tabindex", "-1");
    elements["recent-title"].scrollIntoView({ block: "start" });
    elements["recent-title"].focus({ preventScroll: true });
  } else {
    elements["review-complete"].querySelector("button").focus();
  }
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


function populateFinalQueues() {
  Object.keys(workspace.queue_counts).forEach((queue) => {
    const option = document.createElement("option");
    option.value = queue;
    option.textContent = queue;
    elements["final-queue"].append(option);
  });
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


function renderAuditStage(stage, detail, elapsedMs) {
  const labels = {
    quality: () => `${detail.raw_model_outputs.toLocaleString()} raw model outputs checked for quality`,
    performix: () => `${(detail.disabled_function_samples + detail.enabled_function_samples).toLocaleString()} Performix function samples parsed`,
    archive: () => `${detail.checksummed_files} capacity files matched the frozen plan`,
    requests: () => `${detail.raw_request_outcomes.toLocaleString()} traffic outcomes reconstructed from ${detail.confirmation_files} windows`,
    policy: () => `${detail.claims_evaluated} release rules evaluated · ${detail.passed ? "passed" : "blocked"}`,
  };
  const item = document.createElement("li");
  const text = document.createElement("strong");
  const timing = document.createElement("time");
  text.textContent = labels[stage] ? labels[stage]() : stage;
  timing.textContent = `${elapsedMs.toFixed(0)} ms`;
  timing.dateTime = `PT${(elapsedMs / 1000).toFixed(3)}S`;
  item.dataset.stage = stage;
  item.append(text, timing);
  elements["audit-progress"].append(item);
  setText("evidence-load-note", text.textContent);
}


async function streamVerifiedAudit() {
  const response = await fetch("/api/audit-stream", { method: "POST" });
  if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receipt = null;

  async function consume(line) {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "stage") {
      renderAuditStage(event.stage, event.detail, Number(event.elapsed_ms));
    }
    if (event.type === "result") receipt = event.receipt;
    if (event.type === "error") throw new Error(event.error);
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) await consume(line);
    if (done) break;
  }
  await consume(buffer);
  if (!receipt) throw new Error("audit stream ended without a release decision");
  return receipt;
}


async function loadVerifiedExperiment() {
  if (!auditAvailable) {
    elements["load-experiment"].disabled = true;
    try {
      showRepositoryEvidence();
    } catch (error) {
      elements["audit-receipt"].hidden = true;
      elements["experiment-results"].hidden = true;
      elements["load-experiment"].disabled = false;
      elements["load-experiment"].textContent = "Retry checked-in evidence";
      setText("evidence-load-note", `Checked-in evidence is incomplete: ${error.message}`);
      elements["evidence-loader"].classList.add("failed");
      setText("evidence-seal", "×");
      renderProofDecision("failed", `The checked-in evidence could not be rendered: ${error.message}`);
    }
    return;
  }
  const expected = data.provenance.evidence;
  elements["load-experiment"].disabled = true;
  elements["load-experiment"].textContent =
    `Verifying ${expected.sustained_raw_confirmation_samples.toLocaleString()} outcomes…`;
  elements["evidence-load-note"].textContent =
    "Reading the archive, recomputing all long windows, and evaluating the contract.";
  setText("evidence-seal", "…");
  elements["audit-receipt"].hidden = true;
  elements["reveal-experiment-results"].hidden = true;
  elements["audit-progress"].replaceChildren();
  elements["audit-progress"].hidden = false;
  try {
    const receipt = await streamVerifiedAudit();
    const valid =
      receipt.passed
      && receipt.experiment_id === data.provenance.experiment_id
      && receipt.claims_verified === data.proof.verified_claims
      && Array.isArray(receipt.claims)
      && receipt.claims.length === receipt.claims_verified
      && receipt.claims.every((claim) => claim.status === "pass")
      && receipt.raw_request_outcomes === expected.sustained_raw_confirmation_samples
      && receipt.raw_quality_outputs === expected.raw_quality_outputs
      && receipt.confirmation_files === expected.sustained_raw_confirmation_files
      && receipt.archive_sha256 === expected.sustained_archive_sha256
      && receipt.matched_control;
    if (!valid) throw new Error("audit receipt does not match the loaded release data");
    proofClaims = receipt.claims;
    renderAuditResult(receipt);
    revealVerifiedProof();
    renderProofDecision(
      "fresh",
      `${receipt.claims_verified} required claims passed after ${receipt.raw_request_outcomes.toLocaleString()} outcomes were re-derived in ${receipt.elapsed_ms.toFixed(0)} ms.`,
    );
    deploymentStatus = {
      ...deploymentStatus,
      release_ready: true,
      audit_experiment_id: receipt.experiment_id,
    };
    renderDeploymentStatus();
    setText(
      "audit-archive-result",
      `${receipt.archive_sha256.slice(0, 12)}… · ${receipt.elapsed_ms.toFixed(0)} ms total`,
    );
    setText(
      "audit-request-result",
      `${receipt.raw_request_outcomes.toLocaleString()} capacity requests · ${receipt.raw_quality_outputs.toLocaleString()} model outputs`,
    );
    setText("audit-control-result", "Same model and runtime; only the KleidiAI setting changed");
    setText("audit-claim-result", `${receipt.claims_verified}/${receipt.claims_verified} required claims passed`);
    elements["audit-receipt"].hidden = false;
    setText("audit-receipt-time", `Completed from local evidence in ${receipt.elapsed_ms.toFixed(0)} ms`);
    elements["load-experiment"].textContent = "Measured experiment verified";
    elements["evidence-load-note"].textContent =
      `${receipt.adapter} recomputed the release decision from the immutable archive in ${receipt.elapsed_ms.toFixed(0)} ms.`;
    elements["evidence-loader"].classList.add("loaded");
    setText("evidence-seal", "✓");
    elements["tab-surge"].classList.add("completed");
    elements["reveal-experiment-results"].hidden = false;
    elements["reveal-experiment-results"].focus({ preventScroll: true });
  } catch (error) {
    console.error(error);
    elements["load-experiment"].disabled = false;
    elements["load-experiment"].textContent = "Retry measured experiment";
    elements["evidence-load-note"].textContent = `Verification blocked: ${error.message}`;
    elements["evidence-load-note"].setAttribute("tabindex", "-1");
    elements["evidence-load-note"].focus();
    elements["evidence-loader"].classList.add("failed");
    setText("evidence-seal", "×");
    renderProofDecision("failed", `The current audit did not approve: ${error.message}`);
  }
}


function revealConfirmedResult() {
  elements["experiment-results"].hidden = false;
  elements["reveal-experiment-results"].hidden = true;
  elements["rate-selection-title"].scrollIntoView({ behavior: "smooth", block: "start" });
  elements["rate-selection-title"].setAttribute("tabindex", "-1");
  elements["rate-selection-title"].focus({ preventScroll: true });
}


function showRepositoryEvidence() {
  const mixed = data.capacity.mixes.mixed;
  const evidence = data.provenance.evidence;
  elements["audit-receipt"].hidden = false;
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
      rate_selection: data.capacity.rate_selection,
    },
    arm: {
      performix_disabled_sample_share_percent: data.proof.performix.disabled_kai_sample_share_percent,
      performix_enabled_sample_share_percent: data.proof.performix.enabled_kai_sample_share_percent,
      linux_perf_cycle_share_percent: data.proof.kleidiai_cycle_callchain_share_percent,
      kernel: data.proof.performix.kernel_family,
      engine_version: data.proof.performix.engine_version,
      cpu: data.proof.performix.cpu,
      enabled_function_samples: data.proof.performix.enabled_function_samples,
      scope_note: data.proof.performix.scope_note,
      pmu_capability_note: data.proof.performix.pmu_capability_note,
    },
    supporting: {
      direct_speedup_min: data.proof.direct_speedup_min,
      direct_speedup_max: data.proof.direct_speedup_max,
      direct_shape_gains: data.proof.direct_shape_gains,
      artifact_reduction_percent: data.proof.artifact_reduction_percent,
      peak_pss_reduction_percent: data.proof.peak_pss_reduction_percent,
      migration_quality_delta_pp: data.proof.migration_quality_delta_pp,
      migration_int4_quality_correct: data.proof.migration_int4_quality_correct,
      migration_bf16_quality_correct: data.proof.migration_bf16_quality_correct,
      migration_quality_total: data.proof.migration_quality_total,
    },
  });
  revealVerifiedProof();
  setText("audit-archive-result", `${evidence.sustained_archive_sha256.slice(0, 12)}… · repository receipt`);
  setText("audit-request-result", `${evidence.sustained_raw_confirmation_samples.toLocaleString()} capacity requests · ${evidence.raw_quality_outputs.toLocaleString()} model outputs`);
  setText("audit-control-result", "Same model and runtime; only the KleidiAI setting changed");
  setText("audit-claim-result", `${data.proof.verified_claims}/${data.proof.verified_claims} claims in the checked-in decision`);
  setText("audit-receipt-time", "Loaded from the published repository receipt");
  elements["experiment-results"].hidden = false;
  elements["load-experiment"].textContent = "Repository evidence opened";
  elements["evidence-load-note"].textContent =
    "GitHub Pages loaded the checked-in audit receipt. The local runbook recomputes the archive during the demo.";
  elements["evidence-loader"].classList.add("loaded");
  setText("evidence-seal", "✓");
  renderProofDecision("recorded");
  elements["capacity-title"].setAttribute("tabindex", "-1");
  elements["capacity-title"].scrollIntoView({ block: "start" });
  elements["capacity-title"].focus({ preventScroll: true });
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
      const p95 = document.createElement("small");
      p95.className = "trial-p95";
      p95.textContent = `p95 ${formatMs(trial.p95_ms[index])}`;
      const dispatch = trial.max_dispatch_ms?.[index];
      if (dispatch !== undefined) {
        p95.title = `Maximum client dispatch delay ${formatMs(dispatch)}`;
      }
      cell.append(mark, p95);
      row.append(cell);
    });
    const interpretation = document.createElement("td");
    const passCount = trial.outcomes.filter((outcome) => outcome === "pass").length;
    interpretation.textContent = `${passCount}/${trial.outcomes.length} passed · ${trial.boundary}`;
    row.append(interpretation);
    body.append(row);
  });
  labelResponsiveTable(body.closest("table"));
}


function renderRateSelection(selection) {
  setText("rate-selection-copy", selection.interpretation);
  setText("rate-discovery-id", `Discovery: ${selection.experiment_id}`);
  setText(
    "rate-confirmation-id",
    `Frozen confirmation: ${selection.confirmation_experiment_id} · commit ${selection.publication.git_commit.slice(0, 7)}`,
  );
  elements["rate-confirmation-id"].href = selection.publication.public_commit_url;
  elements["rate-selection-grid"].replaceChildren();
  selection.trial_matrix.forEach((trial) => {
    const item = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("strong");
    const passCount = trial.outcomes.filter((outcome) => outcome === "pass").length;
    label.textContent = trial.treatment.replace("KleidiAI disabled", "Standard service").replace("KleidiAI enabled", "Optimized service");
    value.textContent = `${trial.rate_rps.toFixed(2)} r/s · ${passCount}/${trial.outcomes.length} passed`;
    item.append(label, value);
    elements["rate-selection-grid"].append(item);
  });
}


function renderLatencyConsequence(trials) {
  const container = elements["latency-consequence-groups"];
  container.replaceChildren();
  const maximumSeconds = Math.max(
    10,
    ...trials.flatMap((trial) => trial.p95_ms.map((value) => value / 1000)),
  );
  trials.forEach((trial) => {
    const group = document.createElement("article");
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const summary = document.createElement("span");
    const bars = document.createElement("div");
    const passing = trial.outcomes.every((outcome) => outcome === "pass");
    title.textContent = trial.treatment.replace("KleidiAI disabled", "Standard service").replace("KleidiAI enabled", "Optimized service");
    summary.textContent = `${trial.rate_rps.toFixed(2)} r/s · ${passing ? "all five within target" : "all five missed target"}`;
    heading.append(title, summary);
    bars.className = "latency-trial-bars";
    bars.style.setProperty("--slo-position", `${(10 / maximumSeconds) * 100}%`);
    trial.p95_ms.forEach((value, index) => {
      const row = document.createElement("div");
      const label = document.createElement("span");
      const track = document.createElement("div");
      const bar = document.createElement("i");
      const measured = document.createElement("b");
      label.textContent = `Trial ${index + 1}`;
      track.className = "latency-track";
      bar.className = passing ? "within" : "missed";
      bar.style.width = `${Math.max(2, (value / 1000 / maximumSeconds) * 100)}%`;
      measured.textContent = `${(value / 1000).toFixed(2)} s`;
      track.append(bar);
      row.append(label, track, measured);
      bars.append(row);
    });
    const target = document.createElement("small");
    target.textContent = "Vertical marker: 10-second p95 target";
    group.append(heading, bars, target);
    container.append(group);
  });
}


function renderAuditResult(receipt) {
  const capacity = receipt.capacity;
  const arm = receipt.arm;
  const supporting = receipt.supporting;
  setText(
    "confirmation-count",
    `${capacity.confirmations} trials × 2 frozen rates × ${capacity.confirmation_seconds}s`,
  );
  setText("equation-treatment", `Optimized capacity ≥ ${capacity.optimized_pass_rps.toFixed(2)} r/s`);
  setText("equation-baseline", `Standard capacity < ${capacity.baseline_fail_rps.toFixed(2)} r/s`);
  setText("headline-ratio", `≥${capacity.minimum_ratio.toFixed(2)}×`);
  setText(
    "capacity-explanation",
    `Discovery tests located each service's capacity boundary. Before the recorded confirmation-server launch, `
    + `the release contract froze ${capacity.baseline_fail_rps.toFixed(2)} r/s just above the standard service's observed limit `
    + `and ${capacity.optimized_pass_rps.toFixed(2)} r/s for the optimized service. `
    + `All ${capacity.confirmations} standard windows failed and all ${capacity.confirmations} optimized windows passed. `
    + `That places standard capacity below ${capacity.baseline_fail_rps.toFixed(2)} r/s and optimized capacity at or above `
    + `${capacity.optimized_pass_rps.toFixed(2)} r/s. The published result is the conservative lower bound shown here.`,
  );
  setText("reveal-disabled-sample-share", `${arm.performix_disabled_sample_share_percent.toFixed(0)}%`);
  setText("reveal-enabled-sample-share", `${arm.performix_enabled_sample_share_percent.toFixed(2)}%`);
  setText("reveal-cycle-share", `${arm.linux_perf_cycle_share_percent.toFixed(2)}%`);
  setText("reveal-kernel", arm.kernel);
  setText("direct-speedup", `${supporting.direct_speedup_min.toFixed(2)}–${supporting.direct_speedup_max.toFixed(2)}× faster`);
  setText(
    "direct-shapes",
    `All ${supporting.direct_shape_gains.length} fixed shapes improved: ${supporting.direct_shape_gains.map((value) => `${value.toFixed(2)}×`).join(" · ")}`,
  );
  setText("summary-capacity", `≥${capacity.minimum_ratio.toFixed(2)}×`);
  setText("summary-performix", `${arm.performix_enabled_sample_share_percent.toFixed(2)}%`);
  setText("capacity-range", `≥${capacity.minimum_ratio.toFixed(2)}× sustainable capacity under the fixed response-time rule`);
  setText("artifact-reduction", `${supporting.artifact_reduction_percent.toFixed(2)}% smaller`);
  setText("memory-reduction", `${supporting.peak_pss_reduction_percent.toFixed(2)}% lower peak PSS`);
  setText(
    "migration-quality",
    `${supporting.migration_quality_delta_pp >= 0 ? "+" : ""}${supporting.migration_quality_delta_pp.toFixed(2)} pp `
      + `(${supporting.migration_int4_quality_correct}/${supporting.migration_quality_total} vs `
      + `${supporting.migration_bf16_quality_correct}/${supporting.migration_quality_total})`,
  );
  setText("performix-version", `Arm Performix ${arm.engine_version} · ${arm.cpu}`);
  setText("performix-disabled-share", `${arm.performix_disabled_sample_share_percent.toFixed(0)}%`);
  setText("performix-enabled-share", `${arm.performix_enabled_sample_share_percent.toFixed(2)}%`);
  setText("performix-sample-count", `${arm.enabled_function_samples.toLocaleString()} measured function samples`);
  setText("performix-linux-share", `${arm.linux_perf_cycle_share_percent.toFixed(2)}%`);
  setText("performix-kernel", arm.kernel);
  setText("performix-scope-note", arm.scope_note);
  setText("performix-capability-note", arm.pmu_capability_note);
  setText("surge-release-decision", receipt.passed ? "PASS" : "BLOCK");
  setText(
    "conclusion-copy",
    `${receipt.claims_verified} required claims passed: capacity, quality, evidence volume, matched Arm execution, and profiler integrity.`,
  );
  renderTrialMatrix(capacity.trial_matrix);
  renderLatencyConsequence(capacity.trial_matrix);
  renderRateSelection(capacity.rate_selection);
}


async function promoteOptimizedLane() {
  elements["promote-route"].disabled = true;
  elements["promote-route"].textContent = "Rechecking both Arm lanes…";
  elements["promotion-result"].textContent = "";
  try {
    const response = await fetch("/api/promote", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
    deploymentStatus = { ...deploymentStatus, ...payload };
    renderDeploymentStatus();
    setText(
      "promotion-result",
      `${payload.backend} on cores ${payload.core_group} is now serving the live support route. `
      + `Its source-model fingerprint ${payload.runtime_identity.source_artifact_sha256.slice(0, 12)}… `
      + `and ${payload.runtime_identity.runtime} ${payload.runtime_identity.runtime_version} matched the audited deployment.`,
    );
    setText("environment-label", "Verified optimized Arm64 lane serving");
    setText(
      "promotion-model-hash",
      `${payload.runtime_identity.source_artifact_sha256.slice(0, 16)}…`,
    );
    setText(
      "promotion-runtime-match",
      `${payload.runtime_identity.runtime} ${payload.runtime_identity.runtime_version} · matched`,
    );
    setText(
      "promotion-arm-match",
      `${payload.runtime_identity.architecture} · ${payload.runtime_identity.threads_per_lane} threads per lane`,
    );
    setText(
      "promotion-control-match",
      `${payload.runtime_identity.changed_control}: ${payload.runtime_identity.baseline_control} → ${payload.runtime_identity.optimized_control}`,
    );
    elements["promotion-identity"].hidden = false;
    elements["tab-proof"].classList.add("completed");
  } catch (error) {
    elements["promotion-result"].textContent = `Activation blocked: ${error.message}`;
    elements["promote-route"].disabled = false;
    elements["promote-route"].textContent = "Retry optimized-lane activation";
  }
}


function routeNextLiveRequest() {
  activateView("workspace");
  elements["live-mode"].checked = true;
  setInferenceMode("live");
}


async function generateAdoptionKit() {
  elements["generate-adoption-kit"].disabled = true;
  elements["generate-adoption-kit"].textContent = "Generating and validating starter…";
  setText("adoption-status", "Creating the files with ArmProof now.");
  try {
    const response = auditAvailable
      ? await fetch("/api/adoption", { method: "POST" })
      : await fetch("./adoption.json", { cache: "no-store" });
    const receipt = await response.json();
    if (!response.ok) throw new Error(receipt.error || `HTTP ${response.status}`);
    setText("adoption-files", `${receipt.generated_files.length} files · ${receipt.generated_files.join(", ")}`);
    setText(
      "adoption-gate",
      `${receipt.validation_status} · ${receipt.validation_detail}`,
    );
    setText("adoption-contract", `${receipt.contract_sha256.slice(0, 16)}…`);
    setText("adoption-workflow", receipt.workflow.trim());
    const download = elements["adoption-download"];
    if (receipt.archive_base64) {
      const bytes = Uint8Array.from(
        atob(receipt.archive_base64),
        (character) => character.charCodeAt(0),
      );
      download.href = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
    } else {
      download.href = receipt.archive_href;
    }
    download.download = receipt.archive_name;
    download.hidden = false;
    elements["adoption-result"].hidden = false;
    setText(
      "adoption-status",
      "Starter structure validated. It remains blocked until the new service collects and seals its own measured evidence.",
    );
    elements["generate-adoption-kit"].textContent = "Collection starter generated";
    elements["adoption-result"].setAttribute("tabindex", "-1");
    elements["adoption-result"].focus();
  } catch (error) {
    elements["generate-adoption-kit"].disabled = false;
    elements["generate-adoption-kit"].textContent = "Retry starter generation";
    setText("adoption-status", `Starter generation unavailable: ${error.message}. The repository includes the same executable example under examples/http-slo/.`);
  }
}


function openAdoptionKit() {
  activateView("proof", { focusHeading: true });
  elements["proof-details"].open = true;
  elements["reuse-title"].setAttribute("tabindex", "-1");
  elements["reuse-title"].scrollIntoView({ behavior: "smooth", block: "start" });
  elements["reuse-title"].focus({ preventScroll: true });
  generateAdoptionKit();
}


function renderRedesignEvidence() {
  const mixed = data.capacity.mixes.mixed;
  const proof = data.proof;
  const evidence = data.provenance.evidence;
  setText("guard-accuracy", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText(
    "guard-evaluation-size",
    `${data.quality.guard_evaluation_cases.toLocaleString()} held-out requests · separate application evaluation`,
  );
  setText("guard-gain", `+${data.quality.guard_queue_gain_pp.toFixed(2)} pp`);
  setText("guard-split", `${data.quality.guard_training_cases} train / ${data.quality.guard_evaluation_cases} held out`);
  setText("schema-valid", `${data.quality.schema_valid_percent.toFixed(0)}%`);
  setText("evidence-experiment-id", data.provenance.experiment_id);
  setText("evidence-checksum-status", `${evidence.sustained_checksummed_files} checksummed files · ${evidence.sustained_raw_confirmation_samples.toLocaleString()} outcomes`);
  setText("evidence-comparison", "Same INT4 model and runtime; only the KleidiAI setting differs");
  setText("experiment-machine", proof.instance);
  setText("experiment-model", `${data.provenance.model} INT4`);
  setText("experiment-slo", `p95 ≤ ${(data.capacity.slo_ms / 1000).toFixed(0)} seconds`);
  setText("experiment-control", evidence.only_changed_control);
  setText("arm-reveal-threads", proof.threads);
  setText("arm-reveal-control", evidence.only_changed_control);
  setText("proof-evidence-count", `${evidence.sustained_checksummed_files} sustained + ${evidence.performix_checksummed_files} Performix checksums`);
  setText("proof-derived-claims", `${proof.verified_claims} contract claims evaluated from ${evidence.sustained_raw_confirmation_samples.toLocaleString()} request outcomes; missing inputs block release.`);
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
  setText("queue-accuracy", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText("queue-gain", `+${data.quality.guard_queue_gain_pp.toFixed(2)} percentage points`);
  setText("absolute-accuracy", `${data.quality.optimized_accuracy_percent.toFixed(2)}%`);
  setText(
    "evidence-chain-counts",
    `Verify ${evidence.sustained_checksummed_files} sustained and ${evidence.performix_checksummed_files} Performix checksummed evidence files.`,
  );
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
    button.addEventListener("click", () => activateView("proof", { focusHeading: true }));
  });
  document.querySelectorAll("[data-go-surge]").forEach((button) => {
    button.addEventListener("click", () => {
      activateView("surge", { focusHeading: true });
    });
  });
  document.querySelectorAll("[data-case-id]").forEach((button) => {
    button.addEventListener("click", () => selectScenario(button.dataset.caseId));
  });
  elements["sample-select"].addEventListener("change", loadSelectedSample);
  elements["intake-form"].addEventListener("submit", routeSelectedMessage);
  elements["confirm-route"].addEventListener("click", review);
  elements["load-experiment"].addEventListener("click", loadVerifiedExperiment);
  elements["reveal-experiment-results"].addEventListener("click", revealConfirmedResult);
  elements["promote-route"].addEventListener("click", promoteOptimizedLane);
  elements["route-next-request"].addEventListener("click", routeNextLiveRequest);
  elements["open-required-audit"].addEventListener("click", () => {
    activateView("surge", { focusHeading: true });
  });
  elements["open-adoption-kit"].addEventListener("click", openAdoptionKit);
  elements["generate-adoption-kit"].addEventListener("click", generateAdoptionKit);
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
    if (view) activateView(view, { focus: false, focusHeading: true, updateHash: false });
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
    populateFinalQueues();
    populateScenarios();
    renderWorkspace();
    renderRedesignEvidence();
    renderProofDecision("recorded");
    bindInteractions();
    document.querySelectorAll("table[data-mobile-cards]").forEach(labelResponsiveTable);
    const initialView = HASH_TO_VIEW[location.hash.slice(1)] ?? "workspace";
    activateView(initialView, { focus: false, scroll: false });
    await configureLiveMode();
  } catch (error) {
    console.error(error);
    document.querySelectorAll(".view").forEach((view) => { view.hidden = true; });
    elements["load-error"].hidden = false;
  }
}


main();
