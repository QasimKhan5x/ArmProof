const QUEUES = [
  "Account security",
  "Cash & ATM",
  "Cards & payments",
  "Transfers",
  "Account support",
  "Manual review",
];


export function describeCapacity(capacity) {
  const trialMatrix = capacity.trial_matrix ?? [];
  const observedCounts = trialMatrix.map((trial) => trial.outcomes?.length ?? 0);
  if (trialMatrix.length === 0 || observedCounts.some((count) => count === 0)) {
    throw new Error("Capacity receipt is missing confirmation outcomes");
  }
  const windowsPerRate = capacity.confirmations ?? observedCounts[0] ?? 0;
  if (observedCounts.some((count) => count !== windowsPerRate)) {
    throw new Error("Capacity receipt has inconsistent confirmation counts");
  }
  const sloSeconds = Number(capacity.slo_ms) / 1000;
  if (!Number.isFinite(sloSeconds) || sloSeconds <= 0) {
    throw new Error("Capacity receipt is missing a valid p95 SLO");
  }
  const windowSeconds = Number(capacity.confirmation_seconds);
  if (!Number.isFinite(windowSeconds) || windowSeconds <= 0) {
    throw new Error("Capacity receipt is missing a valid confirmation duration");
  }
  return {
    rate_count: trialMatrix.length,
    windows_per_rate: windowsPerRate,
    total_windows: observedCounts.reduce((total, count) => total + count, 0),
    window_seconds: windowSeconds,
    slo_seconds: sloSeconds,
    outcomeSummary(outcomes) {
      const passed = outcomes.filter((outcome) => outcome === "pass").length;
      if (passed === outcomes.length) return `all ${outcomes.length} within target`;
      if (passed === 0) return `all ${outcomes.length} missed target`;
      return `${passed}/${outcomes.length} within target`;
    },
  };
}


export function createWorkspace(data) {
  return {
    active: null,
    resolved: [],
    queue_counts: Object.fromEntries(QUEUES.map((queue) => [queue, 0])),
    available_cases: data.routing_cases.map((item) => item.request_id),
  };
}

export function findRecordedCase(cases, text) {
  const normalized = text.trim();
  return cases.find((item) => item.source_text === normalized) ?? null;
}


export function selectRecordedCase(workspace, recordedCase) {
  if (!recordedCase || !new Set(["recorded_model_output", "live_model_output"]).has(recordedCase.mode)) {
    throw new Error("SurgeDesk accepts only recorded or live model outputs");
  }
  return {
    ...workspace,
    active: { ...recordedCase, review_status: "pending" },
  };
}


export function resolveTicket(workspace, decision) {
  if (!workspace.active) {
    throw new Error("No ticket is awaiting review");
  }
  if (!new Set(["confirm", "correct"]).has(decision)) {
    throw new Error(`Unknown review decision: ${decision}`);
  }
  const corrected = decision === "correct";
  const ticket = {
    ...workspace.active,
    review_status: corrected ? "corrected" : "confirmed",
    final_queue: corrected ? workspace.active.expected_queue : workspace.active.queue,
    final_intent: corrected
      ? workspace.active.expected_intent
      : workspace.active.suggested_intent,
    procedure: corrected
      ? workspace.active.expected_procedure
      : workspace.active.suggested_procedure,
  };
  const queueCounts = { ...workspace.queue_counts };
  queueCounts[ticket.final_queue] = (queueCounts[ticket.final_queue] ?? 0) + 1;
  return {
    ...workspace,
    active: null,
    resolved: [ticket, ...workspace.resolved],
    queue_counts: queueCounts,
  };
}


export function resolveTicketToQueue(workspace, finalQueue) {
  if (!workspace.active) {
    throw new Error("No ticket is awaiting review");
  }
  if (!Object.hasOwn(workspace.queue_counts, finalQueue)) {
    throw new Error(`Unknown support queue: ${finalQueue}`);
  }
  const corrected = finalQueue !== workspace.active.queue;
  const usesBenchmarkCorrection = corrected && finalQueue === workspace.active.expected_queue;
  const ticket = {
    ...workspace.active,
    review_status: corrected ? "corrected" : "confirmed",
    final_queue: finalQueue,
    final_intent: usesBenchmarkCorrection
      ? workspace.active.expected_intent
      : corrected
      ? null
      : workspace.active.suggested_intent,
    procedure: usesBenchmarkCorrection
      ? workspace.active.expected_procedure
      : corrected
      ? "No procedure assigned. The selected queue must review the request before any customer action."
      : workspace.active.suggested_procedure,
  };
  const queueCounts = { ...workspace.queue_counts };
  queueCounts[finalQueue] += 1;
  return {
    ...workspace,
    active: null,
    resolved: [ticket, ...workspace.resolved],
    queue_counts: queueCounts,
  };
}
