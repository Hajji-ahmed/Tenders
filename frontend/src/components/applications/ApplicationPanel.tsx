"use client";

import { FolderPlus, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { DocumentStatusList } from "@/components/applications/DocumentStatusList";
import { TemplatePicker } from "@/components/applications/TemplatePicker";
import { JobProgress } from "@/components/jobs/JobProgress";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAddDocuments,
  useApplication,
  useGenerateDocuments,
  useOpenApplication,
  useTemplates,
} from "@/lib/queries/applications";
import { useTenderAnalysis } from "@/lib/queries/analysis";
import type { Job, TenderDetail } from "@/lib/types";

type Props = { tender: TenderDetail; onChanged: () => void };

/** Le dossier ne s'ouvre qu'après la décision GO (même règle que l'API). */
const OPENABLE = ["GO", "PREPARATION", "VALIDATION"];

/** Onglet Candidature : ouverture du dossier, choix des modèles, rédaction et relecture. */
export function ApplicationPanel({ tender, onChanged }: Props) {
  const application = useApplication(tender.id);
  const analysis = useTenderAnalysis(tender.id);
  const templates = useTemplates();
  const open = useOpenApplication(tender.id);
  const addDocuments = useAddDocuments(tender.id);
  const generate = useGenerateDocuments();
  const [job, setJob] = useState<Job | null>(null);
  const busy = job !== null || generate.isPending || addDocuments.isPending;

  async function onOpen() {
    try {
      await open.mutateAsync();
      toast.success("Dossier de candidature ouvert");
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible d'ouvrir le dossier.");
    }
  }

  async function onAdd(templateIds: string[]) {
    const id = application.data?.id;
    if (!id) return;
    try {
      const created = await addDocuments.mutateAsync({ applicationId: id, templateIds });
      toast.success(`${created.length} document${created.length > 1 ? "s" : ""} ajouté${created.length > 1 ? "s" : ""}`);
      void application.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Ajout impossible.");
    }
  }

  async function onGenerate(documentIds?: string[]) {
    const id = application.data?.id;
    if (!id) return;
    try {
      setJob(await generate.mutateAsync({ applicationId: id, documentIds }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible de lancer la rédaction.");
    }
  }

  function onSettled(settled: Job) {
    setJob(null);
    if (settled.status === "failed") toast.error(settled.error ?? "La rédaction a échoué.");
    else toast.success("Documents rédigés — à relire avant envoi");
    void application.refetch();
    onChanged();
  }

  if (application.isPending || !templates.data) {
    return <Skeleton className="h-64 w-full rounded-xl" />;
  }

  if (!application.data) {
    const allowed = OPENABLE.includes(tender.status);
    return (
      <Card accent="deep">
        <CardHeader>
          <CardTitle>Dossier de candidature</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {allowed
              ? "Ouvrez le dossier pour préparer les documents : l'opportunité passera en préparation."
              : "Le dossier s'ouvre après la décision GO. Décidez d'abord dans l'onglet Analyse."}
          </p>
          <Button onClick={() => void onOpen()} disabled={!allowed || open.isPending}>
            <FolderPlus />
            Créer le dossier de candidature
          </Button>
        </CardContent>
      </Card>
    );
  }

  const documents = application.data.documents;
  const present = documents.map((d) => d.document_type);

  return (
    <div className="space-y-4">
      {job && <JobProgress jobId={job.id} onSettled={onSettled} />}

      <Card accent="deep">
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Documents à préparer</CardTitle>
          {documents.length > 0 && (
            <Button onClick={() => void onGenerate()} disabled={busy}>
              <Sparkles />
              Rédiger tout le dossier
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Les documents sont rédigés à partir du profil, de l&apos;analyse du dossier et de vos réponses.
            Tout ce qui manque est laissé en clair : rien n&apos;est inventé, rien ne part sans votre relecture.
          </p>
          <TemplatePicker
            templates={templates.data.items}
            requested={analysis.data?.requested_documents ?? []}
            present={present}
            onAdd={onAdd}
            busy={busy}
          />
        </CardContent>
      </Card>

      <DocumentStatusList
        applicationId={application.data.id}
        documents={documents}
        onGenerate={onGenerate}
        busy={busy}
      />
    </div>
  );
}
