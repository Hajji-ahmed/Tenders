"use client";

import { FilePlus2, Repeat } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import type { DocumentTypeKey, RequestedDocumentItem, Template } from "@/lib/types";

type Props = {
  templates: Template[];
  /** Pièces demandées par le règlement (analyse du dossier) : elles guident la présélection. */
  requested: RequestedDocumentItem[];
  /** Types déjà présents au dossier : on ne les propose pas deux fois. */
  present?: DocumentTypeKey[];
  onAdd: (templateIds: string[]) => Promise<void> | void;
  busy?: boolean;
};

/** Toujours de la partie : une candidature sans lettre n'existe pas. */
const ALWAYS: DocumentTypeKey = "lettre_candidature";

/** Mots qui trahissent un type de document dans la liste des pièces demandées par le règlement. */
const KEYWORDS: Record<DocumentTypeKey, string[]> = {
  presentation: ["présentation", "presentation", "plaquette", "capacités", "capacites"],
  lettre_candidature: ["lettre", "candidature"],
  offre_technique: ["offre technique", "mémoire technique", "memoire technique", "proposition technique"],
  methodologie: ["méthodolog", "methodolog", "démarche", "demarche"],
  comprehension_besoin: ["compréhension", "comprehension", "besoin"],
  organisation_planning: ["planning", "organisation", "calendrier", "délai d'exécution"],
  equipe: ["équipe", "equipe", "moyens humains", "effectif"],
  cv: ["cv", "curriculum"],
  references: ["référence", "reference", "satisfaction", "attestation de bonne exécution"],
  declaration: ["déclaration", "declaration", "honneur"],
};

function normalise(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

/** Ce que le dossier réclame explicitement, plus la lettre ; jamais ce qui est déjà là. */
export function preselectTemplates(
  templates: Template[],
  requested: RequestedDocumentItem[],
  present: DocumentTypeKey[] = [],
): DocumentTypeKey[] {
  const asked = requested.map((r) => normalise(r.name));
  const chosen = templates
    .map((t) => t.document_type)
    .filter((type) => !present.includes(type))
    .filter(
      (type) =>
        type === ALWAYS ||
        (KEYWORDS[type] ?? []).some((word) => asked.some((name) => name.includes(normalise(word)))),
    );
  return chosen;
}

/** Choix des documents à préparer : ce que le règlement demande est coché d'avance. */
export function TemplatePicker({ templates, requested, present = [], onAdd, busy = false }: Props) {
  const preselected = useMemo(
    () => preselectTemplates(templates, requested, present),
    [templates, requested, present],
  );
  const [checked, setChecked] = useState<DocumentTypeKey[]>(preselected);
  const [adding, setAdding] = useState(false);

  const byType = new Map(templates.map((t) => [t.document_type, t]));
  const selectedIds = checked.map((type) => byType.get(type)?.id).filter((id): id is string => Boolean(id));

  function toggle(type: DocumentTypeKey) {
    setChecked((current) =>
      current.includes(type) ? current.filter((t) => t !== type) : [...current, type],
    );
  }

  async function add() {
    setAdding(true);
    try {
      await onAdd(selectedIds);
      setChecked([]);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="space-y-3">
      <ul className="divide-y divide-border rounded-xl bg-card ring-1 ring-foreground/10">
        {templates.map((template) => {
          const already = present.includes(template.document_type);
          const id = `template-${template.document_type}`;
          return (
            <li key={template.id} className="flex items-start gap-3 px-3 py-2.5 text-sm">
              {already ? (
                <span aria-hidden className="mt-0.5 size-4 rounded border border-input bg-muted" />
              ) : (
                <input
                  id={id}
                  type="checkbox"
                  className="mt-0.5 size-4 rounded border-input accent-brand-green"
                  checked={checked.includes(template.document_type)}
                  disabled={busy}
                  onChange={() => toggle(template.document_type)}
                />
              )}
              <div className="min-w-0 flex-1">
                {already ? (
                  <p className="font-medium text-muted-foreground">{template.name}</p>
                ) : (
                  <label htmlFor={id} className="font-medium text-foreground">
                    {template.name}
                  </label>
                )}
                <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                  <span>
                    {template.section_count} section{template.section_count > 1 ? "s" : ""}
                  </span>
                  {template.repeat_for && (
                    <span className="inline-flex items-center gap-1 text-brand-blue">
                      <Repeat aria-hidden className="size-3" />
                      un par {template.repeat_for === "experts" ? "expert" : "projet"}
                    </span>
                  )}
                  {already && <span className="text-brand-green-dark">déjà au dossier</span>}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      <Button onClick={() => void add()} disabled={busy || adding || selectedIds.length === 0}>
        <FilePlus2 />
        Ajouter au dossier
        {selectedIds.length > 0 && ` (${selectedIds.length})`}
      </Button>
    </div>
  );
}
