import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EntityTable, type Column } from "@/components/common/EntityTable";

type Row = { id: string; name: string; level: string | null };

const columns: Column<Row>[] = [
  { key: "name", label: "Nom" },
  { key: "level", label: "Niveau", render: (row) => row.level ?? "—" },
];

const rows: Row[] = [
  { id: "1", name: "Audit énergétique", level: "expert" },
  { id: "2", name: "Bilan carbone", level: null },
];

describe("EntityTable", () => {
  it("renders one line per row with rendered cells", () => {
    render(<EntityTable columns={columns} rows={rows} />);
    expect(screen.getAllByRole("row")).toHaveLength(3); // en-tête + 2 lignes
    expect(screen.getByText("Audit énergétique")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("calls onEdit and onDelete with the row", async () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    render(<EntityTable columns={columns} rows={rows} onEdit={onEdit} onDelete={onDelete} />);
    await userEvent.click(screen.getAllByRole("button", { name: /modifier/i })[1]);
    expect(onEdit).toHaveBeenCalledWith(rows[1]);
    await userEvent.click(screen.getAllByRole("button", { name: /supprimer/i })[0]);
    expect(onDelete).toHaveBeenCalledWith(rows[0]);
  });

  it("shows the empty state", () => {
    render(<EntityTable columns={columns} rows={[]} emptyLabel="Aucune compétence" />);
    expect(screen.getByText("Aucune compétence")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /supprimer/i })).not.toBeInTheDocument();
  });
});

describe("EntityTable extra actions", () => {
  it("renders custom per-row actions before edit/delete", async () => {
    const onTest = vi.fn();
    render(
      <EntityTable
        columns={columns}
        rows={rows}
        onEdit={() => {}}
        extraActions={(row) => (
          <button type="button" onClick={() => onTest(row)}>
            Tester {row.name}
          </button>
        )}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Tester Bilan carbone" }));
    expect(onTest).toHaveBeenCalledWith(expect.objectContaining({ id: "2" }));
    expect(screen.getAllByRole("button", { name: "Modifier" })).toHaveLength(2);
  });
});
