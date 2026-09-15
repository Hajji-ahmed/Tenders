"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page, Tender, TenderDetail, TenderStatus } from "@/lib/types";

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
