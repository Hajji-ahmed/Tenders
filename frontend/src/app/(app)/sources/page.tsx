"use client";

import { FlaskConical, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EntityDialog, type EntityValues, type FieldSpec } from "@/components/common/EntityDialog";
import { EntityTable } from "@/components/common/EntityTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { SourceTestDialog } from "@/components/sources/SourceTestDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateSource, useDeleteSource, useSources, useTestSource, useUpdateSource } from "@/lib/queries/sources";
import { SOURCE_KIND_LABELS, SOURCE_KIND_OPTIONS, toSourceForm, toSourcePayload } from "@/lib/sources";
import type { SourceTestReport, TenderSource } from "@/lib/types";

const FIELDS: FieldSpec[] = [
  { name: "name", label: "Nom", type: "text", required: true, placeholder: "Portail des marchés publics" },
  { name: "kind", label: "Type", type: "select", required: true, options: SOURCE_KIND_OPTIONS.filter((o) => o.value !== "api") },
  { name: "base_url", label: "URL", type: "text", placeholder: "https://…", help: "Flux RSS, page d'accueil du portail ou du site — inutile pour un moteur", full: true },
  { name: "priority", label: "Priorité", type: "number", help: "Plus petit = interrogée en premier (100 par défaut)" },
  { name: "is_enabled", label: "Source active", type: "checkbox" },
  { name: "include_domains", label: "Moteur : domaines autorisés", type: "tags", placeholder: "marchespublics.gov.ma, ao.ma", help: "Vide = tout le web" },
  { name: "max_results", label: "Moteur : résultats par requête", type: "number" },
  { name: "listing_paths", label: "Portail / site : pages de listing", type: "tags", placeholder: "/appels-offres, /consultations" },
  { name: "link_pattern", label: "Portail / site : motif des liens (regex)", type: "text", placeholder: "/ao/\\d+" },
  { name: "max_links", label: "Portail / site : liens max par page", type: "number" },
  { name: "render_js", label: "Page dynamique (rendu JavaScript, plus lent)", type: "checkbox" },
];

const fmtDate = (s: string | null) =>
  s ? new Date(s).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" }) : "Jamais";

export default function SourcesPage() {
  const sources = useSources();
  const create = useCreateSource();
  const update = useUpdateSource();
  const remove = useDeleteSource();
  const testSource = useTestSource();

  const [dialog, setDialog] = useState<{ open: boolean; row: TenderSource | null }>({ open: false, row: null });
  const [toDelete, setToDelete] = useState<TenderSource | null>(null);
  const [test, setTest] = useState<{ source: TenderSource; report: SourceTestReport | null } | null>(null);

  async function submit(values: EntityValues) {
    const payload = toSourcePayload(values);
    if (dialog.row) {
      await update.mutateAsync({ id: dialog.row.id, values: payload });
      toast.success("Source mise à jour");
    } else {
      await create.mutateAsync(payload);
      toast.success("Source ajoutée");
    }
  }

  async function runTest(source: TenderSource) {
    setTest({ source, report: null });
    try {
      const report = await testSource.mutateAsync(source.id);
      setTest({ source, report });
    } catch (e) {
      setTest(null);
      toast.error(e instanceof Error ? e.message : "Test impossible");
    }
  }

  const rows = sources.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Recherche"
        title="Sources"
        count={sources.data ? sources.data.total : undefined}
        description="Où chercher : moteur de recherche (Tavily), flux RSS, portails et sites d'appels d'offres. « Tester » vérifie une configuration sans rien enregistrer."
        actions={
          <Button variant="accent" onClick={() => setDialog({ open: true, row: null })}>
            <Plus />
            Nouvelle source
          </Button>
        }
      />

      {sources.isPending ? (
        <div className="space-y-2" aria-busy="true" aria-label="Chargement">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : sources.isError ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Impossible de charger les sources.
        </p>
      ) : (
        <EntityTable
          headerVariant="inverse"
          columns={[
            {
              key: "name",
              label: "Source",
              render: (r) => (
                <span className="flex items-center gap-2">
                  <span className="font-medium text-foreground">{r.name}</span>
                  {!r.is_enabled && <Badge variant="muted">Inactive</Badge>}
                </span>
              ),
            },
            { key: "kind", label: "Type", render: (r) => <Badge variant="info">{SOURCE_KIND_LABELS[r.kind]}</Badge> },
            {
              key: "base_url",
              label: "URL",
              render: (r) =>
                r.base_url ? (
                  <a href={r.base_url} target="_blank" rel="noreferrer" className="text-brand-blue-dark hover:underline">
                    {r.base_url}
                  </a>
                ) : (
                  <span className="text-muted-foreground">—</span>
                ),
            },
            { key: "priority", label: "Priorité", className: "tabular-nums" },
            {
              key: "last_status",
              label: "Dernier passage",
              render: (r) => (
                <span className="flex items-center gap-2">
                  <span className="text-muted-foreground">{fmtDate(r.last_run_at)}</span>
                  {r.last_status === "ok" && <Badge variant="success">OK</Badge>}
                  {r.last_status === "error" && (
                    <Badge variant="destructive" title={r.last_error ?? undefined}>
                      Erreur
                    </Badge>
                  )}
                  {r.last_status === "skipped" && <Badge variant="muted">Ignorée</Badge>}
                </span>
              ),
            },
          ]}
          rows={rows}
          emptyLabel="Aucune source — ajoutez un flux RSS ou un portail pour commencer."
          extraActions={(r) => (
            <Button variant="outline" size="sm" aria-label={`Tester ${r.name}`} onClick={() => runTest(r)} disabled={testSource.isPending}>
              <FlaskConical />
              Tester
            </Button>
          )}
          onEdit={(row) => setDialog({ open: true, row })}
          onDelete={(row) => setToDelete(row)}
        />
      )}

      <EntityDialog
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        title={dialog.row ? "Modifier la source" : "Nouvelle source"}
        description="Les champs « Moteur » et « Portail / site » ne s'appliquent qu'au type correspondant."
        fields={FIELDS}
        defaultValues={dialog.row ? toSourceForm(dialog.row) : { is_enabled: true, priority: 100 }}
        onSubmit={submit}
      />

      {test && (
        <SourceTestDialog
          open
          onOpenChange={(open) => !open && setTest(null)}
          sourceName={test.source.name}
          report={test.report}
          pending={test.report === null}
        />
      )}

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        title={`Supprimer la source « ${toDelete?.name ?? ""} » ?`}
        description="Les opportunités déjà collectées depuis cette source sont conservées."
        onConfirm={async () => {
          if (!toDelete) return;
          await remove.mutateAsync(toDelete.id);
          toast.success("Source supprimée");
        }}
      />
    </div>
  );
}
