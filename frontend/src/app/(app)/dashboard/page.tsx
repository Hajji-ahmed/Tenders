import {
  ArrowRight,
  Briefcase,
  Building2,
  CalendarClock,
  FileClock,
  FileText,
  Search,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { cn } from "cn";

import { PageHeader } from "@/components/layout/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type KpiAccent = "green" | "yellow" | "blue";

// Indicateurs provisoires — branchés sur l'API en Phase 11.
// Liserés : vert (activité), jaune (signal d'échéance), bleu lagon (information) — le trio, une fois par écran.
const KPIS: { label: string; value: string; hint: string; icon: LucideIcon; accent: KpiAccent }[] = [
  { label: "Opportunités actives", value: "—", hint: "collectées, non archivées", icon: Briefcase, accent: "green" },
  { label: "Échéances sous 7 jours", value: "—", hint: "à traiter en priorité", icon: CalendarClock, accent: "yellow" },
  { label: "Documents à renouveler", value: "—", hint: "attestations expirant sous 30 jours", icon: FileClock, accent: "blue" },
];

const KPI_ICON: Record<KpiAccent, string> = {
  green: "bg-brand-green-tint text-brand-green",
  yellow: "bg-brand-yellow text-brand-yellow-ink",
  blue: "bg-brand-blue-tint text-brand-blue",
};

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
      <PageHeader eyebrow="Pilotage" title="Dashboard" description="Vue d'ensemble de l'activité appels d'offres" />

      {/* Bandeau héros : bleu lagon (4e couleur), motif disque/arcs, tiret jaune, CTA jaune — se distingue de la sidebar verte */}
      <section data-surface="inverse" className="brand-hero brand-hero-blue brand-hero-sm rounded-xl px-6 py-6">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-xl space-y-3">
            <div aria-hidden className="h-1 w-10 rounded-full bg-brand-yellow" />
            <h2 className="text-xl font-semibold tracking-tight">
              Bienvenue sur l&apos;espace appels d&apos;offres d&apos;InnoSustain
            </h2>
            <p className="text-sm leading-relaxed text-white/85">
              Les indicateurs (opportunités, scores, échéances) apparaîtront ici. Commencez par les trois étapes
              ci-dessous.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {/* Le seul bouton accent de l'écran */}
            <Link href="/tenders" className={buttonVariants({ variant: "accent" })}>
              Voir les opportunités
              <ArrowRight data-icon="inline-end" />
            </Link>
            <Link href="/search-profiles" className={buttonVariants({ variant: "outline-inverse" })}>
              Configurer la recherche
            </Link>
          </div>
        </div>
      </section>

      {/* Tuiles indicateurs : cartes blanches, liseré vert / jaune / bleu, chiffre vert foncé */}
      <div className="grid gap-4 md:grid-cols-3">
        {KPIS.map(({ label, value, hint, icon: Icon, accent }) => (
          <Card key={label} accent={accent} size="sm">
            <CardContent className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
                <p className="text-3xl font-semibold tracking-tight tabular-nums text-brand-green-dark">{value}</p>
                <p className="text-xs text-muted-foreground">{hint}</p>
              </div>
              <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg", KPI_ICON[accent])}>
                <Icon className="size-4" />
              </span>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Trois étapes : icône verte sur teinte, numéro = pastille jaune / chiffre brun foncé */}
      <section className="space-y-3">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-brand-green-dark">Mise en route</h2>
          <span aria-hidden className="h-px flex-1 bg-border" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {STEPS.map(({ href, icon: Icon, title, text }, i) => (
            <Link
              key={href}
              href={href}
              className="group/step rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-brand-green/40"
            >
              <Card className="h-full transition-shadow group-hover/step:shadow-sm group-hover/step:ring-brand-green/60">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <span className="flex size-9 items-center justify-center rounded-lg bg-brand-green-tint text-brand-green">
                      <Icon className="size-4" />
                    </span>
                    <span className="rounded-md bg-brand-yellow px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-brand-yellow-ink">
                      0{i + 1}
                    </span>
                  </div>
                  <CardTitle className="pt-2">{title}</CardTitle>
                </CardHeader>
                <CardContent className="flex items-end justify-between gap-3 text-sm text-muted-foreground">
                  <p>{text}</p>
                  <ArrowRight className="size-4 shrink-0 text-brand-green opacity-0 transition-opacity group-hover/step:opacity-100" />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
