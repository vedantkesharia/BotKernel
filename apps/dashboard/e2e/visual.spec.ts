import { signIn } from "./auth-helper";
import { expect, test } from "@playwright/test";

const routes = [["overview", "/app"], ["agents", "/app/agents"], ["graph", "/app/graph"], ["incidents", "/app/incidents"], ["experiments", "/app/experiments"]] as const;

for (const [name, path] of routes) {
  test(`${name} desktop and mobile visual review`, async ({ page }, testInfo) => {
    const browserErrors: string[] = [];
    page.on("pageerror", error => browserErrors.push(error.message));
    page.on("console", message => { if (message.type() === "error") browserErrors.push(message.text()); });
    for (const [size, width, height] of [["desktop", 1440, 900], ["laptop", 1280, 800], ["mobile", 390, 844]] as const) {
      await page.setViewportSize({ width, height });
      await page.goto(path);
      await signIn(page);
      await expect(page.locator("h1")).toBeVisible();
      await expect(page.locator(".topbar .pill")).toHaveText("Connected");
      if (name === "overview") await expect(page.locator(".hero-panel")).toBeVisible();
      if (name === "agents") {
        await expect(page.locator(".identity-panel")).toBeVisible();
        await expect(page.locator(".identity-stats strong")).toHaveCount(4);
        await expect(page.locator(".identity-stats strong").nth(3)).toBeVisible();
      }
      if (name === "graph") {
        const content = page.locator(".react-flow__node").first().or(page.locator(".graph-empty"));
        await expect(content).toBeVisible();
      }
      if (name === "incidents") await expect(page.locator(".incident-detail")).toBeVisible();
      if (name === "experiments") {
        const content = page.locator(".experiment-results").or(page.locator(".experiment-history .empty"));
        await expect(content).toBeVisible({ timeout: 15_000 });
      }
      await page.screenshot({ path: testInfo.outputPath(`${name}-${size}.png`), fullPage: true });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    expect(browserErrors).toEqual([]);
  });
}
