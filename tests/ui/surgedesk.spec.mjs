import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";


const appUrl = "http://127.0.0.1:8765/surgedesk/";


function captureBrowserErrors(page) {
  const messages = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) messages.push(message.text());
  });
  page.on("pageerror", (error) => messages.push(error.message));
  return messages;
}


test("operator confirms and corrects recorded support routes", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto(appUrl);

  await expect(page.getByRole("heading", { name: "Route an incoming request" })).toBeVisible();
  await expect(page.locator("#demo-source")).toContainText("EXP-2026-009");
  await expect(page.locator("#guard-accuracy")).toHaveText("86.75%");
  await expect(page.locator("#guard-gain")).toHaveText("+12.34 pp");
  await expect(page.locator("#schema-valid")).toHaveText("100%");
  await expect(page.locator("#customer-message")).toHaveValue(/gym bag/);

  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#suggested-intent")).toHaveText("Lost Or Stolen Card");
  await expect(page.locator("#suggested-queue")).toHaveText("Account security");
  await page.getByRole("button", { name: "Confirm route" }).click();
  await expect(page.locator("#reviewed-tickets tr")).toHaveCount(1);
  await expect(page.locator("#reviewed-tickets")).toContainText("Confirmed");
  await expect(page.locator("#review-complete")).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue to Arm result" })).toBeFocused();

  await page.locator("#sample-select").selectOption("banking77-quality-0007");
  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#review-warning")).toContainText("changed the LLM route");
  await expect(page.locator("#llm-queue")).toHaveText("Account security");
  await expect(page.locator("#suggested-queue")).toHaveText("Cards & payments");
  await mkdir("build/screenshots", { recursive: true });
  await page.screenshot({
    path: "build/screenshots/surgedesk-triage.png",
    fullPage: true,
    style: ".skip-link { display: none !important; }",
  });
  await page.getByRole("button", { name: "Confirm route" }).click();

  await page.locator("#sample-select").selectOption("banking77-quality-0044");
  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#review-warning")).toContainText("differs from the benchmark queue");
  await page.getByRole("button", { name: "Apply benchmark correction" }).click();
  await expect(page.locator("#reviewed-tickets tr")).toHaveCount(3);
  await expect(page.locator("#reviewed-tickets")).toContainText("Corrected");

  await page.locator("#customer-message").fill("A new message without recorded evidence");
  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#intake-error")).toBeVisible();
  await expect(page.locator("#intake-error")).toContainText("No recorded Phi-4 Mini result");
  expect(messages).toEqual([]);
});


test("guided scenarios and URL-addressable keyboard tabs support a clean demo", async ({ page }) => {
  await page.goto(appUrl);

  await page.getByRole("button", { name: "Guard intervention" }).click();
  await expect(page.locator("#sample-select")).toHaveValue("banking77-quality-0007");
  await expect(page.locator("#customer-message")).toHaveValue("i have not received my card");
  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#review-warning")).toContainText("changed the LLM route");

  await page.getByRole("tab", { name: "1. Triage" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page).toHaveURL(/#surge$/);
  await expect(page.getByRole("tab", { name: "2. Arm result" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`${appUrl}#proof`);
  await expect(page.getByRole("heading", { name: "Approved at the conservative Graviton boundary" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "3. Release proof" })).toHaveAttribute("aria-selected", "true");
});


test("configured gateway enables a live Graviton route", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.route("**/surgedesk/live-status.json", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ live_available: true, mode: "live" }),
  }));
  await page.route("**/api/route", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      request_id: "live-1",
      source_text: "My card was stolen",
      suggested_intent: "lost_or_stolen_card",
      suggested_label: "Lost Or Stolen Card",
      llm_queue: "Account security",
      guard_queue: "Account security",
      queue: "Account security",
      guard_overrode: false,
      guard_margin: 9.2,
      priority: "Urgent",
      suggested_procedure: "Verify the customer and freeze the card.",
      expected_procedure: null,
      queue_correct: null,
      correct: null,
      mode: "live_model_output",
      backend: "kleidiai-enabled",
      inference_ms: 418.2,
    }),
  }));
  await page.goto(appUrl);
  await expect(page.locator("#live-mode")).toBeEnabled();
  await page.getByLabel("Live Graviton endpoint").check();
  await page.locator("#customer-message").fill("My card was stolen");
  await page.getByRole("button", { name: "Run live route" }).click();
  await expect(page.locator("#suggested-queue")).toHaveText("Account security");
  await expect(page.locator("#inference-source")).toContainText("kleidiai-enabled");
  await expect(page.locator("#review-warning")).toContainText("live two-stage suggestion");
  expect(messages).toEqual([]);
});


