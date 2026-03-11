import { chromium } from "playwright";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(__dirname, "public");
const BASE = "http://127.0.0.1:8000";
const VIEWPORT = { width: 1920, height: 1080 };

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function captureOverview(browser) {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: { dir: PUBLIC, size: VIEWPORT },
  });
  const page = await ctx.newPage();

  await page.goto(`${BASE}/?section=overview&page_size=99`);
  await page.waitForLoadState("networkidle");
  await sleep(3000);

  await page.evaluate(() => window.scrollTo({ top: 400, behavior: "smooth" }));
  await sleep(2000);

  await page.evaluate(() => window.scrollTo({ top: 800, behavior: "smooth" }));
  await sleep(2000);

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await sleep(1500);

  await ctx.close();

  const video = page.video();
  const videoPath = await video.path();
  const dest = path.join(PUBLIC, "overview.webm");
  const fs = await import("fs");
  fs.renameSync(videoPath, dest);
  console.log("Saved overview.webm");
}

async function capturePayments(browser) {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: { dir: PUBLIC, size: VIEWPORT },
  });
  const page = await ctx.newPage();

  await page.goto(`${BASE}/?section=payments&page=0&page_size=20`);
  await page.waitForLoadState("networkidle");
  await sleep(2500);

  await page.evaluate(() => window.scrollTo({ top: 300, behavior: "smooth" }));
  await sleep(1500);

  const rows = page.locator("tr.row-clickable");
  const count = await rows.count();
  if (count > 2) {
    await rows.nth(2).click();
    await sleep(3000);
    await page.click("[data-modal-close]");
    await sleep(1000);
  }

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await sleep(1500);

  await ctx.close();

  const video = page.video();
  const videoPath = await video.path();
  const dest = path.join(PUBLIC, "payments.webm");
  const fs = await import("fs");
  fs.renameSync(videoPath, dest);
  console.log("Saved payments.webm");
}

async function captureInbox(browser) {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: { dir: PUBLIC, size: VIEWPORT },
  });
  const page = await ctx.newPage();

  await page.goto(
    `${BASE}/?section=inbox&tab=missing_eobs&page=0&page_size=20`
  );
  await page.waitForLoadState("networkidle");
  await sleep(3000);

  await page.evaluate(() => window.scrollTo({ top: 300, behavior: "smooth" }));
  await sleep(1500);

  await page.click('a[href*="tab=missing_txn"]');
  await page.waitForLoadState("networkidle");
  await sleep(3000);

  await page.evaluate(() => window.scrollTo({ top: 300, behavior: "smooth" }));
  await sleep(1500);

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await sleep(1000);

  await ctx.close();

  const video = page.video();
  const videoPath = await video.path();
  const dest = path.join(PUBLIC, "inbox.webm");
  const fs = await import("fs");
  fs.renameSync(videoPath, dest);
  console.log("Saved inbox.webm");
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    await captureOverview(browser);
    await capturePayments(browser);
    await captureInbox(browser);
    console.log("All recordings done.");
  } finally {
    await browser.close();
  }
})();
