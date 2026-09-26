"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { SearchResults } from "@/lib/types";

export const MIN_QUERY = 3; // même seuil que l'API : en deçà, la recherche ne part pas

export const searchKeys = {
  run: (q: string, semantic: boolean) => ["search", q, semantic] as const,
};

/** Recherche interne : texte partout, et — si `semantic` — le contenu des documents et les fiches proches. */
export function useInternalSearch(q: string, { semantic = false }: { semantic?: boolean } = {}) {
  const query = q.trim();
  return useQuery({
    queryKey: searchKeys.run(query, semantic),
    queryFn: () =>
      api<SearchResults>(
        `/search?q=${encodeURIComponent(query)}${semantic ? "&semantic=true" : ""}`,
      ),
    enabled: query.length >= MIN_QUERY,
    staleTime: 30_000,
  });
}
