"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { cn } from "cn";

import { TenderSources } from "@/components/tenders/TenderSources";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TENDER_STATUS_LABELS, scoreLevel, urgencyOf, type ScoreLevel, type UrgencyLevel } from "@/lib/tenders";
import type { Tender, TenderStatus } from "@/lib/types";

type Props = { rows: Tender[]; emptyLabel?: string };

export const SCORE_TEXT: Record<ScoreLevel, string> = {
  high: "text-brand-green-dark",
  medium: "text-brand-yellow-ink",
  low: "text-destructive",
};

const URGENCY_VARIANT: Record<UrgencyLevel, "warning" | "warning-soft" | "info" | "muted" | "destructive"> = {
  critical: "warning", // signal fort : à traiter aujourd'hui
  high: "warning-soft",
  medium: "info",
  low: "muted",
  none: "muted",
  expired: "destructive",
};

const STATUS_VARIANT: Partial<Record<TenderStatus, "success" | "inverse" | "muted" | "destructive" | "info">> = {
  GO: "success",
  GAGNE: "success",
  NO_GO: "destructive",
  PERDU: "destructive",
  ARCHIVE: "muted",
  SOUMIS: "inverse",
  PRET: "inverse",
};

export function formatDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("fr-FR", { timeZone: "UTC" }) : "";
}

/** Liste des opportunités : titre (lien vers l'annonce), organisme, pays, échéance + urgence, statut, sources, score. */
export function TendersTable({ rows, emptyLabel = "Aucune opportunité pour l'instant — lancez une recherche depuis un profil." }: Props) {
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
          <TableHead>Opportunité</TableHead>
          <TableHead>Organisme</TableHead>
          <TableHead>Pays</TableHead>
          <TableHead>Échéance</TableHead>
          <TableHead>Statut</TableHead>
          <TableHead>Sources</TableHead>
          <TableHead className="text-right">Score</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((t) => {
          const urgency = urgencyOf(t.days_left);
          return (
            <TableRow key={t.id}>
              <TableCell className="max-w-[26rem] whitespace-normal">
                <div className="flex items-start gap-1.5">
                  <Link href={`/tenders/${t.id}`} className="font-medium text-foreground hover:text-brand-green-dark hover:underline">
                    {t.title}
                  </Link>
                  {t.source_url && (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label="Voir l'annonce"
                      title="Voir l'annonce"
                      className="mt-0.5 shrink-0 text-brand-blue hover:text-brand-blue-dark"
                    >
                      <ExternalLink aria-hidden className="size-3.5" />
                    </a>
                  )}
                </div>
                {t.sector && <p className="text-xs text-muted-foreground">{t.sector}</p>}
              </TableCell>
              <TableCell className="max-w-[16rem] truncate">{t.organization ?? <span className="text-muted-foreground">—</span>}</TableCell>
              <TableCell>{t.country ?? <span className="text-muted-foreground">—</span>}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {t.deadline_at && <span className="tabular-nums">{formatDate(t.deadline_at)}</span>}
                  <Badge variant={URGENCY_VARIANT[urgency.level]}>{urgency.label}</Badge>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={STATUS_VARIANT[t.status] ?? "secondary"}>{TENDER_STATUS_LABELS[t.status]}</Badge>
              </TableCell>
              <TableCell>
                <TenderSources tenderId={t.id} count={t.source_count} />
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {t.score_total === null ? (
                  <span aria-label="Score non calculé" className="text-muted-foreground">
                    —
                  </span>
                ) : (
                  <span data-level={scoreLevel(t.score_total).level} className={cn("font-semibold", SCORE_TEXT[scoreLevel(t.score_total).level])}>
                    {t.score_total}
                  </span>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
