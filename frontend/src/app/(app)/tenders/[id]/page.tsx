"use client";

import { ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { JobProgress } from "@/components/jobs/JobProgress";
import { PageHeader } from "@/components/layout/PageHeader";
import { DecisionButtons } from "@/components/tenders/DecisionButtons";
import { DossierSection } from "@/components/tenders/DossierSection";
import { QuestionsSection } from "@/components/tenders/QuestionsSection";
import { RequirementsSection } from "@/components/tenders/RequirementsSection";
import { ScoreBreakdown } from "@/components/tenders/ScoreBreakdown";
import { ScoreCard } from "@/components/tenders/ScoreCard";
import { StatusTimeline } from "@/components/tenders/StatusTimeline";
import { formatDate } from "@/components/tenders/TendersTable";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDecide, useLaunchScoring, useTender, useTenderHistory, useTenderScore } from "@/lib/queries/tenders";
import { TENDER_STATUS_LABELS, urgencyOf } from "@/lib/tenders";
import type { DecisionKind, Job, TenderDetail } from "@/lib/types";

const TABS = [
  { value: "overview", label: "Aperçu" },
  { value: "analysis", label: "Analyse" },
  { value: "requirements", label: "Exigences" },
  { value: "questions", label: "Questions" },
  { value: "application", label: "Candidature" },
  { value: "history", label: "Historique" },
] as const;
type TabValue = (typeof TABS)[number]["value"];
const isTab = (v: string | null): v is TabValue => TABS.some((t) => t.value === v);

function formatBudget(t: TenderDetail): string {
  if (t.budget_min === null && t.budget_max === null) return "—";
  const fmt = (n: number) => n.toLocaleString("fr-FR");
  const range = t.budget_min !== null && t.budget_max !== null ? `${fmt(t.budget_min)} – ${fmt(t.budget_max)}` : fmt((t.budget_max ?? t.budget_min) as number);
  return `${range} ${t.currency ?? ""}`.trim();
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-2 py-1.5 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-foreground">{children}</dd>
    </div>
  );
}

