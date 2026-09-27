import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EvidencePopover, evidenceHref, evidenceLabel } from "@/components/tenders/EvidencePopover";
import type { Evidence } from "@/lib/types";

const evidence: Evidence[] = [
  { kind: "chunk", id: "c1", label: "Kbis.pdf p. 2", document_id: "doc-kbis", page: 2 },
  { kind: "document", id: "d1", label: "Attestation fiscale 2026" },
  { kind: "expert", id: "e1", label: "Nadia F. — Chef de projet énergie" },
  { kind: "answer", id: "a1", label: "Oui, attestation CNSS du 3 septembre 2026" },
];

describe("EvidencePopover", () => {
  it("shows the number of proofs and opens the list", async () => {
    render(<EvidencePopover code="ADM-001" evidence={evidence} />);
    const trigger = screen.getByRole("button", { name: /4 preuves/i });

    await userEvent.click(trigger);

    const popover = await screen.findByRole("dialog", { name: /preuves/i });
    const items = within(popover).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items[0]).toHaveTextContent("Kbis.pdf — p. 2");
    expect(within(items[0]).getByText("Extrait de document")).toBeInTheDocument();
    expect(items[3]).toHaveTextContent("Votre réponse");
  });

  it("links a document proof to the document, a profile proof to its tab, and leaves an answer alone", async () => {
    render(<EvidencePopover code="ADM-001" evidence={evidence} />);
    await userEvent.click(screen.getByRole("button", { name: /4 preuves/i }));
    const popover = await screen.findByRole("dialog", { name: /preuves/i });

    expect(within(popover).getByRole("link", { name: /kbis/i })).toHaveAttribute(
      "href",
      "/documents?open=doc-kbis", // l'extrait mène à la pièce dont il vient
    );
    expect(within(popover).getByRole("link", { name: /attestation fiscale/i })).toHaveAttribute(
      "href",
      "/documents?open=d1",
    );
    expect(within(popover).getByRole("link", { name: /nadia/i })).toHaveAttribute(
      "href",
      "/company?tab=experts&id=e1",
    );
    expect(within(popover).queryByRole("link", { name: /votre réponse|oui, attestation/i })).not.toBeInTheDocument();
  });

  it("renders nothing when a requirement has no proof", () => {
    const { container } = render(<EvidencePopover code="ADM-002" evidence={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("evidence helpers", () => {
  it("names a chunk after its file and page, as cited by the model", () => {
    expect(evidenceLabel({ kind: "chunk", id: "c1", label: "Kbis.pdf p. 2" })).toBe("Kbis.pdf — p. 2");
    expect(evidenceLabel({ kind: "document", id: "d1", label: "Kbis.pdf" })).toBe("Kbis.pdf");
  });

  it("routes each kind of proof to the page that holds it", () => {
    expect(evidenceHref({ kind: "certification", id: "x", label: "ISO 14001" })).toBe(
      "/company?tab=certifications&id=x",
    );
    expect(evidenceHref({ kind: "project", id: "p", label: "Audit" })).toBe("/company?tab=projects&id=p");
    expect(evidenceHref({ kind: "chunk", id: "c", label: "a.pdf p. 1" })).toBeNull(); // le morceau n'a pas de page
    expect(evidenceHref({ kind: "answer", id: "a", label: "Oui" })).toBeNull();
  });
});
