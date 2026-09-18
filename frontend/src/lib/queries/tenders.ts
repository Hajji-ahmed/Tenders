"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import type {
  DecisionKind,
  Job,
  Kanban,
  Page,
  StatusHistoryEntry,
  Tender,
  TenderDetail,
  TenderScore,
  TenderSourceLink,
  TenderStatus,
} from "@/lib/types";

export type TenderFilters = {
  q?: string;
  status?: TenderStatus;
  country?: string;
  sector?: string;
  active_only?: boolean;
  sort?: string;
  page?: number;
  size?: number;
};

export const tenderKeys = {
  all: ["tenders"] as const,
  list: (filters: TenderFilters) => ["tenders", "list", filters] as const,
  detail: (id: string) => ["tenders", "detail", id] as const,
  sources: (id: string) => ["tenders", "detail", id, "sources"] as const,
  score: (id: string) => ["tenders", "detail", id, "score"] as const,
  history: (id: string) => ["tenders", "detail", id, "history"] as const,
  kanban: ["tenders", "kanban"] as const,
};

function toQuery(filters: TenderFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useTenders(filters: TenderFilters = {}) {
  return useQuery({
    queryKey: tenderKeys.list(filters),
    queryFn: () => api<Page<Tender>>(`/tenders${toQuery(filters)}`),
  });
}

export function useTender(id: string | null) {
  return useQuery({
    queryKey: tenderKeys.detail(id ?? ""),
    queryFn: () => api<TenderDetail>(`/tenders/${id}`),
    enabled: id !== null,
  });
}

/** Annonces à l'origine d'une fiche (doublons regroupés) — chargées à la demande (`enabled`). */
export function useTenderSources(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: tenderKeys.sources(id),
    queryFn: () => api<TenderSourceLink[]>(`/tenders/${id}/sources`),
    enabled,
  });
}

/** Score d'une fiche ; `null` tant qu'il n'a pas été calculé (404 `score_missing`). */
export function useTenderScore(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: tenderKeys.score(id),
    queryFn: async () => {
      try {
        return await api<TenderScore>(`/tenders/${id}/score`);
      } catch (e) {
        if (e instanceof ApiError && e.code === "score_missing") return null;
        throw e;
      }
    },
    enabled,
  });
}

export function useTenderHistory(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: tenderKeys.history(id),
    queryFn: () => api<StatusHistoryEntry[]>(`/tenders/${id}/history`),
    enabled,
  });
}

export function useKanban() {
  return useQuery({ queryKey: tenderKeys.kanban, queryFn: () => api<Kanban>("/tenders/kanban") });
}

/** Toute mutation sur une fiche invalide l'arbre `tenders` : listes, détail, score, kanban. */
function useInvalidateTenders() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: tenderKeys.all });
}

/** POST /tenders/{id}/score — enfile le job `calculate_match_score` (202 + JobOut). */
export function useLaunchScoring() {
  return useMutation({
    mutationFn: (id: string) => api<Job>(`/tenders/${id}/score`, { method: "POST" }),
  });
}

export function useDecide() {
  const invalidate = useInvalidateTenders();
  return useMutation({
    mutationFn: ({ id, decision, reason }: { id: string; decision: DecisionKind; reason: string | null }) =>
      api<Tender>(`/tenders/${id}/decision`, { method: "POST", body: JSON.stringify({ decision, reason }) }),
    onSuccess: () => invalidate(),
  });
}

export function useChangeStatus() {
  const invalidate = useInvalidateTenders();
  return useMutation({
    mutationFn: ({ id, status, comment }: { id: string; status: TenderStatus; comment?: string | null }) =>
      api<Tender>(`/tenders/${id}/status`, { method: "POST", body: JSON.stringify({ status, comment: comment ?? null }) }),
    onSuccess: () => invalidate(),
  });
}
