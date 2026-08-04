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


async function mockMatchedSurge(page) {
  await page.route("**/surgedesk/live-status.json", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      live_available: true,
      matched_surge_available: true,
      audit_available: true,
      mode: "live",
      matched_status: "matched",
      matched_identity: {
        model_identity: "a".repeat(64),
        runtime: "onnxruntime-genai",
        runtime_version: "0.15.0.dev0",
        threads_per_lane: 8,
        architecture: "aarch64",
        changed_control: "mlas.disable_kleidiai",
        baseline_control: "1",
        optimized_control: "0",
      },
      lanes: {
        baseline: { backend: "kleidiai-disabled", core_group: "0-7" },
        optimized: { backend: "kleidiai-enabled", core_group: "8-15" },
      },
    }),
  }));
  await page.route("**/api/surge/**", async (route) => {
    const lane = route.request().url().endsWith("baseline") ? "baseline" : "optimized";
    const request = route.request().postDataJSON();
    await new Promise((resolve) => setTimeout(resolve, lane === "baseline" ? 320 : 120));
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        lane,
        sequence: request.sequence,
        request_id: `surge-${request.run_id}-${request.sequence}`,
        backend: lane === "baseline" ? "kleidiai-disabled" : "kleidiai-enabled",
        core_group: lane === "baseline" ? "0-7" : "8-15",
        gateway_started_at: "2026-08-04T12:00:00.000Z",
        gateway_latency_ms: lane === "baseline" ? 320 + request.sequence : 120 + request.sequence,
        suggested_label: "Lost Or Stolen Card",
      }),
    });
  });
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
  await expect(page.getByRole("button", { name: "Open platform capacity audit" })).toBeFocused();

  await page.locator("#sample-select").selectOption("banking77-quality-0007");
  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#review-warning")).toContainText("changed the LLM route");
  await expect(page.locator("#llm-queue")).toHaveText("Account security");
  await expect(page.locator("#suggested-queue")).toHaveText("Cards & payments");
  await mkdir("build/screenshots", { recursive: true });
  await page.evaluate(() => document.activeElement?.blur());
  await page.locator(".skip-link").evaluate((element) => {
    element.hidden = true;
  });
  await page.screenshot({
    path: "build/screenshots/surgedesk-triage.png",
    fullPage: true,
  });
  await page.locator(".skip-link").evaluate((element) => {
    element.hidden = false;
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

  await page.getByRole("tab", { name: "1. Support workflow" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page).toHaveURL(/#surge$/);
  await expect(page.getByRole("tab", { name: "2. Capacity audit" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`${appUrl}#proof`);
  await expect(page.getByRole("heading", { name: "Checked-in conservative release receipt" })).toBeVisible();
  await expect(page.locator("#proof-decision-status")).toHaveText("RECORDED PASS");
  await expect(page.getByRole("tab", { name: "3. Release gate" })).toHaveAttribute("aria-selected", "true");
});


test("configured gateway enables a live matched Arm64 route", async ({ page }) => {
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
  await page.getByLabel("Live matched Arm64 endpoint").check();
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
  await mockMatchedSurge(page);
  await page.goto(appUrl);
  await page.getByRole("tab", { name: "2. Capacity audit" }).click();

  await expect(page.locator("#evidence-experiment-id")).toHaveText("EXP-2026-009");
  await expect(page.locator("#evidence-checksum-status")).toContainText("69 checksummed files · 4,200 outcomes");
  await expect(page.locator("#evidence-comparison")).toContainText("one runtime flag differs");
  await expect(page.locator("#experiment-results")).toBeHidden();

  await page.locator("#surge-message").fill("Please freeze my stolen card immediately");
  await page.getByRole("button", { name: "Run matched request check" }).click();
  await expect(page.locator("#baseline-live-slots .complete")).toHaveCount(3);
  await expect(page.locator("#optimized-live-slots .complete")).toHaveCount(3);

  await page.getByRole("button", { name: "Verify measured experiment" }).click();
  await expect(page.getByRole("button", { name: "Measured experiment verified" })).toBeDisabled();
  await expect(page.locator("#experiment-results")).toBeVisible();
  await expect(page.locator("#audit-request-result")).toHaveText("4,200 outcomes across 20 files");
  await expect(page.locator("#audit-claim-result")).toHaveText("9/9 required claims passed");
  await expect(page.locator("#trial-matrix-body tr")).toHaveCount(4);
  await expect(page.locator("#trial-matrix-body tr").nth(0).locator(".pass")).toHaveCount(5);
  await expect(page.locator("#trial-matrix-body tr").nth(1).locator(".fail")).toHaveCount(5);
  await expect(page.locator("#trial-matrix-body tr").nth(2).locator(".pass")).toHaveCount(5);
  await expect(page.locator("#trial-matrix-body tr").nth(3).locator(".pass")).toHaveCount(1);
  await expect(page.locator("#original-gate-status")).toHaveText("REJECTED");
  await expect(page.locator("#original-gate-explanation")).toContainText("required all 5 optimized windows at 0.60 r/s to fail");
  await expect(page.locator("#original-gate-explanation")).toContainText("1 passed");
  await expect(page.locator("#original-gate-explanation")).toContainText("separate, narrower lower-bound claim");
  await expect(page.locator("#equation-treatment")).toHaveText("0.56 r/s optimized pass");
  await expect(page.locator("#equation-baseline")).toHaveText("0.28 r/s baseline fail");
  await expect(page.locator("#headline-ratio")).toHaveText("≥2.00×");
  await expect(page.locator("#reveal-enabled-sample-share")).toHaveText("67.02%");
  await expect(page.locator("#reveal-cycle-share")).toHaveText("68.53%");
  await page.getByRole("tab", { name: "3. Release gate" }).click();
  await expect(page.getByRole("heading", { name: "Fresh audit approved the conservative Graviton boundary" })).toBeVisible();
  await expect(page.locator("#proof-decision-status")).toHaveText("VERIFIED NOW");
  await page.screenshot({ path: "build/screenshots/surgedesk-proof.png", fullPage: true });
  await page.getByRole("tab", { name: "2. Capacity audit" }).click();
  expect(messages).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({
    path: "build/screenshots/surgedesk-surge.png",
    fullPage: true,
  });
  await page.locator("#experiment-results").screenshot({
    path: "build/screenshots/surgedesk-capacity-proof.png",
  });
});


test("static Pages fallback opens the same derived audit without a gateway", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.route("**/surgedesk/live-status.json", async (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      audit_available: false,
      live_available: false,
      matched_surge_available: false,
      mode: "recorded",
    }),
  }));
  await page.goto(`${appUrl}#surge`);
  await page.getByRole("button", { name: "Open checked-in evidence" }).click();
  await expect(page.locator("#experiment-results")).toBeVisible();
  await expect(page.locator("#original-gate-status")).toHaveText("REJECTED");
  await expect(page.locator("#original-gate-explanation")).toContainText(
    "1 passed",
  );
  await expect(page.locator("#headline-ratio")).toHaveText("≥2.00×");
  await expect(page.locator("#evidence-load-note")).toContainText(
    "GitHub Pages loaded the checked-in audit receipt",
  );
  expect(messages).toEqual([]);
});

