import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const reportUrl = pathToFileURL(path.resolve('report/index.html')).href;
const blockedRoot = path.resolve('build/blocked-report');
const blockedUrl = pathToFileURL(path.join(blockedRoot, 'index.html')).href;

test.beforeAll(async () => {
  await mkdir(blockedRoot, { recursive: true });
  const environment = { ...process.env, PYTHONPATH: 'src' };
  const decision = spawnSync('python3.12', [
    '-m', 'armproof.cli', 'verify',
    '--contract', 'examples/fixture-fail/contract.json',
    '--comparison', 'examples/fixture-fail/comparison.json',
    '--output', path.join(blockedRoot, 'decision.json'),
  ], { env: environment });
  expect(decision.status).toBe(2);
  const report = spawnSync('python3.12', [
    '-m', 'armproof.cli', 'report',
    '--decision', path.join(blockedRoot, 'decision.json'),
    '--summary', 'examples/fixture-fail/summary.json',
    '--comparison', 'examples/fixture-fail/comparison.json',
    '--output', blockedRoot,
  ], { env: environment });
  expect(report.status).toBe(0);
});

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'tablet', width: 768, height: 900 },
  { name: 'mobile', width: 320, height: 780 },
]) {
  test(`${viewport.name} report is complete and stable`, async ({ page }) => {
    const messages = [];
    page.on('console', message => {
      if (message.type() === 'error' || message.type() === 'warning') messages.push(message.text());
    });
    await page.setViewportSize(viewport);
    await page.goto(reportUrl);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Measured capacity cleared the release checks.');
    await expect(page.locator('.mix')).toHaveCount(1);
    await expect(page.locator('.claim')).toHaveCount(10);
    await expect(page.locator('#min-ratio')).toHaveText('2.0x');
    await expect(page.locator('#capacity-description')).toContainText('Conservative lower bound');
    await expect(page.locator('.bar-row').nth(0)).toContainText('Baseline fail');
    await expect(page.locator('.bar-row').nth(1)).toContainText('Optimized pass');
    await expect(page.locator('#reproduction-note')).toBeHidden();
    await page.getByRole('tab', { name: 'Evidence & provenance' }).click();
    await expect(page.locator('#verification-detail')).toContainText('files verified');
    await expect(page.locator('#verification-detail')).toContainText('capacity, raw quality, runtime experiments, deployment measurements and native Arm Performix bundles');
    await expect(page.locator('#verification-detail')).toContainText('Git object ab22cc0 contains the exact plan');
    await expect(page.locator('#verification-detail')).toContainText(
      'launch time recorded in experiment metadata',
    );
    await expect(page.locator('#verification-detail')).toContainText(
      'not independent AWS attestation',
    );
    await expect(page.locator('#performix-section')).toBeVisible();
    await expect(page.locator('#performix-disabled')).toContainText('0%');
    await expect(page.locator('#performix-enabled')).toContainText('67.35%');
    await expect(page.locator('#performix-crosscheck')).toContainText('different units');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    expect(await page.evaluate(() => [...document.querySelectorAll('body *')].filter(element => element.scrollWidth > element.clientWidth + 1).map(element => element.className))).toEqual([]);
    await mkdir('build/screenshots', { recursive: true });
    await page.screenshot({ path: `build/screenshots/report-${viewport.name}-overview.png`, fullPage: true });
    await page.getByRole('tab', { name: 'Evidence & provenance' }).click();
    await expect(page.getByRole('heading', { name: 'Evidence history' })).toBeVisible();
    await expect(page.locator('#history')).toContainText('EXP-2026-009');
    await expect(page.locator('#history')).toContainText('Original exact bracket rejected');
    await expect(page.locator('#history')).toContainText('EXP-2026-010');
    await expect(page.locator('#history')).toContainText('EXP-2026-012');
    await expect(page.locator('#history')).toContainText('missing source-artifact identity');
    await expect(page.locator('#history')).toContainText('EXP-2026-014');
    await expect(page.locator('#provenance tr')).toHaveCount(4);
    expect(messages).toEqual([]);
    if (viewport.name === 'desktop') {
      await page.screenshot({ path: 'build/screenshots/report-desktop-evidence.png', fullPage: true });
    }
  });
}

test('blocked decision is unmistakable and actionable', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.goto(blockedUrl);
  await expect(page.locator('#decision-title')).toHaveText('Release blocked');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Optimization evidence blocked before merge.');
  await expect(page.locator('#decision-subtitle')).toHaveText('Required claims did not pass');
  await expect(page.locator('#min-ratio')).toHaveText('1.2x');
  await expect(page.locator('#deployment-section')).toBeHidden();
  await expect(page.locator('.check.fail')).toHaveCount(1);
  await expect(page.locator('.claim code').filter({ hasText: 'threshold_not_met' })).toBeVisible();
  await page.screenshot({ path: 'build/screenshots/report-blocked.png', fullPage: true });
});
