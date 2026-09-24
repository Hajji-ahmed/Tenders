import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobProgress } from "@/components/jobs/JobProgress";
import type { Job } from "@/lib/types";

const state: { job: Partial<Job> | undefined; pending: boolean } = { job: undefined, pending: false };

vi.mock("@/lib/queries/jobs", () => ({
  useJob: () => ({ data: state.job, isPending: state.pending, isError: false }),
  pollInterval: () => false,
}));

const base: Job = {
  id: "j1",
  type: "search_tenders",
  status: "running",
  entity_kind: "search_profile",
  entity_id: "p1",
  progress: 50,
  message: "Source 1/2 : Tavily",
  error: null,
  result: null,
  started_at: "2026-09-14T10:00:00Z",
  finished_at: null,
  created_at: "2026-09-14T10:00:00Z",
};

beforeEach(() => {
  state.job = undefined;
  state.pending = false;
});

describe("JobProgress", () => {
  it("shows the progress and the current message while running", () => {
    state.job = base;
    render(<JobProgress jobId="j1" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("Source 1/2 : Tavily")).toBeInTheDocument();
    expect(screen.getByText(/en cours/i)).toBeInTheDocument();
  });

  it("shows « Terminé » with the created, merged and known counts when done", () => {
    state.job = { ...base, status: "done", progress: 100, result: { created: 3, merged: 2, skipped: 1, invalid: 0 } };
    render(<JobProgress jobId="j1" />);
    expect(screen.getByText("Terminé")).toBeInTheDocument();
    expect(screen.getByText("3 nouvelles opportunités · 2 annonces fusionnées · 1 déjà connue")).toBeInTheDocument();
  });

  it("summarises document, analysis and scoring jobs by their own result", () => {
    state.job = { ...base, type: "download_tender_documents", status: "done", progress: 100, result: { done: 2, failed: 1 } };
    const { unmount } = render(<JobProgress jobId="j1" />);
    expect(screen.getByText("2 pièces téléchargées · 1 en échec")).toBeInTheDocument();
    unmount();

    state.job = { ...base, type: "analyze_tender", status: "done", progress: 100, message: "Analyse terminée : 4 critères, 4 dates clés", result: { indexed: 1, index_failed: 3, criteria: 4 } };
    const second = render(<JobProgress jobId="j1" />);
    expect(screen.getByText("Analyse terminée : 4 critères, 4 dates clés")).toBeInTheDocument();
    second.unmount();

    state.job = { ...base, type: "calculate_match_score", status: "done", progress: 100, result: { total: 72.5, adjustment: 5 } };
    const third = render(<JobProgress jobId="j1" />);
    expect(screen.getByText("Score 72.5 / 100")).toBeInTheDocument();
    third.unmount();

    state.job = { ...base, type: "evaluate_eligibility", status: "done", progress: 100, result: { ratio: 0.375, mandatory_unmet: ["ADM-002", "EXP-001"], questions: 3 } };
    const fourth = render(<JobProgress jobId="j1" />);
    expect(screen.getByText("Éligibilité 38 % · 2 obligatoires non satisfaites · 3 questions à traiter")).toBeInTheDocument();
    fourth.unmount();

    state.job = { ...base, type: "generate_questions", status: "done", progress: 100, result: { created: 2, open: 5 } };
    render(<JobProgress jobId="j1" />);
    expect(screen.getByText("5 questions à traiter (2 nouvelles)")).toBeInTheDocument();
  });

  it("names the running job instead of always saying « Recherche »", () => {
    state.job = { ...base, type: "evaluate_eligibility", message: "Évaluation de 18 exigences" };
    render(<JobProgress jobId="j1" />);
    expect(screen.getByText("Évaluation de l'éligibilité")).toBeInTheDocument();
  });

  it("shows the error message when failed", () => {
    state.job = { ...base, status: "failed", error: "ValueError: Profil de recherche introuvable" };
    render(<JobProgress jobId="j1" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Profil de recherche introuvable");
    expect(screen.getByText("Échec")).toBeInTheDocument();
  });
});

describe("JobProgress onSettled", () => {
  it("notifies once when the job reaches a final state", () => {
    const onSettled = vi.fn();
    state.job = { ...base, status: "done", progress: 100, result: { created: 1 } };
    const { rerender } = render(<JobProgress jobId="j1" onSettled={onSettled} />);
    rerender(<JobProgress jobId="j1" onSettled={onSettled} />);
    expect(onSettled).toHaveBeenCalledTimes(1);
    expect(onSettled).toHaveBeenCalledWith(expect.objectContaining({ status: "done" }));
  });
});
