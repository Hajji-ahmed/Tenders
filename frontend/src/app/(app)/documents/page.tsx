"use client";

import { ChevronLeft, ChevronRight, Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { DocumentDrawer } from "@/components/documents/DocumentDrawer";
import { DocumentFilters } from "@/components/documents/DocumentFilters";
import { DocumentsTable } from "@/components/documents/DocumentsTable";
import { UploadDialog } from "@/components/documents/UploadDialog";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { type DocumentFilters as Filters, useDocuments, useUploadDocument } from "@/lib/queries/documents";

const PAGE_SIZE = 20;

export default function DocumentsPage() {
  const [filters, setFilters] = useState<Filters>({});
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const page = filters.page ?? 1;
  const documents = useDocuments({ ...filters, page, size: PAGE_SIZE });
  const upload = useUploadDocument();

  const total = documents.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Boolean(filters.q || filters.category || filters.status || filters.usable_only);

  async function submitUpload(form: FormData) {
    const doc = await upload.mutateAsync(form);
    toast.success(`« ${doc.name} » déposé`);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Documents"
        count={documents.data ? total : undefined}
        description="Attestations, certifications, CV, références… Un document expiré est signalé et exclu des candidatures (RB-007)."
        actions={
          <Button variant="accent" onClick={() => setUploadOpen(true)}>
            <Upload />
            Déposer un document
          </Button>
        }
      />

      <DocumentFilters value={filters} onChange={setFilters} />

      {documents.isPending ? (
        <div className="space-y-2" aria-busy="true" aria-label="Chargement">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : documents.isError ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Impossible de charger les documents.
        </p>
      ) : (
        <DocumentsTable
          rows={documents.data.items}
          onOpen={(d) => setSelectedId(d.id)}
          emptyLabel={hasFilters ? "Aucun document ne correspond à ces filtres." : "Aucun document pour l'instant — déposez votre première attestation ou présentation."}
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

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} onSubmit={submitUpload} />
      <DocumentDrawer documentId={selectedId} onOpenChange={(open) => !open && setSelectedId(null)} />
    </div>
  );
}
