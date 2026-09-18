import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tenderKeys, useTenderSources } from "@/lib/queries/tenders";

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      return { ok: true, status: 200, json: async () => [{ id: "l1", url: "https://a/1" }] } as unknown as Response;
    }),
  );
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  return { calls, wrapper };
}

afterEach(() => vi.unstubAllGlobals());

describe("useTenderSources", () => {
  it("loads the provenance links of a tender under its own query key", async () => {
    const { calls, wrapper } = setup();
    const { result } = renderHook(() => useTenderSources("t1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toEqual(["/api/v1/tenders/t1/sources"]);
    expect(result.current.data).toEqual([{ id: "l1", url: "https://a/1" }]);
    expect(tenderKeys.sources("t1")).toEqual(["tenders", "detail", "t1", "sources"]);
  });

  it("does not fetch while disabled (list closed)", async () => {
    const { calls, wrapper } = setup();
    const { result } = renderHook(() => useTenderSources("t1", { enabled: false }), { wrapper });
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toEqual([]);
    expect(result.current.fetchStatus).toBe("idle");
  });
});
