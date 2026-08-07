import { test, expect } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";


const appUrl = `http://127.0.0.1:${process.env.SURGEDESK_TEST_PORT}/surgedesk/`;
const demoData = JSON.parse(await readFile("surgedesk/data.json", "utf8"));


function captureBrowserErrors(page) {
  const messages = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) messages.push(message.text());
  });
  page.on("pageerror", (error) => messages.push(error.message));
  return messages;
}


async function overflowingElements(page) {
  return page.evaluate(() => [...document.querySelectorAll("body *")]
    .filter((element) => {
      const rect = element.getBoundingClientRect();
      const clipped = [...function* ancestors(node) {
        for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
          yield parent;
        }
      }(element)].some((parent) => ["auto", "scroll", "hidden", "clip"].includes(getComputedStyle(parent).overflowX));
      return !clipped && rect.width > 0
        && (rect.left < -0.5 || rect.right > document.documentElement.clientWidth + 0.5);
    })
    .map((element) => {
      const rect = element.getBoundingClientRect();
      return `${element.tagName.toLowerCase()}#${element.id}.${element.className} [${rect.left}, ${rect.right}]`;
    }));
}


test("a live ticket causes the audit, traffic switch, and optimized second route", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto(appUrl);
  await expect(page.locator("#opening-capacity")).toHaveText("Awaiting validation");
  await expect(page.locator(".opening-result")).toContainText("Local release check required");
  await page.setViewportSize({ width: 1440, height: 900 });
  await mkdir("build/screenshots", { recursive: true });
  await page.screenshot({ path: "build/screenshots/surgedesk-opening.png" });
  await page.setViewportSize({ width: 320, height: 780 });

  await expect(page.getByLabel("Connected Arm64 service")).toBeChecked();
  await expect(page.locator(".developer-mode")).not.toHaveAttribute("open", "");
  await expect(page.locator("#sample-select")).toBeHidden();
  await expect(page.locator("#sample-select-label")).toBeHidden();
  await expect(page.locator("#customer-message")).toHaveAttribute(
    "placeholder",
    "Enter a support request for the local integration fixture",
  );
  expect(await page.locator("#view-workspace").innerText()).not.toMatch(/\bproduction\b/i);
  await page.locator("#customer-message").fill(
    "My card was stolen while I am travelling. Freeze it and help me replace it.",
  );
  await page.getByRole("button", { name: "Compare current route with Arm candidate" }).click();
  await expect(page.locator("#shadow-comparison")).toBeVisible();
  await expect(page.locator("#shadow-baseline-latency")).toContainText("ms");
  await expect(page.locator("#shadow-optimized-latency")).toContainText("ms");
  await expect(page.locator("#shadow-optimized-result")).toContainText("shadow only");
  await expect(page.locator("#shadow-baseline-receipt")).toContainText("shadow-baseline-");
  await expect(page.locator("#shadow-baseline-receipt")).toContainText("aarch64/16 threads · control=1");
  await expect(page.locator("#shadow-optimized-receipt")).toContainText("shadow-optimized-");
  await expect(page.locator("#shadow-optimized-receipt")).toContainText("aarch64/16 threads · control=0");
  await expect(page.locator("#shadow-observation")).toContainText("10 500-second traffic windows");
  await expect(page.locator("#shadow-observation")).not.toContainText("lower observed latency");
  await expect(page.locator("#workspace-mode")).toContainText("Local integration fixture");
  await expect(page.locator("#shadow-source-chip")).toHaveText("Local fixture · synthetic timing");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator("#shadow-comparison").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-live-shadow.png" });
  await page.setViewportSize({ width: 320, height: 780 });
  await expect(page.locator("#inference-source")).toContainText("Standard service · KleidiAI off");
  await expect(page.locator("#live-request-receipt")).toBeVisible();
  await expect(page.locator("#live-request-id")).toContainText("shadow-baseline-");
  const firstRequestId = await page.locator("#live-request-id").textContent();
  await expect(page.locator("#live-arm-runtime")).toContainText("aarch64 · 16 threads");
  await expect(page.locator("#live-control")).toHaveText("KleidiAI off · raw flag 1");
  await expect(page.locator("#live-observed-label")).toHaveText("Fixture response");
  await expect(page.locator("#live-input-digest")).toHaveText(/[0-9a-f]{16}/);
  await expect(page.locator("#live-output-digest")).toHaveText(/[0-9a-f]{16}/);
  await expect(page.locator("#review-warning")).toContainText("fixture response");
  await expect(page.locator("#review-warning")).not.toContainText("live");
  await page.locator("#final-queue").selectOption("Account security");
  await page.getByRole("button", { name: "Route ticket" }).click();
  await page.getByRole("button", { name: "Check the Arm optimization" }).click();

  await expect(page.locator("#experiment-results")).toBeHidden();
  await expect(page.locator("#optimization-summary")).toBeHidden();
  await page.getByRole("button", { name: "Recompute release decision" }).click();
  await expect(page.locator("#audit-progress li")).toHaveCount(6);
  await expect(page.locator('#audit-progress li[data-stage="quality"]')).toContainText("Quality outputs checked");
  await expect(page.locator('#audit-progress li[data-stage="performix"]')).toContainText("Arm profiler evidence parsed");
  await expect(page.locator('#audit-progress li[data-stage="requests"]')).toContainText("10 500-second traffic windows");
  await expect(page.locator('#audit-progress li[data-stage="memory"]')).toContainText("sustained treatment windows verified");
  await expect(page.locator("#audit-progress time")).toHaveCount(6);
  await expect(page.locator("#audit-receipt")).toBeVisible();
  await expect(page.locator("#experiment-results")).toBeHidden();
  await expect(page.locator("#opening-capacity")).toHaveText(
    `≥${demoData.proof.runtime_memory.candidate_rps.toFixed(2)} r/s`,
  );
  await expect(page.locator("#audit-request-result")).toContainText("2,100 capacity requests");
  await expect(page.locator("#audit-request-result")).toContainText("1,540 model outputs");
  await expect(page.locator("#release-result-title")).toContainText("At least 2.0×");
  await expect(page.locator("#result-control-outcomes")).toHaveText("0/5 long windows passed");
  await expect(page.locator("#result-treatment-outcomes")).toHaveText("5/5 long windows passed");
  await expect(page.locator("#result-quality-delta")).toContainText("86.75% queue accuracy");
  await page.getByRole("button", { name: "Review the three measured changes" }).click();
  await expect(page.locator("#experiment-results")).toBeVisible();
  await expect(page.locator("#result-quality-scope")).toContainText("Five-queue recommendation improved from 74.42% to 86.75%");
  await expect(page.locator("#result-quality-scope")).toContainText("harder 77-intent diagnostic scored 46.49%");
  await expect(page.locator("#optimization-stages > li")).toHaveCount(3);
  await expect(page.locator("#journey-final-capacity")).toHaveText(
    `≥${demoData.proof.runtime_memory.candidate_rps.toFixed(2)} requests/s`,
  );
  await expect(page.locator(".experiment-method")).not.toHaveAttribute("open", "");
  await page.setViewportSize({ width: 1440, height: 900 });
  await mkdir("build/screenshots", { recursive: true });
  await page.locator("#release-result-title").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-accepted-result.png" });
  await page.setViewportSize({ width: 320, height: 780 });
  await expect(page.locator("#trial-matrix-body tr")).toHaveCount(2);
  await expect(page.locator("#trial-matrix-body tr").nth(0).locator(".fail")).toHaveCount(5);
  await expect(page.locator("#trial-matrix-body tr").nth(1).locator(".pass")).toHaveCount(5);
  await expect(page.locator("#latency-consequence-groups article")).toHaveCount(2);
  await expect(page.locator("#latency-consequence-groups article").nth(0)).toContainText("all 5 missed target");
  await expect(page.locator("#latency-consequence-groups article").nth(1)).toContainText("all 5 within target");
  await expect(page.locator("#trial-matrix-head th")).toHaveCount(8);
  await expect(page.locator("#latency-window-label")).toHaveText("p95 from every 500-second trial");
  await expect(page.locator("#summary-capacity-context")).toHaveText(
    "Same c8g.4xlarge server and 10-second p95 SLO",
  );
  await expect(page.locator("#headline-ratio")).toHaveText("≥2.00×");
  await expect(page.locator("#rate-confirmation-id")).toHaveText("Preregistered confirmation run");
  await expect(page.locator("#rate-confirmation-id")).toHaveAttribute("href", /\/commit\//);

  await page.locator("#experiment-results").getByRole(
    "button", { name: "Continue to traffic decision" },
  ).click();
  await expect(page.locator("#optimization-summary")).toBeVisible();
  await expect(page.locator("#performix-proof")).toBeVisible();
  await expect(page.locator("#memory-proof")).toBeVisible();
  await expect(page.locator("#summary-footprint")).toContainText("smaller");
  await expect(page.locator("#summary-final-capacity")).toHaveText(
    `≥${demoData.proof.runtime_memory.candidate_rps.toFixed(2)} r/s`,
  );
  await expect(page.locator("#memory-release-conditions li")).toHaveCount(5);
  await expect(page.locator("#memory-release-conditions")).toContainText("simplification was rejected");
  await expect(page.locator("#performix-disabled-count")).toContainText("0 / 944,847");
  await expect(page.locator("#performix-sample-count")).toContainText("245,876 / 365,062");
  await page.getByRole("button", { name: "Select optimized fixture route" }).click();
  await expect(page.locator("#promotion-confirmation")).toBeVisible();
  await expect(page.locator("#promotion-confirm-environment")).toContainText("synthetic timing");
  await expect(page.locator("#promotion-confirm-audit")).toContainText("Fresh release receipt");
  await page.getByRole("button", { name: "Confirm gateway switch" }).click();
  await expect(page.locator("#promotion-result")).toContainText("selected the optimized fixture route");
  await expect(page.locator("#environment-label")).toContainText("Local integration fixture");
  await expect(page.locator("#environment-label")).toContainText("optimized route selected");
  await expect(page.locator("#environment-label")).toContainText("synthetic timing");
  await expect(page.locator("#promotion-identity")).toBeVisible();
  await expect(page.locator("#promotion-control-match")).toContainText("1 → 0");
  await expect(page.locator("#promotion-candidate-label")).toHaveText("Previous route");
  await expect(page.locator("#opening-status")).toContainText("Release receipt passed · fixture route selected");
  await expect(page.locator("#workspace-candidate-label")).toHaveText("Arm optimization status");
  await expect(page.locator("#workspace-candidate")).toHaveText("Released · selected in fixture");
  await expect(page.locator("#route-next-request")).toBeVisible();
  await expect(page.locator("#rollback-route")).toBeVisible();
  expect(await page.locator(".deployment-promotion").innerText()).not.toMatch(/\blive\b|production|serving traffic/i);
  expect(await overflowingElements(page)).toEqual([]);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mkdir("build/screenshots", { recursive: true });
  await page.locator(".deployment-promotion").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-release-proof.png" });
  await page.setViewportSize({ width: 320, height: 780 });
  await page.getByRole("button", { name: "Send a request through the optimized service" }).click();
  await expect(page.locator("#review-complete")).toBeHidden();
  await page.locator("#customer-message").fill(
    "My card is about to expire. How do I get a replacement?",
  );
  await page.getByRole("button", { name: "Run optimized fixture route" }).click();
  await expect(page.locator("#inference-source")).toContainText("Optimized service · I8MM + tuned runtime");
  await expect(page.locator("#live-control")).toHaveText("KleidiAI on · raw flag 0");
  const secondRequestId = await page.locator("#live-request-id").textContent();
  expect(secondRequestId).not.toBe(firstRequestId);
  await expect(page.locator("#suggested-intent")).toContainText("Card About To Expire");
  await page.locator("#final-queue").selectOption("Cards & payments");
  await page.getByRole("button", { name: "Route ticket" }).click();
  await expect(page.locator("#reviewed-tickets")).toContainText("Standard service");
  await expect(page.locator("#reviewed-tickets")).toContainText("Optimized service");
  await expect(page.locator("#reviewed-tickets")).toContainText("My card is about to expire");
  await expect(page.locator("#reviewed-tickets")).toContainText("fixture");
  await expect(page.locator("#reviewed-tickets")).toContainText(firstRequestId);
  await expect(page.locator("#reviewed-tickets")).toContainText(secondRequestId);
  await expect(page.locator("#reviewed-tickets")).toContainText("mlas.disable_kleidiai=1");
  await expect(page.locator("#reviewed-tickets")).toContainText("mlas.disable_kleidiai=0");
  await expect(page.locator("#reviewed-tickets")).toContainText(demoData.provenance.experiment_id);
  await expect(page.locator("#reviewed-tickets .ticket-receipt")).toHaveCount(2);
  for (const receipt of await page.locator("#reviewed-tickets .ticket-receipt").all()) {
    await expect(receipt).toContainText("aarch64/16 threads");
    await expect(receipt).toContainText(/\d{2}:\d{2}:\d{2}/);
  }
  await expect(page.locator("#live-cutover-summary")).toBeVisible();
  await expect(page.locator("#intake-form")).toBeHidden();
  await expect(page.locator("#start-next-request")).toBeVisible();
  await expect(page.locator("#live-cutover-title")).toHaveText("The integration gateway selected the optimized Arm route");
  await expect(page.locator("#cutover-source-chip")).toContainText("Local integration fixture");
  await expect(page.locator("#cutover-before-lane")).toContainText("KleidiAI off");
  await expect(page.locator("#cutover-after-lane")).toContainText("I8MM + tuned runtime");
  await expect(page.locator("#cutover-before-request")).toContainText("Account security");
  await expect(page.locator("#cutover-before-request")).toContainText("compare-");
  await expect(page.locator("#cutover-after-request")).toContainText("Cards & payments");
  await expect(page.locator("#cutover-audit")).toContainText("receipt verified");
  await expect(page.locator("#cutover-capacity")).toContainText(
    `≥${demoData.proof.runtime_memory.candidate_rps.toFixed(2)} requests/s`,
  );
  await expect(page.locator("#cutover-comparison-binding")).toContainText("compare-");
  await expect(page.locator("#cutover-before-binding")).toContainText(firstRequestId);
  await expect(page.locator("#cutover-after-binding")).toContainText(secondRequestId);
  await expect(page.locator("#cutover-receipt-sha")).toHaveText(/^[0-9a-f]{64}$/);
  await expect(page.locator("#cutover-audit-binding")).toHaveText(/^[0-9a-f]{64}$/);
  await expect(page.locator("#cutover-evidence-digests li")).toHaveCount(
    demoData.provenance.release_evidence_ids.length,
  );
  for (const experimentId of demoData.provenance.release_evidence_ids) {
    await expect(page.locator("#cutover-evidence-digests")).toContainText(experimentId);
  }
  for (const digest of await page.locator("#cutover-evidence-digests code").all()) {
    await expect(digest).toHaveText(/^[0-9a-f]{64}$/);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator("#live-cutover-summary").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-live-cutover.png" });
  expect(await overflowingElements(page)).toEqual([]);

  await page.setViewportSize({ width: 1440, height: 1000 });
  await mkdir("build/screenshots", { recursive: true });
  await page.screenshot({ path: "build/screenshots/surgedesk-live-flow.png", fullPage: true });
  expect(messages).toEqual([]);

  await page.getByRole("tab", { name: "Traffic switch" }).click();
  await page.getByRole("button", { name: "Return to standard service" }).click();
  await expect(page.locator("#promotion-result")).toContainText("returned to the standard service");
  await expect(page.locator("#promotion-current-lane")).toContainText("kleidiai-disabled");
  await expect(page.locator("#promote-route")).toBeDisabled();
  await expect(page.locator("#promotion-audit-status")).toContainText("Evidence validation required");
});


test("a rejected optimized response refreshes the UI to the standard route", async ({ page }) => {
  const api = appUrl.replace(/surgedesk\/$/, "");
  const workflowId = "workflow-playwright-drift";
  const headers = { "Content-Type": "application/json" };
  const comparison = await page.request.post(`${api}api/shadow-compare`, {
    headers,
    data: { text: "My card was stolen.", workflow_id: workflowId },
  });
  expect(comparison.ok()).toBeTruthy();
  const audit = await page.request.post(`${api}api/audit`, {
    headers,
    data: { workflow_id: workflowId },
  });
  expect(audit.ok()).toBeTruthy();
  const promote = await page.request.post(`${api}api/promote`, {
    headers,
    data: { workflow_id: workflowId },
  });
  expect(promote.ok()).toBeTruthy();

  let driftObserved = false;
  await page.route("**/api/route", async (route) => {
    driftObserved = true;
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ error: "route_runtime_identity_changed" }),
    });
  });
  await page.route("**/surgedesk/live-status.json", async (route) => {
    if (!driftObserved) {
      await route.continue();
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        audit_available: true,
        live_available: true,
        matched_lanes_available: true,
        mode: "live",
        deployment: {
          active_lane: "baseline",
          release_ready: false,
          audit_experiment_id: null,
          promoted_at: null,
        },
        lanes: {
          baseline: { backend: "kleidiai-disabled", core_group: "0-15" },
          optimized: { backend: "kleidiai-enabled", core_group: "0-15" },
        },
      }),
    });
  });

  await page.goto(appUrl);
  await expect(page.locator("#proof-decision-status")).toHaveText("ACTIVE RELEASE");
  await page.locator("#customer-message").fill("My card was stolen.");
  await page.getByRole("button", { name: "Run optimized fixture route" }).click();
  await expect(page.locator("#intake-error")).toContainText("route_runtime_identity_changed");
  await expect(page.locator("#workspace-serving")).toContainText("Standard service");
  await expect(page.locator("#workspace-release-status")).toContainText("Waiting for the measured release check");
  await expect(page.locator("#proof-decision-status")).toHaveText("AWAITING CHECK");
});


