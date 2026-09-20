import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentsPanel } from "@/components/tenders/DocumentsPanel";
import type { TenderDocumentRef } from "@/lib/types";

function doc(over: Partial<TenderDocumentRef>): TenderDocumentRef {
  return {
    id: "d1",
    tender_id: "t1",
    name: "RC.pdf",
    source_url: "https://portail.ma/rc.pdf",
    mime_type: "application/pdf",
    size_bytes: 9103,
    download_status: "done",
    extraction_status: "done",
    page_count: 2,
    error: null,
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    ...over,
  };
}

const docs: TenderDocumentRef[] = [
  doc({}),
  doc({ id: "d2", name: "scan.pdf", download_status: "done", extraction_status: "failed", error: "PDF protégé ou illisible", page_count: null }),
  doc({ id: "d3", name: "absent.pdf", download_status: "failed", extraction_status: "pending", error: "HTTP 404", size_bytes: null }),
  doc({ id: "d4", name: "annexe.pdf", download_status: "pending", extraction_status: "pending", size_bytes: null }),
];

describe("DocumentsPanel", () => {
  it("lists documents with readable statuses, errors and a download link when the file is stored", () => {
    render(<DocumentsPanel tenderId="t1" documents={docs} onFetch={vi.fn()} onUpload={vi.fn()} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(4);
    expect(rows[0]).toHaveTextContent("RC.pdf");
    expect(rows[0]).toHaveTextContent("8,9 Ko");
    expect(rows[0]).toHaveTextContent("2 pages");
    expect(within(rows[0]).getByRole("link", { name: /télécharger/i })).toHaveAttribute("href", "/api/v1/tenders/t1/documents/d1/download");
    expect(within(rows[0]).getByText("Texte extrait")).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("PDF protégé ou illisible");
    expect(within(rows[1]).getByText("Extraction impossible")).toBeInTheDocument();
    expect(rows[2]).toHaveTextContent("HTTP 404");
    expect(within(rows[2]).getByText("Téléchargement échoué")).toBeInTheDocument();
    expect(within(rows[2]).queryByRole("link", { name: /télécharger/i })).not.toBeInTheDocument();
    expect(within(rows[3]).getByText("En attente")).toBeInTheDocument();
  });

  it("triggers the fetch job and the manual upload", async () => {
    const onFetch = vi.fn();
    const onUpload = vi.fn().mockResolvedValue(undefined);
    render(<DocumentsPanel tenderId="t1" documents={[]} onFetch={onFetch} onUpload={onUpload} />);
    expect(screen.getByText(/aucune pièce/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /récupérer les documents/i }));
    expect(onFetch).toHaveBeenCalledTimes(1);

    const file = new File([new Uint8Array([37, 80, 68, 70])], "CCTP.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText(/déposer une pièce/i), file);
    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("disables the fetch button while a job runs", () => {
    render(<DocumentsPanel tenderId="t1" documents={docs} onFetch={vi.fn()} onUpload={vi.fn()} busy />);
    expect(screen.getByRole("button", { name: /récupérer les documents/i })).toBeDisabled();
  });
});
