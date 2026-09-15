"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page, SourceTestReport, TenderSource } from "@/lib/types";

export const sourceKeys = { all: ["sources"] as const };

export function useSources() {
  return useQuery({
    queryKey: sourceKeys.all,
    queryFn: () => api<Page<TenderSource>>("/sources?page=1&size=100"),
  });
}

function useInvalidateSources() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: sourceKeys.all });
}

export function useCreateSource() {
  const invalidate = useInvalidateSources();
  return useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api<TenderSource>("/sources", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateSource() {
  const invalidate = useInvalidateSources();
  return useMutation({
    mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) =>
      api<TenderSource>(`/sources/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
    onSuccess: () => invalidate(),
  });
}

export function useDeleteSource() {
  const invalidate = useInvalidateSources();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/sources/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  });
}

/** POST /sources/{id}/test : collecte limitée, rien n'est enregistré. */
export function useTestSource() {
  return useMutation({
    mutationFn: (id: string) => api<SourceTestReport>(`/sources/${id}/test`, { method: "POST" }),
  });
}
