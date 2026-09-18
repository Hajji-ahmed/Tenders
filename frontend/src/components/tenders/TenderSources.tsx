"use client";

import { ExternalLink, Layers } from "lucide-react";
import { useState } from "react";
import { cn } from "cn";

import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { useTenderSources } from "@/lib/queries/tenders";
import type { TenderSourceLink } from "@/lib/types";

type Props = { tenderId: string; count: number };

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function collectedOn(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { timeZone: "UTC" });
}

function SourceItem({ link }: { link: TenderSourceLink }) {
  return (
    <li className="space-y-0.5">
      <a
        href={link.url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-start gap-1.5 font-medium text-foreground hover:text-brand-green-dark hover:underline"
      >
        <span className="break-all">{link.title_seen ?? link.url}</span>
        <ExternalLink aria-hidden className="mt-0.5 size-3.5 shrink-0 text-brand-blue" />
      </a>
      <p className="text-xs text-muted-foreground">
        {link.source_name ?? "Source inconnue"} · {hostOf(link.url)} · {collectedOn(link.collected_at)}
      </p>
    </li>
  );
}

/** Colonne « Sources » : nombre d'annonces derrière la fiche (plusieurs = doublons regroupés, RB-001)
 * et, au clic, la liste des annonces avec leur URL, chargée à l'ouverture seulement. */
export function TenderSources({ tenderId, count }: Props) {
  const [open, setOpen] = useState(false);
  const sources = useTenderSources(tenderId, { enabled: open });
  const merged = count > 1;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        title={merged ? `${count} annonces regroupées en une fiche` : undefined}
        className={cn(
          "inline-flex h-7 items-center gap-1.5 rounded-md px-1.5 text-sm whitespace-nowrap transition-colors hover:bg-brand-blue-tint focus-visible:ring-2 focus-visible:ring-brand-green/40 focus-visible:outline-none",
          merged ? "font-medium text-brand-blue" : "text-muted-foreground",
        )}
      >
        {merged && <Layers aria-hidden className="size-3.5" />}
        {count} source{count > 1 ? "s" : ""}
      </PopoverTrigger>
      <PopoverContent aria-label="Provenance" className="space-y-2">
        <PopoverTitle>Provenance</PopoverTitle>
        {merged && <PopoverDescription>Ces {count} annonces décrivent le même appel d&apos;offres et ont été regroupées en une seule fiche.</PopoverDescription>}
        {sources.isPending ? (
          <div className="space-y-2" aria-busy="true" aria-label="Chargement">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-3/4" />
          </div>
        ) : sources.isError ? (
          <p role="alert" className="text-destructive">
            Impossible de charger les annonces.
          </p>
        ) : (
          <ul className="space-y-2">
            {sources.data.map((link) => (
              <SourceItem key={link.id} link={link} />
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
