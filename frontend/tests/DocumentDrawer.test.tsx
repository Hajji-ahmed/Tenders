import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as baseRender, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  page_count: 2,
  is_expired: true,
  is_usable: false,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const versions: DocumentVersion[] = [
  { id: "v2", document_id: "d2", version_number: 2, sha256: "b", author: "test@innosustain.com", changelog: "Renouvellement 2026", created_at: "2026-09-01T10:00:00Z" },
  { id: "v1", document_id: "d2", version_number: 1, sha256: "a", author: null, changelog: null, created_at: "2025-01-01T10:00:00Z" },
];

/** `fetch` simulé plutôt qu'un `vi.mock` du module de requêtes : les fichiers de test partagent un
 * worker (`isolate: false`), et un module déjà chargé par un autre fichier échappe au mock. */
const state = { doc: base as CompanyDocument };
const calls: { method: string; url: string }[] = [];

function render(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return baseRender(ui, { wrapper });
}

/** Le tiroir affiché avec son document chargé (les squelettes ont disparu). */
async function openDrawer(onOpenChange: (open: boolean) => void = () => {}) {
  const result = render(<DocumentDrawer documentId="d2" onOpenChange={onOpenChange} />);
  await screen.findByRole("heading", { name: "RC pro" });
  return result;
}

beforeEach(() => {
  state.doc = base;
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ method: init?.method ?? "GET", url });
      const body = url.endsWith("/versions") ? versions : url.endsWith("/reindex") ? { id: "j1" } : state.doc;
      return { ok: true, status: 200, json: async () => body } as unknown as Response;
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("DocumentDrawer", () => {
  it("shows the document, its status, metadata, versions and download link", async () => {
    await openDrawer();
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByText("Expiré")).toBeInTheDocument();
    expect(within(drawer).getByText("Attestation")).toBeInTheDocument();
    expect(within(drawer).getByText("2 Mo")).toBeInTheDocument();
    expect(within(drawer).getByText("assurance")).toBeInTheDocument();
    expect(await within(drawer).findByText("Renouvellement 2026")).toBeInTheDocument();
    expect(within(drawer).getByText("v1")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: /télécharger/i })).toHaveAttribute("href", "/api/v1/documents/d2/download");
  });

  it("shows the indexing state and can send the document back to the knowledge base", async () => {
    await openDrawer();
    expect(screen.getByText("Indexé")).toBeInTheDocument();
    expect(screen.getByText(/2 pages lues/i)).toBeInTheDocument();
    expect(screen.getByText(/n'est plus cité/i)).toBeInTheDocument(); // document expiré (RB-007)

    await userEvent.click(screen.getByRole("button", { name: /réindexer/i }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "POST", url: "/api/v1/documents/d2/reindex" }),
    );
  });

  it("names a failed indexing plainly", async () => {
    state.doc = { ...base, extraction_status: "failed", page_count: null };
    await openDrawer();
    expect(screen.getByText("Indexation impossible")).toBeInTheDocument();
    expect(screen.queryByText(/pages lues/i)).not.toBeInTheDocument();
  });

  it("offers a new version and archiving only while the document is not archived", async () => {
    const { unmount } = await openDrawer();
    expect(screen.getByRole("button", { name: /nouvelle version/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /archiver/i })).toBeInTheDocument();
    unmount();

    state.doc = { ...base, status: "archived" };
    await openDrawer();
    expect(screen.queryByRole("button", { name: /nouvelle version/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /archiver/i })).not.toBeInTheDocument();
  });

  it("archives after confirmation and closes", async () => {
    const onOpenChange = vi.fn();
    await openDrawer(onOpenChange);
    await userEvent.click(screen.getByRole("button", { name: /^archiver$/i }));
    const confirm = await screen.findByRole("dialog", { name: /archiver « RC pro »/i });
    await userEvent.click(within(confirm).getByRole("button", { name: /^archiver$/i }));
    await waitFor(() =>
      expect(calls).toContainEqual({ method: "DELETE", url: "/api/v1/documents/d2" }),
    );
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
