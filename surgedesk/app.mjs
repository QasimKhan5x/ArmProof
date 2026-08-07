import {
  createWorkspace,
  describeCapacity,
  findRecordedCase,
  resolveTicketToQueue,
  selectRecordedCase,
} from "./model.mjs";


const elements = Object.fromEntries(
  [...document.querySelectorAll("[id]")].map((element) => [element.id, element]),
);
const workflowId = crypto.randomUUID();

let data;
let workspace;
let inferenceMode = "recorded";
let matchedLanesAvailable = false;
let auditAvailable = false;
let observationSource = "recorded";
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
  surge: "evidence",
  proof: "release",
};
const HASH_TO_VIEW = Object.fromEntries(
  Object.entries(VIEW_TO_HASH).map(([view, hash]) => [hash, view]),
);
HASH_TO_VIEW.surge = "surge";
HASH_TO_VIEW.proof = "proof";


function setText(id, value) {
  elements[id].textContent = String(value);
}


function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}


async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}


function evidenceBindingsMatch(observed) {
  return canonicalJson(observed) === canonicalJson(data.provenance.evidence_binding_sha256);
}


async function receiptHashMatches(receipt) {
  if (
    !receipt
    || !/^[0-9a-f]{64}$/.test(receipt.receipt_sha256 ?? "")
    || typeof receipt.canonical_body !== "string"
  ) return false;
  const { receipt_sha256: expected, canonical_body: canonicalBody, ...body } = receipt;
  let parsedBody;
  try {
    parsedBody = JSON.parse(canonicalBody);
  } catch {
    return false;
  }
  return canonicalJson(parsedBody) === canonicalJson(body)
    && await sha256Hex(canonicalBody) === expected;
}


async function verifyCutoverReceipt(receipt) {
  return await receiptHashMatches(receipt)
    && receipt.workflow_id === workflowId
    && receipt.release.experiment_id === data.provenance.experiment_id
    && evidenceBindingsMatch(receipt.release.evidence_sha256)
    && receipt.release.audit_receipt_sha256 === deploymentStatus.audit_receipt_sha256
    && receipt.before.lane === "baseline"
    && receipt.candidate_shadow.lane === "optimized"
    && receipt.after.lane === "optimized";
}


