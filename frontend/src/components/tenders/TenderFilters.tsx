"use client";

import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { NativeSelect } from "@/components/common/NativeSelect";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TenderFilters as Filters } from "@/lib/queries/tenders";
import { SORT_OPTIONS, TENDER_STATUS_OPTIONS } from "@/lib/tenders";
import type { TenderStatus } from "@/lib/types";

type Props = { value: Filters; onChange: (next: Filters) => void };

const SEARCH_DELAY_MS = 300;

function compact(filters: Filters): Filters {
  const out: Filters = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "" && v !== false) (out as Record<string, unknown>)[k] = v;
  }
  return out;
}

/** Filtres de la liste des opportunités : recherche différée, statut, pays, tri, inactives. */
export function TenderFilters({ value, onChange }: Props) {
  const [q, setQ] = useState(value.q ?? "");
  const [country, setCountry] = useState(value.country ?? "");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef(value);
  useEffect(() => {
    latest.current = value;
  }, [value]);

  function patch(partial: Partial<Filters>) {
    onChange(compact({ ...latest.current, ...partial, page: 1 }));
  }

  function debounced(partial: Partial<Filters>) {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => patch(partial), SEARCH_DELAY_MS);
  }

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="min-w-56 flex-1 space-y-2">
        <Label htmlFor="tenders-search">Rechercher</Label>
        <div className="relative">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="tenders-search"
            type="search"
            placeholder="Titre ou description…"
            className="pl-8"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              debounced({ q: e.target.value.trim() });
            }}
          />
        </div>
      </div>
      <div className="w-40 space-y-2">
        <Label htmlFor="tenders-status">Statut</Label>
        <NativeSelect
          id="tenders-status"
          options={TENDER_STATUS_OPTIONS}
          placeholder="Tous"
          value={value.status ?? ""}
          onChange={(e) => patch({ status: (e.target.value || undefined) as TenderStatus | undefined })}
        />
      </div>
      <div className="w-24 space-y-2">
        <Label htmlFor="tenders-country">Pays</Label>
        <Input
          id="tenders-country"
          maxLength={2}
          placeholder="MA"
          className="uppercase"
          value={country}
          onChange={(e) => {
            const v = e.target.value.toUpperCase();
            setCountry(v);
            if (v.length === 0 || v.length === 2) patch({ country: v || undefined });
          }}
        />
      </div>
      <div className="w-52 space-y-2">
        <Label htmlFor="tenders-sort">Tri</Label>
        <NativeSelect id="tenders-sort" options={SORT_OPTIONS} value={value.sort ?? "-created"} onChange={(e) => patch({ sort: e.target.value })} />
      </div>
      <label htmlFor="tenders-inactive" className="flex h-8 items-center gap-2 text-sm font-medium">
        <input
          id="tenders-inactive"
          type="checkbox"
          className="size-4 rounded border-input accent-brand-green"
          checked={value.active_only === false}
          onChange={(e) => patch({ active_only: e.target.checked ? false : undefined })}
        />
        Inclure les expirées
      </label>
    </div>
  );
}
