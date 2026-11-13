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
    const diagramLayout = await page.locator(".demo-canvas").evaluate(canvas => {
      const bounds = canvas.getBoundingClientRect();
      const nodes = [...canvas.querySelectorAll<HTMLElement>(".demo-diagram [data-node]")].map(node => {
        const rect = node.getBoundingClientRect();
        return { name: node.dataset.node, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height };
      });
      const overlaps = nodes.flatMap((node, index) => nodes.slice(index + 1).filter(other =>
        Math.min(node.right, other.right) - Math.max(node.left, other.left) > 1 &&
        Math.min(node.bottom, other.bottom) - Math.max(node.top, other.top) > 1,
      ).map(other => `${node.name}/${other.name}`));
      const outside = nodes.filter(node => node.left < bounds.left || node.right > bounds.right || node.top < bounds.top || node.bottom > bounds.bottom);
      const wires = [...canvas.querySelectorAll<SVGPathElement>(".demo-wire")];
      const endpoints: Record<string, [string, string]> = {
        "resource-cost": ["resource", "cost"],
        "resource-performance": ["resource", "performance"],
        "cost-admission": ["cost", "gateway"],
        "performance-admission": ["performance", "gateway"],
        "admission-postgres": ["gateway", "outbox"],
        "postgres-publisher": ["outbox", "publisher"],
        "publisher-worker": ["publisher", "worker"],
        "worker-effect": ["worker", "effect"],
        "effect-resource": ["effect", "resource"],
        "effect-controller": ["effect", "controller"],
        "controller-investigator": ["controller", "investigator"],
      };
      const connectorIntersections = wires.flatMap(wire => {
        const [source, target] = endpoints[wire.dataset.edge ?? ""] ?? [];
        if (!source || !target) return [`${wire.dataset.edge}/unknown-endpoints`];
        const length = wire.getTotalLength();
        return Array.from({ length: 19 }, (_, index) => {
          const point = wire.getPointAtLength(length * (index + 1) / 20);
          const blocker = nodes.find(node => {
            if (node.name === source || node.name === target) return false;
            const left = node.left - bounds.left;
            const right = node.right - bounds.left;
            const top = node.top - bounds.top;
            const bottom = node.bottom - bounds.top;
            return point.x > left + 1 && point.x < right - 1 && point.y > top + 1 && point.y < bottom - 1;
          });
          return blocker ? `${wire.dataset.edge}/${blocker.name}` : "";
        }).filter(Boolean);
      });
      const overflowingAgentTitles = [...canvas.querySelectorAll<HTMLElement>(".demo-agent b")]
        .filter(title => title.scrollWidth > title.clientWidth + 1)
        .map(title => title.textContent?.trim() ?? "");
      const stabilityWire = wires.find(wire => wire.dataset.edge === "effect-controller");
      const stabilityController = nodes.find(node => node.name === "controller");
      const stabilityEndpoint = stabilityWire && stabilityController
        ? stabilityWire.getPointAtLength(stabilityWire.getTotalLength())
        : null;
      const stabilityEndpointOffset = stabilityEndpoint && stabilityController
        ? Math.min(
          Math.abs(stabilityEndpoint.x - (stabilityController.left - bounds.left)),
          Math.abs(stabilityEndpoint.x - (stabilityController.right - bounds.left)),
          Math.abs(stabilityEndpoint.y - (stabilityController.top - bounds.top)),
          Math.abs(stabilityEndpoint.y - (stabilityController.bottom - bounds.top)),
        )
        : null;
      return {
        nodes,
        oversizedNodes: nodes.filter(node => node.height > 84).map(node => node.name),
        overlaps,
        outside,
        wireCount: wires.length,
        emptyWires: wires.filter(wire => !wire.getAttribute("d")?.trim()).map(wire => wire.dataset.edge),
        missingAgentAdmissionEdges: ["cost-admission", "performance-admission"].filter(id => !wires.some(wire => wire.dataset.edge === id)),
        connectorIntersections,
        overflowingAgentTitles,
        stabilityEndpointOffset,
        wiresHidden: getComputedStyle(canvas.querySelector(".demo-wires")!).display === "none",
      };
    });
    expect(diagramLayout.nodes).toHaveLength(10);
    expect(diagramLayout.oversizedNodes).toEqual([]);
    expect(diagramLayout.overlaps).toEqual([]);
    expect(diagramLayout.outside).toEqual([]);
    expect(diagramLayout.wireCount).toBe(11);
    expect(diagramLayout.emptyWires).toEqual([]);
    expect(diagramLayout.missingAgentAdmissionEdges).toEqual([]);
    expect(diagramLayout.connectorIntersections).toEqual([]);
    expect(diagramLayout.overflowingAgentTitles).toEqual([]);
    expect(diagramLayout.stabilityEndpointOffset).not.toBeNull();
    expect(diagramLayout.stabilityEndpointOffset).toBeLessThan(1);
    expect(diagramLayout.wiresHidden).toBe(false);
    const stepperOverflow = await page.locator(".demo-stepper").evaluate(stepper => stepper.scrollWidth > stepper.clientWidth + 1);
    expect(stepperOverflow).toBe(false);
    const primaryCta = page.locator(".hero-actions .button-primary");
    const ctaBox = await primaryCta.boundingBox();
    expect(ctaBox).not.toBeNull();
    expect(ctaBox!.y + ctaBox!.height).toBeLessThan(height);
    await page.getByRole("button", { name: /6\. Contain/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".demo-story")).toContainText("The controller sees the interaction");
    await page.getByRole("button", { name: "Controller response" }).click();
    await expect(page.locator(".conflict-resolution")).toContainText("Selective hold");
    for (const [label, kind, title] of [
      ["Mission control", "overview", "Operational overview"],
      ["Agent fleet", "fleet", "Independent runtimes"],
      ["Effect graph", "graph", "Versioned effects"],
      ["Investigations", "investigation", "Evidence-led analysis"],
    ] as const) {
      const tab = page.getByRole("button", { name: new RegExp(label, "i") });
      await tab.click();
      await expect(tab).toHaveAttribute("aria-pressed", "true");
      await expect(page.locator(".preview-panel")).toContainText(title);
      await expect(page.locator(`.preview-surface.preview-${kind}`)).toBeVisible();
      await expect(page.locator(".preview-disclaimer")).toContainText("no live metrics or records");
    }
    const previewOverflow = await page.locator(".preview-surface").evaluate(surface => surface.scrollWidth > surface.clientWidth + 1);
    expect(previewOverflow).toBe(false);
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