function formatMs(value) {
  if (!value) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round(value)} ms`;
}


function formatShadowReceipt(result) {
  const runtime = result.runtime_identity;
  const observed = new Date(result.observed_at);
  const observedAt = Number.isNaN(observed.getTime())
    ? result.observed_at
    : observed.toLocaleTimeString([], { hour12: false });
  const control = runtime.optimization_control["mlas.disable_kleidiai"];
  const memory = runtime.memory_configuration;
  const tuningCount = Object.keys(runtime.runtime_tuning ?? {}).length;
  const tuning = tuningCount ? ` · ${tuningCount} ORT settings` : "";
  return `${result.request_id} · ${observedAt} · ${runtime.architecture}/${runtime.threads} threads · control=${control}${tuning} · declared ${memory.allocator}/THP ${memory.transparent_huge_pages} · in ${result.input_sha256.slice(0, 8)} / out ${result.model_output_sha256.slice(0, 8)}`;
}


function liveServiceLabel(lane) {
  return lane === "optimized"
    ? "Optimized service · I8MM + tuned runtime"
    : "Standard service · KleidiAI off";
}


function renderEnvironmentLabel() {
  if (inferenceMode !== "live") {
    setText("environment-label", "Recorded Graviton evidence");
    return;
  }
  const route = deploymentStatus.active_lane === "optimized" ? "optimized route selected" : "baseline route selected";
  setText(
    "environment-label",
    observationSource === "local_integration_fixture"
      ? `Local integration fixture · ${route} · synthetic timing`
      : `Connected Graviton gateway · ${route}`,
  );
}


function liveActionLabel() {
  return deploymentStatus.active_lane === "baseline" && matchedLanesAvailable
    ? "Compare current route with Arm candidate"
    : observationSource === "local_integration_fixture"
      ? "Run optimized fixture route"
      : "Run optimized live route";
}


function matchedComparisonText() {
  return `Compute isolation: same model, runtime, workload, machine, and ${data.proof.threads} threads; `
    + `${data.provenance.evidence.only_changed_control} is the service control under test`;
}


function capacityWindowLabel() {
  const mixed = data.capacity.mixes.mixed;
  const windowCount = mixed.confirmations_per_treatment * mixed.trial_matrix.length;
  return `${windowCount} ${mixed.confirmation_seconds}-second traffic windows`;
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
    if (proofState === "pending") {
      mark.className = "unknown-label";
      mark.textContent = "Awaiting check";
    } else if (proofState === "recorded" && claim.status === "pass") {
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
  if (["recorded", "pending", "active"].includes(state)) proofClaims = data.proof.claims;
  const header = elements["proof-decision-title"].closest(".proof-decision");
  const mark = header.querySelector(".decision-mark");
  header.classList.toggle("failed", state === "failed");
  elements["environment-status"].classList.toggle("failed", state === "failed");
  if (state === "fresh") {
    setText("proof-decision-source", "Revalidated during this session");
    setText("proof-decision-title", "Saved evidence approved the conservative Graviton boundary");
    setText("proof-decision-detail", detail);
    setText("proof-decision-status", "REVALIDATED NOW");
    mark.textContent = "✓";
  } else if (state === "failed") {
    setText("proof-decision-source", "Current ArmProof audit");
    setText("proof-decision-title", "Current evidence check blocked the release");
    setText("proof-decision-detail", detail);
    setText("proof-decision-status", "BLOCKED");
    mark.textContent = "×";
  } else if (state === "active") {
    setText("proof-decision-source", "Current gateway release");
    setText("proof-decision-title", "The optimized service has an active ArmProof release");
    setText("proof-decision-detail", detail);
    setText("proof-decision-status", "ACTIVE RELEASE");
    mark.textContent = "✓";
  } else if (state === "pending") {
    setText("proof-decision-source", "Current release check");
    setText("proof-decision-title", "The optimized candidate is awaiting evidence validation");
    setText(
      "proof-decision-detail",
      "The checked-in result is available, but this live route remains on the standard service until ArmProof revalidates it.",
    );
    setText("proof-decision-status", "AWAITING CHECK");
    mark.textContent = "·";
  } else {
    setText("proof-decision-source", "Checked-in ArmProof receipt");
    setText("proof-decision-title", "Checked-in release receipt");
    setText(
      "proof-decision-detail",
      `${data.proof.verified_claims} contract claims and ${data.proof.runtime_release_conditions.length} runtime conditions passed when this receipt was generated. `
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
        + (active.release_audit_id ? ` · release audit ${active.release_audit_id}` : "")
      : `Recorded ${data.provenance.model} · ${data.provenance.runtime}`,
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
    const control = runtime.optimization_control["mlas.disable_kleidiai"];
    setText("live-control", `KleidiAI ${control === "0" ? "on" : "off"} · raw flag ${control}`);
    setText("live-input-digest", active.input_sha256.slice(0, 16));
    setText("live-output-digest", active.model_output_sha256.slice(0, 16));
  }
  if (active.mode === "live_model_output") {
    elements["review-warning"].textContent = active.guard_overrode
      ? `The routing guard changed the live model route from ${active.llm_queue} to ${active.guard_queue}. Human validation is required.`
      : observationSource === "local_integration_fixture"
        ? "This fixture response has no benchmark label. Human validation is required."
        : "This live suggestion has no benchmark label. Human validation is required.";
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
    cell.textContent = "No tickets reviewed in this session.";
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
      const sourceLabel = observationSource === "local_integration_fixture" ? "fixture" : "observed";
      label.textContent = `${liveServiceLabel(ticket.deployment_lane)} · ${formatMs(ticket.gateway_latency_ms)} ${sourceLabel}`;
      const receipt = document.createElement("small");
      const observed = new Date(ticket.observed_at);
      const observedAt = Number.isNaN(observed.getTime())
        ? ticket.observed_at
        : observed.toLocaleTimeString([], { hour12: false });
      receipt.className = "ticket-receipt";
      receipt.textContent = `${ticket.request_id} · ${observedAt} · `
        + `${ticket.runtime_identity.architecture}/${ticket.runtime_identity.threads} threads · `
        + `mlas.disable_kleidiai=${ticket.runtime_identity.optimization_control["mlas.disable_kleidiai"]}`
        + ` · in ${ticket.input_sha256.slice(0, 8)} / out ${ticket.model_output_sha256.slice(0, 8)}`
        + (ticket.release_audit_id ? ` · ${ticket.release_audit_id}` : "")
        + (ticket.audit_receipt_sha256 ? ` · audit ${ticket.audit_receipt_sha256.slice(0, 10)}…` : "");
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
  const treatmentTicket = workspace.resolved.find(
    (ticket) => ticket.deployment_lane === "optimized"
      && ticket.cutover_receipt
      && ticket.cutover_receipt_verified,
  );
  const cutoverComplete = Boolean(treatmentTicket);
  elements["live-cutover-summary"].hidden = !cutoverComplete;
  if (cutoverComplete) {
    const receipt = treatmentTicket.cutover_receipt;
    elements["intake-form"].before(elements["live-cutover-summary"]);
    setText("cutover-before-lane", "Standard · KleidiAI off");
    setText(
      "cutover-before-request",
      `${receipt.before.queue} · ${receipt.comparison_id} · ${receipt.before.request_id}`,
    );
    setText("cutover-after-lane", "Optimized · I8MM + tuned runtime");
    setText("cutover-after-request", `${receipt.after.queue} · ${receipt.after.request_id}`);
    setText("cutover-audit", "Release receipt verified");
    setText(
      "cutover-capacity",
      `Approved at ≥${data.proof.runtime_memory.candidate_rps.toFixed(2)} requests/s`,
    );
    setText("cutover-receipt-sha", receipt.receipt_sha256);
    setText("cutover-comparison-binding", receipt.comparison_id);
    setText(
      "cutover-before-binding",
      `${receipt.before.request_id} · in ${receipt.before.input_sha256.slice(0, 12)}… · out ${receipt.before.model_output_sha256.slice(0, 12)}…`,
    );
    setText(
      "cutover-after-binding",
      `${receipt.after.request_id} · in ${receipt.after.input_sha256.slice(0, 12)}… · out ${receipt.after.model_output_sha256.slice(0, 12)}…`,
    );
    setText("cutover-audit-binding", receipt.release.audit_receipt_sha256);
    elements["cutover-evidence-digests"].replaceChildren();
    Object.entries(receipt.release.evidence_sha256).forEach(([experimentId, digest]) => {
      const item = document.createElement("li");
      const label = document.createElement("strong");
      const value = document.createElement("code");
      label.textContent = experimentId;
      value.textContent = digest;
      item.append(label, value);
      elements["cutover-evidence-digests"].append(item);
    });
    elements["review-complete"].hidden = true;
  }
  setText(
    "review-complete-title",
    latest.review_status === "corrected"
      ? `Corrected to ${latest.final_queue}`
      : `Routed to ${latest.final_queue}`,
  );
}


function revealVerifiedProof() {
  for (const id of ["optimization-summary", "performix-proof", "memory-proof", "proof-details"]) {
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
    const compare = deploymentStatus.active_lane === "baseline" && matchedLanesAvailable;
    elements["route-request"].textContent = compare
      ? "Running matched request…"
      : "Routing on optimized Arm service…";
    if (compare) {
      elements["shadow-comparison"].hidden = false;
      setText("shadow-baseline-latency", "Running…");
      setText("shadow-optimized-latency", "Waiting…");
      setText("shadow-baseline-result", "Serving baseline-lane request");
      setText("shadow-optimized-result", "Shadow copy follows on the same cores");
      setText("shadow-baseline-receipt", "Receipt pending");
      setText("shadow-optimized-receipt", "Receipt pending");
      setText("shadow-observation", "Running the serving lane, then the candidate without full-core contention…");
    }
    try {
      const response = await fetch(compare ? "/api/shadow-compare" : "/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: elements["customer-message"].value,
          workflow_id: workflowId,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      if (payload.cutover_receipt) {
        if (!await verifyCutoverReceipt(payload.cutover_receipt)) {
          throw new Error("cutover receipt did not match the verified release evidence");
        }
        payload.cutover_receipt_verified = true;
      }
      if (compare) {
        const baseline = payload.lanes.baseline;
        const optimized = payload.lanes.optimized;
        baseline.comparison_id = payload.comparison_id;
        optimized.comparison_id = payload.comparison_id;
        setText("shadow-baseline-latency", formatMs(baseline.gateway_latency_ms));
        setText("shadow-optimized-latency", formatMs(optimized.gateway_latency_ms));
        setText("shadow-baseline-result", `${baseline.suggested_label} · ${baseline.queue}`);
        setText("shadow-optimized-result", `${optimized.suggested_label} · ${optimized.queue} · shadow only`);
        setText("shadow-baseline-receipt", formatShadowReceipt(baseline));
        setText("shadow-optimized-receipt", formatShadowReceipt(optimized));
        setText(
          "shadow-observation",
          `${payload.comparison_id} completed on both configurations and proposed ${payload.same_queue ? "the same" : "different"} final queue. `
            + `The release decision comes from ${capacityWindowLabel()}, quality checks, and Arm profiles.`,
        );
        workspace = selectRecordedCase(workspace, baseline);
      } else {
        workspace = selectRecordedCase(workspace, payload);
      }
      elements["intake-error"].hidden = true;
      renderWorkspace();
      elements["review-panel"].scrollIntoView({ behavior: "smooth", block: "nearest" });
      elements["review-title"].setAttribute("tabindex", "-1");
      elements["review-title"].focus({ preventScroll: true });
    } catch (error) {
      await configureLiveMode();
      elements["intake-error"].textContent = `Request failed: ${error.message}`;
      elements["intake-error"].hidden = false;
      elements["intake-error"].setAttribute("tabindex", "-1");
      elements["intake-error"].focus();
    } finally {
      elements["route-request"].disabled = false;
      elements["route-request"].textContent = liveActionLabel();
    }
    return;
  }
  const recordedCase = findRecordedCase(data.routing_cases, elements["customer-message"].value);
  if (!recordedCase) {
    elements["intake-error"].textContent = `No recorded ${data.provenance.model} result exists for edited text. Select an evidence-backed ${data.provenance.dataset} request in the checked-in view.`;
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


function setInferenceMode(mode, { focus = true } = {}) {
  inferenceMode = mode;
  const live = mode === "live";
  elements["sample-select"].disabled = live;
  elements["sample-select"].hidden = live;
  elements["sample-select-label"].hidden = live;
  elements["scenario-picker"].hidden = live;
  renderEnvironmentLabel();
  elements["workspace-mode"].textContent = live
    ? observationSource === "local_integration_fixture"
      ? "Local integration fixture · synthetic timing"
      : "Connected Graviton gateway"
    : "Archived Graviton response";
  elements["intake-note"].textContent = live
    ? deploymentStatus.active_lane === "baseline"
      ? "The serving lane handles the request; the candidate receives a sequential shadow copy for a contention-free comparison."
      : observationSource === "local_integration_fixture"
        ? "This message is sent through the evidence-cleared optimized fixture route; timing is synthetic."
        : "This message is sent through the evidence-cleared optimized service and local queue guard."
    : "Select an archived support case to load its recorded model output.";
  elements["route-request"].textContent = live ? liveActionLabel() : "Review recorded request";
  elements["customer-message"].readOnly = !live;
  if (live) {
    elements["customer-message"].value = "";
    elements["customer-message"].placeholder = observationSource === "local_integration_fixture"
      ? "Enter a support request for the local integration fixture"
      : "Enter a support request for the Arm64 service";
    if (focus) elements["customer-message"].focus();
  } else {
    elements["customer-message"].placeholder = "";
    loadSelectedSample();
  }
  if (!live) elements["shadow-comparison"].hidden = true;
  elements["intake-error"].hidden = true;
  workspace = { ...workspace, active: null };
  renderWorkspace();
  if (live && deploymentStatus.active_lane === "optimized") {
    elements["review-complete"].hidden = true;
  }
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
    observationSource = status.observation_source ?? "recorded";
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
    if (status.live_available && status.matched_lanes_available) {
      if (
        deploymentStatus.active_lane === "optimized"
        && deploymentStatus.release_ready
        && deploymentStatus.audit_experiment_id
      ) {
        renderProofDecision(
          "active",
          `${deploymentStatus.audit_experiment_id} remains authorized by this gateway session.`,
        );
      } else {
        renderProofDecision("pending");
      }
      elements["live-mode"].checked = true;
      setInferenceMode("live", { focus: false });
    }
    const fixture = observationSource === "local_integration_fixture";
    setText(
      "session-request-scope",
      fixture ? "Fixture requests and synthetic lane receipts" : "Live requests and lane receipts",
    );
    setText("shadow-source-chip", fixture ? "Local fixture · synthetic timing" : "Observed now on Graviton");
    setText("live-observed-label", fixture ? "Fixture response" : "Observed now");
    setText("cutover-source-chip", fixture ? "Local integration fixture · synthetic timing" : "Observed now on Graviton");
    setText("cutover-eyebrow", fixture ? "Integration flow complete" : "Connected gateway cutover complete");
    setText(
      "live-cutover-title",
      fixture
        ? "The integration gateway selected the optimized Arm route"
        : "The optimized Arm service is handling support traffic",
    );
    setText(
      "cutover-description",
      fixture
        ? "The local fixture exercised the complete before-and-after release flow; its timing is synthetic."
        : "A matched request established the starting route; a new inference request confirms the approved route is selected.",
    );
    renderDeploymentStatus();
    if (!auditAvailable) {
      elements["load-experiment"].textContent = "Open checked-in evidence";
      elements["evidence-load-note"].textContent =
        "This public page can inspect the repository receipt. Run the local gateway to hash and re-derive the archive.";
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
  elements["rollback-route"].hidden = !optimized;
  setText(
    "opening-capacity",
    publicEvidence || optimized || freshAudit
      ? `≥${data.proof.runtime_memory.candidate_rps.toFixed(2)} r/s`
      : "Awaiting validation",
  );
  const fixture = observationSource === "local_integration_fixture";
  setText("promotion-eyebrow", fixture ? "Release engineer · integration route decision" : "Release engineer · connected gateway decision");
  setText("promotion-current-label", fixture ? "Active fixture route" : "Serving now");
  setText("promotion-candidate-label", "Candidate");
  setText("promotion-audit-label", "Required evidence");
  elements["promote-route"].hidden = false;
  elements["open-required-audit"].textContent = "Open required capacity audit";
  setText(
    "workspace-serving",
    !connected
      ? "Recorded model result"
      : optimized
        ? liveServiceLabel("optimized")
        : liveServiceLabel("baseline"),
  );
  setText(
    "workspace-candidate",
    optimized
        ? fixture ? "Released · selected in fixture" : "Released · selected by connected gateway"
      : connected
        ? liveServiceLabel("optimized")
        : publicEvidence
          ? `I8MM + tuned runtime · measured`
          : "Connect both matched Arm64 services",
  );
  setText(
    "workspace-candidate-label",
    optimized ? "Arm optimization status" : "Arm optimization candidate",
  );
  setText(
    "workspace-release-status",
    optimized
      ? fixture
        ? "Release receipt passed · fixture route selected"
        : "Release receipt passed · optimized gateway route selected"
      : freshAudit
        ? "Fresh release receipt passed · gateway switch ready"
      : publicEvidence
        ? "Recorded Graviton release checks passed"
        : "Waiting for the measured release check",
  );
  setText(
    "opening-status",
    optimized
      ? fixture
        ? "Release receipt passed · fixture route selected"
        : "Release receipt passed · optimized route selected"
      : freshAudit
        ? "Fresh release receipt passed · switch ready"
        : publicEvidence
          ? "Checked-in result; local audit required to recompute"
          : fixture
            ? "Local release check required"
            : "Current-session release check required",
  );
  elements["opening-status"].classList.toggle("approved", optimized || freshAudit);
  setText(
    "promotion-current-lane",
    !connected
      ? "No matched live route connected"
      : `${deploymentStatus.backend} · cores ${deploymentStatus.core_group}`,
  );
  setText(
    "promotion-audit-status",
    freshAudit
      ? "Fresh release receipt verified"
      : "Evidence validation required",
  );
  if (publicEvidence) {
    elements["tab-proof"].textContent = "Release status";
    setText("promotion-eyebrow", "Recorded release decision");
    setText("promotion-current-label", "Baseline");
    setText("promotion-current-lane", `${data.capacity.mixes.mixed.trial_matrix[0].treatment} · measured`);
    setText("promotion-candidate-label", "Released candidate");
    setText("promotion-candidate-lane", `${data.capacity.mixes.mixed.trial_matrix[1].treatment} · measured`);
    setText("promotion-audit-label", "Release evidence");
    setText(
      "promotion-audit-status",
      `${data.proof.verified_claims} compute and quality checks plus ${data.proof.runtime_release_conditions.length} runtime conditions passed`,
    );
    setText("promotion-title", "The optimized candidate cleared the checked-in release policy");
    setText(
      "promotion-detail",
      `The repository receipt binds the ${data.provenance.machine} model, matched Arm-compute comparison, memory ablation, sustained traffic outcomes, quality rows, and profiler evidence. Live routing remains unavailable on this public page.`,
    );
    elements["promote-route"].hidden = true;
    elements["open-required-audit"].hidden = false;
    elements["open-required-audit"].textContent = "Inspect release evidence";
    elements["route-next-request"].hidden = true;
  } else if (optimized) {
    elements["tab-proof"].textContent = "Traffic switch";
    setText("promotion-current-label", fixture ? "Active fixture route" : "Serving now");
    setText("promotion-candidate-label", "Previous route");
    setText("promotion-candidate-lane", liveServiceLabel("baseline"));
    setText("promotion-title", fixture ? "The optimized route is selected in the integration fixture" : "The optimized service is handling live requests");
    setText(
      "promotion-detail",
      fixture
        ? "The fixture gateway selected its optimized route only after the measured release check passed and both service declarations were checked again. Timing remains synthetic."
        : "The gateway changed its active route only after the measured release check passed and both service declarations were checked again.",
    );
    elements["promote-route"].disabled = true;
    elements["promote-route"].textContent = fixture ? "Optimized fixture route selected" : "Connected gateway switched";
    elements["route-next-request"].hidden = false;
    elements["open-required-audit"].hidden = true;
  } else if (freshAudit && matchedLanesAvailable) {
    elements["tab-proof"].textContent = "Traffic switch";
    setText(
      "promotion-title",
      fixture
        ? "The measured optimized route is ready for fixture selection"
        : "The measured optimized service is ready for the connected gateway",
    );
    setText(
      "promotion-detail",
      fixture
        ? "The release check passed. The fixture gateway will recheck both Arm service declarations before selecting the optimized route."
        : "The release check passed. The gateway will recheck both Arm service declarations, then switch traffic from the standard service to the optimized service.",
    );
    elements["promote-route"].disabled = false;
    elements["promote-route"].textContent = fixture ? "Select optimized fixture route" : "Switch connected gateway to optimized service";
    elements["route-next-request"].hidden = true;
    elements["open-required-audit"].hidden = true;
  } else {
    elements["tab-proof"].textContent = matchedLanesAvailable ? "Traffic switch" : "Release status";
    setText("promotion-title", connected
      ? fixture
        ? "The standard route is selected in the integration fixture"
        : "The standard service is handling support requests"
      : "Connect both matched Arm64 lanes to enable a gateway switch");
    setText(
      "promotion-detail",
      connected
        ? fixture
          ? "Run the measured release check before selecting the optimized fixture route."
          : "Run the measured release check before routing live requests to the optimized service."
        : "The public evidence remains inspectable, but changing the connected route requires both matched endpoints and a fresh local audit.",
    );
    elements["promote-route"].disabled = true;
    elements["promote-route"].textContent = connected
      ? "Recompute the release decision first"
      : "Matched Arm64 lanes required";
    elements["route-next-request"].hidden = true;
    elements["open-required-audit"].hidden = false;
  }
  renderEnvironmentLabel();
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
  if (workspace.resolved.length > 1 && !elements["live-cutover-summary"].hidden) {
    elements["intake-form"].hidden = true;
    elements["live-cutover-title"].setAttribute("tabindex", "-1");
    elements["live-cutover-summary"].scrollIntoView({ block: "start" });
    elements["live-cutover-title"].focus({ preventScroll: true });
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
    "straight-through": ["Stolen card", "Account security request"],
    "guard-intervention": ["Missing card", "Card delivery question"],
    "human-correction": ["Statement fee", "Operator review required"],
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
    quality: () => "Quality outputs checked against the release limit",
    performix: () => "Arm profiler evidence parsed",
    memory: () => `${detail.confirmation_windows} sustained treatment windows verified`,
    archive: () => "Capacity archive matched the frozen plan",
    requests: () => `${capacityWindowLabel()} reconstructed`,
    policy: () => `Release policy ${detail.passed ? "passed" : "blocked"}`,
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
  const response = await fetch("/api/audit-stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow_id: workflowId }),
  });
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
    "Reading the archive, re-deriving every recorded long window, and evaluating the contract.";
  setText("evidence-seal", "…");
  elements["audit-receipt"].hidden = true;
  elements["audit-progress"].replaceChildren();
  elements["audit-progress"].hidden = false;
  try {
    const receipt = await streamVerifiedAudit();
    const receiptHashValid = await receiptHashMatches(receipt);
    const valid =
      receipt.passed
      && receipt.workflow_id === workflowId
      && receipt.experiment_id === data.provenance.experiment_id
      && JSON.stringify(receipt.release_evidence_ids) === JSON.stringify(data.provenance.release_evidence_ids)
      && evidenceBindingsMatch(receipt.release_evidence_sha256)
      && receiptHashValid
      && receipt.claims_verified === data.proof.verified_claims
      && Array.isArray(receipt.claims)
      && receipt.claims.length === receipt.claims_verified
      && receipt.claims.every((claim) => claim.status === "pass")
      && receipt.raw_request_outcomes === expected.sustained_raw_confirmation_samples
      && receipt.raw_quality_outputs === expected.raw_quality_outputs
      && receipt.confirmation_files === expected.sustained_raw_confirmation_files
      && receipt.archive_sha256 === expected.sustained_archive_sha256
      && receipt.memory.passed
      && receipt.memory.candidate_rps === data.proof.runtime_memory.candidate_rps
      && receipt.memory.confirmation_passes === receipt.memory.confirmation_windows
      && receipt.memory.simplification_failures === receipt.memory.simplification_windows
      && receipt.matched_control;
    if (!valid) throw new Error("audit receipt does not match the loaded release data");
    proofClaims = receipt.claims;
    renderAuditResult(receipt);
    revealVerifiedProof();
    renderProofDecision(
      "fresh",
      `${receipt.claims_verified} contract claims and ${receipt.memory.release_conditions.length} runtime conditions passed after the bound evidence was re-derived in ${receipt.elapsed_ms.toFixed(0)} ms.`,
    );
    deploymentStatus = {
      ...deploymentStatus,
      release_ready: true,
      audit_experiment_id: receipt.experiment_id,
      release_evidence_ids: receipt.release_evidence_ids,
      release_evidence_sha256: receipt.release_evidence_sha256,
      audit_receipt_sha256: receipt.receipt_sha256,
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
    setText("audit-control-result", matchedComparisonText());
    setText(
      "audit-claim-result",
      `${receipt.claims_verified}/${receipt.claims_verified} contract claims + ${receipt.memory.release_conditions.length} runtime conditions passed`,
    );
    elements["audit-receipt"].hidden = false;
    setText("audit-receipt-time", `Completed from local evidence in ${receipt.elapsed_ms.toFixed(0)} ms`);
    elements["load-experiment"].textContent = "Saved evidence revalidated";
    elements["evidence-load-note"].textContent =
      `${receipt.adapter} recomputed the release decision from the checksum-bound archive in ${receipt.elapsed_ms.toFixed(0)} ms.`;
    elements["evidence-loader"].classList.add("loaded");
    setText("evidence-seal", "✓");
    elements["tab-surge"].classList.add("completed");
    elements["experiment-results"].hidden = true;
    elements["audit-receipt-title"].setAttribute("tabindex", "-1");
    elements["audit-receipt"].scrollIntoView({ behavior: "smooth", block: "start" });
    elements["audit-receipt-title"].focus({ preventScroll: true });
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
      slo_ms: data.capacity.slo_ms,
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
      disabled_function_samples: data.proof.performix.disabled_function_samples,
      disabled_kai_function_samples: data.proof.performix.disabled_kai_function_samples,
      enabled_kai_function_samples: data.proof.performix.enabled_kai_function_samples,
      scope_note: data.proof.performix.scope_note,
      pmu_capability_note: data.proof.performix.pmu_capability_note,
    },
    memory: {
      ...data.proof.runtime_memory,
      release_conditions: data.proof.runtime_release_conditions,
    },
    supporting: {
      direct_speedup_min: data.proof.direct_speedup_min,
      direct_speedup_max: data.proof.direct_speedup_max,
      direct_shape_gains: data.proof.direct_shape_gains,
      artifact_reduction_percent: data.proof.artifact_reduction_percent,
      migration_peak_pss_reduction_percent: data.proof.migration_peak_pss_reduction_percent,
      migration_quality_delta_pp: data.proof.migration_quality_delta_pp,
      migration_int4_quality_correct: data.proof.migration_int4_quality_correct,
      migration_bf16_quality_correct: data.proof.migration_bf16_quality_correct,
      migration_quality_total: data.proof.migration_quality_total,
    },
  });
  revealVerifiedProof();
  setText("audit-archive-result", `${evidence.sustained_archive_sha256.slice(0, 12)}… · repository receipt`);
  setText("audit-request-result", `${evidence.sustained_raw_confirmation_samples.toLocaleString()} capacity requests · ${evidence.raw_quality_outputs.toLocaleString()} model outputs`);
  setText("audit-control-result", matchedComparisonText());
  setText(
    "audit-claim-result",
    `${data.proof.verified_claims}/${data.proof.verified_claims} contract claims + ${data.proof.runtime_release_conditions.length} runtime conditions`,
  );
  setText("audit-receipt-time", "Loaded from the published repository receipt");
  elements["experiment-results"].hidden = true;
  elements["load-experiment"].textContent = "Repository evidence opened";
  elements["evidence-load-note"].textContent =
    "GitHub Pages loaded the checked-in audit receipt. The local gateway recomputes the archive when requested.";
  elements["evidence-loader"].classList.add("loaded");
  setText("evidence-seal", "✓");
  renderProofDecision("recorded");
  elements["audit-receipt-title"].setAttribute("tabindex", "-1");
  elements["audit-receipt"].scrollIntoView({ block: "start" });
  elements["audit-receipt-title"].focus({ preventScroll: true });
}


function renderTrialMatrix(trials) {
  const header = elements["trial-matrix-head"];
  const headerRow = document.createElement("tr");
  const trialCount = Math.max(...trials.map((trial) => trial.outcomes.length));
  [
    "Treatment",
    "Tested rate",
    ...Array.from({ length: trialCount }, (_, index) => `Trial ${index + 1}`),
    "Interpretation",
  ].forEach((label) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    headerRow.append(cell);
  });
  header.replaceChildren(headerRow);
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
  setText("rate-discovery-id", "Discovery run");
  setText(
    "rate-confirmation-id",
    "Preregistered confirmation run",
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


function renderLatencyConsequence(trials, description) {
  const container = elements["latency-consequence-groups"];
  container.replaceChildren();
  const maximumSeconds = Math.max(
    description.slo_seconds,
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
    summary.textContent = `${trial.rate_rps.toFixed(2)} r/s · ${description.outcomeSummary(trial.outcomes)}`;
    heading.append(title, summary);
    bars.className = "latency-trial-bars";
    bars.style.setProperty("--slo-position", `${(description.slo_seconds / maximumSeconds) * 100}%`);
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
    target.textContent = `Vertical marker: ${description.slo_seconds}-second p95 target`;
    group.append(heading, bars, target);
    container.append(group);
  });
}


function renderAuditResult(receipt) {
  const capacity = receipt.capacity;
  const description = describeCapacity(capacity);
  const arm = receipt.arm;
  const supporting = receipt.supporting;
  const memory = receipt.memory;
  const controlTrial = capacity.trial_matrix[0];
  const treatmentTrial = capacity.trial_matrix[1];
  const controlPasses = controlTrial.outcomes.filter((outcome) => outcome === "pass").length;
  const treatmentPasses = treatmentTrial.outcomes.filter((outcome) => outcome === "pass").length;
  const qualityDelta = data.quality.accuracy_delta_pp;
  setText("result-capacity-ratio", `At least ${capacity.minimum_ratio.toFixed(1)}×`);
  setText(
    "result-capacity-scope",
    `CPU-only generative classification on the same ${data.proof.instance}, model, runtime, workload, ${data.proof.threads} threads, and `
      + `${description.slo_seconds}-second p95 rule. The optimized boundary represents ${(capacity.optimized_pass_rps * 3600).toLocaleString()} offered messages/hour. Offered rate differs intentionally to locate each capacity boundary.`,
  );
  setText("result-control-boundary", `${capacity.baseline_fail_rps.toFixed(2)} requests/s`);
  setText("result-control-outcomes", `${controlPasses}/${controlTrial.outcomes.length} long windows passed`);
  setText("result-treatment-boundary", `${capacity.optimized_pass_rps.toFixed(2)} requests/s`);
  setText("result-treatment-outcomes", `${treatmentPasses}/${treatmentTrial.outcomes.length} long windows passed`);
  setText("result-quality-delta", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}% queue accuracy`);
  setText(
    "result-quality-scope",
    `Five-queue recommendation improved from ${(data.quality.guard_queue_accuracy_percent - data.quality.guard_queue_gain_pp).toFixed(2)}% to ${data.quality.guard_queue_accuracy_percent.toFixed(2)}%. `
      + `The harder 77-intent diagnostic scored ${data.quality.optimized_accuracy_percent.toFixed(2)}% (${qualityDelta.toFixed(2)} pp vs standard); every route remains human-confirmed.`,
  );
  setText(
    "confirmation-count",
    `${description.windows_per_rate} trials × ${description.rate_count} frozen rates × ${description.window_seconds}s`,
  );
  setText(
    "trial-matrix-title",
    `${description.rate_count} frozen rates across ${description.total_windows} long confirmation windows`,
  );
  setText(
    "latency-consequence-title",
    `Every window compared against the ${description.slo_seconds}-second response target`,
  );
  setText(
    "latency-window-label",
    `p95 from every ${description.window_seconds}-second trial`,
  );
  setText(
    "summary-capacity-context",
    `Same ${data.proof.instance} server and ${description.slo_seconds}-second p95 SLO`,
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
  setText("summary-capacity", `≥${capacity.minimum_ratio.toFixed(2)}×`);
  setText("summary-footprint", `${supporting.artifact_reduction_percent.toFixed(2)}% smaller`);
  setText(
    "summary-performix",
    `${arm.performix_disabled_sample_share_percent.toFixed(0)}% → ${arm.performix_enabled_sample_share_percent.toFixed(2)}%`,
  );
  setText("summary-final-capacity", `≥${memory.candidate_rps.toFixed(2)} r/s`);
  setText("summary-final-context", `${memory.confirmation_passes}/${memory.confirmation_windows} sustained windows within the fixed p95 SLO`);
  setText("performix-version", `Arm Performix ${arm.engine_version} · ${arm.cpu}`);
  setText("performix-disabled-share", `${arm.performix_disabled_sample_share_percent.toFixed(0)}%`);
  setText("performix-enabled-share", `${arm.performix_enabled_sample_share_percent.toFixed(2)}%`);
  setText("performix-disabled-count", `${arm.disabled_kai_function_samples.toLocaleString()} / ${arm.disabled_function_samples.toLocaleString()} measured function samples`);
  setText("performix-sample-count", `${arm.enabled_kai_function_samples.toLocaleString()} / ${arm.enabled_function_samples.toLocaleString()} measured function samples`);
  setText("performix-linux-share", `${arm.linux_perf_cycle_share_percent.toFixed(2)}%`);
  setText("performix-kernel", arm.kernel);
  setText("performix-scope-note", arm.scope_note);
  setText("performix-capability-note", arm.pmu_capability_note);
  renderOptimizationJourney(memory);
  renderMemoryProof(memory);
  setText("surge-release-decision", receipt.passed ? "PASS" : "BLOCK");
  setText(
    "conclusion-copy",
    `${receipt.claims_verified} compute and quality claims plus ${memory.release_conditions.length} runtime release conditions passed.`,
  );
  renderTrialMatrix(capacity.trial_matrix);
  renderLatencyConsequence(capacity.trial_matrix, description);
  renderRateSelection(capacity.rate_selection);
}


