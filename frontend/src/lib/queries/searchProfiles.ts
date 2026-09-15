"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { jobKeys } from "@/lib/queries/jobs";
import type { Job, Page, SearchProfile } from "@/lib/types";

export const searchProfileKeys = {
  all: ["search-profiles"] as const,
  searches: ["searches"] as const,
};

export function useSearchProfiles() {
  return useQuery({
    queryKey: searchProfileKeys.all,
    queryFn: () => api<Page<SearchProfile>>("/search-profiles?page=1&size=100"),
  });
}

function useInvalidateProfiles() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: searchProfileKeys.all });
}

export function useCreateSearchProfile() {
  const invalidate = useInvalidateProfiles();
  return useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api<SearchProfile>("/search-profiles", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateSearchProfile() {
  const invalidate = useInvalidateProfiles();
  return useMutation({
    mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) =>
      api<SearchProfile>(`/search-profiles/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
    onSuccess: () => invalidate(),
  });
}

export function useDeleteSearchProfile() {
  const invalidate = useInvalidateProfiles();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/search-profiles/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  });
}

/** Dernières recherches lancées (jobs `search_tenders`). */
export function useSearches() {
  return useQuery({
    queryKey: searchProfileKeys.searches,
    queryFn: () => api<Job[]>("/searches?limit=10"),
  });
}

/** POST /searches → 202 : le job démarre côté worker ; on met en cache sa première version. */
export function useLaunchSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (searchProfileId: string) =>
      api<Job>("/searches", { method: "POST", body: JSON.stringify({ search_profile_id: searchProfileId }) }),
    onSuccess: (job) => {
      qc.setQueryData(jobKeys.detail(job.id), job);
      qc.invalidateQueries({ queryKey: searchProfileKeys.searches });
    },
  });
}