test("matched live request check sends real requests to both configured lanes", async ({ page }) => {
  await mockMatchedSurge(page);
  await page.goto(`${appUrl}#surge`);
  await expect(page.locator("#run-live-surge")).toBeEnabled();
  await page.locator("#surge-message").fill("Please freeze my stolen card immediately");
  await page.getByRole("button", { name: "Run matched request check" }).click();
  await expect(page.locator("#baseline-live-slots .complete")).toHaveCount(3);
  await expect(page.locator("#optimized-live-slots .complete")).toHaveCount(3);
  await expect(page.locator("#baseline-live-slots")).toContainText("kleidiai-disabled");
  await expect(page.locator("#optimized-live-slots")).toContainText("kleidiai-enabled");
  await expect(page.locator("#live-match-proof")).toContainText("compared runtime control mlas.disable_kleidiai: 1 → 0");
  await expect(page.locator("#live-surge-result")).toContainText("all six matched requests completed");
});

test("proof view exposes the authoritative evidence chain", async ({ page }) => {
  await page.goto(`${appUrl}#proof`);
  await expect(page.getByRole("heading", { name: "How the release decision is produced" })).toBeVisible();
  await expect(page.locator("#proof-evidence-count")).toHaveText("69 sustained + 35 Performix checksums");
  await expect(page.locator("#proof-decision-detail")).toContainText("9 required claims");
  await expect(page.locator("#proof-claims")).toContainText("68.53%");
  await expect(page.getByRole("heading", { name: "Arm Performix and Linux perf observed the optimized path" })).toBeVisible();
  await expect(page.locator("#performix-disabled-share")).toHaveText("0%");
  await expect(page.locator("#performix-enabled-share")).toHaveText("67.02%");
  await expect(page.locator("#performix-linux-share")).toHaveText("68.53%");
  await expect(page.locator("#performix-kernel")).toContainText("neon_i8mm");
  await expect(page.locator(".evidence-chain li")).toHaveCount(4);
  await expect(page.getByRole("heading", { name: "Scaffold another Arm AI service" })).toBeVisible();
  await expect(page.locator(".reuse-steps")).toContainText("armproof init");
  await expect(page.getByRole("button", { name: "Test a one-byte evidence change" })).toBeEnabled();
  await page.getByRole("button", { name: "Test a one-byte evidence change" }).click();
  await expect(page.locator("#tamper-result")).toContainText("BLOCK  archive_digest_mismatch");
  await expect(page.locator("#tamper-result")).toContainText("one byte changed in a temporary copy");
  await page.getByRole("button", { name: "Generate a starter kit preview" }).click();
  await expect(page.locator("#scaffold-preview")).toContainText("created  armproof.json");
  await expect(page.locator("#scaffold-preview")).toContainText("BLOCK until evidence exists");
});


