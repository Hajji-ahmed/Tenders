import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceTestDialog } from "@/components/sources/SourceTestDialog";
import type { SourceTestReport } from "@/lib/types";

const report: SourceTestReport = {
  status: "ok",
  error: "https://feed/ao/3 : HTTP 404",
  found: 5,
  skipped_known: 1,
  fetched: 3,
  errors: 1,
  extracted: 2,
  queries: ["appel d'offres SI Maroc", "appel d'offres ERP Maroc"],
  candidates: [
    { is_tender: true, confidence: 0.9, title: "AO 1", organization: "Commune A", country: "MA", sector: "IT", deadline_at: "2026-10-30", source_url: "https://feed/ao/1", document_urls: [] },
    { is_tender: true, confidence: 0.7, title: "AO 2", organization: null, country: null, sector: null, deadline_at: null, source_url: "https://feed/ao/2", document_urls: ["https://feed/ao/2/dce.pdf"] },
  ],
};

describe("SourceTestDialog", () => {
  it("shows the counters, the queries and the candidates read", () => {
    render(<SourceTestDialog open onOpenChange={() => {}} sourceName="Flux portail" report={report} pending={false} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Flux portail");
    expect(screen.getByText("Source OK")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument(); // trouvées
    expect(screen.getByText("appel d'offres SI Maroc")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /AO 1/ })).toHaveAttribute("href", "https://feed/ao/1");
    expect(screen.getByText("Commune A")).toBeInTheDocument();
    expect(screen.getByText(/1 pièce/)).toBeInTheDocument();
    expect(screen.getByText(/HTTP 404/)).toBeInTheDocument();
  });

  it("explains an error status and a pending test", () => {
    const { unmount } = render(
      <SourceTestDialog open onOpenChange={() => {}} sourceName="Cassé" report={{ ...report, status: "error", error: "Flux RSS injoignable", candidates: [] }} pending={false} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Flux RSS injoignable");
    expect(screen.getByText("Source en erreur")).toBeInTheDocument();
    unmount();

    render(<SourceTestDialog open onOpenChange={() => {}} sourceName="Cassé" report={null} pending />);
    expect(screen.getByText(/test en cours/i)).toBeInTheDocument();
  });
});
