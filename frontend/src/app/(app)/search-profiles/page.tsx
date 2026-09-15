"use client";

import { Play, Plus } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EntityDialog, type EntityValues, type FieldSpec } from "@/components/common/EntityDialog";
import { EntityTable } from "@/components/common/EntityTable";
import { JobProgress } from "@/components/jobs/JobProgress";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  searchProfileKeys,
  useCreateSearchProfile,
  useDeleteSearchProfile,
  useLaunchSearch,
  useSearchProfiles,
  useUpdateSearchProfile,
} from "@/lib/queries/searchProfiles";
import { tenderKeys } from "@/lib/queries/tenders";
import type { SearchProfile } from "@/lib/types";

const FIELDS: FieldSpec[] = [
  { name: "name", label: "Nom du profil", type: "text", required: true, placeholder: "Décarbonation Afrique de l'Ouest" },
  { name: "keywords", label: "Mots-clés", type: "tags", help: "Séparés par des virgules — chaque mot-clé génère des requêtes", placeholder: "bilan carbone, efficacité énergétique, plan climat" },
  { name: "sectors", label: "Secteurs", type: "tags", placeholder: "Énergie, Environnement, Eau" },
  { name: "countries", label: "Pays (codes ISO)", type: "tags", help: "MA, SN, CI… (2 lettres)", placeholder: "MA, SN, CI" },
  { name: "regions", label: "Régions / villes", type: "tags" },
  { name: "technologies", label: "Technologies", type: "tags" },
  { name: "certifications", label: "Certifications requises", type: "tags" },
  { name: "budget_min", label: "Budget minimum", type: "number" },
  { name: "budget_max", label: "Budget maximum", type: "number" },
  { name: "currency", label: "Devise", type: "text", placeholder: "MAD" },
  { name: "deadline_min_days", label: "Délai minimum (jours)", type: "number", help: "Ignorer les AO qui expirent avant" },
  { name: "deadline_max_days", label: "Délai maximum (jours)", type: "number" },
  { name: "is_active", label: "Profil actif (utilisable pour lancer une recherche)", type: "checkbox", full: true },
];

const fmtDate = (s: string | null) =>
  s ? new Date(s).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" }) : "Jamais";

export default function SearchProfilesPage() {
  const profiles = useSearchProfiles();
  const create = useCreateSearchProfile();
  const update = useUpdateSearchProfile();
  const remove = useDeleteSearchProfile();
  const launch = useLaunchSearch();
  const qc = useQueryClient();
  // Fin d'une recherche : la date de dernier passage du profil et la liste des opportunités changent.
  const refreshAfterRun = useCallback(() => {
    qc.invalidateQueries({ queryKey: searchProfileKeys.all });
    qc.invalidateQueries({ queryKey: tenderKeys.all });
  }, [qc]);

  const [dialog, setDialog] = useState<{ open: boolean; row: SearchProfile | null }>({ open: false, row: null });
  const [toDelete, setToDelete] = useState<SearchProfile | null>(null);
  // Recherches lancées depuis cette page : profil → job suivi en direct.
  const [runs, setRuns] = useState<Array<{ jobId: string; profile: SearchProfile }>>([]);

  async function submit(values: EntityValues) {
    if (dialog.row) {
      await update.mutateAsync({ id: dialog.row.id, values });
      toast.success("Profil mis à jour");
    } else {
      await create.mutateAsync(values);
      toast.success("Profil créé");
    }
  }

  async function run(profile: SearchProfile) {
    try {
      const job = await launch.mutateAsync(profile.id);
      setRuns((r) => [{ jobId: job.id, profile }, ...r.filter((x) => x.profile.id !== profile.id)]);
      toast.success(`Recherche lancée pour « ${profile.name} »`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Lancement impossible");
    }
  }

  const rows = profiles.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Recherche"
        title="Paramètres de recherche"
        count={profiles.data ? profiles.data.total : undefined}
        description="Chaque profil décrit ce que vous cherchez (mots-clés, secteurs, pays…) ; « Lancer » interroge toutes les sources actives."
        actions={
          <Button variant="accent" onClick={() => setDialog({ open: true, row: null })}>
            <Plus />
            Nouveau profil
          </Button>
        }
      />

      {runs.length > 0 && (
        <section aria-label="Recherches lancées" className="space-y-2">
          {runs.map((r) => (
            <div key={r.jobId} className="space-y-1">
              <p className="text-sm font-medium text-brand-green-dark">{r.profile.name}</p>
              <JobProgress jobId={r.jobId} onSettled={refreshAfterRun} />
            </div>
          ))}
        </section>
      )}

      {profiles.isPending ? (
        <div className="space-y-2" aria-busy="true" aria-label="Chargement">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : profiles.isError ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Impossible de charger les profils.
        </p>
      ) : (
        <EntityTable
          headerVariant="inverse"
          columns={[
            {
              key: "name",
              label: "Profil",
              render: (r) => (
                <span className="flex items-center gap-2">
                  <span className="font-medium text-foreground">{r.name}</span>
                  {!r.is_active && <Badge variant="muted">Inactif</Badge>}
                </span>
              ),
            },
            { key: "keywords", label: "Mots-clés", render: (r) => r.keywords.join(", ") || "—" },
            { key: "sectors", label: "Secteurs", render: (r) => r.sectors.join(", ") || "—" },
            { key: "countries", label: "Pays", render: (r) => r.countries.join(", ") || "—" },
            { key: "last_run_at", label: "Dernière recherche", render: (r) => fmtDate(r.last_run_at) },
          ]}
          rows={rows}
          emptyLabel="Aucun profil de recherche — créez-en un pour commencer la veille."
          extraActions={(r) => (
            <Button
              variant="outline"
              size="sm"
              disabled={!r.is_active || launch.isPending}
              aria-label={`Lancer la recherche ${r.name}`}
              onClick={() => run(r)}
            >
              <Play />
              Lancer
            </Button>
          )}
          onEdit={(row) => setDialog({ open: true, row })}
          onDelete={(row) => setToDelete(row)}
        />
      )}

      <EntityDialog
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        title={dialog.row ? "Modifier le profil" : "Nouveau profil de recherche"}
        fields={FIELDS}
        defaultValues={dialog.row ? (dialog.row as unknown as EntityValues) : { is_active: true }}
        onSubmit={submit}
      />

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        title={`Supprimer le profil « ${toDelete?.name ?? ""} » ?`}
        description="Les opportunités déjà collectées sont conservées."
        onConfirm={async () => {
          if (!toDelete) return;
          await remove.mutateAsync(toDelete.id);
          toast.success("Profil supprimé");
        }}
      />
    </div>
  );
}
