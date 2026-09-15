import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TendersTable } from "@/components/tenders/TendersTable";
import type { Tender } from "@/lib/types";

function tender(over: Partial<Tender>): Tender {
  return {
    id: "t1",
    reference: null,
    title: "Refonte du SI",
    organization: "Commune de Rabat",
    organization_type: null,
    country: "MA",
    region: null,
    sector: "IT",
    market_type: null,
    budget_min: null,
    budget_max: null,
    currency: null,
    published_at: null,
    deadline_at: "2026-10-30T23:59:59Z",
    questions_deadline_at: null,
    source_url: "https://portail.ma/ao/1",
    description: null,
    summary: null,
    status: "NOUVEAU",
    urgency: "none",
    is_active: true,
    search_profile_id: null,
    days_left: 3,
    source_count: 2,
    document_count: 1,
    score_total: null,
    created_at: "2026-09-14T00:00:00Z",
    updated_at: "2026-09-14T00:00:00Z",
    ...over,
  };
}

describe("TendersTable", () => {
  it("renders organisation, country, deadline with urgency, status, sources and score placeholder", () => {
    render(<TendersTable rows={[tender({})]} />);
    expect(screen.getByRole("link", { name: /Refonte du SI/ })).toHaveAttribute("href", "https://portail.ma/ao/1");
    expect(screen.getByText("Commune de Rabat")).toBeInTheDocument();
    expect(screen.getByText("MA")).toBeInTheDocument();
    expect(screen.getByText("30/10/2026")).toBeInTheDocument();
    expect(screen.getByText("3 j")).toBeInTheDocument();
    expect(screen.getByText("Nouveau")).toBeInTheDocument();
    expect(screen.getByText("2 sources")).toBeInTheDocument();
    expect(screen.getByLabelText("Score non calculé")).toHaveTextContent("—");
  });

  it("handles missing deadline and a GO status", () => {
    render(<TendersTable rows={[tender({ deadline_at: null, days_left: null, status: "GO", source_count: 1 })]} />);
    expect(screen.getByText("Sans échéance")).toBeInTheDocument();
    expect(screen.getByText("Go")).toBeInTheDocument();
    expect(screen.getByText("1 source")).toBeInTheDocument();
  });

  it("renders an empty state", () => {
    render(<TendersTable rows={[]} />);
    expect(screen.getByText(/aucune opportunité/i)).toBeInTheDocument();
  });
});