test("public mode reveals checked-in proof only after the visitor requests it", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.route("**/surgedesk/live-status.json", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      audit_available: false,
      live_available: false,
      matched_lanes_available: false,
      mode: "recorded",
      deployment: {},
      lanes: {},
    }),
  }));
  await page.goto(`${appUrl}#surge`);
  await expect(page.locator("#experiment-results")).toBeHidden();
  await page.getByRole("button", { name: "Open checked-in evidence" }).click();
  await expect(page.locator("#audit-receipt")).toBeVisible();
  await page.getByRole("button", { name: "Review the three measured changes" }).click();
  await expect(page.locator("#trial-matrix-body tr")).toHaveCount(2);
  await expect(page.locator("#headline-ratio")).toHaveText("≥2.00×");
  await page.getByRole("tab", { name: "Release status" }).click();
  await expect(page.locator("#optimization-summary")).toBeVisible();
  await expect(page.locator("#promotion-title")).toContainText("cleared the checked-in release policy");
  await expect(page.locator("#promote-route")).toBeHidden();
  await expect(page.locator("#open-required-audit")).toHaveText("Inspect release evidence");
  await expect(page.locator("#proof-claims tr")).toHaveCount(10);
  await expect(page.locator("body")).not.toContainText(/tamper|altered archive/i);
  await page.locator("#proof-details > summary").click();
  await expect(page.getByRole("link", { name: "Use ArmProof with another bounded HTTP inference service" })).toBeVisible();
  await mkdir("build/screenshots", { recursive: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "build/screenshots/surgedesk-public-release-proof.png" });
  await page.getByRole("tab", { name: "Release evidence" }).click();
  await page.locator("#latency-consequence-title").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-capacity.png" });
  expect(messages).toEqual([]);
});


