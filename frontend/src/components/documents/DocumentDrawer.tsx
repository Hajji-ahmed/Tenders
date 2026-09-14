"use client";

import { Archive, Download, FilePlus2, History, Pencil } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EntityDialog, type EntityValues, type FieldSpec } from "@/components/common/EntityDialog";
import { formatDate, StatusBadge } from "@/components/documents/DocumentsTable";
import { NewVersionDialog } from "@/components/documents/NewVersionDialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { CATEGORY_LABELS, CATEGORY_OPTIONS, documentDownloadUrl, fileKind, formatBytes } from "@/lib/documents";
import {
  type DocumentUpdate,
  useArchiveDocument,
  useDocument,
  useDocumentVersions,
  useNewVersion,
  useUpdateDocument,
} from "@/lib/queries/documents";
import type { CompanyDocument } from "@/lib/types";

type Props = {
  /** Document affiché ; `null` = tiroir fermé. */
  documentId: string | null;
  onOpenChange: (open: boolean) => void;
};

const EDIT_FIELDS: FieldSpec[] = [
  { name: "name", label: "Nom", type: "text", required: true },
  { name: "category", label: "Catégorie", type: "select", required: true, options: CATEGORY_OPTIONS },
  { name: "issued_at", label: "Délivré le", type: "date" },
  { name: "expires_at", label: "Expire le", type: "date", help: "Passé cette date, le document est marqué « Expiré »." },
  { name: "tags", label: "Étiquettes", type: "tags" },
  { name: "description", label: "Description", type: "textarea" },
];

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function Details({ doc, onClose }: { doc: CompanyDocument; onClose: () => void }) {
  const versions = useDocumentVersions(doc.id);
  const update = useUpdateDocument();
  const newVersion = useNewVersion();
  const archive = useArchiveDocument();
  const [editing, setEditing] = useState(false);
  const [versioning, setVersioning] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const active = doc.status !== "archived";

  async function saveMeta(values: EntityValues) {
    await update.mutateAsync({ id: doc.id, values: values as DocumentUpdate });
    toast.success("Document mis à jour");
  }

  async function addVersion(form: FormData) {
    await newVersion.mutateAsync({ id: doc.id, form });
    toast.success("Nouvelle version enregistrée");
  }

  async function confirmArchive() {
    await archive.mutateAsync(doc.id);
    toast.success("Document archivé");
    onClose();
  }

  return (
    <>
      <SheetHeader className="pr-12">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <Badge variant="info">{CATEGORY_LABELS[doc.category]}</Badge>
          <StatusBadge status={doc.status} />
        </div>
        <SheetTitle className="text-lg font-semibold text-brand-green-dark">{doc.name}</SheetTitle>
        <SheetDescription className="flex flex-wrap gap-x-2">
          <span>Version {doc.version}</span>
          <span aria-hidden>·</span>
          <span>{formatBytes(doc.size_bytes)}</span>
          <span aria-hidden>·</span>
          <span>{fileKind(doc.mime_type)}</span>
        </SheetDescription>
      </SheetHeader>

      <div className="flex flex-wrap gap-2 px-4">
        <a href={documentDownloadUrl(doc.id)} className={buttonVariants({ variant: "default" })}>
          <Download />
          Télécharger
        </a>
        <Button variant="outline" onClick={() => setEditing(true)}>
          <Pencil />
          Modifier
        </Button>
        {active && (
          <Button variant="outline" onClick={() => setVersioning(true)}>
            <FilePlus2 />
            Nouvelle version
          </Button>
        )}
        {active && (
          <Button variant="ghost" className="text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => setArchiving(true)}>
            <Archive />
            Archiver
          </Button>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 pb-4">
        <dl className="space-y-2">
          <Row label="Délivré le">{doc.issued_at ? formatDate(doc.issued_at) : "—"}</Row>
          <Row label="Expire le">
            {doc.expires_at ? (
              <span className={doc.is_expired ? "font-medium text-destructive" : undefined}>{formatDate(doc.expires_at)}</span>
            ) : (
              "—"
            )}
          </Row>
          <Row label="Étiquettes">
            {doc.tags.length ? (
              <span className="flex flex-wrap gap-1">
                {doc.tags.map((t) => (
                  <Badge key={t} variant="secondary">
                    {t}
                  </Badge>
                ))}
              </span>
            ) : (
              "—"
            )}
          </Row>
          <Row label="Description">{doc.description || "—"}</Row>
          <Row label="Ajouté le">{formatDate(doc.created_at)}</Row>
          <Row label="Empreinte">
            <code className="text-xs text-muted-foreground">{doc.sha256.slice(0, 16)}…</code>
          </Row>
        </dl>

        <Separator />

        <section aria-labelledby="versions-title" className="space-y-2">
          <h3 id="versions-title" className="flex items-center gap-2 text-sm font-semibold text-brand-green-dark">
            <History aria-hidden className="size-4 text-brand-blue" />
            Historique des versions
          </h3>
          {versions.isPending ? (
            <Skeleton className="h-12 w-full" />
          ) : versions.isError ? (
            <p role="alert" className="text-sm text-destructive">
              Impossible de charger les versions.
            </p>
          ) : (
            <ol className="space-y-2">
              {(versions.data ?? []).map((v) => (
                <li key={v.id} className="rounded-lg border bg-card px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold tabular-nums text-brand-green-dark">v{v.version_number}</span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(v.created_at).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" })}
                    </span>
                  </div>
                  {v.changelog && <p className="mt-1 text-foreground">{v.changelog}</p>}
                  {v.author && <p className="mt-0.5 text-xs text-muted-foreground">{v.author}</p>}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <EntityDialog
        open={editing}
        onOpenChange={setEditing}
        title="Modifier le document"
        fields={EDIT_FIELDS}
        defaultValues={doc as unknown as EntityValues}
        onSubmit={saveMeta}
      />
      <NewVersionDialog open={versioning} onOpenChange={setVersioning} documentName={doc.name} onSubmit={addVersion} />
      <ConfirmDialog
        open={archiving}
        onOpenChange={setArchiving}
        title={`Archiver « ${doc.name} » ?`}
        description="Le document ne sera plus proposé pour les candidatures ; son historique et ses versions sont conservés."
        confirmLabel="Archiver"
        onConfirm={confirmArchive}
      />
    </>
  );
}

/** Tiroir latéral de détail d'un document : métadonnées, versions, téléchargement, nouvelle version, archivage. */
export function DocumentDrawer({ documentId, onOpenChange }: Props) {
  const doc = useDocument(documentId);
  return (
    <Sheet open={documentId !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="data-[side=right]:sm:max-w-lg">
        {doc.isPending ? (
          <div className="space-y-3 p-4" aria-busy="true" aria-label="Chargement">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : doc.isError || !doc.data ? (
          <p role="alert" className="m-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            Impossible de charger le document.
          </p>
        ) : (
          <Details doc={doc.data} onClose={() => onOpenChange(false)} />
        )}
      </SheetContent>
    </Sheet>
  );
}
