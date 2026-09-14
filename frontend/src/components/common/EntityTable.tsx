"use client";

import { Pencil, Trash2 } from "lucide-react";
import { cn } from "cn";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export type Column<T> = {
  key: string;
  label: string;
  /** Rendu personnalisé ; par défaut la valeur `row[key]` (ou « — » si vide). */
  render?: (row: T) => React.ReactNode;
  className?: string;
};

type Props<T extends { id: string }> = {
  columns: Column<T>[];
  rows: T[];
  onEdit?: (row: T) => void;
  onDelete?: (row: T) => void;
  emptyLabel?: string;
  /** En-tête de la table principale de la page en vert encre (`inverse`) — une seule par page. */
  headerVariant?: "default" | "inverse";
};

function defaultCell<T>(row: T, key: string): React.ReactNode {
  const value = (row as Record<string, unknown>)[key];
  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">—</span>;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "Oui" : "Non";
  return String(value);
}

/** Tableau générique des sous-ressources (compétences, technologies…) avec actions Modifier / Supprimer. */
export function EntityTable<T extends { id: string }>({
  columns,
  rows,
  onEdit,
  onDelete,
  emptyLabel = "Aucun élément",
  headerVariant = "default",
}: Props<T>) {
  const hasActions = Boolean(onEdit || onDelete);

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-brand-green/30 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
        {emptyLabel}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader variant={headerVariant}>
        <TableRow>
          {columns.map((c) => (
            <TableHead key={c.key} className={c.className}>
              {c.label}
            </TableHead>
          ))}
          {hasActions && (
            <TableHead className="w-24 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            {columns.map((c) => (
              <TableCell key={c.key} className={cn("max-w-[28rem] truncate", c.className)}>
                {c.render ? c.render(row) : defaultCell(row, c.key)}
              </TableCell>
            ))}
            {hasActions && (
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  {onEdit && (
                    <Button variant="ghost" size="icon-sm" aria-label="Modifier" onClick={() => onEdit(row)}>
                      <Pencil />
                    </Button>
                  )}
                  {onDelete && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Supprimer"
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => onDelete(row)}
                    >
                      <Trash2 />
                    </Button>
                  )}
                </div>
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
