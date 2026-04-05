import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchJson } from "./client";

describe("fetchJson", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed json for ok responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      text: async () => JSON.stringify({ ok: true }),
    }));

    await expect(fetchJson("/api/test")).resolves.toEqual({ ok: true });
  });

  it("throws the server detail for failed json responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      headers: { get: () => "application/json" },
      text: async () => JSON.stringify({ detail: { message: "bad request" } }),
    }));

    await expect(fetchJson("/api/test")).rejects.toMatchObject({ message: "bad request" });
  });

  it("throws a helpful message for html responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "text/html" },
      text: async () => "<html></html>",
    }));

    await expect(fetchJson("/api/test")).rejects.toThrow("Server returned HTML instead of JSON");
  });
});
