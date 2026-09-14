import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EntityDialog, type FieldSpec } from "@/components/common/EntityDialog";

const fields: FieldSpec[] = [
  { name: "name", label: "Nom", type: "text", required: true },
  { name: "category", label: "Catégorie", type: "select", options: [{ value: "expertise", label: "Expertise" }, { value: "service", label: "Service" }] },
  { name: "years", label: "Années", type: "number" },
  { name: "expires_at", label: "Expire le", type: "date" },
  { name: "tags", label: "Étiquettes", type: "tags" },
  { name: "is_reference", label: "Référence", type: "checkbox" },
];

describe("EntityDialog", () => {
  it("submits typed values (numbers, dates, tags, booleans; empty → null)", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<EntityDialog open onOpenChange={() => {}} title="Ajouter" fields={fields} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Nom"), "Audit énergétique");
    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "service");
    await userEvent.type(screen.getByLabelText("Années"), "12");
    await userEvent.type(screen.getByLabelText("Étiquettes"), " ISO 14001, énergie ,, ISO 14001 ");
    await userEvent.click(screen.getByLabelText("Référence"));
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith({
      name: "Audit énergétique",
      category: "service",
      years: 12,
      expires_at: null,
      tags: ["ISO 14001", "énergie"],
      is_reference: true,
    });
  });

  it("blocks submission when a required field is empty", async () => {
    const onSubmit = vi.fn();
    render(<EntityDialog open onOpenChange={() => {}} title="Ajouter" fields={fields} onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/requis/i);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("defaults a required select to its first option so a fresh form can be submitted", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const required: FieldSpec[] = [
      { name: "name", label: "Nom", type: "text", required: true },
      { name: "category", label: "Catégorie", type: "select", required: true, options: [{ value: "expertise", label: "Expertise" }, { value: "service", label: "Service" }] },
    ];
    render(<EntityDialog open onOpenChange={() => {}} title="Ajouter" fields={required} onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Nom"), "Audit");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ name: "Audit", category: "expertise" }));
  });

  it("pre-fills default values for edition", () => {
    render(
      <EntityDialog
        open
        onOpenChange={() => {}}
        title="Modifier"
        fields={fields}
        defaultValues={{ name: "Bilan carbone", years: 3, tags: ["a", "b"], is_reference: true }}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Nom")).toHaveValue("Bilan carbone");
    expect(screen.getByLabelText("Années")).toHaveValue(3);
    expect(screen.getByLabelText("Étiquettes")).toHaveValue("a, b");
    expect(screen.getByLabelText("Référence")).toBeChecked();
  });
});
