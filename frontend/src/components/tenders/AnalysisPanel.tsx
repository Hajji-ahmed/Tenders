"use client";

import { CalendarDays, ClipboardList, FileCheck2, ListChecks, Scale, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { TenderAnalysis } from "@/lib/types";

type Props = { analysis: TenderAnalysis };

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { timeZone: "UTC" });
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });
}

/** Renvoi vers la page du dossier d'où l'information vient (CdC §35 : éléments extraits avec sources). */
function Page({ n }: { n: number | null }) {
  if (n === null) return null;
  return (
    <span className="rounded bg-brand-blue-tint px-1.5 py-0.5 text-[11px] font-medium text-brand-blue-dark" title="Page source dans le dossier">
      p. {n}
    </span>
  );
}

function Section({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-green-dark/80">
        <Icon aria-hidden className="size-3.5" />
        {title}
      </h3>
      {children}
    </section>
  );
}

function Empty() {
  return <p className="text-sm text-muted-foreground">Non trouvé dans les pièces.</p>;
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2 py-1.5 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-foreground">{value ?? <span className="text-muted-foreground">—</span>}</dd>
    </div>
  );
}

/** Lecture structurée du dossier par l'IA : faits clés, dates, critères, pièces demandées, éligibilité, résumé. */
export function AnalysisPanel({ analysis }: Props) {
  return (
    <Card accent="blue">
      <CardHeader className="gap-2">
        <CardTitle>Analyse du dossier</CardTitle>
        <p className="flex items-center gap-1.5 rounded-md border border-brand-blue/30 bg-brand-blue-tint/60 px-2.5 py-1.5 text-xs text-brand-blue-dark">
          <Sparkles aria-hidden className="size-3.5" />
          Analyse générée par IA, à vérifier — chaque élément renvoie à la page du dossier d&apos;où il vient.
          <span className="ml-auto text-muted-foreground">
            {formatDateTime(analysis.analyzed_at)}
            {analysis.model && ` · ${analysis.model}`}
          </span>
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-foreground">{analysis.object}</p>
            <p className="rounded-lg bg-muted/50 px-3 py-2 text-sm leading-relaxed text-foreground">{analysis.summary}</p>
          </div>
          <dl className="divide-y divide-border">
            <Fact label="Organisme" value={analysis.organization} />
            <Fact label="Référence" value={analysis.reference} />
            <Fact label="Budget" value={analysis.budget} />
            <Fact label="Durée" value={analysis.duration} />
            <Fact label="Lieu" value={analysis.location} />
          </dl>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Section icon={CalendarDays} title="Dates clés">
            {analysis.key_dates.length === 0 ? (
              <Empty />
            ) : (
              <ul className="space-y-1.5 text-sm">
                {analysis.key_dates.map((d, i) => (
                  <li key={`${d.label}-${i}`} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-foreground">{d.label}</span>
                    <span className="tabular-nums">{d.date ? formatDate(d.date) : <span className="text-muted-foreground">date non précisée</span>}</span>
                    <Page n={d.source_page} />
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section icon={ListChecks} title="Livrables">
            {analysis.deliverables.length === 0 ? (
              <Empty />
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {analysis.deliverables.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <Section icon={Scale} title="Critères d'évaluation">
          {analysis.criteria.length === 0 ? (
            <Empty />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Critère</TableHead>
                  <TableHead className="w-24 text-right">Poids</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="w-16">Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {analysis.criteria.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium text-foreground">{c.name}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.weight === null ? <span className="text-muted-foreground">—</span> : `${c.weight} %`}</TableCell>
                    <TableCell className="max-w-[24rem] whitespace-normal text-muted-foreground">{c.description ?? ""}</TableCell>
                    <TableCell>
                      <Page n={c.source_page} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Section>

        <div className="grid gap-6 lg:grid-cols-2">
          <Section icon={FileCheck2} title="Pièces demandées">
            {analysis.requested_documents.length === 0 ? (
              <Empty />
            ) : (
              <ul className="space-y-1.5 text-sm">
                {analysis.requested_documents.map((d, i) => (
                  <li key={`${d.name}-${i}`} className="flex flex-wrap items-center gap-2">
                    <span>{d.name}</span>
                    <Badge variant={d.mandatory ? "warning-soft" : "muted"}>{d.mandatory ? "Obligatoire" : "Facultatif"}</Badge>
                    <Page n={d.source_page} />
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section icon={ClipboardList} title="Conditions d'éligibilité">
            {analysis.eligibility_conditions.length === 0 ? (
              <Empty />
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {analysis.eligibility_conditions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </CardContent>
    </Card>
  );
}