test("recorded support examples remain human-confirmed and clearly labeled", async ({ page }) => {
  await page.route("**/surgedesk/live-status.json", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      audit_available: false,
      live_available: false,
      matched_lanes_available: false,
      mode: "recorded",
      deployment: {},
      lanes: {},
    }),
  }));
  await page.goto(appUrl);
  await expect(page.getByRole("heading", { name: "Route an incoming request" })).toBeVisible();
  await expect(page.locator(".routing-quality-details")).not.toHaveAttribute("open", "");
  await page.getByRole("button", { name: "Missing card" }).click();
  await page.getByRole("button", { name: "Review recorded request" }).click();
  await expect(page.locator("#review-warning")).toContainText("routing guard changed");
  await expect(page.locator("#inference-source")).toContainText("Recorded");
  await mkdir("build/screenshots", { recursive: true });
  await page.locator("#review-panel").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-triage-guard.png" });
  await page.getByRole("button", { name: "Route ticket" }).click();
  await expect(page.locator("#reviewed-tickets")).toContainText("Confirmed");
});


test("mobile public evidence remains readable without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 });
  await page.route("**/surgedesk/live-status.json", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ audit_available: false, live_available: false }),
  }));
  await page.goto(`${appUrl}#surge`);
  await page.getByRole("button", { name: "Open checked-in evidence" }).click();
  await expect(page.locator("#audit-receipt")).toBeVisible();
  await page.getByRole("button", { name: "Review the three measured changes" }).click();
  await expect(page.locator("#trial-matrix-body tr")).toHaveCount(2);
  expect(await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  )).toBe(true);
  const mobileControls = await page.locator("button:visible").evaluateAll(
    (buttons) => buttons.map((button) => button.getBoundingClientRect().height),
  );
  expect(Math.min(...mobileControls)).toBeGreaterThanOrEqual(44);
  await page.locator(".experiment-method").getByText("Inspect rate selection").click();
  const firstTrial = page.locator("#trial-matrix-body tr").first();
  await expect(firstTrial.locator("td").first()).toBeVisible();
  expect(await firstTrial.evaluate(
    (row) => getComputedStyle(row).display,
  )).toBe("grid");
  await page.getByRole("tab", { name: "Release status" }).click();
  await expect(page.locator("#optimization-summary")).toBeVisible();
  await expect(page.locator("#proof-claims tr")).toHaveCount(10);
  expect(await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  )).toBe(true);
  await page.getByRole("tab", { name: "Support" }).click();
  await page.locator(".app-header").scrollIntoViewIfNeeded();
  await mkdir("build/screenshots", { recursive: true });
  await page.screenshot({ path: "build/screenshots/surgedesk-mobile.png" });
});
