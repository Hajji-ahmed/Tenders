import type { TenderStatus } from "@/lib/types";

export const TENDER_STATUS_LABELS: Record<TenderStatus, string> = {
  NOUVEAU: "Nouveau",
  A_ANALYSER: "À analyser",
  GO: "Go",
  NO_GO: "No-go",
  PREPARATION: "Préparation",
  VALIDATION: "Validation",
  PRET: "Prêt",
  SOUMIS: "Soumis",
  GAGNE: "Gagné",
  PERDU: "Perdu",
  ARCHIVE: "Archivé",
};

export const TENDER_STATUS_OPTIONS = (Object.keys(TENDER_STATUS_LABELS) as TenderStatus[]).map((value) => ({
  value,
  label: TENDER_STATUS_LABELS[value],
}));

export type UrgencyLevel = "none" | "expired" | "critical" | "high" | "medium" | "low";

/** Niveau d'urgence affiché depuis `days_left`, mêmes seuils que RB-002 côté API (`compute_urgency`) :
 * ≤ 2 j critique, 3–7 j haute, 8–14 j moyenne, au-delà basse. */
export function urgencyOf(daysLeft: number | null): { level: UrgencyLevel; label: string } {
  if (daysLeft === null) return { level: "none", label: "Sans échéance" };
  if (daysLeft < 0) return { level: "expired", label: "Dépassée" };
  if (daysLeft === 0) return { level: "critical", label: "Aujourd'hui" };
  const label = `${daysLeft} j`;
  if (daysLeft <= 2) return { level: "critical", label };
  if (daysLeft <= 7) return { level: "high", label };
  if (daysLeft <= 14) return { level: "medium", label };
  return { level: "low", label };
}

export const SORT_OPTIONS = [
  { value: "-created", label: "Plus récentes" },
  { value: "deadline", label: "Échéance la plus proche" },
  { value: "-deadline", label: "Échéance la plus lointaine" },
  { value: "created", label: "Plus anciennes" },
];
