"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { toast } from "sonner";

import { ProfileForm, type ProfileValues } from "@/components/company/ProfileForm";
import {
  CertificationsTab,
  ExpertsTab,
  ProjectsTab,
  ReferencesTab,
  SkillsTab,
  TechnologiesTab,
} from "@/components/company/tabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCompanyProfile, useUpdateProfile } from "@/lib/queries/company";

const TABS = [
  { value: "info", label: "Informations", countKey: null },
  { value: "skills", label: "Compétences", countKey: "skills" },
  { value: "technologies", label: "Technologies", countKey: "technologies" },
  { value: "certifications", label: "Certifications", countKey: "certifications" },
  { value: "experts", label: "Experts", countKey: "experts" },
  { value: "projects", label: "Projets", countKey: "projects" },
  { value: "references", label: "Références", countKey: "references" },
] as const;

type TabValue = (typeof TABS)[number]["value"];
const isTab = (v: string | null): v is TabValue => TABS.some((t) => t.value === v);

function CompanyPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tab: TabValue = isTab(params.get("tab")) ? (params.get("tab") as TabValue) : "info";

  const profile = useCompanyProfile();
  const updateProfile = useUpdateProfile();

  function setTab(value: string) {
    const next = new URLSearchParams(params.toString());
    if (value === "info") next.delete("tab");
    else next.set("tab", value);
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  async function saveProfile(values: ProfileValues) {
    await updateProfile.mutateAsync(values);
    toast.success("Profil enregistré");
  }

  const counts = profile.data?.counts ?? {};
  const displayName = profile.data?.trade_name || profile.data?.legal_name || "InnoSustain";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Profil entreprise"
        description={`Informations de référence de ${displayName} — utilisées par le matching, l'éligibilité et la génération des documents.`}
      />

      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <div className="overflow-x-auto">
          <TabsList variant="line" className="h-10 w-full justify-start gap-2 sm:w-auto">
            {TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="px-3">
                {t.label}
                {t.countKey && typeof counts[t.countKey] === "number" && (
                  <span className="ml-1.5 rounded-full bg-muted px-1.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
                    {counts[t.countKey]}
                  </span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        <TabsContent value="info" className="pt-4">
          {profile.isPending ? (
            <Skeleton className="h-96 w-full rounded-2xl" />
          ) : profile.isError || !profile.data ? (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              Impossible de charger le profil.
            </p>
          ) : (
            <ProfileForm profile={profile.data} onSubmit={saveProfile} />
          )}
        </TabsContent>
        <TabsContent value="skills" className="pt-4"><SkillsTab /></TabsContent>
        <TabsContent value="technologies" className="pt-4"><TechnologiesTab /></TabsContent>
        <TabsContent value="certifications" className="pt-4"><CertificationsTab /></TabsContent>
        <TabsContent value="experts" className="pt-4"><ExpertsTab /></TabsContent>
        <TabsContent value="projects" className="pt-4"><ProjectsTab /></TabsContent>
        <TabsContent value="references" className="pt-4"><ReferencesTab /></TabsContent>
      </Tabs>
    </div>
  );
}

// useSearchParams exige une frontière Suspense pour le rendu statique.
export default function CompanyPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-2xl" />}>
      <CompanyPageInner />
    </Suspense>
  );
}
