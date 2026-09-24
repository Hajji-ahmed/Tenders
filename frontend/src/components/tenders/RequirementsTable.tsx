"use client";

import { Asterisk, CircleAlert, Pencil, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { NativeSelect } from "@/components/common/NativeSelect";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  EVIDENCE_LABELS,
  PRIORITY_LABELS,
  REQUIREMENT_CATEGORY_LABELS,
  REQUIREMENT_CATEGORY_OPTIONS,
  REQUIREMENT_STATUS,
  REQUIREMENT_STATUS_OPTIONS,
} from "@/lib/requirements";
import type {
  EligibilitySummary,
  Evidence,
  RequirementCategory,
  RequirementStatus,
  RequirementUpdate,
  TenderRequirement,
} from "@/lib/types";

type Props = {
  requirements: TenderRequirement[];
  /** Synthèse de la dernière évaluation ; `null` si elle n'a pas encore eu lieu. */
  summary: EligibilitySummary | null;
  onUpdate: (requirementId: string, patch: RequirementUpdate) => Promise<void> | void;
  busy?: boolean;
};

/** Page du dossier d'où l'exigence est tirée (CdC §35 : traçabilité). */
function Source({ req }: { req: TenderRequirement }) {
  if (!req.source_document_name) return <span className="text-muted-foreground">—</span>;
  const label = req.source_page ? `${req.source_document_name} — p. ${req.source_page}` : req.source_document_name;
  return (
    <span
      className="rounded bg-brand-blue-tint px-1.5 py-0.5 text-[11px] font-medium text-brand-blue-dark"
      title={req.source_excerpt ?? "Pièce source"}
    >
      {label}
    </span>
  );
}

/** Éléments du profil retenus par le moteur (les liens vers la pièce ou l'entité arrivent en 8.5). */
function EvidenceChips({ evidence }: { evidence: Evidence[] }) {
  if (evidence.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1" aria-label="Preuves retenues">
      {evidence.map((e) => (
        <li
          key={`${e.kind}-${e.id}`}
          className="inline-flex items-center gap-1 rounded-md bg-brand-green-tint px-1.5 py-0.5 text-xs text-brand-green-dark"
          title={EVIDENCE_LABELS[e.kind] ?? e.kind}
        >
          {e.label}
        </li>
      ))}
    </ul>
  );
}

/** Exigences du dossier : statut d'éligibilité, source, justification, preuves, édition manuelle,
 * filtres et bandeau RB-003 sur les exigences obligatoires non satisfaites. */
