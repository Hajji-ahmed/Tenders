"use client";

import { Building2, CalendarClock, MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { cn } from "cn";

import { SCORE_TEXT, formatDate } from "@/components/tenders/TendersTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TENDER_STATUS_LABELS, nextStatuses, scoreLevel, urgencyOf } from "@/lib/tenders";
import type { KanbanColumn, Tender, TenderStatus } from "@/lib/types";

type Props = {
  columns: KanbanColumn[];
  onChangeStatus: (tender: Tender, status: TenderStatus) => Promise<void> | void;
};

// Teinte de l'en-tête de colonne selon l'étape du cycle : découverte (bleu), décision (jaune),
// production (vert), issue (vert foncé / gris).
const COLUMN_TONE: Record<TenderStatus, string> = {
  NOUVEAU: "border-brand-blue",
  A_ANALYSER: "border-brand-blue",
  GO: "border-brand-yellow",
  NO_GO: "border-border",
  PREPARATION: "border-brand-green",
  VALIDATION: "border-brand-green",
  PRET: "border-brand-green",
  SOUMIS: "border-brand-green-ink",
  GAGNE: "border-brand-green-dark",
  PERDU: "border-border",
  ARCHIVE: "border-border",
};

function KanbanCard({ tender, onChangeStatus }: { tender: Tender; onChangeStatus: Props["onChangeStatus"] }) {
  const urgency = urgencyOf(tender.days_left);
  const next = nextStatuses(tender.status);
  const level = tender.score_total === null ? null : scoreLevel(tender.score_total).level;
  return (
    <article className="space-y-2 rounded-lg bg-card p-3 text-sm ring-1 ring-foreground/10">
      <div className="flex items-start justify-between gap-2">
        <Link href={`/tenders/${tender.id}`} className="line-clamp-2 font-medium text-foreground hover:text-brand-green-dark hover:underline">
          {tender.title}
        </Link>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" size="icon-sm" aria-label={`Changer le statut de ${tender.title}`} className="-mt-1 -mr-1 shrink-0" />}
          >
            <MoreHorizontal />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuGroup>
              <DropdownMenuLabel>Passer à</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {next.length === 0 ? (
                <DropdownMenuItem disabled>Aucune transition</DropdownMenuItem>
              ) : (
                next.map((status) => (
                  <DropdownMenuItem key={status} onClick={() => onChangeStatus(tender, status)}>
                    {TENDER_STATUS_LABELS[status]}
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {tender.organization && (
        <p className="flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          <Building2 aria-hidden className="size-3.5 shrink-0" />
          {tender.organization}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <CalendarClock aria-hidden className="size-3.5" />
          {tender.deadline_at ? <span className="tabular-nums">{formatDate(tender.deadline_at)}</span> : <span>Sans échéance</span>}
          {tender.days_left !== null && (
            <Badge variant={urgency.level === "critical" ? "warning" : urgency.level === "high" ? "warning-soft" : "muted"} className="h-4 px-1.5 text-[10px]">
              {urgency.label}
            </Badge>
          )}
        </span>
        <span
          className={cn("text-sm font-semibold tabular-nums", level ? SCORE_TEXT[level] : "text-muted-foreground")}
          aria-label={tender.score_total === null ? "Score non calculé" : `Score ${tender.score_total}`}
        >
          {tender.score_total === null ? "—" : tender.score_total}
        </span>
      </div>
    </article>
  );
}

/** Colonnes du cycle de vie ; changement de statut par menu (pas de glisser-déposer en MVP). */
export function KanbanBoard({ columns, onChangeStatus }: Props) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex min-w-max gap-3">
        {columns.map((column) => {
          const label = TENDER_STATUS_LABELS[column.status];
          return (
            <section
              key={column.status}
              aria-label={`${label} (${column.items.length})`}
              className="flex w-64 shrink-0 flex-col rounded-xl bg-muted/50 p-2"
            >
              <h2 className={cn("mb-2 flex items-center justify-between border-t-[3px] px-1 pt-2 text-sm font-semibold text-brand-green-dark", COLUMN_TONE[column.status])}>
                {label}
                <span className="rounded-full bg-card px-2 text-xs font-semibold tabular-nums text-muted-foreground ring-1 ring-foreground/10">
                  {column.items.length}
                </span>
              </h2>
              <div className="flex flex-1 flex-col gap-2">
                {column.items.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-border px-2 py-6 text-center text-xs text-muted-foreground">Vide</p>
                ) : (
                  column.items.map((t) => <KanbanCard key={t.id} tender={t} onChangeStatus={onChangeStatus} />)
                )}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
