import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DecisionButtons } from "@/components/tenders/DecisionButtons";

describe("DecisionButtons", () => {
  it("asks for a reason then calls onDecide with the decision", async () => {
    const onDecide = vi.fn().mockResolvedValue(undefined);
    render(<DecisionButtons status="A_ANALYSER" onDecide={onDecide} />);

    await userEvent.click(screen.getByRole("button", { name: "GO" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/Confirmer le GO/);
    await userEvent.type(screen.getByLabelText(/motif/i), "Bon fit sectoriel");
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    expect(onDecide).toHaveBeenCalledWith("go", "Bon fit sectoriel");
  });

  it("lets NO-GO go through without a reason and reports a failure in the dialog", async () => {
    const onDecide = vi.fn().mockRejectedValue(new Error("Passage SOUMIS → NO_GO impossible"));
    render(<DecisionButtons status="GO" onDecide={onDecide} />);

    await userEvent.click(screen.getByRole("button", { name: "NO-GO" }));
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    expect(onDecide).toHaveBeenCalledWith("no_go", null);
    expect(await screen.findByRole("alert")).toHaveTextContent("Passage SOUMIS → NO_GO impossible");
  });

  it("only offers the decisions the workflow allows", () => {
    const { unmount } = render(<DecisionButtons status="GO" onDecide={vi.fn()} />);
    expect(screen.getByRole("button", { name: "GO" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "NO-GO" })).toBeEnabled();
    unmount();

    render(<DecisionButtons status="SOUMIS" onDecide={vi.fn()} />);
    expect(screen.getByRole("button", { name: "GO" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "NO-GO" })).toBeDisabled();
    expect(screen.getByText(/dossier déjà engagé/i)).toBeInTheDocument();
  });
});
