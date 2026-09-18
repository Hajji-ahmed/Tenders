"use client";

import { ArrowRight, Bot, UserRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { TENDER_STATUS_LABELS } from "@/lib/tenders";
import type { StatusHistoryEntry } from "@/lib/types";

type Props = { entries: StatusHistoryEntry[] };

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });
}

/** Historique des statuts, du plus récent au plus ancien : transition, auteur (ou système), motif. */
export function StatusTimeline({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-brand-green/30 bg-card px-6 py-8 text-center text-sm text-muted-foreground">
        Aucun changement de statut pour l&apos;instant.
      </p>
    );
  }
  const ordered = [...entries].sort((a, b) => b.changed_at.localeCompare(a.changed_at));
  return (
    <ol className="relative space-y-4 border-l border-border pl-6">
      {ordered.map((e) => (
        <li key={e.id} className="relative">
          <span aria-hidden className="absolute top-1.5 -left-[1.6rem] size-2.5 rounded-full border-2 border-brand-green bg-card" />
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {e.from_status && (
              <>
                <Badge variant="muted">{TENDER_STATUS_LABELS[e.from_status]}</Badge>
                <ArrowRight aria-hidden className="size-3.5 text-muted-foreground" />
              </>
            )}
            <Badge variant="secondary">{TENDER_STATUS_LABELS[e.to_status]}</Badge>
            <span className="text-xs text-muted-foreground">{formatDateTime(e.changed_at)}</span>
          </div>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            {e.changed_by ? <UserRound aria-hidden className="size-3.5" /> : <Bot aria-hidden className="size-3.5 text-brand-blue" />}
            {e.changed_by ?? "Système"}
          </p>
          {e.comment && <p className="mt-1 text-sm text-foreground">{e.comment}</p>}
        </li>
      ))}
    </ol>
  );
}
