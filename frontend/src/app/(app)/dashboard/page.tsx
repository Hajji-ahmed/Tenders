import { ArrowRight, Building2, FileText, Search } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Page provisoire — remplacée par le vrai dashboard (indicateurs, échéances) en Phase 11.
const STEPS = [
  {
    href: "/company",
    icon: Building2,
    title: "Profil entreprise",
    text: "Compétences, technologies, certifications, experts et références : la base du matching.",
  },
  {
    href: "/documents",
    icon: FileText,
    title: "Documents",
    text: "Attestations, CV, présentations… avec dates d'expiration et versions.",
  },
  {
    href: "/search-profiles",
    icon: Search,
    title: "Recherche",
    text: "Critères et sources pour collecter automatiquement les appels d'offres.",
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Vue d'ensemble de l'activité appels d'offres" />

      <Card className="border-l-4 border-l-brand-green">
        <CardHeader>
          <CardTitle>Bienvenue sur l&apos;espace appels d&apos;offres d&apos;InnoSustain</CardTitle>
          <CardDescription>
            Les indicateurs (opportunités, scores, échéances) apparaîtront ici. Commencez par les trois étapes
            ci-dessous.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {STEPS.map(({ href, icon: Icon, title, text }, i) => (
          <Link key={href} href={href} className="group outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-xl">
            <Card className="h-full transition-colors group-hover:border-brand-green/40">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-secondary text-brand-green">
                    <Icon className="size-4" />
                  </span>
                  <span className="text-xs font-medium text-muted-foreground">Étape {i + 1}</span>
                </div>
                <CardTitle className="pt-2 text-base">{title}</CardTitle>
              </CardHeader>
              <CardContent className="flex items-end justify-between gap-3 text-sm text-muted-foreground">
                <p>{text}</p>
                <ArrowRight className="size-4 shrink-0 text-brand-green opacity-0 transition-opacity group-hover:opacity-100" />
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
