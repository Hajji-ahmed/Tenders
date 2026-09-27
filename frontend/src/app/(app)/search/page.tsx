"use client";

import { Search, Sparkles } from "lucide-react";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/layout/PageHeader";
import { SearchResults } from "@/components/search/SearchResults";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { MIN_QUERY, useInternalSearch } from "@/lib/queries/search";

const DEBOUNCE_MS = 300;

function SearchPageInner() {
  const params = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [query, setQuery] = useState(text);
  const [semantic, setSemantic] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);

  useEffect(() => {
    input.current?.focus(); // la page s'ouvre au clavier (Ctrl+K) : le curseur est déjà dans le champ
  }, []);

  const search = useInternalSearch(query, { semantic });
  const short = query.length < MIN_QUERY;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Recherche interne"
        count={search.data && !short ? search.data.total : undefined}
        description="Opportunités, documents et profil en une seule requête. La recherche par le sens lit aussi l'intérieur des pièces indexées et cite le passage trouvé."
      />

      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-64 flex-1 space-y-2">
          <Label htmlFor="internal-search">Rechercher</Label>
          <div className="relative">
            <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="internal-search"
              ref={input}
              type="search"
              className="pl-8"
              placeholder="Un mot, un client, une norme, une phrase du dossier…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
        </div>
        <label htmlFor="semantic" className="flex h-8 items-center gap-2 text-sm font-medium">
          <input
            id="semantic"
            type="checkbox"
            className="size-4 rounded border-input accent-brand-green"
            checked={semantic}
            onChange={(e) => setSemantic(e.target.checked)}
          />
          <Sparkles aria-hidden className="size-3.5 text-brand-blue" />
          Recherche par le sens
        </label>
      </div>

      {search.isError ? (
        <p role="alert" className="text-sm text-destructive">
          La recherche a échoué. Réessayez dans un instant.
        </p>
      ) : (
        <SearchResults
          results={short ? null : (search.data ?? null)}
          loading={!short && search.isFetching && !search.data}
        />
      )}
    </div>
  );
}

// useSearchParams exige une frontière Suspense pour le rendu statique.
export default function SearchPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-2xl" />}>
      <SearchPageInner />
    </Suspense>
  );
}
