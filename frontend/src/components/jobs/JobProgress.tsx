"use client";

import { CheckCircle2, CircleAlert, LoaderCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { cn } from "cn";

import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import { useJob } from "@/lib/queries/jobs";
import type { Job } from "@/lib/types";

type Props = {
  jobId: string;
  className?: string;
  /** Appelé une seule fois quand le job atteint un état final (done / failed) — pour rafraîchir les listes. */
  onSettled?: (job: Job) => void;
};

const plural = (n: number, one: string, many: string) => `${n} ${n > 1 ? many : one}`;

/** Une ligne de bilan par type de job ; à défaut, le dernier message de progression. */
function summary(job: Job): string | null {
  const r = job.result;
  switch (job.type) {
    case "search_tenders": {
      if (!r) return job.message;
      const created = Number(r.created ?? 0);
      const parts = [plural(created, "nouvelle opportunité", "nouvelles opportunités")];
      if (Number(r.merged ?? 0)) parts.push(plural(Number(r.merged), "annonce fusionnée", "annonces fusionnées"));
      if (Number(r.skipped ?? 0)) parts.push(plural(Number(r.skipped), "déjà connue", "déjà connues"));
      return parts.join(" · ");
    }
    case "download_tender_documents": {
      if (!r) return job.message;
      const parts = [plural(Number(r.done ?? 0), "pièce téléchargée", "pièces téléchargées")];
      if (Number(r.failed ?? 0)) parts.push(`${r.failed} en échec`);
      return parts.join(" · ");
    }
    case "calculate_match_score":
      return r && r.total !== undefined ? `Score ${r.total} / 100` : job.message;
    default:
      return job.message;
  }
}

/** Suivi en direct d'un job (sondage toutes les 2 s) : barre, message, résultat ou erreur. */
export function JobProgress({ jobId, className, onSettled }: Props) {
  const job = useJob(jobId, { poll: true });
  const data = job.data;
  const settled = useRef(false);
  useEffect(() => {
    if (!data || settled.current) return;
    if (data.status === "done" || data.status === "failed") {
      settled.current = true;
      onSettled?.(data);
    }
  }, [data, onSettled]);

  if (!data) {
    return (
      <p className={cn("flex items-center gap-2 text-sm text-muted-foreground", className)} aria-busy="true">
        <LoaderCircle aria-hidden className="size-4 animate-spin" />
        Lancement…
      </p>
    );
  }

  if (data.status === "failed") {
    return (
      <div className={cn("rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm", className)}>
        <p className="flex items-center gap-2 font-semibold text-destructive">
          <CircleAlert aria-hidden className="size-4" />
          Échec
        </p>
        <p role="alert" className="mt-0.5 text-destructive">
          {data.error ?? "Erreur inconnue"}
        </p>
      </div>
    );
  }

  if (data.status === "done") {
    const text = summary(data);
    return (
      <div className={cn("rounded-lg border border-brand-green/30 bg-brand-green-tint px-3 py-2 text-sm", className)}>
        <p className="flex items-center gap-2 font-semibold text-brand-green-dark">
          <CheckCircle2 aria-hidden className="size-4 text-brand-green" />
          Terminé
        </p>
        {text && <p className="mt-0.5 text-brand-green-dark/80">{text}</p>}
      </div>
    );
  }

  return (
    <div className={cn("rounded-lg border bg-card px-3 py-2", className)}>
      <Progress value={data.progress} aria-label="Progression de la recherche">
        <ProgressLabel className="flex items-center gap-2 text-brand-green-dark">
          <LoaderCircle aria-hidden className="size-4 animate-spin text-brand-blue" />
          Recherche en cours
        </ProgressLabel>
        <ProgressValue />
      </Progress>
      {data.message && <p className="mt-1.5 text-xs text-muted-foreground">{data.message}</p>}
    </div>
  );
}
