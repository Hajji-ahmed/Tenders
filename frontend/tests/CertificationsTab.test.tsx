import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CertificationsTab } from "@/components/company/tabs";
import type { Certification } from "@/lib/types";

const rows: Certification[] = [
  {
    id: "1",
    name: "ISO 14001",
    issuer: "AFNOR",
    category: "qualite",
    issued_at: "2025-01-01",
    expires_at: "2027-01-01",
    document_id: null,
    is_valid: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "2",
    name: "ISO 9001",
    issuer: null,
    category: "qualite",
    issued_at: null,
    expires_at: "2026-08-01",
    document_id: null,
    is_valid: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

vi.mock("@/lib/queries/company", () => ({
  useEntityList: () => ({ data: { items: rows, total: 2, page: 1, size: 100 }, isPending: false, isError: false }),
  useCreateEntity: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateEntity: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteEntity: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe("CertificationsTab", () => {
  it("lists certifications and flags the expired one", () => {
    render(<CertificationsTab />);
    expect(screen.getByText("ISO 14001")).toBeInTheDocument();
    expect(screen.getByText("Valide")).toBeInTheDocument();
    expect(screen.getByText("Expirée")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ajouter/i })).toBeInTheDocument();
  });
});
