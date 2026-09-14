import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { UploadDialog } from "@/components/documents/UploadDialog";

describe("UploadDialog", () => {
  it("refuses to submit without a file", async () => {
    const onSubmit = vi.fn();
    render(<UploadDialog open onOpenChange={() => {}} onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: /déposer/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/fichier/i);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("flags an unsupported file dropped onto the zone (drag & drop bypasses `accept`)", async () => {
    render(<UploadDialog open onOpenChange={() => {}} onSubmit={vi.fn()} />);
    const zone = screen.getByRole("group", { name: "Zone de dépôt" });
    fireEvent.drop(zone, { dataTransfer: { files: [new File(["x"], "photo.png", { type: "image/png" })] } });
    expect(await screen.findByRole("alert")).toHaveTextContent(/non autorisé/i);
  });

  it("pre-fills the name from the file and submits a multipart body", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<UploadDialog open onOpenChange={() => {}} onSubmit={onSubmit} />);
    const file = new File(["%PDF"], "attestation-fiscale.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("Fichier"), file);
    expect(screen.getByLabelText("Nom")).toHaveValue("attestation-fiscale");
    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "attestation");
    await userEvent.type(screen.getByLabelText("Expire le"), "2027-06-30");
    await userEvent.click(screen.getByRole("button", { name: /déposer/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const form = onSubmit.mock.calls[0][0] as FormData;
    expect(form.get("file")).toBe(file);
    expect(form.get("category")).toBe("attestation");
    expect(form.get("name")).toBe("attestation-fiscale");
    expect(form.get("expires_at")).toBe("2027-06-30");
  });
});