export function RequirementsTable({ requirements, summary, onUpdate, busy = false }: Props) {
  const [status, setStatus] = useState<RequirementStatus | "">("");
  const [category, setCategory] = useState<RequirementCategory | "">("");
  const [mandatoryOnly, setMandatoryOnly] = useState(false);
  const [editing, setEditing] = useState<string | null>(null); // exigence dont le statut est corrigé
  const [saving, setSaving] = useState<string | null>(null);

  const rows = useMemo(
    () =>
      requirements.filter(
        (r) =>
          (status === "" || r.status === status) &&
          (category === "" || r.category === category) &&
          (!mandatoryOnly || r.is_mandatory),
      ),
    [requirements, status, category, mandatoryOnly],
  );
  const unmet = summary?.mandatory_unmet ?? [];

  async function change(req: TenderRequirement, next: RequirementStatus) {
    setSaving(req.id);
    try {
      await onUpdate(req.id, { status: next });
      setEditing(null);
    } finally {
      setSaving(null);
    }
  }

  if (requirements.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-brand-green/30 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
        Aucune exigence extraite. Lancez « Analyser le dossier » dans l&apos;onglet Analyse : chaque obligation du
        règlement est reprise avec son code (<span className="font-medium">ADM-001</span>,{" "}
        <span className="font-medium">TECH-001</span>…), sa source et son statut d&apos;éligibilité.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {unmet.length > 0 && (
        <p
          role="alert"
          className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <CircleAlert aria-hidden className="size-4 shrink-0" />
          <span className="font-semibold">
            {unmet.length} exigence{unmet.length > 1 ? "s" : ""} obligatoire{unmet.length > 1 ? "s" : ""} non
            satisfaite{unmet.length > 1 ? "s" : ""}
          </span>
          <span className="text-destructive/80">{unmet.join(", ")}</span>
        </p>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-52 space-y-2">
          <Label htmlFor="req-status">Statut</Label>
          <NativeSelect
            id="req-status"
            options={REQUIREMENT_STATUS_OPTIONS}
            placeholder="Tous"
            value={status}
            onChange={(e) => setStatus(e.target.value as RequirementStatus | "")}
          />
        </div>
        <div className="w-44 space-y-2">
          <Label htmlFor="req-category">Catégorie</Label>
          <NativeSelect
            id="req-category"
            options={REQUIREMENT_CATEGORY_OPTIONS}
            placeholder="Toutes"
            value={category}
            onChange={(e) => setCategory(e.target.value as RequirementCategory | "")}
          />
        </div>
        <label htmlFor="req-mandatory" className="flex h-8 items-center gap-2 text-sm font-medium">
          <input
            id="req-mandatory"
            type="checkbox"
            className="size-4 rounded border-input accent-brand-green"
            checked={mandatoryOnly}
            onChange={(e) => setMandatoryOnly(e.target.checked)}
          />
          Obligatoires seulement
        </label>
        <p className="ml-auto text-sm text-muted-foreground">
          {rows.length} / {requirements.length} exigence{requirements.length > 1 ? "s" : ""}
        </p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">Code</TableHead>
            <TableHead className="w-32">Catégorie</TableHead>
            <TableHead>Exigence</TableHead>
            <TableHead className="w-44">Statut</TableHead>
            <TableHead>Jugement</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((req) => {
            const state = REQUIREMENT_STATUS[req.status];
            return (
              <TableRow key={req.id} data-status={req.status}>
                <TableCell className="align-top font-medium text-foreground">
                  <span className="flex items-center gap-0.5">
                    {req.code}
                    {req.is_mandatory && (
                      <span title="Exigence obligatoire" aria-label="Exigence obligatoire">
                        <Asterisk aria-hidden className="size-3 text-destructive" />
                      </span>
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground">{PRIORITY_LABELS[req.priority]}</span>
                </TableCell>
                <TableCell className="align-top">
                  <Badge variant="info">{REQUIREMENT_CATEGORY_LABELS[req.category]}</Badge>
                </TableCell>
                <TableCell className="max-w-[24rem] space-y-1 whitespace-normal align-top">
                  <p className="text-foreground">{req.description}</p>
                  <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Source req={req} />
                    {req.evidence_required && <span>Preuve attendue : {req.evidence_required}</span>}
                  </p>
                </TableCell>
                <TableCell className="space-y-1.5 align-top">
                  <div className="flex items-center gap-1.5">
                    <Badge variant={state.variant}>{state.label}</Badge>
                    <button
                      type="button"
                      aria-label={`Modifier le statut de ${req.code}`}
                      title="Corriger le statut à la main"
                      className="text-muted-foreground transition-colors hover:text-brand-green-dark"
                      onClick={() => setEditing(editing === req.id ? null : req.id)}
                    >
                      <Pencil aria-hidden className="size-3.5" />
                    </button>
                  </div>
                  {editing === req.id && (
                    <NativeSelect
                      aria-label={`Statut de ${req.code}`}
                      className="h-7 text-xs"
                      options={REQUIREMENT_STATUS_OPTIONS}
                      value={req.status}
                      disabled={busy || saving === req.id}
                      onChange={(e) => void change(req, e.target.value as RequirementStatus)}
                    />
                  )}
                  {req.manual_status && (
                    <span className="flex items-center gap-1 text-[11px] text-muted-foreground" title="Une ré-extraction ne reviendra pas dessus">
                      <Pencil aria-hidden className="size-3" />
                      Statut saisi à la main
                    </span>
                  )}
                </TableCell>
                <TableCell className="max-w-[22rem] space-y-1.5 whitespace-normal align-top text-muted-foreground">
                  {req.justification ? (
                    <p className="flex items-start gap-1.5">
                      {!req.manual_status && <Sparkles aria-hidden className="mt-0.5 size-3 shrink-0 text-brand-blue" />}
                      {req.justification}
                    </p>
                  ) : (
                    <p>—</p>
                  )}
                  <EvidenceChips evidence={req.evidence} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
