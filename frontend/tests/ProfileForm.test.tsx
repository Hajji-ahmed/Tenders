import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProfileForm } from "@/components/company/ProfileForm";
import type { CompanyProfile } from "@/lib/types";

const profile: CompanyProfile = {
  id: "c1",
  legal_name: "Innovative & Sustainable Solutions",
  trade_name: "InnoSustain",
  description: null,
  country: "MA",
  city: "Rabat",
  address: null,
  website: null,
  email: null,
  phone: null,
  sectors: ["Environnement", "Énergie"],
  positioning: null,
  ai_summary: null,
  ai_summary_updated_at: null,
  counts: {},
  updated_at: "2026-09-14T00:00:00Z",
};

describe("ProfileForm", () => {
  it("pre-fills the profile and submits cleaned values", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProfileForm profile={profile} onSubmit={onSubmit} />);

    expect(screen.getByLabelText("Raison sociale")).toHaveValue("Innovative & Sustainable Solutions");
    expect(screen.getByLabelText("Secteurs d'activité")).toHaveValue("Environnement, Énergie");

    await userEvent.clear(screen.getByLabelText("Ville"));
    await userEvent.type(screen.getByLabelText("Ville"), "Casablanca");
    await userEvent.type(screen.getByLabelText("Secteurs d'activité"), ", Conseil");
    await userEvent.type(screen.getByLabelText("Pays (code ISO)"), "{selectall}ma");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        legal_name: "Innovative & Sustainable Solutions",
        city: "Casablanca",
        country: "MA",
        sectors: ["Environnement", "Énergie", "Conseil"],
        description: null,
      }),
    );
  });

  it("requires the legal name", async () => {
    const onSubmit = vi.fn();
    render(<ProfileForm profile={{ ...profile, legal_name: "" }} onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/raison sociale/i);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
