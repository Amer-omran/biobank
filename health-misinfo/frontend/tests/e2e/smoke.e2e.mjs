// End-to-end smoke test against a RUNNING stack (Next.js + FastAPI + DB).
//   E2E_BASE_URL=http://localhost:3000 E2E_EMAIL=... E2E_PASSWORD=... node tests/e2e/smoke.e2e.mjs
// Optional: E2E_SCREENSHOTS=<dir> to save screenshots. Exits non-zero on the first failure.
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
const SHOTS = process.env.E2E_SCREENSHOTS;
if (!EMAIL || !PASSWORD) throw new Error("E2E_EMAIL and E2E_PASSWORD are required");

const results = [];
async function step(name, fn) {
  try {
    await fn();
    results.push(["PASS", name]);
    console.log(`PASS  ${name}`);
  } catch (e) {
    results.push(["FAIL", name]);
    console.error(`FAIL  ${name}\n      ${e.message.split("\n")[0]}`);
    throw e;
  }
}
const shot = async (page, name) => SHOTS && page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
const expect = (cond, msg) => {
  if (!cond) throw new Error(msg);
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
const consoleErrors = [];
page.on("pageerror", (e) => consoleErrors.push(e.message));

try {
  await step("login page renders RTL Arabic by default", async () => {
    await page.goto(`${BASE}/login`);
    await page.waitForLoadState("networkidle"); // wait for hydration before typing
    expect((await page.getAttribute("html", "dir")) === "rtl", "html dir should be rtl");
    expect((await page.getAttribute("html", "lang")) === "ar", "html lang should be ar");
    await shot(page, "01-login-ar");
  });

  await step("wrong password is rejected with a message", async () => {
    await page.fill("#email", EMAIL);
    await page.fill("#password", "wrong-password-123");
    await page.click("button[type=submit]");
    await page.getByText("البريد الإلكتروني أو كلمة المرور غير صحيحة.").waitFor();
  });

  await step("sign in and see dashboard with explicit model-not-trained state", async () => {
    await page.fill("#password", PASSWORD);
    await page.click("button[type=submit]");
    await page.waitForURL(`${BASE}/`);
    await page.getByText("غير مدرَّب").first().waitFor();
    await shot(page, "02-dashboard-ar");
  });

  await step("language switcher flips to English LTR and persists", async () => {
    await page.getByRole("button", { name: "تغيير اللغة إلى الإنجليزية" }).click();
    expect((await page.getAttribute("html", "dir")) === "ltr", "html dir should be ltr");
    await page.getByText("Not trained").first().waitFor();
    await page.reload();
    expect((await page.getAttribute("html", "lang")) === "en", "locale cookie should persist");
    await shot(page, "03-dashboard-en");
  });

  let analysisUrl;
  await step("analyze an Arabic claim: no prediction, similar fact-checked claims shown", async () => {
    await page.goto(`${BASE}/analyze`);
    await page.waitForLoadState("networkidle");
    await page.fill("#claim", "منظمة الصحة العالمية تعلن انتهاء جائحة كورونا بشكل رسمي");
    await page.getByRole("button", { name: "Analyze" }).click();
    await page.getByText("No prediction was produced", { exact: false }).waitFor();
    expect((await page.getByText("Model prediction:").count()) === 0, "must not show a prediction");
    const rows = await page.locator("table tbody tr").count();
    console.log(`      similar fact-checked claims shown: ${rows}`);
    await shot(page, "04-analyze-en");
  });

  await step("request expert review", async () => {
    await page.getByRole("button", { name: "Request expert review" }).click();
    await page.getByText("Sent to the review queue").waitFor();
  });

  await step("history lists the analysis and opens details", async () => {
    await page.goto(`${BASE}/history`);
    await page.getByRole("link", { name: "Details" }).first().click();
    await page.waitForURL(/\/history\/\d+/);
    analysisUrl = page.url();
    await page.getByText("Reviews").first().waitFor();
  });

  await step("datasets page shows imports, progress and license registry", async () => {
    await page.goto(`${BASE}/datasets`);
    await page.getByText("Provenance & license registry").waitFor();
    await shot(page, "05-datasets-en");
  });

  await step("admin split builder refuses an invalid split (never forced)", async () => {
    await page.goto(`${BASE}/admin`);
    await page.waitForLoadState("networkidle");
    await page.fill("#sp-v", `e2e-${Date.now()}`);
    await page.getByRole("button", { name: "Build split" }).click();
    await page.getByText("Split refused").waitFor();
    await shot(page, "06-admin-en");
  });

  await step("expert review queue: submit a review for the analysis", async () => {
    await page.goto(`${BASE}/reviews`);
    await page.waitForLoadState("networkidle");
    const card = page.locator("section").filter({ hasText: "منظمة الصحة العالمية تعلن انتهاء" }).first();
    await card.getByLabel("Needs review").check();
    await card.getByLabel("Evidence URLs (one per line)").fill("https://www.who.int/");
    await card.getByRole("button", { name: "Submit" }).click();
    await page.getByText("Review submitted", { exact: false }).waitFor();
  });

  await step("analytics shows 'no measured results' rather than numbers", async () => {
    await page.goto(`${BASE}/analytics`);
    await page.getByText("No measured results").waitFor();
    await shot(page, "07-analytics-en");
  });

  await step("reports: summary PDF and analyses CSV download", async () => {
    const pdf = await page.request.get(`${BASE}/api/v1/reports?type=summary&format=pdf`);
    expect(pdf.ok() && (await pdf.body()).subarray(0, 4).toString() === "%PDF", "summary PDF");
    const csv = await page.request.get(`${BASE}/api/v1/reports?type=analyses&format=csv`);
    expect(csv.ok() && (await csv.text()).includes("model_not_trained"), "analyses CSV");
  });

  await step("mobile Arabic layout has no horizontal overflow", async () => {
    const m = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, storageState: await ctx.storageState() });
    await m.addCookies([{ name: "hmd_lang", value: "ar", url: BASE }]);
    const p = await m.newPage();
    await p.goto(analysisUrl ?? `${BASE}/analyze`);
    await p.waitForLoadState("networkidle");
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow <= 1, `horizontal overflow ${overflow}px`);
    await shot(p, "08-mobile-ar");
    await m.close();
  });

  await step("no uncaught page errors", async () => {
    expect(consoleErrors.length === 0, consoleErrors.join(" | "));
  });
} finally {
  await browser.close();
  const failed = results.filter((r) => r[0] === "FAIL").length;
  console.log(`\n${results.length - failed}/${results.length} e2e steps passed`);
  if (failed) process.exitCode = 1;
}
