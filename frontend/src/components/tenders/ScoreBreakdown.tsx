"use client";

import { Check, X } from "lucide-react";
import { cn } from "cn";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SCORE_LABELS, scoreLevel, type ScoreLevel } from "@/lib/tenders";
import type { SubScore } from "@/lib/types";

type Props = { breakdown: SubScore[] };

const BAR: Record<ScoreLevel, string> = {
  high: "bg-brand-green",
  medium: "bg-brand-yellow",
  low: "bg-destructive/70",
};

function Chips({ items, kind }: { items: string[]; kind: "matched" | "missing" }) {
  if (items.length === 0) return null;
  const Icon = kind === "matched" ? Check : X;
  return (
    <ul className="flex flex-wrap gap-1" aria-label={kind === "matched" ? "Reconnu" : "Manquant"}>
      {items.map((item) => (
        <li
          key={item}
          className={cn(
            "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs",
            kind === "matched" ? "bg-brand-green-tint text-brand-green-dark" : "bg-destructive/10 text-destructive",
          )}
        >
          <Icon aria-hidden className="size-3" />
          {item}
        </li>
      ))}
    </ul>
  );
}

/** Les huit critères du score : sous-score, poids, raison en français, ce qui est reconnu / manquant. */
export function ScoreBreakdown({ breakdown }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Critère</TableHead>
          <TableHead className="w-40">Score</TableHead>
          <TableHead className="w-16 text-right">Poids</TableHead>
          <TableHead>Explication</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {breakdown.map((s) => {
          const { level } = scoreLevel(s.score);
          const label = SCORE_LABELS[s.key as keyof typeof SCORE_LABELS] ?? s.key;
          return (
            <TableRow key={s.key} data-level={level}>
              <TableCell className="font-medium text-foreground">{label}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <span className="w-10 text-right font-semibold tabular-nums text-brand-green-dark">{s.score}</span>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
                    <span className={cn("block h-full rounded-full", BAR[level])} style={{ width: `${s.score}%` }} />
                  </span>
                </div>
              </TableCell>
              <TableCell className="text-right tabular-nums text-muted-foreground">{s.weight} %</TableCell>
              <TableCell className="max-w-[28rem] space-y-1.5 whitespace-normal">
                <p>{s.reason}</p>
                <Chips items={s.matched} kind="matched" />
                <Chips items={s.missing} kind="missing" />
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
