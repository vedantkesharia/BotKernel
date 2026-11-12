import { afterEach, expect, it, vi } from "vitest";
import { clearOperatorToken, get, hasOperatorToken, login, onUnauthorized, post } from "./api";

afterEach(() => { clearOperatorToken(); vi.unstubAllGlobals(); });

it("returns backend data", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => [{ id: "agent" }],
  }));
  expect(await get("/agents")).toEqual([{ id: "agent" }]);
});

it("authenticates requests in memory and clears access on 401", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ role: "operator" }) })
    .mockResolvedValueOnce({ ok: true, json: async () => [] })
    .mockResolvedValueOnce({ ok: false, status: 401 });
  vi.stubGlobal("fetch", fetchMock);
  const expired = vi.fn();
  const unsubscribe = onUnauthorized(expired);
  await login("private-token");
  expect(hasOperatorToken()).toBe(true);
  await get("/agents");
  expect((fetchMock.mock.calls[1][1].headers as Headers).get("Authorization")).toBe("Bearer private-token");
  await expect(get("/incidents")).rejects.toThrow("401");
  expect(expired).toHaveBeenCalledOnce();
  expect(hasOperatorToken()).toBe(false);
  unsubscribe();
});

it("does not retain an invalid credential", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
  await expect(login("wrong")).rejects.toThrow("401");
  expect(hasOperatorToken()).toBe(false);
});

it("does not sign out a new session when an old request returns 401", async () => {
  let finishOld!: (value: { ok: false; status: number }) => void;
  const pending = new Promise<{ ok: false; status: number }>(resolve => { finishOld = resolve; });
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce({ ok: true })
    .mockReturnValueOnce(pending)
    .mockResolvedValueOnce({ ok: true }));
  const expired = vi.fn();
  const unsubscribe = onUnauthorized(expired);
  await login("old-token");
  const oldRequest = get("/incidents");
  await login("new-token");
  finishOld({ ok: false, status: 401 });
  await expect(oldRequest).rejects.toThrow("401");
  expect(hasOperatorToken()).toBe(true);
  expect(expired).not.toHaveBeenCalled();
  unsubscribe();
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
