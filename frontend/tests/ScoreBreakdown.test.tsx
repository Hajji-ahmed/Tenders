import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScoreBreakdown } from "@/components/tenders/ScoreBreakdown";
import type { SubScore } from "@/lib/types";

const breakdown: SubScore[] = [
  { key: "sector", score: 100, weight: 20, reason: "Secteur « Énergie » = secteur de l'entreprise « Énergie »", matched: ["Énergie"], missing: [] },
  { key: "technologies", score: 50, weight: 15, reason: "1/2 technologies demandées maîtrisées", matched: ["Python"], missing: ["Kafka"] },
  { key: "skills", score: 0, weight: 15, reason: "Aucune compétence de l'entreprise citée dans l'appel d'offres", matched: [], missing: [] },
  { key: "country", score: 100, weight: 10, reason: "Pays de l'entreprise (MA)", matched: ["MA"], missing: [] },
  { key: "budget", score: 50, weight: 10, reason: "Budget non renseigné (appel d'offres ou profil)", matched: [], missing: [] },
  { key: "experience", score: 75, weight: 15, reason: "2 projets réalisés dans le secteur", matched: ["Audit ONEE", "Plan climat"], missing: [] },
  { key: "certifications", score: 33.3, weight: 5, reason: "1/3 certifications exigées détenues et valides", matched: ["ISO 14001"], missing: ["ISO 27001 (expirée)", "ISO 45001"] },
  { key: "eligibility", score: 50, weight: 10, reason: "Éligibilité non évaluée (analyse des exigences à venir)", matched: [], missing: [] },
];

describe("ScoreBreakdown", () => {
  it("renders the eight criteria with score, weight, reason and what is missing", () => {
    render(<ScoreBreakdown breakdown={breakdown} />);
    const rows = screen.getAllByRole("row").slice(1); // sans l'en-tête
    expect(rows).toHaveLength(8);
    expect(within(rows[0]).getByText("Secteur")).toBeInTheDocument();
    expect(within(rows[0]).getByText("100")).toBeInTheDocument();
    expect(within(rows[0]).getByText("20 %")).toBeInTheDocument();
    expect(within(rows[6]).getByText("Certifications")).toBeInTheDocument();
    expect(within(rows[6]).getByText("ISO 27001 (expirée)")).toBeInTheDocument();
    expect(within(rows[6]).getByText("ISO 14001")).toBeInTheDocument();
    expect(within(rows[6]).getByText("33.3")).toBeInTheDocument();
    expect(within(rows[7]).getByText(/non évaluée/)).toBeInTheDocument();
  });

  it("marks weak criteria and strong ones for a quick read", () => {
    render(<ScoreBreakdown breakdown={breakdown} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[2]).toHaveAttribute("data-level", "low"); // compétences 0
    expect(rows[0]).toHaveAttribute("data-level", "high"); // secteur 100
    expect(rows[1]).toHaveAttribute("data-level", "medium"); // technologies 50
  });
});
