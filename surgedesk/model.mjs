const QUEUES = [
  "Account security",
  "Cash & ATM",
  "Cards & payments",
  "Transfers",
  "Account support",
  "Manual review",
];


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
  if (!recordedCase || recordedCase.mode !== "recorded_model_output") {
    throw new Error("SurgeDesk accepts only evidence-backed recorded cases");
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


function percentile95(values) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.ceil(sorted.length * 0.95) - 1];
}


function snapshotRun(run, progress) {
  const boundedProgress = Math.max(0, Math.min(1, progress));
  const completed = Math.floor(run.events.length * boundedProgress);
  const visibleEvents = run.events.slice(0, completed);
  const p95 = boundedProgress === 1
    ? run.p95_ms
    : percentile95(visibleEvents.map((event) => event.latency_ms));
  const breaches = visibleEvents.filter((event) => !event.within_slo).length;
  let sloStatus = "running";
  if (boundedProgress === 0) sloStatus = "waiting";
  if (boundedProgress === 1) sloStatus = run.passed ? "passed" : "failed";
  return {
    completed,
    total: run.events.length,
    p95_ms: p95,
    max_queue_ms: visibleEvents.length
      ? Math.max(...visibleEvents.map((event) => event.queue_ms))
      : 0,
    breaches,
    offered_rps: run.offered_rps,
    slo_status: sloStatus,
    events: visibleEvents,
  };
}


export function buildReplaySnapshot(replay, progress) {
  return {
    baseline: snapshotRun(replay.baseline, progress),
    optimized: snapshotRun(replay.optimized, progress),
    progress: Math.max(0, Math.min(1, progress)),
  };
}
