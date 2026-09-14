import { ArrowRight, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { cn } from "cn";

export type KpiAccent = "green" | "yellow" | "blue";

const ACCENT: Record<KpiAccent, { icon: string; bar: string }> = {
  green: { icon: "bg-brand-green-tint text-brand-green", bar: "bg-brand-green" },
  yellow: { icon: "bg-brand-yellow/25 text-brand-yellow-ink", bar: "bg-brand-yellow" },
  blue: { icon: "bg-brand-blue-tint text-brand-blue", bar: "bg-brand-blue" },
};

export type KpiCardProps = {
  label: string;
  value: number | string;
  hint: string;
  icon: LucideIcon;
  accent: KpiAccent;
  href: string;
  loading?: boolean;
};

/** Indicateur clé : icône teintée, libellé, valeur forte, trait d'accent, description. Toute la carte est un lien. */
export function KpiCard({ label, value, hint, icon: Icon, accent, href, loading = false }: KpiCardProps) {
  const colors = ACCENT[accent];
  return (
    <Link
      href={href}
      aria-label={`${label} : ${value}. ${hint}`}
      className="group/kpi flex h-full flex-col rounded-2xl border border-border bg-card p-5 shadow-card outline-none transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-card-hover focus-visible:ring-3 focus-visible:ring-brand-green/40 sm:p-6"
    >
      <div className="flex items-center gap-3">
        <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", colors.icon)}>
          <Icon className="size-5" aria-hidden />
        </span>
        <p className="flex-1 text-xs font-semibold uppercase tracking-[0.1em] text-muted-foreground">{label}</p>
        <ArrowRight
          aria-hidden
          className="size-4 shrink-0 text-muted-foreground/60 transition-transform duration-200 group-hover/kpi:translate-x-0.5 group-hover/kpi:text-brand-green"
        />
      </div>
      <p
        className={cn(
          "mt-5 text-4xl font-bold leading-none tracking-tight tabular-nums text-brand-green-dark",
          loading && "animate-pulse text-muted-foreground/40",
        )}
      >
        {loading ? "…" : value}
      </p>
      <span aria-hidden className={cn("mt-4 h-1 w-10 rounded-full", colors.bar)} />
      <p className="mt-3 text-sm text-muted-foreground">{hint}</p>
    </Link>
  );
}

export function KpiGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 sm:gap-5">{children}</div>;
}
