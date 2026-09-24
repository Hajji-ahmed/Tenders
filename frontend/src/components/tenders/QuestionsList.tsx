"use client";

import { CircleSlash, MessageCircleQuestion, Send, Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PRIORITY_LABELS, PRIORITY_ORDER, REQUIREMENT_STATUS } from "@/lib/requirements";
import type { Priority, Question } from "@/lib/types";

type Props = {
  questions: Question[];
  onAnswer: (questionId: string, answer: string) => Promise<void> | void;
  onSkip: (questionId: string) => Promise<void> | void;
  onGenerate: () => void;
  /** Un job (évaluation, génération) est en cours. */
  busy?: boolean;
};

const PRIORITY_BADGE: Record<Priority, "warning" | "warning-soft" | "muted"> = {
  CRITIQUE: "warning",
  IMPORTANTE: "warning-soft",
  FACULTATIVE: "muted",
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });
}

function QuestionCard({ question, onAnswer, onSkip, busy }: Omit<Props, "questions" | "onGenerate"> & { question: Question }) {
  const [editing, setEditing] = useState(question.status !== "answered");
  const [text, setText] = useState(question.answer?.answer ?? "");
  const [invalid, setInvalid] = useState(false);
  const [sending, setSending] = useState(false);
  const state = REQUIREMENT_STATUS[question.requirement_status];

  async function submit() {
    const value = text.trim();
    if (!value) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setSending(true);
    try {
      await onAnswer(question.id, value);
      setEditing(false);
    } finally {
      setSending(false);
    }
  }

  return (
    <li className="space-y-2.5 rounded-xl bg-card p-3 ring-1 ring-foreground/10">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant="outline">{question.requirement_code}</Badge>
        <Badge variant={state.variant}>{state.label}</Badge>
        {question.is_mandatory && <span className="text-destructive">Exigence obligatoire</span>}
        {question.status === "skipped" && <span className="text-muted-foreground">Question ignorée</span>}
        {question.answer && (
          <span className="ml-auto text-muted-foreground">Répondu le {formatDateTime(question.answer.answered_at)}</span>
        )}
      </div>

      <p className="flex items-start gap-1.5 text-sm text-foreground">
        <Sparkles aria-hidden className="mt-0.5 size-3.5 shrink-0 text-brand-blue" />
        {question.text}
      </p>

      {question.answer && !editing ? (
        <div className="flex flex-wrap items-start gap-2">
          <p className="min-w-0 flex-1 rounded-lg bg-brand-green-tint/60 px-3 py-2 text-sm text-brand-green-dark">
            {question.answer.answer}
          </p>
          <Button variant="outline" size="sm" onClick={() => setEditing(true)} disabled={busy}>
            Modifier la réponse
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          <Label htmlFor={`answer-${question.id}`} className="text-xs text-muted-foreground">
            Votre réponse à {question.requirement_code}
          </Label>
          <Textarea
            id={`answer-${question.id}`}
            rows={2}
            value={text}
            aria-invalid={invalid}
            placeholder="Ex. : Oui, attestation CNSS du 3 septembre 2026 — ou : Non, profil à recruter"
            onChange={(e) => {
              setText(e.target.value);
              if (invalid) setInvalid(false);
            }}
          />
          {invalid && (
            <p role="alert" className="text-xs text-destructive">
              Saisissez une réponse : « Oui » ou « Non » suffit, précisez si vous le pouvez.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void submit()} disabled={busy || sending}>
              <Send />
              Répondre
            </Button>
            {question.status === "open" && (
              <Button variant="ghost" size="sm" onClick={() => void onSkip(question.id)} disabled={busy || sending}>
                <CircleSlash />
                Ignorer
              </Button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

/** Questions ciblées groupées par priorité : réponse (qui re-juge l'exigence), abandon, génération.
 * Une réponse « Oui » / « Non » suffit ; elle prime sur le jugement des règles (RB-005 : IA à vérifier). */
export function QuestionsList({ questions, onAnswer, onSkip, onGenerate, busy = false }: Props) {
  const open = questions.filter((q) => q.status === "open").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <MessageCircleQuestion aria-hidden className="size-4 text-brand-blue" />
          {questions.length === 0
            ? "Rien à traiter pour l'instant."
            : `${open} question${open > 1 ? "s" : ""} à traiter sur ${questions.length}`}
        </p>
        <Button variant={questions.length === 0 ? "default" : "outline"} size="sm" onClick={onGenerate} disabled={busy}>
          <Sparkles />
          {questions.length === 0 ? "Générer les questions" : "Générer les questions manquantes"}
        </Button>
      </div>

      {questions.length === 0 ? (
        <p className="rounded-xl border border-dashed border-brand-blue/40 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
          Aucune question : l&apos;évaluation d&apos;éligibilité en pose une par exigence qu&apos;elle ne peut pas
          trancher (document absent, référence à confirmer, profil manquant). Vos réponses mettent à jour les statuts.
        </p>
      ) : (
        PRIORITY_ORDER.map((priority) => {
          const group = questions.filter((q) => q.priority === priority);
          if (group.length === 0) return null;
          return (
            <section key={priority} aria-label={PRIORITY_LABELS[priority]} className="space-y-2">
              <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-brand-green-dark/80">
                <Badge variant={PRIORITY_BADGE[priority]}>{PRIORITY_LABELS[priority]}</Badge>
                {group.length} question{group.length > 1 ? "s" : ""}
              </h3>
              <ul className="space-y-2">
                {group.map((question) => (
                  <QuestionCard key={question.id} question={question} onAnswer={onAnswer} onSkip={onSkip} busy={busy} />
                ))}
              </ul>
            </section>
          );
        })
      )}
    </div>
  );
}
