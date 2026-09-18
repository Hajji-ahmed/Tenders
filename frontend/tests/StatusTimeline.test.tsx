import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusTimeline } from "@/components/tenders/StatusTimeline";
import type { StatusHistoryEntry } from "@/lib/types";

const entries: StatusHistoryEntry[] = [
  { id: "h1", from_status: "NOUVEAU", to_status: "A_ANALYSER", comment: "Score 72.5 ≥ seuil de pertinence 70", changed_by: null, changed_at: "2026-09-18T10:00:00Z" },
  { id: "h2", from_status: "A_ANALYSER", to_status: "GO", comment: "Bon fit", changed_by: "test@innosustain.com", changed_at: "2026-09-18T11:30:00Z" },
];

describe("StatusTimeline", () => {
  it("lists the changes, newest first, with labels, author and comment", () => {
    render(<StatusTimeline entries={entries} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("À analyser");
    expect(items[0]).toHaveTextContent("Go");
    expect(items[0]).toHaveTextContent("test@innosustain.com");
    expect(items[0]).toHaveTextContent("Bon fit");
    expect(items[1]).toHaveTextContent("Système");
    expect(items[1]).toHaveTextContent("Score 72.5");
  });

  it("renders an empty state", () => {
    render(<StatusTimeline entries={[]} />);
    expect(screen.getByText(/aucun changement/i)).toBeInTheDocument();
  });
});