function renderOptimizationJourney(memory) {
  setText("journey-final-capacity", `≥${memory.candidate_rps.toFixed(2)} requests/s`);
  setText(
    "journey-final-confirmation",
    `${memory.confirmation_passes}/${memory.confirmation_windows} sustained windows passed`,
  );
  const list = elements["optimization-stages"];
  list.replaceChildren();
  const formatOutcome = {
    model: (outcome) => [
      `${outcome.artifact_reduction_percent.toFixed(2)}% smaller model`,
      `${outcome.migration_peak_pss_reduction_percent.toFixed(2)}% lower peak memory`,
    ],
    compute: (outcome) => [
      `≥${outcome.minimum_capacity_ratio.toFixed(2)}× sustainable capacity`,
      `${outcome.performix_kai_sample_share_percent.toFixed(2)}% Performix kai_* samples`,
    ],
    memory: (outcome) => [
      `≥${outcome.final_capacity_rps.toFixed(2)} requests/s`,
      `${outcome.p95_reduction_percent.toFixed(2)}% lower median p95 at the stress rate`,
      `Simpler recipe missed the SLO in ${outcome.simplification_failures}/${outcome.simplification_windows} long windows`,
    ],
  };
  data.optimization_journey.stages.forEach((stage) => {
    const item = document.createElement("li");
    item.dataset.stage = stage.id;
    const sequence = document.createElement("span");
    sequence.className = "stage-sequence";
    sequence.textContent = stage.sequence;
    const copy = document.createElement("div");
    const label = document.createElement("small");
    const title = document.createElement("h3");
    const reason = document.createElement("p");
    const outcomes = document.createElement("ul");
    const evidence = document.createElement("footer");
    label.textContent = `Stage ${stage.sequence}`;
    title.textContent = stage.change;
    reason.textContent = stage.reason;
    formatOutcome[stage.id](stage.outcome).forEach((value) => {
      const row = document.createElement("li");
      row.textContent = value;
      outcomes.append(row);
    });
    evidence.textContent = `Evidence: ${stage.evidence}`;
    copy.append(label, title, reason, outcomes, evidence);
    item.append(sequence, copy);
    list.append(item);
  });
}


