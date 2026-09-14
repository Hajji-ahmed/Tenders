"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EntityDialog, type EntityValues, type FieldSpec } from "@/components/common/EntityDialog";
import { EntityTable, type Column } from "@/components/common/EntityTable";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  type EntityMap,
  type EntityName,
  useCreateEntity,
  useDeleteEntity,
  useEntityList,
  useUpdateEntity,
} from "@/lib/queries/company";

export type ResourceTabConfig<N extends EntityName> = {
  entity: N;
  /** Libellés : singulier (« une compétence »), pluriel pour l'état vide, nom affiché d'une ligne. */
  labels: { singular: string; empty: string; addButton: string; nameOf: (row: EntityMap[N]) => string };
  columns: Column<EntityMap[N]>[];
  fields: FieldSpec[];
  description?: string;
};

/**
 * Onglet générique d'une sous-ressource du profil : liste, ajout, édition, suppression.
 * Toute la logique CRUD des six onglets est ici ; chaque onglet ne fournit que sa configuration.
 */
export function ResourceTab<N extends EntityName>({ entity, labels, columns, fields, description }: ResourceTabConfig<N>) {
  type Row = EntityMap[N];
  const list = useEntityList(entity);
  const create = useCreateEntity(entity);
  const update = useUpdateEntity(entity);
  const remove = useDeleteEntity(entity);

  const [dialog, setDialog] = useState<{ open: boolean; row: Row | null }>({ open: false, row: null });
  const [toDelete, setToDelete] = useState<Row | null>(null);

  async function submit(values: EntityValues) {
    if (dialog.row) {
      await update.mutateAsync({ id: dialog.row.id, values });
      toast.success(`${labels.singular} mise à jour`);
    } else {
      await create.mutateAsync(values);
      toast.success(`${labels.singular} ajoutée`);
    }
  }

  async function confirmDelete() {
    if (!toDelete) return;
    await remove.mutateAsync(toDelete.id);
    toast.success(`${labels.singular} supprimée`);
  }

  const rows = list.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {description}
          {list.data && (
            <span className="ml-1 font-medium text-foreground">
              · {list.data.total} élément{list.data.total > 1 ? "s" : ""}
            </span>
          )}
        </p>
        <Button variant="accent" onClick={() => setDialog({ open: true, row: null })}>
          <Plus />
          {labels.addButton}
        </Button>
      </div>

      {list.isPending ? (
        <div className="space-y-2" aria-busy="true" aria-label="Chargement">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : list.isError ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Impossible de charger la liste.
        </p>
      ) : (
        <EntityTable
          columns={columns}
          rows={rows}
          emptyLabel={labels.empty}
          onEdit={(row) => setDialog({ open: true, row })}
          onDelete={(row) => setToDelete(row)}
        />
      )}

      <EntityDialog
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        title={dialog.row ? `Modifier ${labels.singular.toLowerCase()}` : `Ajouter ${labels.singular.toLowerCase()}`}
        fields={fields}
        defaultValues={dialog.row ? (dialog.row as unknown as EntityValues) : undefined}
        onSubmit={submit}
      />

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        title={`Supprimer ${toDelete ? labels.nameOf(toDelete) : ""} ?`}
        description="Cette action est définitive."
        onConfirm={confirmDelete}
      />
    </div>
  );
}
