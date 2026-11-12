import { signIn } from "./auth-helper";
import { expect, test } from "@playwright/test";

for (const [label, width, height] of [["desktop", 1440, 900], ["mobile", 390, 844]] as const) {
  test(`graph dropdown is dark and keyboard accessible on ${label}`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/app/graph");
    await signIn(page);
    const trigger = page.getByRole("combobox", { name: "Graph time window" });
    await trigger.focus();
    await page.keyboard.press("Enter");
    const list = page.getByRole("listbox");
    await expect(list).toBeVisible();
    await expect(list).toHaveCSS("background-color", "rgb(36, 39, 41)");
    await expect(page.getByRole("option", { name: "Last hour" })).toHaveCSS("color", "rgb(197, 221, 202)");
    await expect(page.getByRole("option", { name: "Last hour" })).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath(`graph-menu-${label}.png`) });
    await page.keyboard.press("ArrowUp");
    await expect(page.getByRole("option", { name: "Last 15 minutes" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(trigger).toContainText("Last 15 minutes");
    await trigger.click();
    await page.keyboard.press("Escape");
    await expect(list).toBeHidden();
    await expect(trigger).toBeFocused();
    await page.getByRole("combobox", { name: "Highlight incident" }).click();
    await expect(page.getByRole("option", { name: "All evidence" })).toBeVisible();
    await page.keyboard.press("Escape");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}
