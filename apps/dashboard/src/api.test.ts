import { expect, it, vi } from "vitest";
import { get, post } from "./api";

it("returns backend data", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => [{ id: "agent" }],
  }));
  expect(await get("/agents")).toEqual([{ id: "agent" }]);
});

it("surfaces backend downtime", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 }));
  await expect(get("/agents")).rejects.toThrow("503");
});

it("submits a bounded comparison and returns persisted results", async () => {
  const result = { run_id: "run", summaries: [] };
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => result });
  vi.stubGlobal("fetch", fetchMock);
  expect(await post("/experiments", { scenario: "oscillation", seeds: [17], duration: 120 })).toEqual(result);
  expect(fetchMock).toHaveBeenCalledWith("/api/experiments", expect.objectContaining({
    method: "POST",
    body: JSON.stringify({ scenario: "oscillation", seeds: [17], duration: 120 }),
  }));
});
