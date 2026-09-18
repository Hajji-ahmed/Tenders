import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TendersTable } from "@/components/tenders/TendersTable";
import type { Tender, TenderSourceLink } from "@/lib/types";

const links: TenderSourceLink[] = [
  { id: "l1", source_id: "s1", source_name: "Tavily", url: "https://portail.ma/ao/1", title_seen: "Refonte SI", collected_at: "2026-09-14T10:00:00Z" },
  { id: "l2", source_id: "s2", source_name: "Flux portail", url: "https://marches.ma/avis/77", title_seen: null, collected_at: "2026-09-15T10:00:00Z" },
];

const state: { sources: TenderSourceLink[] | undefined; pending: boolean; enabled: boolean | undefined } = {
  sources: links,
  pending: false,
  enabled: undefined,
};

vi.mock("@/lib/queries/tenders", () => ({
  useTenderSources: (_id: string, opts?: { enabled?: boolean }) => {
    state.enabled = opts?.enabled;
    return { data: state.sources, isPending: state.pending, isError: false };
  },
}));

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
    urgency: "high",
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

beforeEach(() => {
  state.sources = links;
  state.pending = false;
  state.enabled = undefined;
});

describe("TendersTable", () => {
  it("renders organisation, country, deadline with urgency, status, sources and score placeholder", () => {
    render(<TendersTable rows={[tender({})]} />);
    expect(screen.getByRole("link", { name: /Refonte du SI/ })).toHaveAttribute("href", "https://portail.ma/ao/1");
    expect(screen.getByText("Commune de Rabat")).toBeInTheDocument();
    expect(screen.getByText("MA")).toBeInTheDocument();
    expect(screen.getByText("30/10/2026")).toBeInTheDocument();
    expect(screen.getByText("3 j")).toBeInTheDocument();
    expect(screen.getByText("Nouveau")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /2 sources/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Score non calculé")).toHaveTextContent("—");
  });

  it("flags a merged tender (several announcements) and not a single-source one", () => {
    render(<TendersTable rows={[tender({}), tender({ id: "t2", title: "Autre", source_count: 1 })]} />);
    expect(screen.getByRole("button", { name: /2 sources/ })).toHaveAttribute("title", "2 annonces regroupées en une fiche");
    expect(screen.getByRole("button", { name: /1 source$/ })).not.toHaveAttribute("title");
  });

  it("lists the source announcements only once the popover is opened", async () => {
    render(<TendersTable rows={[tender({})]} />);
    expect(state.enabled).toBe(false); // pas de requête tant que la liste n'est pas ouverte

    await userEvent.click(screen.getByRole("button", { name: /2 sources/ }));

    expect(state.enabled).toBe(true);
    const popover = await screen.findByRole("dialog", { name: /provenance/i });
    const items = within(popover).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByRole("link", { name: /Refonte SI/ })).toHaveAttribute("href", "https://portail.ma/ao/1");
    expect(within(items[0]).getByText(/Tavily/)).toBeInTheDocument();
    expect(within(items[1]).getByRole("link", { name: /marches\.ma\/avis\/77/ })).toHaveAttribute("href", "https://marches.ma/avis/77");
    expect(within(items[1]).getByText(/Flux portail/)).toBeInTheDocument();
    expect(within(items[1]).getByText(/15\/09\/2026/)).toBeInTheDocument();
  });

  it("handles missing deadline and a GO status", () => {
    render(<TendersTable rows={[tender({ deadline_at: null, days_left: null, urgency: "none", status: "GO", source_count: 1 })]} />);
    expect(screen.getByText("Sans échéance")).toBeInTheDocument();
    expect(screen.getByText("Go")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /1 source$/ })).toBeInTheDocument();
  });

  it("renders an empty state", () => {
    render(<TendersTable rows={[]} />);
    expect(screen.getByText(/aucune opportunité/i)).toBeInTheDocument();
  });
});
