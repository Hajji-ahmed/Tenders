"use client";

import { Download, FileArchive, FileSpreadsheet, FileText, PanelRightOpen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CATEGORY_LABELS, documentDownloadUrl, formatBytes, STATUS_LABELS } from "@/lib/documents";
import type { CompanyDocument, DocumentStatus } from "@/lib/types";

type Props = {
  rows: CompanyDocument[];
  onOpen: (doc: CompanyDocument) => void;
  emptyLabel?: string;
};

const STATUS_VARIANT: Record<DocumentStatus, "success" | "warning" | "warning-soft" | "muted"> = {
  valid: "success",
  expired: "warning", // signal fort : à renouveler (RB-007 : exclu des candidatures)
  draft: "warning-soft",
  archived: "muted",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABELS[status]}</Badge>;
}

export function formatDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("fr-FR", { timeZone: "UTC" }) : "";
}

function FileIcon({ mime }: { mime: string }) {
  const cls = "size-4 shrink-0 text-brand-blue";
  if (mime.includes("spreadsheet")) return <FileSpreadsheet aria-hidden className={cls} />;
  if (mime.includes("zip")) return <FileArchive aria-hidden className={cls} />;
  return <FileText aria-hidden className={cls} />;
}

/** Tableau principal de la page Documents : statut RB-007, taille, version, expiration, ouverture et téléchargement. */
export function DocumentsTable({ rows, onOpen, emptyLabel = "Aucun document ne correspond." }: Props) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-brand-green/30 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
        {emptyLabel}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader variant="inverse">
        <TableRow>
          <TableHead>Document</TableHead>
          <TableHead>Catégorie</TableHead>
          <TableHead>Taille</TableHead>
          <TableHead>Expire le</TableHead>
          <TableHead>Statut</TableHead>
          <TableHead className="w-24 text-right">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((d) => (
          <TableRow key={d.id}>
            <TableCell className="max-w-[28rem]">
              <button
                type="button"
                onClick={() => onOpen(d)}
                aria-label={`Ouvrir ${d.name}`}
                className="flex max-w-full items-center gap-2 text-left font-medium text-foreground hover:text-brand-green-dark hover:underline"
              >
                <FileIcon mime={d.mime_type} />
                <span className="truncate">{d.name}</span>
                {d.version > 1 && (
                  <span className="rounded-full bg-muted px-1.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
                    v{d.version}
                  </span>
                )}
              </button>
            </TableCell>
            <TableCell>
              <Badge variant="info">{CATEGORY_LABELS[d.category]}</Badge>
            </TableCell>
            <TableCell className="tabular-nums text-muted-foreground">{formatBytes(d.size_bytes)}</TableCell>
            <TableCell className="tabular-nums">
              {d.expires_at ? formatDate(d.expires_at) : <span className="text-muted-foreground">—</span>}
            </TableCell>
            <TableCell>
              <StatusBadge status={d.status} />
            </TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-1">
                <a
                  href={documentDownloadUrl(d.id)}
                  aria-label={`Télécharger ${d.name}`}
                  className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
                >
                  <Download />
                </a>
                <Button variant="ghost" size="icon-sm" aria-label={`Détails ${d.name}`} onClick={() => onOpen(d)}>
                  <PanelRightOpen />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