function renderMemoryProof(memory) {
  setText(
    "memory-confirmation-badge",
    `${memory.confirmation_passes}/${memory.confirmation_windows} sustained windows passed`,
  );
  setText(
    "memory-proof-copy",
    `At ${memory.candidate_rps.toFixed(2)} requests/s, KleidiAI alone missed the p95 objective in every sustained window. `
      + "The complete thread, allocator, and huge-page recipe passed all five. The allocator-and-huge-page variant failed all five sustained windows, so it was not released.",
  );
  setText("memory-baseline-p95", formatMs(memory.baseline_median_p95_ms));
  setText("memory-optimized-p95", formatMs(memory.optimized_median_p95_ms));
  setText("memory-simplified-p95", formatMs(memory.simplification_median_p95_ms));
  setText(
    "memory-simplified-result",
    `${memory.simplification_failures}/${memory.simplification_windows} windows missed the SLO`,
  );
  setText("memory-capacity-gain", `+${memory.capacity_gain_percent.toFixed(2)}%`);
  setText(
    "memory-capacity-detail",
    `${memory.previous_capacity_rps.toFixed(2)} → ${memory.candidate_rps.toFixed(2)} requests/s verified floor`,
  );

  const labels = {
    current: "KleidiAI only",
    "thp-only": "Add THP",
    "thread-thp": "Thread overrides + THP",
    "mimalloc-thp": "mimalloc + THP",
  };
  const rows = Object.entries(memory.ablation_median_p95_ms);
  const maximum = Math.max(...rows.map(([, value]) => value));
  elements["memory-ablation"].replaceChildren();
  rows.forEach(([id, value]) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const track = document.createElement("div");
    const bar = document.createElement("i");
    const measured = document.createElement("strong");
    label.textContent = labels[id] ?? id;
    track.className = "memory-ablation-track";
    bar.style.width = `${Math.max(4, value / maximum * 100)}%`;
    if (id === "mimalloc-thp") bar.className = "short-screen-best";
    measured.textContent = formatMs(value);
    track.append(bar);
    row.append(label, track, measured);
    elements["memory-ablation"].append(row);
  });

  elements["memory-release-conditions"].replaceChildren();
  memory.release_conditions.forEach((condition) => {
    const item = document.createElement("li");
    const mark = document.createElement("span");
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    const detail = document.createElement("small");
    mark.textContent = "✓";
    title.textContent = condition.label;
    detail.textContent = condition.detail
      ?? (condition.observed !== undefined
        ? `${condition.observed}/${condition.required} required windows`
        : condition.digest
          ? `Output digest ${condition.digest.slice(0, 12)}…`
          : "Verified from the checksum-bound archive");
    copy.append(title, detail);
    item.append(mark, copy);
    elements["memory-release-conditions"].append(item);
  });
}


