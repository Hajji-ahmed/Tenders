"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import { tenderKeys } from "@/lib/queries/tenders";
import type { Job, TenderAnalysis, TenderDocumentRef } from "@/lib/types";

export const analysisKeys = {
  documents: (id: string) => ["tenders", "detail", id, "documents"] as const,
  analysis: (id: string) => ["tenders", "detail", id, "analysis"] as const,
};

/** Pièces d'une fiche (URL découvertes, téléchargées ou déposées) avec leurs statuts. */
export function useTenderDocuments(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: analysisKeys.documents(id),
    queryFn: () => api<TenderDocumentRef[]>(`/tenders/${id}/documents`),
    enabled,
  });
}

/** Analyse structurée du dossier ; `null` tant qu'elle n'existe pas (404 `analysis_missing`). */
export function useTenderAnalysis(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: analysisKeys.analysis(id),
    queryFn: async () => {
      try {
        return await api<TenderAnalysis>(`/tenders/${id}/analysis`);
      } catch (e) {
        if (e instanceof ApiError && e.code === "analysis_missing") return null;
        throw e;
      }
    },
    enabled,
  });
}

function useInvalidateTender(id: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: tenderKeys.detail(id) });
}

/** POST /tenders/{id}/documents/fetch — job `download_tender_documents` (202). */
export function useFetchDocuments(id: string) {
  return useMutation({
    mutationFn: () => api<Job>(`/tenders/${id}/documents/fetch`, { method: "POST" }),
  });
}

/** POST /tenders/{id}/documents — dépôt manuel d'une pièce (multipart). */
export function useUploadTenderDocument(id: string) {
  const invalidate = useInvalidateTender(id);
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.set("file", file);
      return api<TenderDocumentRef>(`/tenders/${id}/documents`, { method: "POST", body: form });
    },
    onSuccess: () => invalidate(),
  });
}

/** POST /tenders/{id}/analyze — chaîne télécharger → indexer → analyser (202). */
export function useLaunchAnalysis(id: string) {
  return useMutation({
    mutationFn: () => api<Job>(`/tenders/${id}/analyze`, { method: "POST" }),
  });
}
