import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ScoreCard } from "@/components/tenders/ScoreCard";
import type { TenderScore } from "@/lib/types";

const score: TenderScore = {
  id: "s1",
  tender_id: "t1",
  total: 72.5,
  breakdown: [],
  strengths: ["Secteur Énergie", "Pays MA"],
  weaknesses: ["Aucune référence directement comparable"],
  justification: "Le score reflète une bonne adéquation sectorielle.",
  ai_adjustment: 5,
  model: "gpt-4.1-mini",
  prompt_version: "v1",
  scoring_version: "1.0",
  computed_at: "2026-09-18T10:00:00Z",
};

describe("ScoreCard", () => {
  it("shows the total, its level, the AI justification with the verification notice and the adjustment", () => {
    render(<ScoreCard score={score} onCompute={() => {}} />);
    expect(screen.getByText("72.5")).toBeInTheDocument();
    expect(screen.getByText("Pertinent")).toBeInTheDocument();
    expect(screen.getByText("Le score reflète une bonne adéquation sectorielle.")).toBeInTheDocument();
    expect(screen.getByText(/Assistance IA — à vérifier/)).toBeInTheDocument();
    expect(screen.getByText(/\+5 pts/)).toBeInTheDocument();
    expect(screen.getByText("Secteur Énergie")).toBeInTheDocument();
    expect(screen.getByText("Aucune référence directement comparable")).toBeInTheDocument();
    expect(screen.getByText(/18\/09\/2026/)).toBeInTheDocument();
  });

  it("flags a fallback justification when the AI was unavailable", () => {
    render(
      <ScoreCard
        score={{ ...score, total: 33.8, ai_adjustment: 0, model: null, justification: "Justification IA indisponible : Secteur 50/100 · Pays 100/100" }}
        onCompute={() => {}}
      />,
    );
    expect(screen.getByText("Peu pertinent")).toBeInTheDocument();
    expect(screen.getByText(/IA indisponible/)).toBeInTheDocument();
    expect(screen.queryByText(/pts/)).not.toBeInTheDocument();
  });

  it("offers to compute the score when none exists", async () => {
    const onCompute = vi.fn();
    render(<ScoreCard score={null} onCompute={onCompute} />);
    expect(screen.getByText(/pas encore calculé/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /calculer le score/i }));
    expect(onCompute).toHaveBeenCalledTimes(1);
  });

  it("disables the recompute button while a calculation runs", () => {
    render(<ScoreCard score={score} onCompute={() => {}} computing />);
    expect(screen.getByRole("button", { name: /recalculer/i })).toBeDisabled();
  });
});
