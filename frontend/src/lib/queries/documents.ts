"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { CompanyDocument, DocumentCategory, DocumentStatus, Page } from "@/lib/types";

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
};

function toQuery(filters: DocumentFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
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

/** Nombre de documents valides qui expirent dans les `days` prochains jours (ou déjà expirés). */
export function countExpiringSoon(docs: CompanyDocument[], days = 30, now = new Date()): number {
  const limit = new Date(now);
  limit.setDate(limit.getDate() + days);
  return docs.filter((d) => {
    if (d.status === "archived" || !d.expires_at) return false;
    return new Date(d.expires_at) <= limit;
  }).length;
}
