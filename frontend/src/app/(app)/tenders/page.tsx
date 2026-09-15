"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { JobProgress } from "@/components/jobs/JobProgress";
import { PageHeader } from "@/components/layout/PageHeader";
import { TenderFilters } from "@/components/tenders/TenderFilters";
import { TendersTable } from "@/components/tenders/TendersTable";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSearches } from "@/lib/queries/searchProfiles";
import { type TenderFilters as Filters, useTenders } from "@/lib/queries/tenders";

const PAGE_SIZE = 20;

export default function TendersPage() {
  const [filters, setFilters] = useState<Filters>({});
  const page = filters.page ?? 1;
  const tenders = useTenders({ ...filters, page, size: PAGE_SIZE });
  const searches = useSearches();
  const running = (searches.data ?? []).filter((j) => j.status === "pending" || j.status === "running");

  const total = tenders.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Boolean(filters.q || filters.status || filters.country || filters.active_only === false);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Veille"
        title="Opportunités"
        count={tenders.data ? total : undefined}
        description="Appels d'offres collectés par vos recherches. Le score et la qualification arrivent avec l'étape suivante."
        actions={
          <Link href="/search-profiles" className={buttonVariants({ variant: "accent" })}>
            <Search />
            Lancer une recherche
          </Link>
        }
      />

      {running.length > 0 && (
        <section aria-label="Recherches en cours" className="space-y-2">
          {running.map((j) => (
            <JobProgress key={j.id} jobId={j.id} />
          ))}
        </section>
      )}

      <TenderFilters value={filters} onChange={setFilters} />

      {tenders.isPending ? (
        <div className="space-y-2" aria-busy="true" aria-label="Chargement">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : tenders.isError ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Impossible de charger les opportunités.
        </p>
      ) : (
        <TendersTable
          rows={tenders.data.items}
          emptyLabel={hasFilters ? "Aucune opportunité ne correspond à ces filtres." : undefined}
        />
      )}

      {pageCount > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-end gap-2 text-sm text-muted-foreground">
          <span>
            Page {page} / {pageCount}
          </span>
          <Button variant="outline" size="icon-sm" aria-label="Page précédente" disabled={page <= 1} onClick={() => setFilters({ ...filters, page: page - 1 })}>
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="icon-sm" aria-label="Page suivante" disabled={page >= pageCount} onClick={() => setFilters({ ...filters, page: page + 1 })}>
            <ChevronRight />
          </Button>
        </nav>
      )}
    </div>
  );
}
