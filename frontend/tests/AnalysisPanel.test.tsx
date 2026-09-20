import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisPanel } from "@/components/tenders/AnalysisPanel";
import type { TenderAnalysis } from "@/lib/types";

const analysis: TenderAnalysis = {
  id: "a1",
  tender_id: "t1",
  object: "Rénovation de l'éclairage public : 4 500 luminaires LED",
  organization: "Commune de Salé",
  reference: "27/2026",
  budget: "18 000 000 MAD TTC",
  duration: "24 mois + 5 ans de maintenance",
  location: "Salé",
  key_dates: [
    { label: "Visite des lieux", date: "2026-10-15", source_page: 4 },
    { label: "Date limite de remise des offres", date: "2026-11-20", source_page: 1 },
    { label: "Démarrage", date: null, source_page: null },
  ],
  deliverables: ["Étude d'exécution", "Plateforme de télégestion"],
  requested_documents: [
    { name: "Attestation fiscale", mandatory: true, source_page: 2 },
    { name: "Lettres de satisfaction", mandatory: false, source_page: 2 },
  ],
  eligibility_conditions: ["Qualification éclairage public classe ≥ 2", "CA > 10 MMAD"],
  summary: "Marché de rénovation LED avec télégestion.",
  model: "gpt-4.1-mini",
  prompt_version: "v1",
  analyzed_at: "2026-09-20T10:00:00Z",
  criteria: [
    { id: "c1", position: 0, name: "Prix", weight: 40, description: "Offre financière", source_page: 2 },
    { id: "c2", position: 1, name: "Valeur technique", weight: 45, description: null, source_page: 2 },
    { id: "c3", position: 2, name: "Délai", weight: null, description: null, source_page: null },
  ],
};

describe("AnalysisPanel", () => {
  it("shows the AI notice, the key facts and the source page next to each dated item", () => {
    render(<AnalysisPanel analysis={analysis} />);
    expect(screen.getByText(/Analyse générée par IA/)).toBeInTheDocument();
    expect(screen.getByText("18 000 000 MAD TTC")).toBeInTheDocument();
    expect(screen.getByText("Commune de Salé")).toBeInTheDocument();
    const visit = screen.getByText("Visite des lieux").closest("li");
    expect(visit).toHaveTextContent("15/10/2026");
    expect(within(visit as HTMLElement).getByText("p. 4")).toBeInTheDocument();
    const start = screen.getByText("Démarrage").closest("li");
    expect(start).toHaveTextContent("date non précisée");
    expect(within(start as HTMLElement).queryByText(/^p\. /)).not.toBeInTheDocument();
  });

  it("lists weighted criteria, requested documents by obligation and eligibility conditions", () => {
    render(<AnalysisPanel analysis={analysis} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Prix");
    expect(rows[0]).toHaveTextContent("40 %");
    expect(within(rows[0]).getByText("p. 2")).toBeInTheDocument();
    expect(rows[2]).toHaveTextContent("—"); // poids inconnu

    const fiscal = screen.getByText("Attestation fiscale").closest("li");
    expect(within(fiscal as HTMLElement).getByText("Obligatoire")).toBeInTheDocument();
    const letters = screen.getByText("Lettres de satisfaction").closest("li");
    expect(within(letters as HTMLElement).getByText("Facultatif")).toBeInTheDocument();
    expect(screen.getByText("CA > 10 MMAD")).toBeInTheDocument();
    expect(screen.getByText("Plateforme de télégestion")).toBeInTheDocument();
    expect(screen.getByText(/20\/09\/2026/)).toBeInTheDocument(); // date d'analyse
  });

  it("renders gracefully when lists are empty", () => {
    render(<AnalysisPanel analysis={{ ...analysis, key_dates: [], criteria: [], requested_documents: [], eligibility_conditions: [], deliverables: [] }} />);
    expect(screen.getAllByText(/non trouvé/i).length).toBeGreaterThanOrEqual(3);
  });
});