test("verified evidence load reveals the fixed-SLO Arm result", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(appUrl);
  await page.getByRole("tab", { name: "2. Arm result" }).click();

  await expect(page.locator("#evidence-experiment-id")).toHaveText("EXP-2026-009");
  await expect(page.locator("#evidence-checksum-status")).toContainText("69 sustained + 282 supporting");
  await expect(page.locator("#evidence-comparison")).toContainText(
    "Contract-matched INT4 treatments",
  );
  await expect(page.locator("#experiment-results")).toBeHidden();

  await page.getByRole("button", { name: "Load verified experiment" }).click();
  await expect(page.getByRole("button", { name: "Verified experiment loaded" })).toBeDisabled();
  await expect(page.locator("#experiment-results")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Same instance. At least 2.0× sustainable capacity." })).toBeVisible();
  await expect(page.locator("#original-gate-status")).toHaveText("BLOCKED");
  await expect(page.locator("#corrected-claim-status")).toHaveText("PROVEN");
  await expect(page.locator("#original-gate-label")).toContainText("2.50×");
  await expect(page.locator("#original-gate-formula")).toHaveText("0.60 r/s ÷ 0.24 r/s = 2.50×");
  await expect(page.locator("#corrected-claim-formula")).toHaveText("0.56 r/s ÷ 0.28 r/s = 2.00×");
  await expect(page.locator("#baseline-status")).toHaveText("failed");
  await expect(page.locator("#optimized-status")).toHaveText("passed");
  await expect(page.locator("#baseline-completed")).toHaveText("8 / 8");
  await expect(page.locator("#optimized-completed")).toHaveText("8 / 8");
  await expect(page.locator("#baseline-rps")).toHaveText("0.267 r/s");
  await expect(page.locator("#optimized-rps")).toHaveText("0.267 r/s");
  await expect(page.locator("#equal-load-source")).toHaveText("EXP-2026-004");
  await expect(page.locator("#baseline-request-strip .late")).toHaveCount(3);
  await expect(page.locator("#baseline-request-strip .request-tile")).toHaveCount(8);
  await expect(page.locator("#optimized-request-strip .request-tile")).toHaveCount(8);
  await expect(page.locator("#optimized-request-strip .late")).toHaveCount(0);
  await expect(page.locator("#baseline-p95")).toHaveText(/s$/);
  await expect(page.locator("#replay-conclusion")).toContainText("at least 2.0×");
  await expect(page.locator("#mix-table tr")).toHaveCount(1);
  await expect(page.locator("#mix-table")).toContainText("3.28–3.31 s p95");
  expect(messages).toEqual([]);
  await page.screenshot({ path: "build/screenshots/surgedesk-surge.png", fullPage: true });
});

test("proof view exposes the authoritative evidence chain", async ({ page }) => {
  await page.goto(`${appUrl}#proof`);
  await expect(page.getByRole("heading", { name: "The dashboard cannot approve itself" })).toBeVisible();
  await expect(page.locator("#proof-evidence-count")).toHaveText("69 sustained + 317 release files");
  await expect(page.locator("#proof-decision-detail")).toContainText("9 required claims");
  await expect(page.locator("#proof-claims")).toContainText("68.53%");
  await expect(page.getByRole("heading", { name: "Arm Performix measured the optimized path executing" })).toBeVisible();
  await expect(page.locator("#performix-disabled-share")).toHaveText("0%");
  await expect(page.locator("#performix-enabled-share")).toHaveText("67.02%");
  await expect(page.locator("#performix-agreement")).toHaveText("1.51 pp apart");
  await expect(page.locator("#performix-kernel")).toContainText("neon_i8mm");
  await expect(page.locator(".evidence-chain li")).toHaveCount(4);
  await expect(page.getByRole("heading", { name: "Scaffold another Arm AI service" })).toBeVisible();
  await expect(page.locator(".reuse-steps")).toContainText("armproof init");
});


test("proof view exposes both the Arm result and quality boundary", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 1280, height: 960 });
  await page.goto(appUrl);
  await page.getByRole("tab", { name: "3. Release proof" }).click();

  await expect(page.getByRole("heading", { name: "Approved at the conservative Graviton boundary" })).toBeVisible();
  await expect(page.locator(".claims-table tbody tr")).toHaveCount(9);
  await expect(page.locator("#proof-claims")).toContainText("Sustained capacity lower bound");
  await expect(page.locator("#proof-claims")).toContainText("Profiler sample integrity");
  await expect(page.locator("#absolute-accuracy")).toHaveText("46.49%");
  await expect(page.getByRole("heading", { name: "86.75% held-out queue accuracy" })).toBeVisible();
  await expect(page.locator(".stack-path li")).toHaveCount(5);
  expect(messages).toEqual([]);
  await page.screenshot({ path: "build/screenshots/surgedesk-proof.png", fullPage: true });
});


test("mobile workflow has no page overflow", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto(appUrl);
  await expect(page.getByRole("heading", { name: "Route an incoming request" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole("tab", { name: "2. Arm result" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole("tab", { name: "3. Release proof" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await expect(page.locator(".claims-table thead")).toBeHidden();
  await expect(page.locator(".claims-table tbody tr").first()).toHaveCSS("display", "grid");
  expect(messages).toEqual([]);
  await page.screenshot({ path: "build/screenshots/surgedesk-mobile.png", fullPage: true });
});
