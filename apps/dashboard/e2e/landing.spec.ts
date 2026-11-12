import { expect, test } from "@playwright/test";
import { signIn } from "./auth-helper";

test("public product landing stays independent of the operator API at all review sizes", async ({ page }) => {
  const apiRequests: string[] = [];
  const pageErrors: string[] = [];
  page.on("request", request => { if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url()); });
  page.on("pageerror", error => pageErrors.push(error.message));

  for (const [name, width, height] of [["desktop", 1440, 900], ["laptop", 1280, 800], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Autonomy needs/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /Launch console/i }).first()).toBeVisible();
    await expect(page.getByRole("group", { name: "Illustrative system stages" })).toBeVisible();
    const primaryCta = page.locator(".hero-actions .button-primary");
    const ctaBox = await primaryCta.boundingBox();
    expect(ctaBox).not.toBeNull();
    expect(ctaBox!.y + ctaBox!.height).toBeLessThan(height);
    await page.getByRole("button", { name: /6\. Contain/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".demo-story")).toContainText("The controller sees the interaction");
    await page.getByRole("button", { name: "Controller response" }).click();
    await expect(page.locator(".conflict-resolution")).toContainText("Selective hold");
    await page.getByRole("button", { name: /Investigations/ }).click();
    await expect(page.locator(".preview-panel")).toContainText("Evidence-led analysis");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `visual-review/landing-viewport-${name}.png` });
    await page.screenshot({ path: `visual-review/landing-${name}.png`, fullPage: true });
  }

  expect(apiRequests).toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: /7\. Investigate/ }).click();
  await expect(page.locator(".demo-story")).toContainText("Operators can inspect the evidence");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("link", { name: /Launch console/i }).first().click();
  await expect(page).toHaveURL(/\/app$/);
  await signIn(page);
  await expect(page.locator(".topbar .pill")).toHaveText("Connected");
  await expect(page.getByRole("heading", { name: "Mission control" })).toBeVisible();
});
