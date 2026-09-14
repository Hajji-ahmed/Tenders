import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentsTable } from "@/components/documents/DocumentsTable";
import type { CompanyDocument } from "@/lib/types";

function doc(over: Partial<CompanyDocument>): CompanyDocument {
  return {
    id: "d1",
    company_id: "c1",
    name: "Attestation fiscale",
    category: "attestation",
    mime_type: "application/pdf",
    size_bytes: 1536,
    sha256: "abc",
    version: 1,
    status: "valid",
    issued_at: null,
    expires_at: "2027-01-01",
    description: null,
    tags: [],
    extraction_status: "pending",
    is_expired: false,
    is_usable: true,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...over,
  };
}

const rows = [
  doc({ id: "d1" }),
  doc({ id: "d2", name: "RC pro", status: "expired", is_expired: true, is_usable: false, expires_at: "2026-01-01" }),
  doc({ id: "d3", name: "Ancienne plaquette", status: "archived", is_usable: false, expires_at: null, version: 3 }),
];

describe("DocumentsTable", () => {
  it("shows one status badge per row (Valide / Expiré / Archivé)", () => {
    render(<DocumentsTable rows={rows} onOpen={() => {}} />);
    expect(screen.getByText("Valide")).toBeInTheDocument();
    expect(screen.getByText("Expiré")).toBeInTheDocument();
    expect(screen.getByText("Archivé")).toBeInTheDocument();
  });

  it("formats size, category, version and expiry date", () => {
    render(<DocumentsTable rows={rows} onOpen={() => {}} />);
    expect(screen.getAllByText("1,5 Ko")).toHaveLength(3);
    expect(screen.getAllByText("Attestation")).toHaveLength(3);
    expect(screen.getByText("v3")).toBeInTheDocument();
    expect(screen.getByText("01/01/2027")).toBeInTheDocument();
  });

  it("opens a row and links to the same-origin download", async () => {
    const onOpen = vi.fn();
    render(<DocumentsTable rows={rows} onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir RC pro" }));
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "d2" }));
    expect(screen.getByRole("link", { name: "Télécharger RC pro" })).toHaveAttribute("href", "/api/v1/documents/d2/download");
  });

  it("renders an empty state", () => {
    render(<DocumentsTable rows={[]} onOpen={() => {}} />);
    expect(screen.getByText(/aucun document/i)).toBeInTheDocument();
  });
});
