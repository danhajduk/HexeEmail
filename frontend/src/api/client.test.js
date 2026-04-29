import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchJson } from "./client";

describe("fetchJson", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("targets the backend on the address-bar host", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      text: async () => JSON.stringify({ ok: true }),
    });
    vi.stubGlobal("window", {
      location: {
        protocol: "http:",
        hostname: "192.168.1.23",
      },
    });
    vi.stubGlobal("fetch", fetch);

    await fetchJson("/api/test");

    expect(fetch).toHaveBeenCalledWith("http://192.168.1.23:9003/api/test", expect.any(Object));
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
