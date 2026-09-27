"use client";

import { CircleAlert, Download, FileText, Quote, RefreshCw, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { EvidencePopover } from "@/components/tenders/EvidencePopover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { documentDownloadUrl } from "@/lib/queries/applications";
import type { AppDocStatus, ApplicationDocument, ApplicationSection } from "@/lib/types";

type Props = {
  applicationId: string;
  documents: ApplicationDocument[];
  onGenerate: (documentIds?: string[]) => void;
  busy?: boolean;
};

const STATUS: Record<AppDocStatus, { label: string; variant: "success" | "warning-soft" | "destructive" | "muted" | "info" }> = {
  pending: { label: "À rédiger", variant: "muted" },
  generating: { label: "Rédaction en cours", variant: "info" },
  draft: { label: "Brouillon à relire", variant: "warning-soft" },
  validated: { label: "Validé", variant: "success" },
  rejected: { label: "Rejeté", variant: "destructive" },
  failed: { label: "Échec", variant: "destructive" },
};

/** Nombre de zones laissées à compléter : c'est le travail qui reste à l'humain. */
export function missingCount(doc: ApplicationDocument): number {
  return doc.sections.reduce((total, section) => total + section.missing_info.length, 0);
}

function SectionRow({ section }: { section: ApplicationSection }) {
  const [open, setOpen] = useState(false);
  const words = (section.content_md ?? "").trim().split(/\s+/).filter(Boolean).length;
  return (
    <li className="px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="font-medium text-foreground hover:text-brand-green-dark"
        >
          {section.title}
        </button>
        <span className="text-xs text-muted-foreground">{words} mots</span>
        {section.missing_info.length > 0 && (
          <Badge variant="warning-soft">
            {section.missing_info.length} à compléter
          </Badge>
        )}
        {section.sources.length > 0 && <EvidencePopover code={section.title} evidence={section.sources} />}
      </div>
      {open && (
        <div className="mt-2 space-y-2">
          <p className="whitespace-pre-wrap rounded-lg bg-muted/40 px-3 py-2 text-sm leading-relaxed text-foreground">
            {section.content_md || "—"}
          </p>
          {section.missing_info.length > 0 && (
            <ul className="space-y-1 text-xs text-muted-foreground" aria-label="À compléter">
              {section.missing_info.map((item) => (
                <li key={item} className="flex items-start gap-1.5">
                  <Quote aria-hidden className="mt-0.5 size-3 shrink-0 text-brand-yellow-ink" />
                  {item}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

/** Les documents du dossier : statut, avertissements, zones à compléter, sections et export. */
export function DocumentStatusList({ applicationId, documents, onGenerate, busy = false }: Props) {
  if (documents.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-brand-green/30 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
        Aucun document dans le dossier. Choisissez les modèles à préparer ci-dessus.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {documents.map((doc) => {
        const state = STATUS[doc.status];
        const missing = missingCount(doc);
        return (
          <li key={doc.id} className="rounded-xl bg-card ring-1 ring-foreground/10">
            <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2.5">
              <FileText aria-hidden className="size-4 shrink-0 text-brand-blue" />
              {/* Le titre prend toute la largeur en petit écran : sinon il se comprime en colonne. */}
              <p className="min-w-0 basis-[calc(100%-1.75rem)] font-medium text-foreground sm:flex-1 sm:basis-auto">
                {doc.title}
              </p>
              <Badge variant={state.variant}>{state.label}</Badge>
              {doc.current_version > 0 && (
                <span className="text-xs text-muted-foreground">v{doc.current_version}</span>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => onGenerate([doc.id])}
                disabled={busy}
              >
                <RefreshCw />
                {doc.current_version > 0 ? "Régénérer" : "Rédiger"}
              </Button>
              {doc.current_version > 0 && (
                <a
                  href={documentDownloadUrl(applicationId, doc.id)}
                  className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-brand-green-dark hover:bg-brand-green-tint"
                >
                  <Download aria-hidden className="size-4" />
                  DOCX
                </a>
              )}
            </div>

            {doc.error && (
              <p role="alert" className="flex items-start gap-1.5 px-3 py-2 text-sm text-destructive">
                <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
                {doc.error}
              </p>
            )}
            {doc.warnings.length > 0 && (
              <div className="border-b border-border bg-brand-yellow-tint/40 px-3 py-2">
                <p className="flex items-center gap-1.5 text-xs font-semibold text-brand-yellow-ink">
                  <TriangleAlert aria-hidden className="size-3.5" />
                  {doc.warnings.length} point{doc.warnings.length > 1 ? "s" : ""} à vérifier avant envoi
                </p>
                <ul className="mt-1 space-y-0.5 text-xs text-brand-yellow-ink/90">
                  {doc.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
            {missing > 0 && (
              <p className="px-3 pt-2 text-xs text-muted-foreground">
                {missing} zone{missing > 1 ? "s" : ""} à compléter dans ce document.
              </p>
            )}

            {doc.sections.length > 0 && (
              <ul className="divide-y divide-border">
                {doc.sections.map((section) => (
                  <SectionRow key={section.id} section={section} />
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}
