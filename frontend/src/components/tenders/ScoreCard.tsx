"use client";

import { Calculator, RefreshCw, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { cn } from "cn";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { scoreLevel, type ScoreLevel } from "@/lib/tenders";
import type { TenderScore } from "@/lib/types";

type Props = {
  /** `undefined` = chargement, `null` = pas encore calculé. */
  score: TenderScore | null | undefined;
  onCompute: () => void;
  computing?: boolean;
};

const RING: Record<ScoreLevel, string> = {
  high: "border-brand-green text-brand-green-dark",
  medium: "border-brand-yellow text-brand-yellow-ink",
  low: "border-destructive/60 text-destructive",
};

const FALLBACK_PREFIX = "Justification IA indisponible";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });
}

function Points({ title, items, icon: Icon, tone }: { title: string; items: string[]; icon: typeof ThumbsUp; tone: "green" | "red" }) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <p className={cn("flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide", tone === "green" ? "text-brand-green-dark" : "text-destructive")}>
        <Icon aria-hidden className="size-3.5" />
        {title}
      </p>
      <ul className="space-y-1 text-sm">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden className={cn("mt-2 size-1.5 shrink-0 rounded-full", tone === "green" ? "bg-brand-green" : "bg-destructive/70")} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Score de pertinence /100 avec son niveau, la justification IA (RB-005 : « à vérifier ») et l'ajustement. */
export function ScoreCard({ score, onCompute, computing = false }: Props) {
  if (score === undefined) {
    return <Skeleton className="h-48 w-full rounded-xl" />;
  }

  if (score === null) {
    return (
      <Card accent="blue">
        <CardHeader>
          <CardTitle>Score de pertinence</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-muted-foreground">Le score n&apos;est pas encore calculé pour cette opportunité.</p>
          <Button onClick={onCompute} disabled={computing}>
            <Calculator />
            {computing ? "Calcul en cours…" : "Calculer le score"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { level, label, variant } = scoreLevel(score.total);
  const fallback = score.justification.startsWith(FALLBACK_PREFIX);

  return (
    <Card accent={level === "high" ? "green" : level === "medium" ? "yellow" : "none"}>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-4">
          <span
            className={cn("flex size-20 shrink-0 flex-col items-center justify-center rounded-full border-4 bg-card", RING[level])}
            aria-label={`Score ${score.total} sur 100`}
          >
            <span className="text-2xl font-bold leading-none tabular-nums">{score.total}</span>
            <span className="mt-0.5 text-[10px] font-medium text-muted-foreground">/ 100</span>
          </span>
          <div className="space-y-1.5">
            <CardTitle>Score de pertinence</CardTitle>
            <Badge variant={variant}>{label}</Badge>
            <p className="text-xs text-muted-foreground">
              Calculé le {formatDateTime(score.computed_at)} · règles v{score.scoring_version}
              {score.ai_adjustment !== 0 && (
                <>
                  {" "}
                  · ajustement IA{" "}
                  <span className="font-semibold text-foreground">
                    {score.ai_adjustment > 0 ? "+" : ""}
                    {score.ai_adjustment} pts
                  </span>
                </>
              )}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={onCompute} disabled={computing} aria-label="Recalculer le score">
          <RefreshCw className={cn(computing && "animate-spin")} />
          {computing ? "Recalcul…" : "Recalculer"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className={cn("rounded-lg border px-3 py-2.5 text-sm", fallback ? "border-border bg-muted/40" : "border-brand-blue/30 bg-brand-blue-tint/60")}>
          <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-blue-dark">
            <Sparkles aria-hidden className="size-3.5" />
            {fallback ? "Justification (règles seules)" : "Justification — Assistance IA — à vérifier"}
          </p>
          <p className="leading-relaxed text-foreground">{score.justification}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Points title="Atouts" items={score.strengths} icon={ThumbsUp} tone="green" />
          <Points title="Points d'attention" items={score.weaknesses} icon={ThumbsDown} tone="red" />
        </div>
      </CardContent>
    </Card>
  );
}
