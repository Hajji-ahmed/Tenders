import type { DecisionKind, ScoreKey, TenderStatus } from "@/lib/types";

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
  { value: "-score", label: "Meilleur score" },
  { value: "deadline", label: "Échéance la plus proche" },
  { value: "-deadline", label: "Échéance la plus lointaine" },
  { value: "created", label: "Plus anciennes" },
];

// --- Score ---

/** Libellés des huit critères du moteur de scoring (mêmes clés que l'API). */
export const SCORE_LABELS: Record<ScoreKey, string> = {
  sector: "Secteur",
  technologies: "Technologies",
  skills: "Compétences",
  country: "Pays",
  budget: "Budget",
  experience: "Expérience",
  certifications: "Certifications",
  eligibility: "Éligibilité",
};

export type ScoreLevel = "high" | "medium" | "low";
export type ScoreLevelInfo = { level: ScoreLevel; label: string; variant: "success" | "warning" | "destructive" };

/** Lecture rapide d'un score /100 : ≥ 70 pertinent (vert), 40–69 à étudier (jaune), < 40 peu pertinent. */
export function scoreLevel(total: number): ScoreLevelInfo {
  if (total >= 70) return { level: "high", label: "Pertinent", variant: "success" };
  if (total >= 40) return { level: "medium", label: "À étudier", variant: "warning" };
  return { level: "low", label: "Peu pertinent", variant: "destructive" };
}

// --- Cycle de vie (miroir de services/tender_status.py) ---

export const TRANSITIONS: Record<TenderStatus, TenderStatus[]> = {
  NOUVEAU: ["A_ANALYSER", "NO_GO", "ARCHIVE"],
  A_ANALYSER: ["GO", "NO_GO", "ARCHIVE"],
  GO: ["PREPARATION", "NO_GO"],
  NO_GO: ["A_ANALYSER", "ARCHIVE"],
  PREPARATION: ["VALIDATION", "NO_GO"],
  VALIDATION: ["PRET", "PREPARATION"],
  PRET: ["SOUMIS", "VALIDATION"],
  SOUMIS: ["GAGNE", "PERDU"],
  GAGNE: ["ARCHIVE"],
  PERDU: ["ARCHIVE"],
  ARCHIVE: [],
};

export const TENDER_STATUS_ORDER = Object.keys(TRANSITIONS) as TenderStatus[];

export function nextStatuses(status: TenderStatus): TenderStatus[] {
  return TRANSITIONS[status];
}

/** Une décision est possible si le statut cible est atteignable (directement ou via « À analyser »)
 * et différent du statut courant. */
export function canDecide(status: TenderStatus, decision: DecisionKind): boolean {
  const target: TenderStatus = decision === "go" ? "GO" : "NO_GO";
  if (status === target) return false;
  const next = TRANSITIONS[status];
  return next.includes(target) || (next.includes("A_ANALYSER") && TRANSITIONS.A_ANALYSER.includes(target));
}
