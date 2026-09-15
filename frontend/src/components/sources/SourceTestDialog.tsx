"use client";

import { ExternalLink, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { SourceTestReport } from "@/lib/types";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceName: string;
  report: SourceTestReport | null;
  pending: boolean;
};

function Counter({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-brand-green-dark">{value}</p>
    </div>
  );
}

/** Résultat de « Tester la source » : rien n'est enregistré, on vérifie seulement la configuration. */
export function SourceTestDialog({ open, onOpenChange, sourceName, report, pending }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Test de « {sourceName} »</DialogTitle>
          <DialogDescription>Collecte limitée à 3 pages — aucune opportunité n&apos;est enregistrée.</DialogDescription>
        </DialogHeader>

        {pending || !report ? (
          <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground" aria-busy="true">
            <LoaderCircle aria-hidden className="size-4 animate-spin text-brand-blue" />
            Test en cours (requêtes, lecture des pages, analyse)…
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              {report.status === "ok" && <Badge variant="success">Source OK</Badge>}
              {report.status === "error" && <Badge variant="destructive">Source en erreur</Badge>}
              {report.status === "skipped" && <Badge variant="muted">Source ignorée</Badge>}
              {report.queries.map((q) => (
                <Badge key={q} variant="info">
                  {q}
                </Badge>
              ))}
            </div>

            {report.error && (
              <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {report.error}
              </p>
            )}

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Counter label="URL trouvées" value={report.found} />
              <Counter label="Pages lues" value={report.fetched} />
              <Counter label="Appels d'offres" value={report.extracted} />
              <Counter label="Erreurs" value={report.errors} />
            </div>

            {report.candidates.length > 0 && (
              <ol className="space-y-2">
                {report.candidates.map((c) => (
                  <li key={c.source_url} className="rounded-lg border bg-card px-3 py-2 text-sm">
                    <a
                      href={c.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 font-medium text-foreground hover:text-brand-green-dark hover:underline"
                    >
                      {c.title}
                      <ExternalLink aria-hidden className="size-3.5 text-brand-blue" />
                    </a>
                    <p className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                      {c.organization && <span className="font-medium text-foreground">{c.organization}</span>}
                      {c.country && <span>{c.country}</span>}
                      {c.sector && <span>{c.sector}</span>}
                      {c.deadline_at && <span>échéance {c.deadline_at}</span>}
                      {c.document_urls.length > 0 && (
                        <span>
                          {c.document_urls.length} pièce{c.document_urls.length > 1 ? "s" : ""}
                        </span>
                      )}
                      <span>confiance {Math.round(c.confidence * 100)} %</span>
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Fermer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
