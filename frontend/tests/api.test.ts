import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, toApiError } from "@/lib/api";

function mockFetch(responses: Array<{ status: number; body?: unknown; text?: string; statusText?: string }>) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const r = responses.shift() ?? { status: 200, body: {} };
    return {
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      statusText: r.statusText ?? "",
      json: async () => {
        if (r.text !== undefined) throw new SyntaxError("not json");
        return r.body;
      },
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

describe("toApiError", () => {
  it("reads the standard envelope", () => {
    const e = toApiError(422, { error: { code: "validation_error", message: "email : invalide" } });
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("validation_error");
    expect(e.message).toBe("email : invalide");
  });

  it("handles a string error (slowapi) and maps 429", () => {
    const e = toApiError(429, { error: "Rate limit exceeded: 5 per 1 minute" });
    expect(e.code).toBe("rate_limited");
    expect(e.message).toContain("Rate limit exceeded");
  });

  it("never produces an empty message (HTTP/2 has no statusText)", () => {
    expect(toApiError(502, undefined, "").message).toBe("Le serveur est momentanément indisponible.");
    expect(toApiError(418, undefined, "").message).toBe("Erreur HTTP 418");
  });
});

describe("api()", () => {
  beforeEach(() => {
    vi.stubGlobal("location", { pathname: "/dashboard", href: "" });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("returns undefined on 204", async () => {
    mockFetch([{ status: 204 }]);
    await expect(api<void>("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("throws ApiError with a French fallback on non-JSON bodies", async () => {
    mockFetch([{ status: 502, text: "<html>Bad Gateway</html>" }]);
    await expect(api("/x")).rejects.toMatchObject({ status: 502, message: expect.stringContaining("indisponible") });
  });

  it("on 401 outside /login: calls logout then redirects", async () => {
    const calls = mockFetch([{ status: 401, body: { error: { code: "unauthorized", message: "x" } } }, { status: 204 }]);
    await expect(api("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(calls[1]?.url).toBe("/api/v1/auth/logout");
    expect(location.href).toBe("/login");
  });

  it("on 401 on /login: no redirect", async () => {
    vi.stubGlobal("location", { pathname: "/login", href: "" });
    const calls = mockFetch([{ status: 401, body: { error: { code: "invalid_credentials", message: "nope" } } }]);
    await expect(api("/auth/login", { method: "POST" })).rejects.toMatchObject({ code: "invalid_credentials" });
    expect(calls).toHaveLength(1);
    expect(location.href).toBe("");
  });
});
