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

  it("shows « Terminé » with the created count when done", () => {
    state.job = { ...base, status: "done", progress: 100, result: { created: 3, skipped: 1, invalid: 0 } };
    render(<JobProgress jobId="j1" />);
    expect(screen.getByText("Terminé")).toBeInTheDocument();
    expect(screen.getByText(/3 nouvelles opportunités/)).toBeInTheDocument();
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
