"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import { tenderKeys } from "@/lib/queries/tenders";
import type { EligibilitySummary, Job, RequirementUpdate, TenderRequirement } from "@/lib/types";

export const requirementKeys = {
  list: (id: string) => ["tenders", "detail", id, "requirements"] as const,
  eligibility: (id: string) => ["tenders", "detail", id, "eligibility"] as const,
};

/** Exigences extraites du dossier, triées par code (`ADM-001`, `TECH-001`…). */
export function useRequirements(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: requirementKeys.list(id),
    queryFn: () => api<TenderRequirement[]>(`/tenders/${id}/requirements`),
    enabled,
  });
}

/** Synthèse d'éligibilité ; `null` tant qu'elle n'a pas été évaluée (404 `eligibility_missing`). */
export function useEligibility(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: requirementKeys.eligibility(id),
    queryFn: async () => {
      try {
        return await api<EligibilitySummary>(`/tenders/${id}/eligibility`);
      } catch (e) {
        if (e instanceof ApiError && e.code === "eligibility_missing") return null;
        throw e;
      }
    },
    enabled,
  });
}

/** POST /tenders/{id}/eligibility — job `evaluate_eligibility`, qui enchaîne sur les questions (202). */
export function useLaunchEligibility(id: string) {
  return useMutation({
    mutationFn: () => api<Job>(`/tenders/${id}/eligibility`, { method: "POST" }),
  });
}

/** PATCH /requirements/{id} — statut, justification, caractère obligatoire ou priorité saisis à la main. */
export function useUpdateRequirement(tenderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ requirementId, patch }: { requirementId: string; patch: RequirementUpdate }) =>
      api<TenderRequirement>(`/requirements/${requirementId}`, { method: "PATCH", body: JSON.stringify(patch) }),
    // Le statut manuel change le résumé d'éligibilité et le score à la prochaine évaluation.
    onSuccess: () => qc.invalidateQueries({ queryKey: tenderKeys.detail(tenderId) }),
  });
}
