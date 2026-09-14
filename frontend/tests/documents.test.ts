import { describe, expect, it } from "vitest";

import {
  buildUploadForm,
  documentDownloadUrl,
  fileKind,
  fileProblem,
  formatBytes,
  MAX_UPLOAD_BYTES,
  STATUS_LABELS,
} from "@/lib/documents";

describe("formatBytes", () => {
  it("renders French units with one decimal at most", () => {
    expect(formatBytes(0)).toBe("0 o");
    expect(formatBytes(512)).toBe("512 o");
    expect(formatBytes(1536)).toBe("1,5 Ko");
    expect(formatBytes(2 * 1024 * 1024)).toBe("2 Mo");
    expect(formatBytes(3.25 * 1024 * 1024 * 1024)).toBe("3,3 Go");
  });
});

describe("fileProblem", () => {
  it("accepts the formats the API allows", () => {
    expect(fileProblem(new File(["x"], "offre.pdf", { type: "application/pdf" }))).toBeNull();
    expect(fileProblem(new File(["x"], "notes.TXT", { type: "text/plain" }))).toBeNull();
  });

  it("rejects an unsupported extension and an oversized file", () => {
    expect(fileProblem(new File(["x"], "photo.png", { type: "image/png" }))).toMatch(/PDF, DOCX, XLSX, TXT, ZIP/);
    const big = new File([new Uint8Array(1)], "gros.pdf", { type: "application/pdf" });
    Object.defineProperty(big, "size", { value: MAX_UPLOAD_BYTES + 1 });
    expect(fileProblem(big)).toMatch(/50 Mo/);
  });
});

describe("buildUploadForm", () => {
  it("sends the file, the category and only the filled metadata; tags are cleaned", () => {
    const file = new File(["x"], "cv.pdf", { type: "application/pdf" });
    const form = buildUploadForm(
      { category: "cv", name: " CV Ahmed ", description: "", issued_at: "", expires_at: "2027-01-01", tags: " a, b,,a " },
      file,
    );
    expect(form.get("file")).toBe(file);
    expect(form.get("category")).toBe("cv");
    expect(form.get("name")).toBe("CV Ahmed");
    expect(form.get("expires_at")).toBe("2027-01-01");
    expect(form.get("tags")).toBe("a, b");
    expect(form.has("issued_at")).toBe(false);
    expect(form.has("description")).toBe(false);
  });
});

describe("labels and links", () => {
  it("maps statuses to French labels and builds the same-origin download link", () => {
    expect(STATUS_LABELS.expired).toBe("Expiré");
    expect(STATUS_LABELS.archived).toBe("Archivé");
    expect(documentDownloadUrl("abc-123")).toBe("/api/v1/documents/abc-123/download");
  });

  it("names the file kind from the MIME type", () => {
    expect(fileKind("application/vnd.openxmlformats-officedocument.wordprocessingml.document")).toBe("DOCX");
    expect(fileKind("application/x-zip-compressed")).toBe("ZIP");
    expect(fileKind("application/pdf")).toBe("PDF");
    expect(fileKind("image/png")).toBe("Fichier");
  });
});
