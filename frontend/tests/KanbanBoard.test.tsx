import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { KanbanBoard } from "@/components/tenders/KanbanBoard";
import type { KanbanColumn, Tender } from "@/lib/types";

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
    source_url: null,
    description: null,
    summary: null,
    status: "NOUVEAU",
    urgency: "high",
    is_active: true,
    search_profile_id: null,
    days_left: 3,
    source_count: 1,
    document_count: 0,
    score_total: 72.5,
    created_at: "2026-09-14T00:00:00Z",
    updated_at: "2026-09-14T00:00:00Z",
    ...over,
  };
}

const columns: KanbanColumn[] = [
  { status: "NOUVEAU", items: [tender({})] },
  { status: "A_ANALYSER", items: [] },
  { status: "GO", items: [tender({ id: "t2", title: "Audit énergétique", status: "GO", score_total: null, deadline_at: null, days_left: null })] },
  { status: "NO_GO", items: [] },
  { status: "PREPARATION", items: [] },
  { status: "VALIDATION", items: [] },
  { status: "PRET", items: [] },
  { status: "SOUMIS", items: [] },
  { status: "GAGNE", items: [] },
  { status: "PERDU", items: [] },
  { status: "ARCHIVE", items: [] },
];

describe("KanbanBoard", () => {
  it("renders one column per status, in workflow order, with counts and cards", () => {
    render(<KanbanBoard columns={columns} onChangeStatus={vi.fn()} />);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings[0]).toContain("Nouveau");
    expect(headings[2]).toContain("Go");
    expect(headings).toHaveLength(11);
    const first = screen.getByRole("region", { name: /Nouveau/ });
    expect(within(first).getByRole("link", { name: /Refonte du SI/ })).toHaveAttribute("href", "/tenders/t1");
    expect(within(first).getByText("72.5")).toBeInTheDocument();
    expect(within(first).getByText("30/10/2026")).toBeInTheDocument();
    expect(within(first).getByText("3 j")).toBeInTheDocument();
    const go = screen.getByRole("region", { name: /^Go/ });
    expect(within(go).getByText("—")).toBeInTheDocument(); // sans score
  });

  it("offers only the allowed next statuses in the card menu and reports the choice", async () => {
    const onChangeStatus = vi.fn().mockResolvedValue(undefined);
    render(<KanbanBoard columns={columns} onChangeStatus={onChangeStatus} />);
    const go = screen.getByRole("region", { name: /^Go/ });

    await userEvent.click(within(go).getByRole("button", { name: /changer le statut/i }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getAllByRole("menuitem").map((i) => i.textContent)).toEqual(["Préparation", "No-go"]);
    await userEvent.click(within(menu).getByRole("menuitem", { name: "Préparation" }));

    expect(onChangeStatus).toHaveBeenCalledWith(expect.objectContaining({ id: "t2" }), "PREPARATION");
  });
});
