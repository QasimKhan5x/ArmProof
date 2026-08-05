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


test("a live ticket causes the audit, activation, and optimized second route", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto(appUrl);

  await page.getByLabel("Live matched Arm64 endpoint").check();
  await page.locator("#customer-message").fill(
    "My card was stolen while I am travelling. Freeze it and help me replace it.",
  );
  await page.getByRole("button", { name: "Run live route" }).click();
  await expect(page.locator("#inference-source")).toContainText("Standard service · KleidiAI off");
  await expect(page.locator("#live-request-receipt")).toBeVisible();
  await expect(page.locator("#live-request-id")).toContainText("surgedesk-");
  const firstRequestId = await page.locator("#live-request-id").textContent();
  await expect(page.locator("#live-arm-runtime")).toContainText("aarch64 · 16 threads");
  await expect(page.locator("#live-control")).toHaveText("mlas.disable_kleidiai=1");
  await page.locator("#final-queue").selectOption("Account security");
  await page.getByRole("button", { name: "Route ticket" }).click();
  await page.getByRole("button", { name: "Review measured upgrade" }).click();

  await expect(page.locator("#experiment-results")).toBeHidden();
  await expect(page.locator("#optimization-summary")).toBeHidden();
  await page.getByRole("button", { name: "Verify measured experiment" }).click();
  await expect(page.locator("#audit-progress li")).toHaveCount(5);
  await expect(page.locator('#audit-progress li[data-stage="quality"]')).toContainText("raw model outputs");
  await expect(page.locator('#audit-progress li[data-stage="performix"]')).toContainText("Performix function samples");
  await expect(page.locator('#audit-progress li[data-stage="requests"]')).toContainText("traffic outcomes");
  await expect(page.locator("#audit-progress time")).toHaveCount(5);
  await expect(page.locator("#audit-receipt")).toBeVisible();
  await expect(page.locator("#experiment-results")).toBeHidden();
  await expect(page.locator("#audit-request-result")).toContainText("2,100 capacity requests");
  await expect(page.locator("#audit-request-result")).toContainText("1,540 model outputs");
  await page.getByRole("button", { name: "Open confirmed result" }).click();
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
  await expect(page.locator("#rate-confirmation-id")).toContainText("EXP-2026-014");
  await expect(page.locator("#rate-confirmation-id")).toHaveAttribute("href", /\/commit\//);

  await page.getByRole("button", { name: "Review and activate the optimized service" }).click();
  await expect(page.locator("#optimization-summary")).toBeVisible();
  await expect(page.locator("#performix-proof")).toBeVisible();
  await page.getByRole("button", { name: "Activate verified optimized service" }).click();
  await expect(page.locator("#promotion-result")).toContainText("now serving");
  await expect(page.locator("#promotion-identity")).toBeVisible();
  await expect(page.locator("#promotion-control-match")).toContainText("1 → 0");
  expect(await overflowingElements(page)).toEqual([]);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mkdir("build/screenshots", { recursive: true });
  await page.locator("#optimization-summary").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-release-proof.png" });
  await page.setViewportSize({ width: 320, height: 780 });
  await page.getByRole("button", { name: "Route the next live request" }).click();
  await page.locator("#customer-message").fill(
    "My card was stolen while I am travelling. Freeze it and help me replace it.",
  );
  await page.getByRole("button", { name: "Run live route" }).click();
  await expect(page.locator("#inference-source")).toContainText("Optimized service · KleidiAI on");
  await expect(page.locator("#live-control")).toHaveText("mlas.disable_kleidiai=0");
  const secondRequestId = await page.locator("#live-request-id").textContent();
  expect(secondRequestId).not.toBe(firstRequestId);
  await expect(page.locator("#suggested-intent")).toContainText("Card");
  await page.locator("#final-queue").selectOption("Account security");
  await page.getByRole("button", { name: "Route ticket" }).click();
  await expect(page.locator("#reviewed-tickets")).toContainText("Standard service");
  await expect(page.locator("#reviewed-tickets")).toContainText("Optimized service");
  await expect(page.locator("#reviewed-tickets")).toContainText("observed");
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
  await expect(page.locator("#adoption-handoff")).toBeVisible();
  await page.getByRole("button", { name: "Carry this release gate to another service" }).click();
  await expect(page.locator("#proof-details")).toHaveAttribute("open", "");
  await expect(page.locator("#adoption-result")).toBeVisible();
  await expect(page.locator("#adoption-gate")).toContainText("STRUCTURE VALID");
  await expect(page.locator("#adoption-workflow")).toContainText("QasimKhan5x/ArmProof@v0.8.2");
  await expect(page.locator("#adoption-download")).toHaveAttribute("download", "armproof-service-starter.zip");
  await expect(page.locator("#adoption-download")).toHaveAttribute("href", /^blob:/);
  expect(await overflowingElements(page)).toEqual([]);

  await page.setViewportSize({ width: 1440, height: 1000 });
  await mkdir("build/screenshots", { recursive: true });
  await page.screenshot({ path: "build/screenshots/surgedesk-live-flow.png", fullPage: true });
  expect(messages).toEqual([]);
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
  await expect(page.locator("#trial-matrix-body tr")).toHaveCount(2);
  await expect(page.locator("#headline-ratio")).toHaveText("≥2.00×");
  await page.getByRole("tab", { name: "Release" }).click();
  await expect(page.locator("#optimization-summary")).toBeVisible();
  await expect(page.locator("#promotion-title")).toContainText("cleared the checked-in release policy");
  await expect(page.locator("#promote-route")).toBeHidden();
  await expect(page.locator("#open-required-audit")).toHaveText("Inspect capacity evidence");
  await expect(page.locator("#proof-claims tr")).toHaveCount(10);
  await expect(page.locator("body")).not.toContainText(/tamper|altered archive/i);
  await mkdir("build/screenshots", { recursive: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "build/screenshots/surgedesk-public-release-proof.png" });
  await page.getByRole("tab", { name: "Capacity" }).click();
  await page.locator("#latency-consequence-title").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "build/screenshots/surgedesk-capacity.png" });
  expect(messages).toEqual([]);
});


test("recorded support examples remain human-confirmed and clearly labeled", async ({ page }) => {
  await page.goto(appUrl);
  await expect(page.getByRole("heading", { name: "Route an incoming request" })).toBeVisible();
  await expect(page.locator(".routing-quality-details")).not.toHaveAttribute("open", "");
  await page.getByRole("button", { name: "Guard intervention" }).click();
  await page.getByRole("button", { name: "Inspect stored output" }).click();
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
  await expect(page.locator("#trial-matrix-body tr")).toHaveCount(2);
  expect(await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  )).toBe(true);
  const mobileControls = await page.locator("button:visible").evaluateAll(
    (buttons) => buttons.map((button) => button.getBoundingClientRect().height),
  );
  expect(Math.min(...mobileControls)).toBeGreaterThanOrEqual(44);
  const firstTrial = page.locator("#trial-matrix-body tr").first();
  await expect(firstTrial.locator("td").first()).toBeVisible();
  expect(await firstTrial.evaluate(
    (row) => getComputedStyle(row).display,
  )).toBe("grid");
  await page.getByRole("tab", { name: "Release" }).click();
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
