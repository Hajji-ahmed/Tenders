import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TemplatePicker, preselectTemplates } from "@/components/applications/TemplatePicker";
import type { RequestedDocumentItem, Template } from "@/lib/types";

function template(over: Partial<Template>): Template {
  return {
    id: over.document_type ?? "t1",
    name: "Modèle",
    document_type: "presentation",
    description: null,
    sections: [],
    language: "fr",
    version: 1,
    is_default: true,
    repeat_for: null,
    section_count: 4,
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:00:00Z",
    ...over,
  };
}

const templates: Template[] = [
  template({ document_type: "presentation", name: "Présentation de l'entreprise" }),
  template({ document_type: "lettre_candidature", name: "Lettre de candidature" }),
  template({ document_type: "offre_technique", name: "Offre technique", section_count: 5 }),
  template({ document_type: "declaration", name: "Déclaration sur l'honneur" }),
  template({ document_type: "cv", name: "CV d'expert", repeat_for: "experts" }),
];

const requested: RequestedDocumentItem[] = [
  { name: "Offre technique détaillée", mandatory: true, source_page: 2 },
  { name: "Déclaration sur l'honneur", mandatory: true, source_page: 2 },
  { name: "Lettres de satisfaction", mandatory: false, source_page: 3 },
];

describe("preselectTemplates", () => {
  it("preselects the templates the tender actually asks for", () => {
    const chosen = preselectTemplates(templates, requested);
    expect(chosen).toContain("offre_technique");
    expect(chosen).toContain("declaration");
    expect(chosen).not.toContain("cv");
  });

  it("always keeps the letter, which every application carries", () => {
    expect(preselectTemplates(templates, [])).toEqual(["lettre_candidature"]);
  });

  it("does not preselect a document already in the file", () => {
    const chosen = preselectTemplates(templates, requested, ["offre_technique"]);
    expect(chosen).not.toContain("offre_technique");
    expect(chosen).toContain("declaration");
  });
});

describe("TemplatePicker", () => {
  it("lists the templates with their section count and marks the repeatable ones", () => {
    render(<TemplatePicker templates={templates} requested={requested} onAdd={vi.fn()} />);
    const offer = screen.getByLabelText(/offre technique/i);
    expect(offer).toBeChecked(); // demandé par le dossier
    expect(screen.getByLabelText(/présentation/i)).not.toBeChecked();
    const cv = screen.getByLabelText(/cv d'expert/i).closest("li") as HTMLElement;
    expect(within(cv).getByText(/un par expert/i)).toBeInTheDocument();
    expect(screen.getByText("5 sections")).toBeInTheDocument();
  });

  it("adds the checked templates", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(<TemplatePicker templates={templates} requested={[]} onAdd={onAdd} />);

    await userEvent.click(screen.getByLabelText(/offre technique/i));
    await userEvent.click(screen.getByRole("button", { name: /ajouter au dossier/i }));

    expect(onAdd).toHaveBeenCalledWith(["lettre_candidature", "offre_technique"]);
  });

  it("cannot add nothing", async () => {
    const onAdd = vi.fn();
    render(<TemplatePicker templates={templates} requested={[]} onAdd={onAdd} />);
    await userEvent.click(screen.getByLabelText(/lettre de candidature/i)); // décoche la présélection
    expect(screen.getByRole("button", { name: /ajouter au dossier/i })).toBeDisabled();
  });

  it("marks a template already in the file and does not offer it again", () => {
    render(
      <TemplatePicker templates={templates} requested={[]} present={["offre_technique"]} onAdd={vi.fn()} />,
    );
    const offer = screen.getByText("Offre technique").closest("li") as HTMLElement;
    expect(within(offer).getByText(/déjà au dossier/i)).toBeInTheDocument();
    expect(within(offer).queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
