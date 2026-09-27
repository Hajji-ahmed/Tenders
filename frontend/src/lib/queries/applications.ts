"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import { tenderKeys } from "@/lib/queries/tenders";
import type { Application, ApplicationDocument, Job, Page, Template } from "@/lib/types";

export const applicationKeys = {
  ofTender: (id: string) => ["tenders", "detail", id, "application"] as const,
  templates: ["templates"] as const,
};

/** Dossier de candidature d'une fiche ; `null` tant qu'il n'a pas été ouvert (404 `application_missing`). */
export function useApplication(tenderId: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: applicationKeys.ofTender(tenderId),
    queryFn: async () => {
      try {
        return await api<Application>(`/tenders/${tenderId}/application`);
      } catch (e) {
        if (e instanceof ApiError && e.code === "application_missing") return null;
        throw e;
      }
    },
    enabled,
  });
}

/** Modèles de documents disponibles (semés par `seed-templates`). */
export function useTemplates({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: applicationKeys.templates,
    queryFn: () => api<Page<Template>>("/templates?size=50"),
    enabled,
    staleTime: 5 * 60_000, // les plans changent rarement
  });
}

function useInvalidateTender(tenderId: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: tenderKeys.detail(tenderId) });
}

/** POST /tenders/{id}/application — ouvre le dossier (la fiche passe en préparation). */
export function useOpenApplication(tenderId: string) {
  const invalidate = useInvalidateTender(tenderId);
  return useMutation({
    mutationFn: () => api<Application>(`/tenders/${tenderId}/application`, { method: "POST" }),
    onSuccess: () => invalidate(),
  });
}

/** POST /applications/{id}/documents — ajoute un document par modèle choisi. */
export function useAddDocuments(tenderId: string) {
  const invalidate = useInvalidateTender(tenderId);
  return useMutation({
    mutationFn: ({ applicationId, templateIds }: { applicationId: string; templateIds: string[] }) =>
      api<ApplicationDocument[]>(`/applications/${applicationId}/documents`, {
        method: "POST",
        body: JSON.stringify({ template_ids: templateIds }),
      }),
    onSuccess: () => invalidate(),
  });
}

/** POST /applications/{id}/generate — job de rédaction (202). */
export function useGenerateDocuments() {
  return useMutation({
    mutationFn: ({ applicationId, documentIds }: { applicationId: string; documentIds?: string[] }) =>
      api<Job>(`/applications/${applicationId}/generate`, {
        method: "POST",
        body: JSON.stringify({ document_ids: documentIds ?? null }),
      }),
  });
}

/** POST /applications/{id}/documents/{docId}/export — refait le DOCX de la version courante. */
export function useExportDocument(tenderId: string) {
  const invalidate = useInvalidateTender(tenderId);
  return useMutation({
    mutationFn: ({ applicationId, documentId }: { applicationId: string; documentId: string }) =>
      api<ApplicationDocument>(`/applications/${applicationId}/documents/${documentId}/export`, {
        method: "POST",
      }),
    onSuccess: () => invalidate(),
  });
}

export function documentDownloadUrl(applicationId: string, documentId: string): string {
  return `/api/v1/applications/${applicationId}/documents/${documentId}/download`;
}
