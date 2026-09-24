"use client";

import { useState } from "react";
import { toast } from "sonner";

import { JobProgress } from "@/components/jobs/JobProgress";
import { QuestionsList } from "@/components/tenders/QuestionsList";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAnswerQuestion, useGenerateQuestions, useQuestions, useSkipQuestion } from "@/lib/queries/questions";
import type { Job } from "@/lib/types";

type Props = { tenderId: string; onAnswered: () => void };

/** Onglet Questions : questions ciblées, génération (job), réponses (qui re-jugent l'exigence) et abandons. */
export function QuestionsSection({ tenderId, onAnswered }: Props) {
  const questions = useQuestions(tenderId);
  const generate = useGenerateQuestions(tenderId);
  const answer = useAnswerQuestion(tenderId);
  const skip = useSkipQuestion(tenderId);
  const [job, setJob] = useState<Job | null>(null);
  const busy = job !== null || generate.isPending;

  async function onGenerate() {
    try {
      setJob(await generate.mutateAsync());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible de lancer la génération.");
    }
  }

  async function onAnswer(questionId: string, text: string) {
    try {
      await answer.mutateAsync({ questionId, answer: text });
      toast.success("Réponse enregistrée — exigence réévaluée");
      onAnswered();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Enregistrement impossible.");
    }
  }

  async function onSkip(questionId: string) {
    try {
      await skip.mutateAsync(questionId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible d'ignorer la question.");
    }
  }

  function onSettled(settled: Job) {
    setJob(null);
    if (settled.status === "failed") toast.error(settled.error ?? "La génération a échoué.");
    void questions.refetch();
  }

  return (
    <Card accent="blue">
      <CardHeader>
        <CardTitle>Questions à trancher</CardTitle>
        <p className="text-sm text-muted-foreground">
          Une question par exigence que les règles n&apos;ont pas pu trancher. Votre réponse fait foi : elle met à jour
          le statut de l&apos;exigence, la synthèse d&apos;éligibilité et le score.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {job && <JobProgress jobId={job.id} onSettled={onSettled} />}
        {questions.isPending ? (
          <Skeleton className="h-48 w-full rounded-xl" />
        ) : questions.isError ? (
          <p role="alert" className="text-sm text-destructive">
            Impossible de charger les questions.
          </p>
        ) : (
          <QuestionsList
            questions={questions.data}
            onAnswer={onAnswer}
            onSkip={onSkip}
            onGenerate={onGenerate}
            busy={busy}
          />
        )}
      </CardContent>
    </Card>
  );
}