test("proof view exposes both the Arm result and quality boundary", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 1280, height: 960 });
  await page.goto(appUrl);
  await page.getByRole("tab", { name: "3. Release gate" }).click();

  await expect(page.getByRole("heading", { name: "Checked-in conservative release receipt" })).toBeVisible();
  await expect(page.locator(".recorded-label")).toHaveCount(9);
  await expect(page.locator(".claims-table tbody tr")).toHaveCount(9);
  await expect(page.locator("#proof-claims")).toContainText("Sustained capacity lower bound");
  await expect(page.locator("#proof-claims")).toContainText("Profiler sample integrity");
  await expect(page.locator("#absolute-accuracy")).toHaveText("46.49%");
  await expect(page.getByRole("heading", { name: "86.75% held-out queue accuracy" })).toBeVisible();
  await expect(page.locator(".stack-path li")).toHaveCount(4);
  await expect(page.getByRole("heading", { name: "BF16 to INT4 reduces the deployment footprint" })).toBeVisible();
  expect(messages).toEqual([]);
});


test("mobile workflow has no page overflow", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto(appUrl);
  await expect(page.getByRole("heading", { name: "Route an incoming request" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole("tab", { name: "2. Capacity audit" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole("tab", { name: "3. Release gate" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await expect(page.locator(".claims-table thead")).toBeHidden();
  await expect(page.locator(".claims-table tbody tr").first()).toHaveCSS("display", "grid");
  expect(messages).toEqual([]);
  await page.screenshot({ path: "build/screenshots/surgedesk-mobile.png", fullPage: true });
});
