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
