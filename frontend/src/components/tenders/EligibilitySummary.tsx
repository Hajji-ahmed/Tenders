"use client";

import { ShieldCheck } from "lucide-react";
import { cn } from "cn";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { REQUIREMENT_STATUS, REQUIREMENT_STATUS_ORDER, eligibilityPercent } from "@/lib/requirements";
import type { EligibilitySummary, RequirementStatus } from "@/lib/types";

type Props = {
  /** `null` : l'éligibilité n'a pas encore été évaluée. */
  summary: EligibilitySummary | null;
  onEvaluate: () => void;
  busy?: boolean;
};

const DOT: Record<RequirementStatus, string> = {
  CONFORME: "bg-brand-green",
  A_VERIFIER: "bg-brand-yellow",
  NON_CONFORME: "bg-destructive",
  INFO_MANQUANTE: "bg-brand-gray",
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });
}

/** Synthèse d'éligibilité : part d'exigences satisfaites, compteurs par statut, date d'évaluation. */
export function EligibilitySummaryCard({ summary, onEvaluate, busy = false }: Props) {
  const percent = summary ? eligibilityPercent(summary.ratio) : null;
  return (
    <Card accent="deep">
      <CardHeader className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck aria-hidden className="size-4 text-brand-green" />
          Éligibilité
        </CardTitle>
        <Button variant={summary ? "outline" : "default"} size="sm" onClick={onEvaluate} disabled={busy}>
          {summary ? "Évaluer à nouveau" : "Évaluer l'éligibilité"}
        </Button>
      </CardHeader>
      <CardContent>
        {summary === null ? (
          <p className="text-sm text-muted-foreground">
            Éligibilité pas encore évaluée. L&apos;évaluation compare chaque exigence au profil de l&apos;entreprise
            (certifications, experts, projets, documents) et pose des questions sur ce qui manque.
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-6">
            <div>
              <p className="text-3xl font-semibold tabular-nums text-brand-green-dark">{percent} %</p>
              <p className="text-xs text-muted-foreground">
                {summary.total} exigence{summary.total > 1 ? "s" : ""}
                {summary.evaluated_at && ` · ${formatDateTime(summary.evaluated_at)}`}
              </p>
            </div>
            <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
              {REQUIREMENT_STATUS_ORDER.map((status) => (
                <li key={status} className="flex items-center gap-1.5">
                  <span aria-hidden className={cn("size-2 rounded-full", DOT[status])} />
                  <span className="font-semibold tabular-nums text-foreground">{summary.by_status[status] ?? 0}</span>
                  <span className="text-muted-foreground">{REQUIREMENT_STATUS[status].label}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
