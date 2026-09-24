import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EligibilitySummaryCard } from "@/components/tenders/EligibilitySummary";
import { RequirementsTable } from "@/components/tenders/RequirementsTable";
import type { EligibilitySummary, TenderRequirement } from "@/lib/types";

function req(over: Partial<TenderRequirement>): TenderRequirement {
  return {
    id: "r1",
    tender_id: "t1",
    code: "ADM-001",
    category: "administrative",
    description: "Attestation fiscale de moins d'un an",
    is_mandatory: true,
    evidence_required: "Attestation fiscale",
    priority: "CRITIQUE",
    status: "CONFORME",
    justification: "Document disponible : Attestation fiscale 2026",
    evidence: [{ kind: "document", id: "d1", label: "Attestation fiscale 2026" }],
    manual_status: false,
    source_document_id: "td1",
    source_document_name: "RC-27-2026.pdf",
    source_page: 2,
    source_excerpt: "Le candidat fournit une attestation fiscale…",
    updated_at: "2026-09-21T10:00:00Z",
    ...over,
  };
}

const requirements: TenderRequirement[] = [
  req({}),
  req({
    id: "r2",
    code: "ADM-002",
    description: "Attestation CNSS de moins de trois mois",
    status: "INFO_MANQUANTE",
    justification: "Aucun document correspondant dans la base documentaire",
    evidence: [],
    source_page: null,
  }),
  req({
    id: "r3",
    code: "EXP-001",
    category: "experience",
    description: "Deux références de plus de 3 000 points lumineux",
    status: "NON_CONFORME",
    justification: "2 requis dans le secteur Éclairage public ; 0 projet au profil",
    evidence: [],
    priority: "IMPORTANTE",
  }),
  req({
    id: "r4",
    code: "METH-001",
    category: "methodologie",
    description: "Note méthodologique détaillée",
    is_mandatory: false,
    status: "A_VERIFIER",
    justification: "À apprécier par un humain (méthodologie / divers)",
    evidence: [],
    priority: "FACULTATIVE",
    manual_status: true,
  }),
];

const summary: EligibilitySummary = {
  total: 4,
  by_status: { CONFORME: 1, A_VERIFIER: 1, NON_CONFORME: 1, INFO_MANQUANTE: 1 },
  mandatory_unmet: ["ADM-002", "EXP-001"],
  ratio: 0.375,
  evaluated_at: "2026-09-21T11:30:00Z",
};

describe("RequirementsTable", () => {
  it("shows the RB-003 banner naming the unmet mandatory requirements", () => {
    render(<RequirementsTable requirements={requirements} summary={summary} onUpdate={vi.fn()} />);
    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent("2 exigences obligatoires non satisfaites");
    expect(banner).toHaveTextContent("ADM-002");
    expect(banner).toHaveTextContent("EXP-001");
  });

  it("hides the banner when every mandatory requirement is met", () => {
    render(
      <RequirementsTable requirements={requirements} summary={{ ...summary, mandatory_unmet: [] }} onUpdate={vi.fn()} />,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("lists each requirement with its status badge, category, source and justification", () => {
    render(<RequirementsTable requirements={requirements} summary={summary} onUpdate={vi.fn()} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(4);

    expect(rows[0]).toHaveTextContent("ADM-001");
    expect(within(rows[0]).getByText("Conforme")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Administrative")).toBeInTheDocument();
    expect(within(rows[0]).getByText("RC-27-2026.pdf — p. 2")).toBeInTheDocument();
    expect(rows[0]).toHaveTextContent("Document disponible : Attestation fiscale 2026");
    const evidence = within(rows[0]).getByRole("list", { name: /preuves/i });
    expect(within(evidence).getByTitle("Document")).toHaveTextContent("Attestation fiscale 2026");
    expect(within(rows[0]).getByTitle(/obligatoire/i)).toBeInTheDocument();

    expect(within(rows[1]).getByText("Information manquante")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Non conforme")).toBeInTheDocument();
    expect(within(rows[3]).getByText("À vérifier")).toBeInTheDocument();
    expect(within(rows[3]).getByText(/saisi à la main/i)).toBeInTheDocument();
  });

  it("filters by status, category and obligation", async () => {
    render(<RequirementsTable requirements={requirements} summary={summary} onUpdate={vi.fn()} />);
    const codes = () =>
      screen
        .getAllByRole("row")
        .slice(1)
        .map((r) => within(r).getAllByRole("cell")[0].textContent?.match(/[A-Z]+-\d+/)?.[0] ?? "");

    await userEvent.selectOptions(screen.getByLabelText("Statut"), "NON_CONFORME");
    expect(codes()).toEqual(["EXP-001"]);

    await userEvent.selectOptions(screen.getByLabelText("Statut"), "");
    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "administrative");
    expect(codes()).toEqual(["ADM-001", "ADM-002"]);

    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "");
    await userEvent.click(screen.getByLabelText(/obligatoires seulement/i));
    expect(codes()).toEqual(["ADM-001", "ADM-002", "EXP-001"]);
  });

  it("edits a status inline", async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<RequirementsTable requirements={requirements} summary={summary} onUpdate={onUpdate} />);
    const row = screen.getAllByRole("row")[2]; // ADM-002
    expect(within(row).queryByLabelText("Statut de ADM-002")).not.toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: /modifier le statut de ADM-002/i }));
    await userEvent.selectOptions(within(row).getByLabelText("Statut de ADM-002"), "CONFORME");
    expect(onUpdate).toHaveBeenCalledWith("r2", { status: "CONFORME" });
  });

  it("invites to run the analysis when there is no requirement yet", () => {
    render(<RequirementsTable requirements={[]} summary={null} onUpdate={vi.fn()} />);
    expect(screen.getByText(/aucune exigence/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("EligibilitySummaryCard", () => {
  it("shows the ratio, the counters by status and the evaluation date", () => {
    render(<EligibilitySummaryCard summary={summary} onEvaluate={vi.fn()} />);
    expect(screen.getByText("38 %")).toBeInTheDocument();
    expect(screen.getByText(/4 exigences/)).toBeInTheDocument();
    const conforme = screen.getByText("Conforme").closest("li");
    expect(conforme).toHaveTextContent("1");
    expect(screen.getByText(/21\/09\/2026/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /évaluer à nouveau/i })).toBeInTheDocument();
  });

  it("offers a first evaluation when none was made", async () => {
    const onEvaluate = vi.fn();
    render(<EligibilitySummaryCard summary={null} onEvaluate={onEvaluate} />);
    expect(screen.getByText(/pas encore évaluée/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /évaluer l'éligibilité/i }));
    expect(onEvaluate).toHaveBeenCalledTimes(1);
  });
});
