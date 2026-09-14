import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentFilters } from "@/components/documents/DocumentFilters";

describe("DocumentFilters", () => {
  it("emits category, status and usable-only changes and resets the page", async () => {
    const onChange = vi.fn();
    render(<DocumentFilters value={{ page: 3 }} onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "cv");
    expect(onChange).toHaveBeenLastCalledWith({ page: 1, category: "cv" });

    await userEvent.selectOptions(screen.getByLabelText("Statut"), "expired");
    expect(onChange).toHaveBeenLastCalledWith({ page: 1, status: "expired" });

    await userEvent.click(screen.getByLabelText("Utilisables seulement"));
    expect(onChange).toHaveBeenLastCalledWith({ page: 1, usable_only: true });
  });

  it("debounces the search text and drops the key when cleared", async () => {
    const onChange = vi.fn();
    render(<DocumentFilters value={{ q: "rc" }} onChange={onChange} />);
    const input = screen.getByRole("searchbox", { name: "Rechercher" });
    expect(input).toHaveValue("rc");

    await userEvent.clear(input);
    await userEvent.type(input, "fiscale");
    expect(onChange).not.toHaveBeenCalled();
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith({ page: 1, q: "fiscale" }));

    await userEvent.clear(input);
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith({ page: 1 }));
  });
});
