import type { Evidence, Priority, RequirementCategory, RequirementStatus } from "@/lib/types";

/** Statuts d'éligibilité (miroir de `RequirementStatus` côté API) avec leur couleur de badge :
 * conforme vert, à vérifier jaune, non conforme rouge, information manquante gris. */
export const REQUIREMENT_STATUS: Record<
  RequirementStatus,
  { label: string; variant: "success" | "warning-soft" | "destructive" | "muted" }
> = {
  CONFORME: { label: "Conforme", variant: "success" },
  A_VERIFIER: { label: "À vérifier", variant: "warning-soft" },
  NON_CONFORME: { label: "Non conforme", variant: "destructive" },
  INFO_MANQUANTE: { label: "Information manquante", variant: "muted" },
};

export const REQUIREMENT_STATUS_ORDER = Object.keys(REQUIREMENT_STATUS) as RequirementStatus[];

export const REQUIREMENT_STATUS_OPTIONS = REQUIREMENT_STATUS_ORDER.map((value) => ({
  value,
  label: REQUIREMENT_STATUS[value].label,
}));

export const REQUIREMENT_CATEGORY_LABELS: Record<RequirementCategory, string> = {
  administrative: "Administrative",
  technique: "Technique",
  financiere: "Financière",
  juridique: "Juridique",
  experience: "Expérience",
  equipe: "Équipe",
  certification: "Certification",
  methodologie: "Méthodologie",
  autre: "Autre",
};

export const REQUIREMENT_CATEGORY_OPTIONS = (
  Object.keys(REQUIREMENT_CATEGORY_LABELS) as RequirementCategory[]
).map((value) => ({ value, label: REQUIREMENT_CATEGORY_LABELS[value] }));

export const PRIORITY_LABELS: Record<Priority, string> = {
  CRITIQUE: "Critique",
  IMPORTANTE: "Importante",
  FACULTATIVE: "Facultative",
};

/** Ordre d'affichage des questions : critique d'abord (même tri que l'API). */
export const PRIORITY_ORDER: Priority[] = ["CRITIQUE", "IMPORTANTE", "FACULTATIVE"];

/** D'où vient une preuve retenue par le moteur : profil, base documentaire ou réponse de l'utilisateur. */
export const EVIDENCE_LABELS: Record<Evidence["kind"], string> = {
  certification: "Certification",
  technology: "Technologie",
  skill: "Compétence",
  expert: "Expert",
  project: "Projet",
  document: "Document",
  answer: "Votre réponse",
  chunk: "Extrait de document",
};

/** Part d'exigences satisfaites, en pourcentage entier — « conforme » compte 1, « à vérifier » 0,5. */
export function eligibilityPercent(ratio: number): number {
  return Math.round(ratio * 100);
}
