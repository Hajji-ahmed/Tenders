"use client";

import { ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { EVIDENCE_LABELS } from "@/lib/requirements";
import type { Evidence } from "@/lib/types";

type Props = { code: string; evidence: Evidence[] };

/** Ce qui est affiché : un extrait cite son fichier et sa page (« Kbis.pdf — p. 2 »). */
export function evidenceLabel(item: Evidence): string {
  if (item.kind !== "chunk") return item.label;
  if (item.page && !item.label.includes(`p. ${item.page}`)) return `${item.label} — p. ${item.page}`;
  return item.label.replace(/\s+p\.\s*(\d+)$/, " — p. $1");
}

/** Où mène une preuve : la pièce d'où vient l'extrait, le document, ou l'entité du profil.
 * Une réponse de l'utilisateur n'a pas de page à ouvrir : elle est déjà sous ses yeux. */
export function evidenceHref(item: Evidence): string | null {
  switch (item.kind) {
    case "chunk":
      return item.document_id ? `/documents?open=${item.document_id}` : null;
    case "document":
      return `/documents?open=${item.id}`;
    case "certification":
      return `/company?tab=certifications&id=${item.id}`;
    case "expert":
      return `/company?tab=experts&id=${item.id}`;
    case "project":
      return `/company?tab=projects&id=${item.id}`;
    case "skill":
      return `/company?tab=skills&id=${item.id}`;
    case "technology":
      return `/company?tab=technologies&id=${item.id}`;
    default:
      return null;
  }
}

/** Sur quoi le moteur s'est appuyé pour juger une exigence : certifications, experts, projets,
 * documents ou extraits cités — chacun ouvrant la page qui le porte (RB-005 : tout est vérifiable). */
export function EvidencePopover({ code, evidence }: Props) {
  if (evidence.length === 0) return null;

  return (
    <Popover>
      <PopoverTrigger
        className="inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-xs font-medium text-brand-green-dark transition-colors hover:bg-brand-green-tint focus-visible:ring-2 focus-visible:ring-brand-green/40 focus-visible:outline-none"
        title={`Preuves retenues pour ${code}`}
      >
        <ShieldCheck aria-hidden className="size-3.5" />
        {evidence.length} preuve{evidence.length > 1 ? "s" : ""}
      </PopoverTrigger>
      <PopoverContent aria-label={`Preuves de ${code}`} className="space-y-2">
        <PopoverTitle>Preuves retenues</PopoverTitle>
        <PopoverDescription className="text-xs text-muted-foreground">
          Ce sur quoi le statut de {code} s&apos;appuie. Ouvrez une preuve pour la vérifier.
        </PopoverDescription>
        <ul className="space-y-1.5">
          {evidence.map((item) => {
            const href = evidenceHref(item);
            const label = evidenceLabel(item);
            return (
              <li key={`${item.kind}-${item.id}`} className="text-sm">
                {href ? (
                  <Link
                    href={href}
                    prefetch={false}
                    className="font-medium text-foreground hover:text-brand-green-dark hover:underline"
                  >
                    {label}
                  </Link>
                ) : (
                  <span className="font-medium text-foreground">{label}</span>
                )}
                <p className="text-xs text-muted-foreground">{EVIDENCE_LABELS[item.kind] ?? item.kind}</p>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
