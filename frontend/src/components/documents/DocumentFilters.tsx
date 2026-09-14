"use client";

import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { NativeSelect } from "@/components/common/NativeSelect";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CATEGORY_OPTIONS, STATUS_OPTIONS } from "@/lib/documents";
import type { DocumentFilters as Filters } from "@/lib/queries/documents";
import type { DocumentCategory, DocumentStatus } from "@/lib/types";

type Props = {
  value: Filters;
  onChange: (next: Filters) => void;
};

const SEARCH_DELAY_MS = 300;

/** Retire les clés vides : la clé de requête reste stable et l'URL ne porte que les filtres actifs. */
function compact(filters: Filters): Filters {
  const out: Filters = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "" && v !== false) (out as Record<string, unknown>)[k] = v;
  }
  return out;
}

/** Barre de filtres de la page Documents : recherche (différée), catégorie, statut, utilisables seulement. */
export function DocumentFilters({ value, onChange }: Props) {
  const [q, setQ] = useState(value.q ?? "");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Dernière valeur des filtres, lue par la recherche différée (un autre filtre a pu changer entre-temps).
  const latest = useRef(value);
  useEffect(() => {
    latest.current = value;
  }, [value]);

  // Tout changement de filtre repart en page 1.
  function patch(partial: Partial<Filters>) {
    onChange(compact({ ...latest.current, ...partial, page: 1 }));
  }

  function search(text: string) {
    setQ(text);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => patch({ q: text.trim() }), SEARCH_DELAY_MS);
  }

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="relative min-w-56 flex-1 space-y-2">
        <Label htmlFor="documents-search">Rechercher</Label>
        <div className="relative">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="documents-search"
            type="search"
            placeholder="Nom ou description…"
            className="pl-8"
            value={q}
            onChange={(e) => search(e.target.value)}
          />
        </div>
      </div>
      <div className="w-44 space-y-2">
        <Label htmlFor="documents-category">Catégorie</Label>
        <NativeSelect
          id="documents-category"
          options={CATEGORY_OPTIONS}
          placeholder="Toutes"
          value={value.category ?? ""}
          onChange={(e) => patch({ category: (e.target.value || undefined) as DocumentCategory | undefined })}
        />
      </div>
      <div className="w-40 space-y-2">
        <Label htmlFor="documents-status">Statut</Label>
        <NativeSelect
          id="documents-status"
          options={STATUS_OPTIONS}
          placeholder="Tous"
          value={value.status ?? ""}
          onChange={(e) => patch({ status: (e.target.value || undefined) as DocumentStatus | undefined })}
        />
      </div>
      <label htmlFor="documents-usable" className="flex h-8 items-center gap-2 text-sm font-medium">
        <input
          id="documents-usable"
          type="checkbox"
          className="size-4 rounded border-input accent-brand-green"
          checked={Boolean(value.usable_only)}
          onChange={(e) => patch({ usable_only: e.target.checked })}
        />
        Utilisables seulement
      </label>
    </div>
  );
}
