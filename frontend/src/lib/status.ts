import type { VariantProps } from "class-variance-authority";

import type { badgeVariants } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";

export type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;

export type StatusStyle = { label: string; variant: BadgeVariant };

/** Statut technique des jobs (types.ts) → badge. */
export const JOB_STATUS: Record<JobStatus, StatusStyle> = {
  pending: { label: "En attente", variant: "warning-soft" },
  running: { label: "En cours", variant: "inverse" },
  done: { label: "Terminé", variant: "success" },
  failed: { label: "Échec", variant: "destructive" },
};

/** Statuts d'appel d'offres — à aligner sur l'enum backend en Phase 11. */
export const TENDER_STATUS = {
  nouveau: { label: "Nouveau", variant: "warning" },
  a_qualifier: { label: "À qualifier", variant: "warning-soft" },
  go: { label: "Go", variant: "success" },
  no_go: { label: "No-Go", variant: "muted" },
  en_preparation: { label: "En préparation", variant: "outline" },
  soumis: { label: "Déposé", variant: "inverse" },
  gagne: { label: "Gagné", variant: "default" },
  perdu: { label: "Perdu", variant: "destructive" },
  expire: { label: "Expiré", variant: "muted" },
} as const satisfies Record<string, StatusStyle>;
