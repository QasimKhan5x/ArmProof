import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  createWorkspace,
  findRecordedCase,
  resolveTicket,
  selectRecordedCase,
} from "../../surgedesk/model.mjs";


const data = JSON.parse(
  await readFile(new URL("../../surgedesk/data.json", import.meta.url), "utf8"),
);


test("selecting a recorded request opens a pending human review", () => {
  const workspace = createWorkspace(data);
  const selected = selectRecordedCase(workspace, data.routing_cases[0]);

  assert.equal(selected.active.request_id, "banking77-quality-0110");
  assert.equal(selected.active.review_status, "pending");
  assert.equal(selected.active.mode, "recorded_model_output");
  assert.equal(selected.resolved.length, 0);
});

test("confirming a suggestion routes the ticket and records human approval", () => {
  const selected = selectRecordedCase(createWorkspace(data), data.routing_cases[0]);
  const resolved = resolveTicket(selected, "confirm");

  assert.equal(resolved.active, null);
  assert.equal(resolved.resolved[0].review_status, "confirmed");
  assert.equal(resolved.resolved[0].final_queue, "Account security");
  assert.match(resolved.resolved[0].procedure, /freeze the card/i);
  assert.equal(resolved.queue_counts["Account security"], 1);
});


test("correcting a known misroute uses the expected human queue", () => {
  const reviewCase = data.routing_cases.find((item) => !item.correct);
  const selected = selectRecordedCase(createWorkspace(data), reviewCase);
  const resolved = resolveTicket(selected, "correct");

  assert.equal(resolved.resolved[0].review_status, "corrected");
  assert.equal(resolved.resolved[0].final_queue, reviewCase.expected_queue);
  assert.equal(resolved.resolved[0].final_intent, reviewCase.expected_intent);
});


test("free-form text is not passed off as recorded model inference", () => {
  assert.equal(findRecordedCase(data.routing_cases, "A completely new request"), null);
  assert.equal(
    findRecordedCase(data.routing_cases, data.routing_cases[1].source_text)?.request_id,
    data.routing_cases[1].request_id,
  );
});
