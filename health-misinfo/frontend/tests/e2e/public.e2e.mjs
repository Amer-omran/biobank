// Public-mode e2e: an anonymous visitor uses the site without signing in.
//   E2E_BASE_URL=http://localhost:3000 node tests/e2e/public.e2e.mjs   (API started with HMD_PUBLIC_MODE=true)
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const SHOTS = process.env.E2E_SCREENSHOTS;
const expect = (c, m) => {
  if (!c) throw new Error(m);
};
let passed = 0;
const step = async (name, fn) => {
  await fn();
  passed++;
  console.log(`PASS  ${name}`);
};

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1360, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await step("visitor lands on the dashboard without a login redirect", async () => {
    await page.goto(`${BASE}/`);
    await page.waitForLoadState("networkidle");
    expect(!page.url().includes("/login"), "redirected to login");
    await page.getByText("غير مدرَّب").first().waitFor();
    await page.getByRole("link", { name: "دخول الفريق" }).waitFor();
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/public-dashboard-ar.png`, fullPage: true });
  });
  await step("navigation hides history, reviews and administration", async () => {
    const nav = await page.locator("aside nav").innerText();
    for (const hidden of ["السجل", "مراجعة الخبراء", "الإدارة"]) expect(!nav.includes(hidden), `nav shows ${hidden}`);
    for (const shown of ["تحليل ادعاء", "مجموعات البيانات", "التحليلات البحثية", "التقارير"]) expect(nav.includes(shown), `nav lacks ${shown}`);
  });
  await step("visitor analyzes a claim (explicit no-prediction state, no review button)", async () => {
    await page.goto(`${BASE}/analyze`);
    await page.waitForLoadState("networkidle");
    await page.fill("#claim", "الثوم يعالج الإنفلونزا خلال يوم واحد");
    await page.getByRole("button", { name: "تحليل" }).click();
    await page.getByText("لم يُصدَر أي تنبؤ", { exact: false }).waitFor();
    expect((await page.getByText("طلب مراجعة خبير").count()) === 0, "review button visible to guest");
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/public-analyze-ar.png`, fullPage: true });
  });
  await step("datasets, analytics and public reports open", async () => {
    for (const p of ["/datasets", "/analytics", "/reports"]) {
      await page.goto(`${BASE}${p}`);
      await page.waitForLoadState("networkidle");
      expect((await page.getByRole("alert").filter({ hasText: "حدث خطأ" }).count()) === 0, `error on ${p}`);
    }
    const pdf = await page.request.get(`${BASE}/api/v1/reports?type=summary&format=pdf`);
    expect(pdf.ok(), "summary pdf");
    expect((await page.request.get(`${BASE}/api/v1/reports?type=analyses&format=csv`)).status() === 401, "analyses csv must need login");
  });
  await step("staff sign-in link still leads to the login page", async () => {
    await page.goto(`${BASE}/`);
    await page.getByRole("link", { name: "دخول الفريق" }).click();
    await page.waitForURL(/\/login/);
  });
  expect(errors.length === 0, errors.join(" | "));
  console.log(`\n${passed}/5 public e2e steps passed`);
} finally {
  await browser.close();
}
