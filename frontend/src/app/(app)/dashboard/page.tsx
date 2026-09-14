"use client";

import { Briefcase, Building2, CalendarClock, FileClock, FileText, Search } from "lucide-react";

import { KpiCard, KpiGrid } from "@/components/dashboard/KpiCard";
import { OnboardingCard, OnboardingSection } from "@/components/dashboard/OnboardingCard";
import { WelcomeBanner } from "@/components/dashboard/WelcomeBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import { countExpiringSoon, useDocuments } from "@/lib/queries/documents";

const STEPS = [
  {
    href: "/company",
    icon: Building2,
    accent: "green",
    title: "Profil entreprise",
    text: "Compétences, technologies, certifications, experts et références : la base du matching.",
  },
  {
    href: "/documents",
    icon: FileText,
    accent: "yellow",
    title: "Documents",
    text: "Attestations, CV, présentations… avec dates d'expiration et versions.",
  },
  {
    href: "/search-profiles",
    icon: Search,
    accent: "blue",
    title: "Recherche",
    text: "Critères et sources pour collecter automatiquement les appels d'offres.",
  },
] as const;

export default function DashboardPage() {
  // Seul indicateur déjà branché sur l'API (documents) ; opportunités et échéances arrivent avec les Phases 3-5.
  const documents = useDocuments({ size: 100 });
  const expiring = documents.data ? countExpiringSoon(documents.data.items, 30) : 0;

  return (
    <div className="space-y-8">
      <PageHeader eyebrow="Pilotage" title="Dashboard" description="Vue d'ensemble de l'activité appels d'offres" art />

      <WelcomeBanner
        title="Bienvenue sur l'espace appels d'offres d'InnoSustain"
        text="Les indicateurs (opportunités, scores, échéances) apparaîtront ici. Commencez par les trois étapes ci-dessous."
        primary={{ label: "Voir les opportunités", href: "/tenders" }}
        secondary={{ label: "Configurer la recherche", href: "/search-profiles" }}
      />

      <KpiGrid>
        <KpiCard label="Opportunités actives" value={0} hint="collectées, non archivées" icon={Briefcase} accent="green" href="/tenders" />
        <KpiCard label="Échéances sous 7 jours" value={0} hint="à traiter en priorité" icon={CalendarClock} accent="yellow" href="/tenders" />
        <KpiCard
          label="Documents à renouveler"
          value={expiring}
          hint="attestations expirant sous 30 jours"
          icon={FileClock}
          accent="blue"
          href="/documents"
          loading={documents.isPending}
        />
      </KpiGrid>

      <OnboardingSection title="Mise en route">
        {STEPS.map((s, i) => (
          <OnboardingCard key={s.href} step={i + 1} {...s} />
        ))}
      </OnboardingSection>
    </div>
  );
}