async function promoteOptimizedLane() {
  elements["promote-route"].disabled = true;
  elements["promote-route"].textContent = "Rechecking both Arm lanes…";
  elements["promotion-result"].textContent = "";
  try {
    const response = await fetch("/api/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow_id: workflowId }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
    deploymentStatus = { ...deploymentStatus, ...payload };
    renderDeploymentStatus();
    const fixture = observationSource === "local_integration_fixture";
    setText(
      "promotion-result",
      `The gateway ${fixture ? "selected the optimized fixture route" : "selected the optimized support route"} using ${payload.backend} on cores ${payload.core_group}. `
      + "The model and runtime artifacts, AWS instance, Arm placement, KleidiAI control, ONNX Runtime settings, declared allocator treatment, and huge-page policy all matched the accepted release.",
    );
    setText(
      "promotion-model-hash",
      `model ${payload.runtime_identity.model_identity.slice(0, 10)}… · source ${payload.runtime_identity.source_artifact_sha256.slice(0, 10)}…`,
    );
    setText(
      "promotion-runtime-match",
      `${payload.runtime_identity.runtime} ${payload.runtime_identity.runtime_version} · wheel ledger ${payload.runtime_identity.runtime_artifact_ledger_sha256.slice(0, 10)}…`,
    );
    setText(
      "promotion-arm-match",
      `${payload.runtime_identity.instance_type} via IMDSv2 · ${payload.runtime_identity.architecture} · cores ${payload.runtime_identity.cpu_affinity[0]}–${payload.runtime_identity.cpu_affinity.at(-1)}`,
    );
    setText(
      "promotion-control-match",
      `${payload.runtime_identity.changed_control}: ${payload.runtime_identity.baseline_control} → ${payload.runtime_identity.optimized_control}`
      + ` · ${Object.keys(payload.runtime_identity.runtime_tuning.optimized).length} ORT settings`
      + ` · declared ${payload.runtime_identity.memory.optimized.allocator} · THP ${payload.runtime_identity.memory.optimized.transparent_huge_pages}`,
    );
    elements["promotion-identity"].hidden = false;
    elements["tab-proof"].classList.add("completed");
    renderEnvironmentLabel();
  } catch (error) {
    elements["promotion-result"].textContent = `Traffic decision blocked: ${error.message}`;
    elements["promote-route"].disabled = false;
    elements["promote-route"].textContent = "Retry traffic decision";
  }
}


function openPromotionConfirmation() {
  const fixture = observationSource === "local_integration_fixture";
  setText(
    "promotion-confirm-environment",
    fixture ? "Local integration fixture · synthetic timing" : "Connected Graviton service",
  );
  setText(
    "promotion-confirm-audit",
    `Fresh release receipt · ${deploymentStatus.audit_receipt_sha256.slice(0, 12)}…`,
  );
  setText(
    "promotion-confirmation-copy",
    fixture
      ? "The fixture gateway will recheck both declared services before selecting its optimized route."
      : "The gateway will recheck both running services before changing the active support route.",
  );
  elements["promotion-confirmation"].showModal();
}


async function rollbackToStandardLane() {
  elements["rollback-route"].disabled = true;
  try {
    const response = await fetch("/api/rollback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow_id: workflowId }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    deploymentStatus = { ...deploymentStatus, ...payload };
    proofState = "recorded";
    elements["promotion-identity"].hidden = true;
    elements["live-cutover-summary"].hidden = true;
    elements["intake-form"].hidden = false;
    setText("promotion-result", "The gateway returned to the standard service.");
    await configureLiveMode();
  } catch (error) {
    setText("promotion-result", `Rollback blocked: ${error.message}`);
  } finally {
    elements["rollback-route"].disabled = false;
  }
}


function routeNextLiveRequest() {
  activateView("workspace");
  elements["intake-form"].hidden = false;
  elements["live-mode"].checked = true;
  setInferenceMode("live");
  elements["shadow-comparison"].hidden = true;
}


function startNextRequest() {
  elements["live-cutover-summary"].hidden = true;
  elements["review-complete"].hidden = true;
  routeNextLiveRequest();
}


function renderRedesignEvidence() {
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
  setText("evidence-comparison", matchedComparisonText());
  setText("experiment-machine", proof.instance);
  setText("experiment-model", `${data.provenance.model} · ${data.provenance.runtime}`);
  setText("experiment-slo", `p95 ≤ ${(data.capacity.slo_ms / 1000).toFixed(0)} seconds`);
  setText("experiment-control", evidence.only_changed_control);
  setText("proof-evidence-count", `${evidence.sustained_checksummed_files} sustained + ${evidence.performix_checksummed_files} Performix + ${evidence.runtime_memory_checksummed_files} memory checksums`);
  setText("proof-derived-claims", `${proof.verified_claims} compute and quality claims plus ${proof.runtime_release_conditions.length} runtime conditions evaluated; missing inputs block release.`);
  setText("deployment-instance", proof.instance);
  setText("deployment-threads", proof.threads);
  setText("deployment-runtime", data.provenance.runtime);
  setText("deployment-optimization", data.provenance.optimization);
  setText("intent-count", data.quality.intent_count);
  setText("queue-accuracy", `${data.quality.guard_queue_accuracy_percent.toFixed(2)}%`);
  setText("queue-gain", `+${data.quality.guard_queue_gain_pp.toFixed(2)} percentage points`);
  setText("absolute-accuracy", `${data.quality.optimized_accuracy_percent.toFixed(2)}%`);
  setText(
    "evidence-chain-counts",
    `Verify ${evidence.sustained_checksummed_files} sustained, ${evidence.performix_checksummed_files} Performix, and ${evidence.runtime_memory_checksummed_files} runtime-treatment evidence files.`,
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
  elements["review-measured-changes"].addEventListener("click", () => {
    elements["experiment-results"].hidden = false;
    elements["optimization-journey-title"].scrollIntoView({ behavior: "smooth", block: "start" });
    elements["optimization-journey-title"].setAttribute("tabindex", "-1");
    elements["optimization-journey-title"].focus({ preventScroll: true });
  });
  elements["promote-route"].addEventListener("click", openPromotionConfirmation);
  elements["confirm-promotion"].addEventListener("click", async () => {
    elements["promotion-confirmation"].close();
    await promoteOptimizedLane();
  });
  elements["rollback-route"].addEventListener("click", rollbackToStandardLane);
  elements["route-next-request"].addEventListener("click", routeNextLiveRequest);
  elements["start-next-request"].addEventListener("click", startNextRequest);
  elements["open-required-audit"].addEventListener("click", () => {
    activateView("surge", { focusHeading: true });
  });
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
    setText("demo-source", `Recorded Graviton release evidence · ${data.provenance.machine}`);
    setText("workspace-mode", "Archived Graviton response");
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
