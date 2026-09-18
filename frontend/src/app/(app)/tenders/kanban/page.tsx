"use client";

import { List } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { KanbanBoard } from "@/components/tenders/KanbanBoard";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useChangeStatus, useKanban } from "@/lib/queries/tenders";
import { TENDER_STATUS_LABELS } from "@/lib/tenders";
import type { Tender, TenderStatus } from "@/lib/types";

export default function KanbanPage() {
  const kanban = useKanban();
  const changeStatus = useChangeStatus();
  const total = kanban.data?.columns.reduce((n, c) => n + c.items.length, 0);

  async function onChangeStatus(tender: Tender, status: TenderStatus) {
    try {
      await changeStatus.mutateAsync({ id: tender.id, status });
      toast.success(`« ${tender.title} » → ${TENDER_STATUS_LABELS[status]}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Changement de statut impossible.");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Veille"
        title="Pipeline"
        count={total}
        description="Les opportunités par étape du cycle de vie. Changez le statut depuis le menu de chaque carte."
        actions={
          <Link href="/tenders" className={buttonVariants({ variant: "outline" })}>
            <List />
            Vue liste
          </Link>
        }
      />
      {kanban.isPending ? (
        <div className="flex gap-3" aria-busy="true" aria-label="Chargement">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-72 w-64 shrink-0 rounded-xl" />
          ))}
        </div>
      ) : kanban.isError || !kanban.data ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Impossible de charger le pipeline.
        </p>
      ) : (
        <KanbanBoard columns={kanban.data.columns} onChangeStatus={onChangeStatus} />
      )}
    </div>
  );
}
