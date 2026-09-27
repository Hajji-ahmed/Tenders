"use client";

import { Award, Briefcase, FileText, FolderKanban, Quote, Search, UserRound, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import type { SearchItem, SearchResults as Results } from "@/lib/types";

type Props = {
  /** `null` : aucune recherche lancée (ou requête trop courte). */
  results: Results | null;
  loading?: boolean;
};

const ICONS: Record<string, LucideIcon> = {
  tenders: Briefcase,
  documents: FileText,
  projects: FolderKanban,
  experts: UserRound,
  references: Users,
  certifications: Award,
};

/** Un score < 1 vient de la recherche par le sens : on l'affiche, la correspondance n'est pas littérale. */
function Similarity({ item }: { item: SearchItem }) {
  if (item.score >= 1) return null;
  return (
    <span className="shrink-0 rounded bg-brand-blue-tint px-1.5 py-0.5 text-[11px] font-medium text-brand-blue-dark" title="Proximité sémantique">
      {Math.round(item.score * 100)} %
    </span>
  );
}

/** Résultats de la recherche interne, groupés par nature ; chaque ligne mène à sa page. */
export function SearchResults({ results, loading = false }: Props) {
  if (loading) {
    return (
      <div role="status" aria-label="Recherche en cours" className="space-y-3">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
      </div>
    );
  }

  if (results === null) {
    return (
      <p className="rounded-xl border border-dashed border-brand-green/30 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
        Tapez au moins 3 caractères : la recherche traverse les opportunités, la base documentaire et le
        profil (projets, experts, références, certifications).
      </p>
    );
  }

  if (results.total === 0) {
    return (
      <p className="rounded-xl border border-dashed border-brand-yellow/50 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
        Aucun résultat pour «&nbsp;{results.query}&nbsp;».
        {!results.semantic && " Essayez la recherche par le sens : elle lit aussi l'intérieur des documents."}
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {results.groups.map((group) => {
        const Icon = ICONS[group.kind] ?? Search;
        return (
          <section key={group.kind} aria-label={group.label} className="space-y-2">
            <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-brand-green-dark/80">
              <Icon aria-hidden className="size-3.5" />
              {group.label}
              <span className="rounded-full bg-muted px-1.5 text-[11px] font-medium text-muted-foreground">
                {group.items.length}
              </span>
            </h2>
            <ul className="divide-y divide-border rounded-xl bg-card ring-1 ring-foreground/10">
              {group.items.map((item) => (
                <li key={`${item.kind}-${item.id}`} className="px-3 py-2.5">
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <Link
                        href={item.url}
                        prefetch={false}
                        className="font-medium text-foreground hover:text-brand-green-dark hover:underline"
                      >
                        {item.title}
                      </Link>
                      {item.subtitle && <p className="text-xs text-muted-foreground">{item.subtitle}</p>}
                    </div>
                    <Similarity item={item} />
                  </div>
                  {item.excerpt && (
                    <p className="mt-1.5 flex items-start gap-1.5 rounded-lg bg-muted/50 px-2.5 py-1.5 text-xs leading-relaxed text-muted-foreground">
                      <Quote aria-hidden className="mt-0.5 size-3 shrink-0 text-brand-blue" />
                      {item.excerpt}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
