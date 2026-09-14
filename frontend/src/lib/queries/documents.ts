"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { CompanyDocument, DocumentCategory, DocumentStatus, DocumentVersion, Page } from "@/lib/types";

export type DocumentFilters = {
  category?: DocumentCategory;
  status?: DocumentStatus;
  tag?: string;
  q?: string;
  usable_only?: boolean;
  page?: number;
  size?: number;
};

export const documentKeys = {
  all: ["documents"] as const,
  list: (filters: DocumentFilters) => ["documents", "list", filters] as const,
  detail: (id: string) => ["documents", "detail", id] as const,
  versions: (id: string) => ["documents", "versions", id] as const,
};

function toQuery(filters: DocumentFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "" && value !== false) params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

/** Liste paginée des documents de l'entreprise (GET /documents). */
export function useDocuments(filters: DocumentFilters = {}) {
  return useQuery({
    queryKey: documentKeys.list(filters),
    queryFn: () => api<Page<CompanyDocument>>(`/documents${toQuery(filters)}`),
  });
}

export function useDocument(id: string | null) {
  return useQuery({
    queryKey: documentKeys.detail(id ?? ""),
    queryFn: () => api<CompanyDocument>(`/documents/${id}`),
    enabled: id !== null,
  });
}

export function useDocumentVersions(id: string | null) {
  return useQuery({
    queryKey: documentKeys.versions(id ?? ""),
    queryFn: () => api<DocumentVersion[]>(`/documents/${id}/versions`),
    enabled: id !== null,
  });
}

/** Toute mutation invalide l'arbre `documents` : listes, détail et versions repartent du serveur. */
function useInvalidateDocuments() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: documentKeys.all });
}

/** POST /documents — corps multipart construit par `buildUploadForm`. */
export function useUploadDocument() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (form: FormData) => api<CompanyDocument>("/documents", { method: "POST", body: form }),
    onSuccess: () => invalidate(),
  });
}

export type DocumentUpdate = Partial<
  Pick<CompanyDocument, "name" | "category" | "description" | "issued_at" | "expires_at" | "tags">
>;

/** PATCH /documents/{id} — métadonnées seulement (le fichier change via une nouvelle version). */
export function useUpdateDocument() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: ({ id, values }: { id: string; values: DocumentUpdate }) =>
      api<CompanyDocument>(`/documents/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
    onSuccess: () => invalidate(),
  });
}

/** POST /documents/{id}/versions — multipart `file` (+ `changelog`). */
export function useNewVersion() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: ({ id, form }: { id: string; form: FormData }) =>
      api<CompanyDocument>(`/documents/${id}/versions`, { method: "POST", body: form }),
    onSuccess: () => invalidate(),
  });
}

/** DELETE /documents/{id} — archivage logique (historique et versions conservés). */
export function useArchiveDocument() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  });
}

/** Nombre de documents valides qui expirent dans les `days` prochains jours (ou déjà expirés). */
export function countExpiringSoon(docs: CompanyDocument[], days = 30, now = new Date()): number {
  const limit = new Date(now);
  limit.setDate(limit.getDate() + days);
  return docs.filter((d) => {
    if (d.status === "archived" || !d.expires_at) return false;
    return new Date(d.expires_at) <= limit;
  }).length;
}
