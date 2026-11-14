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
      const endpoints = Object.fromEntries(wires.map(wire => [
        wire.dataset.edge ?? "",
        [wire.dataset.source ?? "", wire.dataset.target ?? ""],
      ]));
      const expectedEdges: Record<string, [string, string]> = {
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
      const edgeGraphErrors = Object.entries(expectedEdges).flatMap(([edge, expected]) =>
        JSON.stringify(endpoints[edge]) === JSON.stringify(expected) ? [] : [edge],
      );
      type AnchorSide = "left" | "right" | "top" | "bottom";
      const compact = bounds.width < 520;
      const edgeAnchors: Record<string, [AnchorSide, AnchorSide]> = {
        "cost-admission": compact ? ["bottom", "top"] : ["right", "left"],
        "performance-admission": compact ? ["bottom", "top"] : ["right", "left"],
        "admission-postgres": ["right", "left"],
        "postgres-publisher": compact ? ["bottom", "top"] : ["right", "left"],
        "publisher-worker": compact ? ["right", "left"] : ["bottom", "top"],
        "worker-effect": compact ? ["bottom", "top"] : ["left", "right"],
        "effect-controller": compact ? ["left", "right"] : ["bottom", "top"],
        "controller-investigator": compact ? ["bottom", "top"] : ["left", "right"],
        "effect-resource": ["bottom", "top"],
      };
      const measureAnchor = (point: DOMPoint, nodeName: string, side: AnchorSide, expectedGap = 0) => {
        const node = nodes.find(item => item.name === nodeName);
        if (!node) return null;
        const left = node.left - bounds.left;
        const right = node.right - bounds.left;
        const top = node.top - bounds.top;
        const bottom = node.bottom - bounds.top;
        if (side === "left") return { gap: left - point.x - expectedGap, aligned: point.y >= top - 1 && point.y <= bottom + 1 };
        if (side === "right") return { gap: point.x - right - expectedGap, aligned: point.y >= top - 1 && point.y <= bottom + 1 };
        if (side === "top") return { gap: top - point.y - expectedGap, aligned: point.x >= left - 1 && point.x <= right + 1 };
        return { gap: point.y - bottom - expectedGap, aligned: point.x >= left - 1 && point.x <= right + 1 };
      };
      const anchorMeasurements = wires.map(wire => {
        const edge = wire.dataset.edge ?? "";
        const [sourceName, targetName] = endpoints[edge] ?? ["", ""];
        const length = wire.getTotalLength();
        const start = wire.getPointAtLength(0);
        const end = wire.getPointAtLength(length);
        const before = wire.getPointAtLength(Math.max(0, length - Math.min(2, length / 2)));
        const isBranch = edge === "resource-cost" || edge === "resource-performance";
        const isTrunk = edge === "resource-branch-trunk";
        const [fromSide, toSide] = edgeAnchors[edge] ?? ["right", "left"];
        const source = isBranch ? null : measureAnchor(start, sourceName, isTrunk ? (compact ? "bottom" : "right") : fromSide);
        const targetSide = isBranch ? (compact ? "top" : "left") : toSide;
        const head = canvas.querySelector<SVGPolygonElement>(`.demo-arrowhead[data-arrow-for="${edge}"]`);
        const tip = head?.points.getItem(0);
        const target = isTrunk || !tip ? null : measureAnchor(new DOMPoint(tip.x, tip.y), targetName, targetSide, 2.5);
        const dx = end.x - before.x;
        const dy = end.y - before.y;
        const direction = targetSide === "left" ? dx
          : targetSide === "right" ? -dx
            : targetSide === "top" ? dy
              : -dy;
        return { edge, source, target, direction };
      });
      const anchorErrors = anchorMeasurements.flatMap(measurement =>
        [measurement.source, measurement.target].some(anchor => anchor && (!anchor.aligned || Math.abs(anchor.gap) > 0.75))
          ? [measurement.edge]
          : [],
      );
      const arrowDirectionErrors = anchorMeasurements.filter(measurement =>
        measurement.edge !== "resource-branch-trunk" && measurement.direction <= 0.1,
      ).map(measurement => measurement.edge);
      const agentAdmissionCurveErrors = compact ? [] : ["cost-admission", "performance-admission"].flatMap(id => {
        const wire = wires.find(item => item.dataset.edge === id);
        if (!wire) return [id];
        const length = wire.getTotalLength();
        const points = Array.from({ length: 81 }, (_, index) => wire.getPointAtLength(length * index / 80));
        const doublesBack = points.some((point, index) => index > 0 && point.x < points[index - 1].x - 0.2);
        const sourceApproach = wire.getPointAtLength(Math.min(2, length));
        const targetApproach = wire.getPointAtLength(Math.max(0, length - 2));
        const horizontalEntry = Math.abs(sourceApproach.y - points[0].y) < 0.75 &&
          Math.abs(targetApproach.y - points[80].y) < 0.75;
        return doublesBack || !horizontalEntry ? [id] : [];
      });
      const arrowheads = [...canvas.querySelectorAll<SVGPolygonElement>(".demo-arrowhead")];
      const missingArrows = wires.filter(wire =>
        wire.dataset.edge !== "resource-branch-trunk" && !arrowheads.some(head => head.dataset.arrowFor === wire.dataset.edge),
      ).map(wire => wire.dataset.edge);
      const trunkHasArrow = arrowheads.some(head => head.dataset.arrowFor === "resource-branch-trunk");
      const arrowheadErrors = wires.filter(wire => wire.dataset.edge !== "resource-branch-trunk").flatMap(wire => {
        const head = arrowheads.find(item => item.dataset.arrowFor === wire.dataset.edge);
        if (!head || head.points.numberOfItems !== 3) return [wire.dataset.edge ?? "unknown-edge"];
        const tip = head.points.getItem(0);
        const firstBase = head.points.getItem(1);
        const secondBase = head.points.getItem(2);
        const length = wire.getTotalLength();
        const pathTip = wire.getPointAtLength(length);
        const pathBeforeTip = wire.getPointAtLength(Math.max(0, length - 0.05));
        const baseCenter = {
          x: (firstBase.x + secondBase.x) / 2,
          y: (firstBase.y + secondBase.y) / 2,
        };
        const pathVector = { x: pathTip.x - pathBeforeTip.x, y: pathTip.y - pathBeforeTip.y };
        const headVector = { x: tip.x - baseCenter.x, y: tip.y - baseCenter.y };
        const alignment = (pathVector.x * headVector.x + pathVector.y * headVector.y) /
          (Math.hypot(pathVector.x, pathVector.y) * Math.hypot(headVector.x, headVector.y));
        const headLength = Math.hypot(headVector.x, headVector.y);
        const headWidth = Math.hypot(firstBase.x - secondBase.x, firstBase.y - secondBase.y);
        return Math.hypot(pathTip.x - baseCenter.x, pathTip.y - baseCenter.y) <= 0.05 &&
          alignment >= 0.995 &&
          Math.abs(headLength - 8) <= 0.05 &&
          Math.abs(headWidth - 6.5) <= 0.05
          ? []
          : [`${wire.dataset.edge ?? "unknown-edge"}:base=${Math.hypot(pathTip.x - baseCenter.x, pathTip.y - baseCenter.y).toFixed(3)},alignment=${alignment.toFixed(4)},length=${headLength.toFixed(3)},width=${headWidth.toFixed(3)}`];
      });
      const arrowheadIntersections = arrowheads.flatMap(head => {
        const [tip, first, second] = [0, 1, 2].map(index => head.points.getItem(index));
        const samples = Array.from({ length: 9 }, (_, step) =>
          Array.from({ length: step + 1 }, (_, across) => {
            const tipWeight = 1 - step / 8;
            const firstWeight = (step - across) / 8;
            const secondWeight = across / 8;
            return {
              x: tip.x * tipWeight + first.x * firstWeight + second.x * secondWeight,
              y: tip.y * tipWeight + first.y * firstWeight + second.y * secondWeight,
            };
          }),
        ).flat();
        const blocker = nodes.find(node => {
          if (node.name === head.dataset.source || node.name === head.dataset.target) return false;
          const left = node.left - bounds.left;
          const right = node.right - bounds.left;
          const top = node.top - bounds.top;
          const bottom = node.bottom - bounds.top;
          return samples.some(point => point.x > left && point.x < right && point.y > top && point.y < bottom);
        });
        return blocker ? [`${head.dataset.arrowFor}/${blocker.name}`] : [];
      });
      const connectorIntersections = wires.flatMap(wire => {
        const length = wire.getTotalLength();
        const sampleCount = Math.max(20, Math.ceil(length / 3));
        return Array.from({ length: sampleCount }, (_, index) => {
          const point = wire.getPointAtLength(length * (index + 0.5) / sampleCount);
          const blocker = nodes.find(node => {
            const left = node.left - bounds.left;
            const right = node.right - bounds.left;
            const top = node.top - bounds.top;
            const bottom = node.bottom - bounds.top;
            return point.x > left + 1 && point.x < right - 1 && point.y > top + 1 && point.y < bottom - 1;
          });
          return blocker ? `${wire.dataset.edge}/${blocker.name}` : "";
        }).filter(Boolean);
      });
      const connectedBranchPairs = new Set([
        ["resource-branch-trunk", "resource-cost"].sort().join("/"),
        ["resource-branch-trunk", "resource-performance"].sort().join("/"),
      ]);
      const trunk = wires.find(wire => wire.dataset.edge === "resource-branch-trunk");
      const branchConnectionErrors = wires.filter(wire =>
        wire.dataset.edge === "resource-cost" || wire.dataset.edge === "resource-performance",
      ).filter(wire => {
        if (!trunk) return true;
        const start = wire.getPointAtLength(0);
        const length = trunk.getTotalLength();
        const steps = Math.max(50, Math.ceil(length));
        let nearest = Number.POSITIVE_INFINITY;
        for (let index = 0; index <= steps; index += 1) {
          const point = trunk.getPointAtLength(length * index / steps);
          nearest = Math.min(nearest, Math.hypot(start.x - point.x, start.y - point.y));
        }
        return nearest > 0.75;
      }).map(wire => wire.dataset.edge);
      const samplesByWire = new Map(wires.map(wire => {
        const length = wire.getTotalLength();
        const count = Math.max(2, Math.ceil(length / 3));
        return [wire, Array.from({ length: count + 1 }, (_, index) => wire.getPointAtLength(length * index / count))] as const;
      }));
      const routeCollisions = wires.flatMap((wire, index) => wires.slice(index + 1).flatMap(other => {
        const pair = [wire.dataset.edge ?? "", other.dataset.edge ?? ""].sort().join("/");
        if (connectedBranchPairs.has(pair)) return [];
        const first = samplesByWire.get(wire) ?? [];
        const second = samplesByWire.get(other) ?? [];
        const collides = first.some(point => second.some(candidate => Math.hypot(point.x - candidate.x, point.y - candidate.y) < 1.5));
        return collides ? [pair] : [];
      }));
      const overflowingAgentTitles = [...canvas.querySelectorAll<HTMLElement>(".demo-agent b")]
        .filter(title => title.scrollWidth > title.clientWidth + 1)
        .map(title => title.textContent?.trim() ?? "");
      const feedback = wires.find(wire => wire.dataset.edge === "effect-resource");
      const feedbackStyle = feedback ? getComputedStyle(feedback) : null;
      const feedbackTail = canvas.querySelector<SVGPathElement>(".demo-wire-feedback-tail");
      const feedbackTailJoinError = feedback && feedbackTail
        ? (() => {
          const end = feedback.getPointAtLength(feedback.getTotalLength());
          const tailEnd = feedbackTail.getPointAtLength(feedbackTail.getTotalLength());
          return Math.hypot(end.x - tailEnd.x, end.y - tailEnd.y);
        })()
        : null;
      return {
        nodes,
        oversizedNodes: nodes.filter(node => node.height > 84).map(node => node.name),
        overlaps,
        outside,
        wireCount: wires.length,
        directedEdgeCount: arrowheads.length,
        edgeGraphErrors,
        emptyWires: wires.filter(wire => !wire.getAttribute("d")?.trim()).map(wire => wire.dataset.edge),
        missingAgentAdmissionEdges: ["cost-admission", "performance-admission"].filter(id => !wires.some(wire => wire.dataset.edge === id)),
        connectorIntersections,
        routeCollisions,
        anchorErrors,
        branchConnectionErrors,
        arrowDirectionErrors,
        agentAdmissionCurveErrors,
        arrowheadErrors,
        arrowheadIntersections,
        missingArrows,
        trunkHasArrow,
        markerCount: canvas.querySelectorAll("marker").length,
        arrowheadCount: arrowheads.length,
        feedbackTailJoinError,
        feedbackTailDasharray: feedbackTail ? getComputedStyle(feedbackTail).strokeDasharray : null,
        feedbackDashed: Boolean(feedbackStyle && feedbackStyle.strokeDasharray !== "none"),
        feedbackStrokeWidth: feedbackStyle ? Number.parseFloat(feedbackStyle.strokeWidth) : null,
        feedbackOpacity: feedbackStyle ? Number.parseFloat(feedbackStyle.opacity) : null,
        overflowingAgentTitles,
        wiresHidden: getComputedStyle(canvas.querySelector(".demo-wires")!).display === "none",
      };
    });
    expect(diagramLayout.nodes).toHaveLength(10);
    expect(diagramLayout.oversizedNodes).toEqual([]);
    expect(diagramLayout.overlaps).toEqual([]);
    expect(diagramLayout.outside).toEqual([]);
    expect(diagramLayout.wireCount).toBe(12);
    expect(diagramLayout.directedEdgeCount).toBe(11);
    expect(diagramLayout.edgeGraphErrors).toEqual([]);
    expect(diagramLayout.emptyWires).toEqual([]);
    expect(diagramLayout.missingAgentAdmissionEdges).toEqual([]);
    expect(diagramLayout.connectorIntersections).toEqual([]);
    expect(diagramLayout.routeCollisions).toEqual([]);
    expect(diagramLayout.anchorErrors).toEqual([]);
    expect(diagramLayout.branchConnectionErrors).toEqual([]);
    expect(diagramLayout.arrowDirectionErrors).toEqual([]);
    expect(diagramLayout.agentAdmissionCurveErrors).toEqual([]);
    expect(diagramLayout.arrowheadErrors).toEqual([]);
    expect(diagramLayout.arrowheadIntersections).toEqual([]);
    expect(diagramLayout.missingArrows).toEqual([]);
    expect(diagramLayout.trunkHasArrow).toBe(false);
    expect(diagramLayout.markerCount).toBe(0);
    expect(diagramLayout.arrowheadCount).toBe(11);
    expect(diagramLayout.feedbackTailJoinError).not.toBeNull();
    expect(diagramLayout.feedbackTailJoinError!).toBeLessThan(0.01);
    expect(diagramLayout.feedbackTailDasharray).toBe("none");
    expect(diagramLayout.feedbackDashed).toBe(true);
    expect(diagramLayout.feedbackStrokeWidth).not.toBeNull();
    expect(diagramLayout.feedbackStrokeWidth!).toBeLessThan(2.4);
    expect(diagramLayout.feedbackOpacity).not.toBeNull();
    expect(diagramLayout.feedbackOpacity!).toBeLessThan(0.8);
    expect(diagramLayout.overflowingAgentTitles).toEqual([]);
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
    await page.locator(".orchestration-demo").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `visual-review/system-model-${name}.png` });
    await page.locator(".demo-canvas").evaluate(canvas => {
      const bounds = canvas.getBoundingClientRect();
      const overlay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      overlay.setAttribute("data-geometry-overlay", "");
      overlay.setAttribute("viewBox", `0 0 ${bounds.width} ${bounds.height}`);
      overlay.style.cssText = "position:absolute;inset:0;width:100%;height:100%;z-index:5;pointer-events:none";
      const add = (tag: string, attributes: Record<string, string>) => {
        const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
        for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
        overlay.append(element);
      };
      for (const node of canvas.querySelectorAll<HTMLElement>(".demo-diagram [data-node]")) {
        const rect = node.getBoundingClientRect();
        add("rect", { x: String(rect.left - bounds.left), y: String(rect.top - bounds.top), width: String(rect.width), height: String(rect.height), fill: "none", stroke: "#e8c47c", "stroke-width": "1" });
      }
      for (const wire of canvas.querySelectorAll<SVGPathElement>(".demo-wire:not([data-edge='resource-branch-trunk'])")) {
        const end = wire.getPointAtLength(wire.getTotalLength());
        const start = wire.getPointAtLength(0);
        const head = canvas.querySelector<SVGPolygonElement>(`.demo-arrowhead[data-arrow-for="${wire.dataset.edge}"]`);
        const tip = head?.points.getItem(0);
        for (const [point, color] of [[start, "#a7d8e4"], [end, "#f4b0a5"], [tip, "#c7eead"]] as const) {
          if (point) add("circle", { cx: String(point.x), cy: String(point.y), r: "2.5", fill: color });
        }
      }
      canvas.append(overlay);
    });
    await page.screenshot({ path: `visual-review/system-model-debug-${name}.png` });
    await page.locator("[data-geometry-overlay]").evaluate(overlay => overlay.remove());
  }

  expect(apiRequests).toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  for (const [viewport, width, height] of [["desktop", 1440, 900], ["laptop", 1280, 800], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
  for (const [index, label] of ["Observe", "Propose", "Admit", "Deliver", "Commit", "Contain", "Investigate"].entries()) {
    await page.getByRole("button", { name: `${index + 1}. ${label}` }).click();
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())));
    const inactiveEndpoints = await page.locator(".demo-wires").evaluate(svg => {
      const activeNodes = new Set([...document.querySelectorAll<HTMLElement>(".demo-diagram [data-node].is-active")]
        .map(node => node.dataset.node ?? ""));
      return [...svg.querySelectorAll<SVGPathElement>(".demo-wire.is-active")]
        .flatMap(edge => [edge.dataset.source ?? "", edge.dataset.target ?? ""])
        .filter(node => node && !activeNodes.has(node));
    });
    expect(inactiveEndpoints, `all edge endpoints should be highlighted during ${label}`).toEqual([]);
    const activeStyles = await page.locator(".demo-wire.is-active:not(.is-feedback)").evaluateAll(edges => edges.map(edge => {
      const style = getComputedStyle(edge);
      return { strokeDasharray: style.strokeDasharray, strokeWidth: style.strokeWidth };
    }));
    expect(activeStyles, `active edges should remain present during ${label}`).not.toHaveLength(0);
    expect(activeStyles.map(style => style.strokeDasharray), `active paths should not break before arrowheads during ${label}`)
      .toEqual(activeStyles.map(() => "none"));
    expect(new Set(activeStyles.map(style => style.strokeWidth)).size, `active primary edges should share a stroke width during ${label}`)
      .toBe(1);
    const activeTargetErrors = await page.locator(".demo-canvas").evaluate(canvas => {
      const canvasRect = canvas.getBoundingClientRect();
      const nodes = new Map([...canvas.querySelectorAll<HTMLElement>(".demo-diagram [data-node]")].map(node => [
        node.dataset.node ?? "",
        node.getBoundingClientRect(),
      ]));
      const paths = [...canvas.querySelectorAll<SVGPathElement>(".demo-wire.is-active:not(.is-feedback)")]
        .filter(edge => edge.dataset.edge !== "resource-branch-trunk");
      return paths.flatMap(edge => {
        const target = nodes.get(edge.dataset.target ?? "");
        if (!target) return [edge.dataset.edge ?? "unknown-target"];
        const head = canvas.querySelector<SVGPolygonElement>(`.demo-arrowhead[data-arrow-for="${edge.dataset.edge}"]`);
        if (!head) return [edge.dataset.edge ?? "missing-arrowhead"];
        const point = head.points.getItem(0);
        const x = point.x + canvasRect.left;
        const y = point.y + canvasRect.top;
        const verticalAligned = y >= target.top - 0.75 && y <= target.bottom + 0.75;
        const horizontalAligned = x >= target.left - 0.75 && x <= target.right + 0.75;
        const expectedGap = 2.5;
        const gaps = [
          { distance: target.left - x, aligned: verticalAligned },
          { distance: x - target.right, aligned: verticalAligned },
          { distance: target.top - y, aligned: horizontalAligned },
          { distance: y - target.bottom, aligned: horizontalAligned },
        ];
        return gaps.some(gap => gap.aligned && Math.abs(gap.distance - expectedGap) <= 0.75)
          ? []
          : [edge.dataset.edge ?? "unknown-edge"];
      });
    });
    expect(activeTargetErrors, `active arrow tips should keep a 2.5px target gap during ${label} at ${viewport}`).toEqual([]);
  }
  }
  await page.getByRole("button", { name: /7\. Investigate/ }).click();
  await expect(page.locator(".demo-story")).toContainText("Operators can inspect the evidence");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("link", { name: /Launch console/i }).first().click();
  await expect(page).toHaveURL(/\/app$/);
  await signIn(page);
  await expect(page.locator(".topbar .pill")).toHaveText("Connected");
  await expect(page.getByRole("heading", { name: "Mission control" })).toBeVisible();
});
