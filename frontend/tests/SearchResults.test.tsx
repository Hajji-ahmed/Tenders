import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SearchResults } from "@/components/search/SearchResults";
import type { SearchResults as Results } from "@/lib/types";

const results: Results = {
  query: "cyber",
  semantic: true,
  total: 4,
  groups: [
    {
      kind: "tenders",
      label: "Opportunités",
      items: [
        {
          id: "t1",
          kind: "tenders",
          title: "Audit de cybersécurité du SI",
          subtitle: "Commune de Salé · 27/2026",
          url: "/tenders/t1",
          score: 1,
          excerpt: null,
        },
      ],
    },
    {
      kind: "documents",
      label: "Documents",
      items: [
        {
          id: "d1",
          kind: "documents",
          title: "Politique de cybersécurité",
          subtitle: "administratif · archivé",
          url: "/documents?open=d1",
          score: 1,
          excerpt: null,
        },
        {
          id: "d2",
          kind: "documents",
          title: "RC-27-2026.pdf",
          subtitle: "p. 2",
          url: "/tenders/t9?tab=analysis",
          score: 0.83,
          excerpt: "Le titulaire assure la supervision et la cybersécurité de la plateforme.",
        },
      ],
    },
    {
      kind: "experts",
      label: "Experts",
      items: [
        {
          id: "e1",
          kind: "experts",
          title: "Karim B.",
          subtitle: "Ingénieur cybersécurité · 11 ans d'expérience",
          url: "/company?tab=experts&id=e1",
          score: 1,
          excerpt: null,
        },
      ],
    },
  ],
};

describe("SearchResults", () => {
  it("groups the results by kind with a count and links to the right page", () => {
    render(<SearchResults results={results} />);
    const groups = screen.getAllByRole("region");
    expect(groups.map((g) => g.getAttribute("aria-label"))).toEqual(["Opportunités", "Documents", "Experts"]);
    expect(groups[1]).toHaveTextContent("2");

    const tender = within(groups[0]).getByRole("link", { name: /audit de cybersécurité/i });
    expect(tender).toHaveAttribute("href", "/tenders/t1");
    expect(within(groups[2]).getByRole("link", { name: /karim/i })).toHaveAttribute(
      "href",
      "/company?tab=experts&id=e1",
    );
  });

  it("shows the matching passage and the similarity of a semantic hit", () => {
    render(<SearchResults results={results} />);
    const piece = screen.getByRole("link", { name: /RC-27-2026/ });
    expect(piece).toHaveAttribute("href", "/tenders/t9?tab=analysis");
    const row = piece.closest("li") as HTMLElement;
    expect(row).toHaveTextContent("plateforme");
    expect(within(row).getByText("83 %")).toBeInTheDocument();
    // une correspondance exacte n'affiche pas de pourcentage : il n'apporte rien
    const exact = screen.getByRole("link", { name: /politique de cybersécurité/i }).closest("li");
    expect(within(exact as HTMLElement).queryByText(/%$/)).not.toBeInTheDocument();
  });

  it("invites to type when nothing was searched yet", () => {
    render(<SearchResults results={null} />);
    expect(screen.getByText(/tapez au moins 3 caractères/i)).toBeInTheDocument();
  });

  it("says plainly when a search found nothing", () => {
    render(<SearchResults results={{ query: "zzz", semantic: false, groups: [], total: 0 }} />);
    expect(screen.getByText(/aucun résultat pour « zzz »/i)).toBeInTheDocument();
  });

  it("shows a skeleton while searching", () => {
    render(<SearchResults results={null} loading />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
