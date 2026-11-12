import { expect, type Page } from "@playwright/test";

export function operatorHeaders() {
  const token = process.env.BOTKERNEL_OPERATOR_TOKEN;
  if (!token) throw new Error("Set BOTKERNEL_OPERATOR_TOKEN to the isolated test API credential.");
  return { Authorization: `Bearer ${token}` };
}

export async function signIn(page: Page) {
  const token = process.env.BOTKERNEL_OPERATOR_TOKEN;
  if (!token) throw new Error("Set BOTKERNEL_OPERATOR_TOKEN to the isolated test API credential.");
  await page.getByLabel("Operator credential").fill(token);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByLabel("Operator credential")).toHaveCount(0);
}
