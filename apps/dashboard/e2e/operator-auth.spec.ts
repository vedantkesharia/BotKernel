import { expect, test } from "@playwright/test";

test("public landing, login, sign-out and revoked credential", async ({ page }) => {
  let valid = true;
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const authorization = route.request().headers().authorization;
    if (path === "/api/auth/session") {
      return route.fulfill({ status: authorization === "Bearer correct" && valid ? 200 : 401, json: { role: "operator" } });
    }
    if (!valid && !["/api/health", "/api/ready"].includes(path)) {
      return route.fulfill({ status: 401, json: { detail: "Invalid credentials" } });
    }
    if (path === "/api/health" || path === "/api/ready") return route.fulfill({ json: { status: "ok", mode: "local simulation" } });
    return route.fulfill({ json: [] });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Operator access" })).toHaveCount(0);
  await page.goto("/app");
  await page.getByLabel("Operator credential").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("Invalid operator credential");
  await page.getByLabel("Operator credential").fill("correct");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Mission control" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Operator access" })).toBeVisible();
  await page.getByLabel("Operator credential").fill("correct");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Mission control" })).toBeVisible();
  valid = false;
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(page.getByRole("alert")).toContainText("no longer valid");
  await expect(page.getByRole("heading", { name: "Operator access" })).toBeVisible();
});
