import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  documentKeys,
  useArchiveDocument,
  useNewVersion,
  useUpdateDocument,
  useUploadDocument,
} from "@/lib/queries/documents";

function setup() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const status = init?.method === "DELETE" ? 204 : 200;
      return { ok: true, status, json: async () => ({ id: "d1" }) } as unknown as Response;
    }),
  );
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  return { qc, invalidate, calls, wrapper };
}

afterEach(() => vi.unstubAllGlobals());

describe("document mutations", () => {
  it("uploads a multipart body without forcing a JSON content-type, then refreshes the list", async () => {
    const { calls, invalidate, wrapper } = setup();
    const { result } = renderHook(() => useUploadDocument(), { wrapper });
    const form = new FormData();
    form.set("category", "cv");
    await result.current.mutateAsync(form);

    expect(calls[0].url).toBe("/api/v1/documents");
    expect(calls[0].init?.method).toBe("POST");
    expect(calls[0].init?.body).toBe(form);
    expect((calls[0].init?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: documentKeys.all }));
  });

  it("adds a version to a document and refreshes its detail and versions", async () => {
    const { calls, invalidate, wrapper } = setup();
    const { result } = renderHook(() => useNewVersion(), { wrapper });
    const form = new FormData();
    await result.current.mutateAsync({ id: "d1", form });
    expect(calls[0].url).toBe("/api/v1/documents/d1/versions");
    expect(calls[0].init?.body).toBe(form);
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: documentKeys.all }));
  });

  it("patches metadata as JSON", async () => {
    const { calls, wrapper } = setup();
    const { result } = renderHook(() => useUpdateDocument(), { wrapper });
    await result.current.mutateAsync({ id: "d1", values: { name: "Nouveau nom", tags: ["a"] } });
    expect(calls[0].url).toBe("/api/v1/documents/d1");
    expect(calls[0].init?.method).toBe("PATCH");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ name: "Nouveau nom", tags: ["a"] });
  });

  it("archives with DELETE", async () => {
    const { calls, invalidate, wrapper } = setup();
    const { result } = renderHook(() => useArchiveDocument(), { wrapper });
    await result.current.mutateAsync("d1");
    expect(calls[0].url).toBe("/api/v1/documents/d1");
    expect(calls[0].init?.method).toBe("DELETE");
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: documentKeys.all }));
  });
});
