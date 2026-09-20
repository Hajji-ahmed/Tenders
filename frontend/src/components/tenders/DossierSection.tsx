"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { JobProgress } from "@/components/jobs/JobProgress";
import { AnalysisPanel } from "@/components/tenders/AnalysisPanel";
import { DocumentsPanel } from "@/components/tenders/DocumentsPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fileProblem } from "@/lib/documents";
import { useFetchDocuments, useLaunchAnalysis, useTenderAnalysis, useTenderDocuments, useUploadTenderDocument } from "@/lib/queries/analysis";
import type { Job } from "@/lib/types";

type Props = { tenderId: string; onTenderChanged: () => void };

/** Onglet Analyse, partie dossier : pièces (récupération, dépôt) et analyse IA structurée du dossier. */
export function DossierSection({ tenderId, onTenderChanged }: Props) {
  const documents = useTenderDocuments(tenderId);
  const analysis = useTenderAnalysis(tenderId);
  const fetchDocs = useFetchDocuments(tenderId);
  const upload = useUploadTenderDocument(tenderId);
  const launch = useLaunchAnalysis(tenderId);
  const [job, setJob] = useState<{ job: Job; kind: "fetch" | "analyze" } | null>(null);
  const busy = job !== null || fetchDocs.isPending || launch.isPending;

  async function onFetch() {
    try {
      setJob({ job: await fetchDocs.mutateAsync(), kind: "fetch" });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible de lancer la récupération.");
    }
  }

  async function onUpload(file: File) {
    const problem = fileProblem(file);
    if (problem) {
      toast.error(problem);
      return;
    }
    try {
      await upload.mutateAsync(file);
      toast.success(`« ${file.name} » déposée`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Dépôt impossible.");
    }
  }

  async function onAnalyze() {
    try {
      setJob({ job: await launch.mutateAsync(), kind: "analyze" });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible de lancer l'analyse.");
    }
  }

  function onSettled(settled: Job) {
    const kind = job?.kind;
    setJob(null);
    if (settled.status === "failed") {
      toast.error(settled.error ?? (kind === "analyze" ? "L'analyse a échoué." : "La récupération a échoué."));
    } else if (kind === "analyze") {
      toast.success("Dossier analysé");
    }
    void documents.refetch();
    void analysis.refetch();
    onTenderChanged(); // résumé, échéance ou référence complétés par l'analyse
  }

  return (
    <>
      <Card accent="deep">
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Pièces du dossier</CardTitle>
          <Button onClick={onAnalyze} disabled={busy}>
            <Sparkles />
            {analysis.data ? "Analyser à nouveau" : "Analyser le dossier"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {job && <JobProgress jobId={job.job.id} onSettled={onSettled} />}
          {documents.isPending ? (
            <Skeleton className="h-20 w-full" />
          ) : documents.isError ? (
            <p role="alert" className="text-sm text-destructive">Impossible de charger les pièces.</p>
          ) : (
            <DocumentsPanel tenderId={tenderId} documents={documents.data} onFetch={onFetch} onUpload={onUpload} busy={busy} />
          )}
        </CardContent>
      </Card>

      {analysis.isPending ? (
        <Skeleton className="h-40 w-full rounded-xl" />
      ) : analysis.data ? (
        <AnalysisPanel analysis={analysis.data} />
      ) : (
        <p className="rounded-xl border border-dashed border-brand-blue/40 bg-card px-6 py-8 text-center text-sm text-muted-foreground">
          Dossier non analysé. Récupérez ou déposez les pièces, puis lancez « Analyser le dossier » : objet, budget,
          dates clés, critères d&apos;évaluation, pièces demandées et conditions d&apos;éligibilité seront extraits
          avec leur page source.
        </p>
      )}
    </>
  );
}
