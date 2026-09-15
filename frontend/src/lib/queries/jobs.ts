"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Job } from "@/lib/types";

export const jobKeys = {
  all: ["jobs"] as const,
  detail: (id: string) => ["jobs", id] as const,
};

const POLL_MS = 2000;

/** Intervalle de sondage : 2 s tant que le job n'est pas terminé (ou pas encore chargé), puis arrêt. */
export function pollInterval(job: Job | undefined): number | false {
  if (!job) return POLL_MS;
  return job.status === "pending" || job.status === "running" ? POLL_MS : false;
}

export function useJob(id: string | null, { poll = true }: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: jobKeys.detail(id ?? ""),
    queryFn: () => api<Job>(`/jobs/${id}`),
    enabled: id !== null,
    refetchInterval: poll ? (query) => pollInterval(query.state.data) : false,
  });
}
