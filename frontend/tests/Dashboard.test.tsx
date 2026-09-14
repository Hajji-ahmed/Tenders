import { render, screen } from "@testing-library/react";
import { Briefcase } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { OnboardingCard } from "@/components/dashboard/OnboardingCard";
import { countExpiringSoon } from "@/lib/queries/documents";
import type { CompanyDocument } from "@/lib/types";

vi.mock("next/navigation", () => ({ usePathname: () => "/documents" }));

describe("Breadcrumb", () => {
  it("derives the current section from the route", () => {
    render(<Breadcrumb />);
    expect(screen.getByRole("link", { name: "Accueil" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByText("Appels d'offres")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toHaveAttribute("aria-current", "page");
  });
});

describe("KpiCard", () => {
  it("is a link with an accessible summary", () => {
    render(<KpiCard label="Opportunités actives" value={3} hint="collectées" icon={Briefcase} accent="green" href="/tenders" />);
    const link = screen.getByRole("link", { name: "Opportunités actives : 3. collectées" });
    expect(link).toHaveAttribute("href", "/tenders");
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});

describe("OnboardingCard", () => {
  it("renders the zero-padded step and links to the target page", () => {
    render(<OnboardingCard step={2} title="Documents" text="…" icon={Briefcase} accent="yellow" href="/documents" />);
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Documents/ })).toHaveAttribute("href", "/documents");
    expect(screen.getByText("Accéder")).toBeInTheDocument();
  });
});

describe("countExpiringSoon", () => {
  const doc = (expires_at: string | null, status: CompanyDocument["status"] = "valid") =>
    ({ expires_at, status }) as CompanyDocument;
  it("counts valid documents expiring within 30 days, ignoring archived ones", () => {
    const now = new Date("2026-09-14");
    const docs = [doc("2026-09-20"), doc("2026-12-01"), doc("2026-09-01"), doc(null), doc("2026-09-15", "archived")];
    expect(countExpiringSoon(docs, 30, now)).toBe(2);
  });
});
