import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentDrawer } from "@/components/documents/DocumentDrawer";
import type { CompanyDocument, DocumentVersion } from "@/lib/types";

const base: CompanyDocument = {
  id: "d2",
  company_id: "c1",
  name: "RC pro",
  category: "attestation",
  mime_type: "application/pdf",
  size_bytes: 2 * 1024 * 1024,
  sha256: "0123456789abcdef0123456789abcdef",
  version: 2,
  status: "expired",
  issued_at: "2025-01-01",
  expires_at: "2026-01-01",
  description: "Responsabilité civile professionnelle",
  tags: ["assurance", "obligatoire"],
  extraction_status: "done",
  is_expired: true,
  is_usable: false,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const versions: DocumentVersion[] = [
  { id: "v2", document_id: "d2", version_number: 2, sha256: "b", author: "test@innosustain.com", changelog: "Renouvellement 2026", created_at: "2026-09-01T10:00:00Z" },
  { id: "v1", document_id: "d2", version_number: 1, sha256: "a", author: null, changelog: null, created_at: "2025-01-01T10:00:00Z" },
];

const state = { doc: base as CompanyDocument };
const archive = vi.fn().mockResolvedValue(undefined);

vi.mock("@/lib/queries/documents", () => ({
  useDocument: () => ({ data: state.doc, isPending: false, isError: false }),
  useDocumentVersions: () => ({ data: versions, isPending: false, isError: false }),
  useUpdateDocument: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useNewVersion: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useArchiveDocument: () => ({ mutateAsync: archive, isPending: false }),
}));

beforeEach(() => {
  state.doc = base;
  archive.mockClear();
});

describe("DocumentDrawer", () => {
  it("shows the document, its status, metadata, versions and download link", () => {
    render(<DocumentDrawer documentId="d2" onOpenChange={() => {}} />);
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByRole("heading", { name: "RC pro" })).toBeInTheDocument();
    expect(within(drawer).getByText("Expiré")).toBeInTheDocument();
    expect(within(drawer).getByText("Attestation")).toBeInTheDocument();
    expect(within(drawer).getByText("2 Mo")).toBeInTheDocument();
    expect(within(drawer).getByText("assurance")).toBeInTheDocument();
    expect(within(drawer).getByText("Renouvellement 2026")).toBeInTheDocument();
    expect(within(drawer).getByText("v1")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: /télécharger/i })).toHaveAttribute("href", "/api/v1/documents/d2/download");
  });

  it("offers a new version and archiving only while the document is not archived", () => {
    const { unmount } = render(<DocumentDrawer documentId="d2" onOpenChange={() => {}} />);
    expect(screen.getByRole("button", { name: /nouvelle version/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /archiver/i })).toBeInTheDocument();
    unmount();

    state.doc = { ...base, status: "archived" };
    render(<DocumentDrawer documentId="d2" onOpenChange={() => {}} />);
    expect(screen.queryByRole("button", { name: /nouvelle version/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /archiver/i })).not.toBeInTheDocument();
  });

  it("archives after confirmation and closes", async () => {
    const onOpenChange = vi.fn();
    render(<DocumentDrawer documentId="d2" onOpenChange={onOpenChange} />);
    await userEvent.click(screen.getByRole("button", { name: /^archiver$/i }));
    const confirm = await screen.findByRole("dialog", { name: /archiver « RC pro »/i });
    await userEvent.click(within(confirm).getByRole("button", { name: /^archiver$/i }));
    await waitFor(() => expect(archive).toHaveBeenCalledWith("d2"));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