function Overview({ tender }: { tender: TenderDetail }) {
  const extra = tender.extra as { technologies?: string[]; required_certifications?: string[] };
  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="whitespace-pre-line leading-relaxed">{tender.description || <span className="text-muted-foreground">Aucune description extraite.</span>}</p>
          {(extra.technologies?.length || extra.required_certifications?.length) ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {!!extra.technologies?.length && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Technologies demandées</p>
                  <div className="flex flex-wrap gap-1">{extra.technologies.map((x) => <Badge key={x} variant="info">{x}</Badge>)}</div>
                </div>
              )}
              {!!extra.required_certifications?.length && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Certifications exigées</p>
                  <div className="flex flex-wrap gap-1">{extra.required_certifications.map((x) => <Badge key={x} variant="secondary">{x}</Badge>)}</div>
                </div>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>
      <div className="space-y-4">
        <Card accent="deep">
          <CardHeader>
            <CardTitle>Fiche</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="divide-y divide-border">
              <Row label="Référence">{tender.reference ?? "—"}</Row>
              <Row label="Organisme">{tender.organization ?? "—"}</Row>
              <Row label="Pays / région">{[tender.country, tender.region].filter(Boolean).join(" · ") || "—"}</Row>
              <Row label="Secteur">{tender.sector ?? "—"}</Row>
              <Row label="Type de marché">{tender.market_type ?? "—"}</Row>
              <Row label="Budget">{formatBudget(tender)}</Row>
              <Row label="Publié le">{tender.published_at ? formatDate(tender.published_at) : "—"}</Row>
              <Row label="Questions avant">{tender.questions_deadline_at ? formatDate(tender.questions_deadline_at) : "—"}</Row>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Sources et pièces</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <ul className="space-y-1.5">
              {tender.source_links.map((l) => (
                <li key={l.id}>
                  <a href={l.url} target="_blank" rel="noreferrer" className="inline-flex items-start gap-1.5 hover:text-brand-green-dark hover:underline">
                    <span className="break-all">{l.title_seen ?? l.url}</span>
                    <ExternalLink aria-hidden className="mt-0.5 size-3.5 shrink-0 text-brand-blue" />
                  </a>
                  <p className="text-xs text-muted-foreground">{l.source_name ?? "Source inconnue"} · {formatDate(l.collected_at)}</p>
                </li>
              ))}
            </ul>
            {tender.documents.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pièces ({tender.documents.length})</p>
                <ul className="space-y-1">
                  {tender.documents.map((d) => (
                    <li key={d.id} className="flex items-center justify-between gap-2">
                      {d.source_url ? (
                        <a href={d.source_url} target="_blank" rel="noreferrer" className="truncate hover:text-brand-green-dark hover:underline">{d.name}</a>
                      ) : (
                        <span className="truncate">{d.name}</span>
                      )}
                      <Badge variant="muted">{d.download_status}</Badge>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Placeholder({ label }: { label: string }) {
  return (
    <p className="rounded-xl border border-dashed border-brand-green/30 bg-card px-6 py-10 text-center text-sm text-muted-foreground">
      {label} — disponible à une prochaine étape.
    </p>
  );
}

function TenderPageInner() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tab: TabValue = isTab(params.get("tab")) ? (params.get("tab") as TabValue) : "overview";

  const tender = useTender(id);
  const score = useTenderScore(id);
  const history = useTenderHistory(id, { enabled: tab === "history" });
  const launch = useLaunchScoring();
  const decide = useDecide();
  const [scoringJob, setScoringJob] = useState<Job | null>(null);

  function setTab(value: string) {
    const next = new URLSearchParams(params.toString());
    if (value === "overview") next.delete("tab");
    else next.set("tab", value);
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  async function computeScore() {
    try {
      const job = await launch.mutateAsync(id);
      setScoringJob(job);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible de lancer le calcul.");
    }
  }

  async function onDecide(decision: DecisionKind, reason: string | null) {
    await decide.mutateAsync({ id, decision, reason });
    toast.success(decision === "go" ? "Décision GO enregistrée" : "Décision NO-GO enregistrée");
  }

  if (tender.isPending) {
    return <Skeleton className="h-96 w-full rounded-2xl" />;
  }
  if (tender.isError || !tender.data) {
    return (
      <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        Opportunité introuvable.
      </p>
    );
  }
  const t = tender.data;
  const urgency = urgencyOf(t.days_left);

  return (
    <div className="space-y-6">
      <Link href="/tenders" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-green-dark">
        <ArrowLeft className="size-4" />
        Toutes les opportunités
      </Link>
      <PageHeader
        eyebrow={t.organization ?? "Opportunité"}
        title={t.title}
        description={[t.reference && `Réf. ${t.reference}`, t.deadline_at && `Échéance ${formatDate(t.deadline_at)} (${urgency.label})`].filter(Boolean).join(" · ") || undefined}
        actions={
          <>
            <Badge variant={t.status === "GO" || t.status === "GAGNE" ? "success" : t.status === "NO_GO" || t.status === "PERDU" ? "destructive" : "secondary"} className="h-6 px-2.5 text-xs">
              {TENDER_STATUS_LABELS[t.status]}
            </Badge>
            {t.source_url && (
              <a href={t.source_url} target="_blank" rel="noreferrer" className={buttonVariants({ variant: "outline" })}>
                <ExternalLink />
                Voir l&apos;annonce
              </a>
            )}
          </>
        }
      />

      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <div className="overflow-x-auto">
          <TabsList variant="line" className="h-10 w-full justify-start gap-2 sm:w-auto">
            {TABS.map((item) => (
              <TabsTrigger key={item.value} value={item.value} className="px-3">
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        <TabsContent value="overview" className="pt-4">
          <Overview tender={t} />
        </TabsContent>
        <TabsContent value="analysis" className="space-y-4 pt-4">
          {scoringJob && (
            <JobProgress
              jobId={scoringJob.id}
              onSettled={(job) => {
                // Le job terminé : le score et la fiche (statut A_ANALYSER possible) repartent du serveur.
                setScoringJob(null);
                if (job.status === "failed") toast.error("Le calcul du score a échoué.");
                void score.refetch();
                void tender.refetch();
              }}
            />
          )}
          <ScoreCard score={score.isPending ? undefined : (score.data ?? null)} onCompute={computeScore} computing={launch.isPending || scoringJob !== null} />
          {score.data && (
            <Card>
              <CardHeader>
                <CardTitle>Détail des critères</CardTitle>
              </CardHeader>
              <CardContent className="px-0">
                <ScoreBreakdown breakdown={score.data.breakdown} />
              </CardContent>
            </Card>
          )}
          <Card accent="yellow">
            <CardHeader>
              <CardTitle>Décision</CardTitle>
            </CardHeader>
            <CardContent>
              <DecisionButtons status={t.status} onDecide={onDecide} />
            </CardContent>
          </Card>
          <DossierSection tenderId={id} onTenderChanged={() => void tender.refetch()} />
        </TabsContent>
        <TabsContent value="requirements" className="pt-4">
          <RequirementsSection
            tenderId={id}
            onEvaluated={() => {
              void score.refetch();
              void tender.refetch();
            }}
          />
        </TabsContent>
        <TabsContent value="questions" className="pt-4">
          <QuestionsSection tenderId={id} onAnswered={() => void score.refetch()} />
        </TabsContent>
        <TabsContent value="application" className="pt-4"><Placeholder label="Dossier de candidature" /></TabsContent>
        <TabsContent value="history" className="pt-4">
          {history.isPending ? <Skeleton className="h-32 w-full" /> : <StatusTimeline entries={history.data ?? []} />}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// useSearchParams exige une frontière Suspense pour le rendu statique.
export default function TenderPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-2xl" />}>
      <TenderPageInner />
    </Suspense>
  );
}
