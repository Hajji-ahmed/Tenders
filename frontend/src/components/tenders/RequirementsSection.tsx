"use client";

import { useState } from "react";
import { toast } from "sonner";

import { JobProgress } from "@/components/jobs/JobProgress";
import { EligibilitySummaryCard } from "@/components/tenders/EligibilitySummary";
import { RequirementsTable } from "@/components/tenders/RequirementsTable";
import { Skeleton } from "@/components/ui/skeleton";
import { useEligibility, useLaunchEligibility, useRequirements, useUpdateRequirement } from "@/lib/queries/requirements";
import type { Job, RequirementUpdate } from "@/lib/types";

type Props = { tenderId: string; onEvaluated: () => void };

/** Onglet Exigences : synthèse d'éligibilité, évaluation (job), tableau des exigences et corrections. */
export function RequirementsSection({ tenderId, onEvaluated }: Props) {
  const requirements = useRequirements(tenderId);
  const eligibility = useEligibility(tenderId);
  const launch = useLaunchEligibility(tenderId);
  const update = useUpdateRequirement(tenderId);
  const [job, setJob] = useState<Job | null>(null);
  const busy = job !== null || launch.isPending;

  async function onEvaluate() {
    try {
      setJob(await launch.mutateAsync());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible de lancer l'évaluation.");
    }
  }

  async function onUpdate(requirementId: string, patch: RequirementUpdate) {
    try {
      await update.mutateAsync({ requirementId, patch });
      toast.success("Statut mis à jour");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Mise à jour impossible.");
    }
  }

  function onSettled(settled: Job) {
    setJob(null);
    if (settled.status === "failed") toast.error(settled.error ?? "L'évaluation a échoué.");
    else toast.success("Éligibilité évaluée");
    void requirements.refetch();
    void eligibility.refetch();
    onEvaluated(); // score, statuts et questions repartent du serveur
  }

  return (
    <div className="space-y-4">
      {job && <JobProgress jobId={job.id} onSettled={onSettled} />}
      {eligibility.isPending ? (
        <Skeleton className="h-28 w-full rounded-xl" />
      ) : (
        <EligibilitySummaryCard summary={eligibility.data ?? null} onEvaluate={onEvaluate} busy={busy} />
      )}
      {requirements.isPending ? (
        <Skeleton className="h-64 w-full rounded-xl" />
      ) : requirements.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Impossible de charger les exigences.
        </p>
      ) : (
        <RequirementsTable
          requirements={requirements.data}
          summary={eligibility.data ?? null}
          onUpdate={onUpdate}
          busy={busy}
        />
      )}
    </div>
  );
}
