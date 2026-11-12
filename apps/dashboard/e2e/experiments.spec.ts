import { expect, test } from "@playwright/test";

test("runs a backend-backed comparison and keeps the lab usable on mobile", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1365, height: 900 });
  await page.goto("/experiments");
  await expect(page.getByRole("heading", { name: "Experiment lab" })).toBeVisible();
  await page.getByLabel("Random seeds").fill("101");
  const creation = page.waitForResponse(
    (response) => response.url().endsWith("/experiments") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run three-mode comparison" }).click();
  expect((await creation).status()).toBe(201);

  const results = page.getByRole("region", { name: "Experiment results" });
  await expect(results).toBeVisible();
  await expect(results.getByRole("heading", { name: "Cost / performance oscillation" })).toBeVisible();
  await expect(results.locator("tbody tr")).toHaveCount(3);
  await expect(results.getByRole("application")).toBeVisible();
  await expect(results.getByRole("link", { name: "report.md" })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Experiment lab" })).toBeVisible();
  await expect(page.locator(".experiment-results")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mobile-strategy")).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(browserErrors).toEqual([]);
});

test("shows backend errors and rejects duplicate seeds before submission", async ({ page }) => {
  await page.route("**/api/experiments", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"unavailable"}' });
    } else {
      await route.continue();
    }
  });
  await page.goto("/experiments");
  await expect(page.getByRole("alert").filter({ hasText: "Unable to load saved experiments" })).toBeVisible();

  await page.getByLabel("Random seeds").fill("17,17");
  const request = page.waitForRequest(
    (candidate) => candidate.url().endsWith("/experiments") && candidate.method() === "POST",
    { timeout: 500 },
  ).catch(() => null);
  await page.getByRole("button", { name: "Run three-mode comparison" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "unique integer seeds" })).toBeVisible();
  expect(await request).toBeNull();
});

test("inspects committed graph relationships and incident evidence", async ({ page, request }) => {
  const api = "http://127.0.0.1:5187/api";
  const agent = `graph-e2e-${crypto.randomUUID()}`;
  const registered = await request.post(`${api}/agents/${agent}`);
  expect(registered.ok()).toBeTruthy();

  const resourcesResponse = await request.get(`${api}/resources`);
  expect(resourcesResponse.ok()).toBeTruthy();
  const resources = await resourcesResponse.json() as { id: string; capacity: number; version: number }[];
  const resource = resources.find((item) => item.id === "service-b") ?? resources[0];
  if (!resource) throw new Error("The isolated API has no simulator resource.");

  let latestActionId = "";
  for (const delta of [1, -1]) {
    const currentResponse = await request.get(`${api}/resources`);
    const currentResources = await currentResponse.json() as { id: string; capacity: number; version: number }[];
    const current = currentResources.find((item) => item.id === resource.id);
    if (!current) throw new Error(`Simulator resource ${resource.id} disappeared.`);
    const submitted = await request.post(`${api}/actions`, {
      data: {
        agent,
        workflow: "dashboard-e2e",
        idempotency_key: crypto.randomUUID(),
        resource: current.id,
        expected_version: current.version,
        capacity: current.capacity + delta,
      },
    });
    expect(submitted.status()).toBe(202);
    const action = await submitted.json() as { id: string };
    latestActionId = action.id;
    await expect.poll(async () => {
      const actionsResponse = await request.get(`${api}/actions`);
      const actions = await actionsResponse.json() as { id: string; state: string }[];
      return actions.find((item) => item.id === action.id)?.state;
    }, { timeout: 20_000 }).toBe("SUCCEEDED");
  }

  await page.goto("/graph");
  const nodes = page.locator(".react-flow__node");
  await expect(nodes.first()).toBeVisible();
  await expect(page.locator(".react-flow__edge").first()).toBeVisible();
  await nodes.first().click();
  await expect(page.locator(".selection")).toContainText("Selected");
  await page.locator(".react-flow__edge").first().dispatchEvent("click");
  await expect(page.locator(".selection")).toContainText("Selected edge:");
  const incidentFilter = page.getByLabel("Highlight incident");
  await incidentFilter.click();
  const incidentOptions = page.getByRole("option").filter({ hasText: "Incident #" });
  if (await incidentOptions.count() > 0) {
    await incidentOptions.first().click();
    await expect(incidentFilter).toContainText("Incident #");
  } else {
    await page.keyboard.press("Escape");
  }
  await page.getByLabel("Filter graph nodes").fill("no-matching-resource");
  await expect(page.getByText("No evidence in view")).toBeVisible();
  await expect(page.locator(".react-flow__edge")).toHaveCount(0);

  await page.goto(`/graph?${new URLSearchParams({ action: latestActionId, resource: resource.id })}`);
  await expect(page.getByText(`action:${latestActionId}`, { exact: true })).toBeVisible();
  await page.getByLabel("Filter graph nodes").fill("no-matching-resource");
  await expect(page.getByText(`action:${latestActionId}`, { exact: true })).toBeVisible();
  await page.getByLabel("Graph time window").click();
  await page.getByRole("option", { name: "Last 15 minutes" }).click();
  await expect(page.getByText(`action:${latestActionId}`, { exact: true })).toBeVisible();

  await page.goto("/incidents");
  const incident = page.locator(".incident-detail").first();
  await expect(incident).toBeVisible();
  await expect(incident.locator(".timeline")).toContainText("sustained recovery verified");
  await incident.locator("summary").filter({ hasText: "Referenced action IDs and raw evidence" }).click();
  await expect(incident.locator("pre")).toContainText("reversal_pairs");
});

test("mobile navigation opens the agent workspace", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/graph");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("complementary", { name: "Primary navigation" })).toBeVisible();
  await page.getByRole("link", { name: "Agent fleet" }).click();
  await expect(page.getByRole("heading", { name: "Agent fleet" })).toBeVisible();
  await expect(page.locator(".identity-panel")).toBeVisible();
  await expect(page.locator(".fleet-row-copy").first()).toBeVisible();
  expect(await page.locator(".fleet-row-copy").first().evaluate((element) => element.clientWidth)).toBeGreaterThan(100);
  await page.getByLabel("Search agents").fill("no-such-agent");
  await expect(page.getByText("No agents found")).toBeVisible();
  await expect(page.locator(".identity-panel")).toHaveCount(0);
});

test("mobile navigation traps focus and closes with Escape", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/app");
  const trigger = page.getByRole("button", { name: "Open navigation" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const navigation = page.getByRole("dialog", { name: "Primary navigation" });
  await expect(navigation).toBeVisible();
  await page.keyboard.press("Tab");
  expect(await navigation.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(navigation).toBeHidden();
  await expect(trigger).toBeFocused();
});
