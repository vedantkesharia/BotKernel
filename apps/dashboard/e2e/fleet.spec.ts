import { signIn } from "./auth-helper";
import { expect, test } from "@playwright/test";

test("fleet filters real registered identities without treating stale heartbeat as process failure", async ({ page }) => {
  await page.goto("/app/agents");
  await signIn(page);
  await expect(page.getByRole("heading", { name: "Agent fleet" })).toBeVisible();
  await expect(page.locator(".fleet-summary")).toBeVisible();
  await expect(page.locator("footer")).toContainText("LOCAL SIMULATION");
  await expect(page.locator(".decision-card-heading")).toBeVisible();
  await expect(page.locator(".identity-panel .overline")).not.toContainText("AGENT AGENT");
  await expect(page.locator(".workflow-rail > div")).toHaveCount(5);
  await expect(page.locator(".workflow-contract")).toContainText("Definition only");
  await expect(page.getByRole("heading", { name: "Recent actions" })).toBeVisible();

  const allRows = page.locator(".fleet-row");
  await expect(allRows.first()).toBeVisible();
  const identity = (await allRows.first().locator("strong").textContent())?.trim();
  expect(identity).toBeTruthy();

  await page.getByRole("button", { name: "Stale", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stale", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(allRows.first()).toBeVisible();
  await expect(page.getByText("HEARTBEAT STALE")).toBeVisible();

  await page.getByRole("button", { name: "All", exact: true }).click();
  await page.getByRole("textbox", { name: "Search agents" }).fill(identity!);
  await expect(allRows).toHaveCount(1);
  await expect(allRows.first()).toContainText(identity!);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
