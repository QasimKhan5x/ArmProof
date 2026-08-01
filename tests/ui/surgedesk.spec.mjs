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
  await expect(page.locator("#demo-source")).toContainText("EXP-2026-004");
  await expect(page.locator("#customer-message")).toHaveValue(/gym bag/);

  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#suggested-intent")).toHaveText("Lost Or Stolen Card");
  await expect(page.locator("#suggested-queue")).toHaveText("Account security");
  await page.getByRole("button", { name: "Confirm route" }).click();
  await expect(page.locator("#reviewed-tickets tr")).toHaveCount(1);
  await expect(page.locator("#reviewed-tickets")).toContainText("Confirmed");

  await page.locator("#sample-select").selectOption("banking77-quality-0001");
  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#review-warning")).toContainText("differs from the benchmark label");
  await page.getByRole("button", { name: "Apply benchmark correction" }).click();
  await expect(page.locator("#reviewed-tickets tr")).toHaveCount(2);
  await expect(page.locator("#reviewed-tickets")).toContainText("Corrected");

  await page.locator("#customer-message").fill("A new message without recorded evidence");
  await page.getByRole("button", { name: "Load model suggestion" }).click();
  await expect(page.locator("#intake-error")).toBeVisible();
  await expect(page.locator("#intake-error")).toContainText("No recorded Phi-4 result");
  expect(messages).toEqual([]);
  await mkdir("build/screenshots", { recursive: true });
  await page.screenshot({ path: "build/screenshots/surgedesk-triage.png", fullPage: true });
});


test("recorded surge reveals the fixed-SLO Arm result", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(appUrl);
  await page.getByRole("tab", { name: "2. Surge replay" }).click();

  await expect(page.getByRole("heading", { name: "Same instance. 3× the capacity." })).toBeVisible();
  await page.getByRole("button", { name: "Run recorded surge" }).click();
  await expect(page.locator("#baseline-status")).toHaveText("failed", { timeout: 3000 });
  await expect(page.locator("#optimized-status")).toHaveText("passed");
  await expect(page.locator("#baseline-completed")).toHaveText("8 / 8");
  await expect(page.locator("#optimized-completed")).toHaveText("18 / 18");
  await expect(page.locator("#baseline-p95")).toHaveText(/s$/);
  await expect(page.locator("#replay-conclusion")).toContainText("3× mixed traffic");
  await expect(page.locator("#mix-table tr")).toHaveCount(3);
  expect(messages).toEqual([]);
  await page.screenshot({ path: "build/screenshots/surgedesk-surge.png", fullPage: true });
});


test("proof view exposes both the Arm result and quality boundary", async ({ page }) => {
  const messages = captureBrowserErrors(page);
  await page.setViewportSize({ width: 1280, height: 960 });
  await page.goto(appUrl);
  await page.getByRole("tab", { name: "3. Release proof" }).click();

  await expect(page.getByRole("heading", { name: "Approved for the measured Graviton deployment" })).toBeVisible();
  await expect(page.locator(".claims-table tbody tr")).toHaveCount(5);
  await expect(page.locator("#absolute-accuracy")).toHaveText("46.49%");
  await expect(page.getByRole("heading", { name: "Human confirmation is required" })).toBeVisible();
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
  await page.getByRole("tab", { name: "2. Surge replay" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole("tab", { name: "3. Release proof" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(messages).toEqual([]);
  await page.screenshot({ path: "build/screenshots/surgedesk-mobile.png", fullPage: true });
});
