"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { tenderKeys } from "@/lib/queries/tenders";
import type { Job, Question, QuestionStatus } from "@/lib/types";

export const questionKeys = {
  list: (id: string, status?: QuestionStatus) => ["tenders", "detail", id, "questions", status ?? "all"] as const,
};

/** Questions ciblées d'une fiche, triées CRITIQUE > IMPORTANTE > FACULTATIVE puis par code d'exigence. */
export function useQuestions(
  id: string,
  { status, enabled = true }: { status?: QuestionStatus; enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: questionKeys.list(id, status),
    queryFn: () => api<Question[]>(`/tenders/${id}/questions${status ? `?status=${status}` : ""}`),
    enabled,
  });
}

/** POST /tenders/{id}/questions/generate — job `generate_questions` (202). */
export function useGenerateQuestions(id: string) {
  return useMutation({
    mutationFn: () => api<Job>(`/tenders/${id}/questions/generate`, { method: "POST" }),
  });
}

/** Une réponse re-juge l'exigence liée, le résumé d'éligibilité et le score : tout l'arbre de la fiche. */
function useInvalidateTender(id: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: tenderKeys.detail(id) });
}

/** POST /questions/{id}/answer. */
export function useAnswerQuestion(tenderId: string) {
  const invalidate = useInvalidateTender(tenderId);
  return useMutation({
    mutationFn: ({ questionId, answer }: { questionId: string; answer: string }) =>
      api<Question>(`/questions/${questionId}/answer`, { method: "POST", body: JSON.stringify({ answer }) }),
    onSuccess: () => invalidate(),
  });
}

/** POST /questions/{id}/skip. */
export function useSkipQuestion(tenderId: string) {
  const invalidate = useInvalidateTender(tenderId);
  return useMutation({
    mutationFn: (questionId: string) => api<Question>(`/questions/${questionId}/skip`, { method: "POST" }),
    onSuccess: () => invalidate(),
  });
}
