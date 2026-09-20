"use client";

import { CloudDownload, Download, FileText, Upload } from "lucide-react";
import { useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ALLOWED_EXTENSIONS, formatBytes } from "@/lib/documents";
import type { TenderDocumentRef } from "@/lib/types";

type Props = {
  tenderId: string;
  documents: TenderDocumentRef[];
  onFetch: () => void;
  onUpload: (file: File) => Promise<void> | void;
  /** Un job (récupération, analyse) est en cours : pas de second lancement. */
  busy?: boolean;
};

type BadgeVariant = "success" | "warning-soft" | "destructive" | "muted" | "info";

/** État lisible d'une pièce : le téléchargement prime, puis l'extraction du texte. */
export function documentState(doc: TenderDocumentRef): { label: string; variant: BadgeVariant } {
  if (doc.download_status === "failed") return { label: "Téléchargement échoué", variant: "destructive" };
  if (doc.download_status !== "done") return { label: "En attente", variant: "muted" };
  if (doc.extraction_status === "done") return { label: "Texte extrait", variant: "success" };
  if (doc.extraction_status === "failed") return { label: "Extraction impossible", variant: "destructive" };
  return { label: "Téléchargée", variant: "info" };
}

/** Pièces du dossier : statuts, erreurs lisibles, téléchargement, dépôt manuel, récupération par job. */
export function DocumentsPanel({ tenderId, documents, onFetch, onUpload, busy = false }: Props) {
  const input = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {documents.length === 0
            ? "Aucune pièce pour l'instant : récupérez celles de l'annonce ou déposez-en une."
            : `${documents.length} pièce${documents.length > 1 ? "s" : ""}`}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onFetch} disabled={busy}>
            <CloudDownload />
            Récupérer les documents
          </Button>
          <Button variant="outline" size="sm" onClick={() => input.current?.click()} disabled={busy}>
            <Upload />
            Déposer une pièce
          </Button>
          <input
            ref={input}
            type="file"
            aria-label="Déposer une pièce"
            className="sr-only"
            accept={ALLOWED_EXTENSIONS.join(",")}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) await onUpload(file);
            }}
          />
        </div>
      </div>

      {documents.length > 0 && (
        <ul className="divide-y divide-border rounded-xl bg-card ring-1 ring-foreground/10">
          {documents.map((doc) => {
            const state = documentState(doc);
            const meta = [
              doc.size_bytes !== null ? formatBytes(doc.size_bytes) : null,
              doc.page_count !== null ? `${doc.page_count} page${doc.page_count > 1 ? "s" : ""}` : null,
              doc.source_url ? "annonce" : "dépôt manuel",
            ].filter(Boolean);
            return (
              <li key={doc.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
                <FileText aria-hidden className="size-4 shrink-0 text-brand-blue" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-foreground">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">{meta.join(" · ")}</p>
                  {doc.error && <p className="text-xs text-destructive">{doc.error}</p>}
                </div>
                <Badge variant={state.variant}>{state.label}</Badge>
                {doc.download_status === "done" && (
                  <a
                    href={`/api/v1/tenders/${tenderId}/documents/${doc.id}/download`}
                    aria-label={`Télécharger ${doc.name}`}
                    title="Télécharger"
                    className="text-muted-foreground hover:text-brand-green-dark"
                  >
                    <Download aria-hidden className="size-4" />
                  </a>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
