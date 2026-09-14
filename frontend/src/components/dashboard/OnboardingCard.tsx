import { ArrowRight, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { cn } from "cn";

export type OnboardingAccent = "green" | "yellow" | "blue";

const ACCENT: Record<
  OnboardingAccent,
  { badge: string; icon: string; cta: string; blob: string; ring: string }
> = {
  green: {
    badge: "bg-brand-green-tint text-brand-green-dark",
    icon: "bg-brand-green-tint text-brand-green",
    cta: "text-brand-green-dark",
    blob: "[--blob-color:var(--brand-green)]",
    ring: "hover:border-brand-green/40",
  },
  yellow: {
    badge: "bg-brand-yellow/25 text-brand-yellow-ink",
    icon: "bg-brand-yellow/25 text-brand-yellow-ink",
    cta: "text-brand-yellow-ink",
    blob: "[--blob-color:var(--brand-yellow)]",
    ring: "hover:border-brand-yellow/60",
  },
  blue: {
    badge: "bg-brand-blue-tint text-brand-blue-dark",
    icon: "bg-brand-blue-tint text-brand-blue",
    cta: "text-brand-blue-dark",
    blob: "[--blob-color:var(--brand-blue)]",
    ring: "hover:border-brand-blue/40",
  },
};

export type OnboardingCardProps = {
  step: number;
  title: string;
  text: string;
  icon: LucideIcon;
  accent: OnboardingAccent;
  href: string;
  cta?: string;
};

/** Étape de mise en route : badge numéroté, icône, titre, description, CTA « Accéder → », forme organique légère. */
export function OnboardingCard({ step, title, text, icon: Icon, accent, href, cta = "Accéder" }: OnboardingCardProps) {
  const colors = ACCENT[accent];
  return (
    <Link
      href={href}
      className={cn(
        "brand-blob group/step flex h-full flex-col rounded-2xl border border-border bg-card p-6 shadow-card outline-none transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:shadow-card-hover focus-visible:ring-3 focus-visible:ring-brand-green/40",
        colors.blob,
        colors.ring,
      )}
    >
      <div className="flex items-start justify-between">
        <span className={cn("inline-flex h-7 items-center rounded-full px-2.5 text-xs font-semibold tabular-nums", colors.badge)}>
          {String(step).padStart(2, "0")}
        </span>
        <span className={cn("flex size-11 items-center justify-center rounded-xl", colors.icon)}>
          <Icon className="size-5" aria-hidden />
        </span>
      </div>
      <h3 className="mt-6 text-lg font-semibold text-brand-green-dark">{title}</h3>
      <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{text}</p>
      <span className={cn("mt-6 inline-flex items-center gap-1.5 text-sm font-semibold", colors.cta)}>
        {cta}
        <ArrowRight aria-hidden className="size-4 transition-transform duration-200 group-hover/step:translate-x-0.5" />
      </span>
    </Link>
  );
}

export function OnboardingSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby="onboarding-title" className="space-y-4">
      <div className="flex items-center gap-3">
        <span aria-hidden className="h-5 w-1 rounded-full bg-brand-green" />
        <h2 id="onboarding-title" className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-green-dark">
          {title}
        </h2>
        <span aria-hidden className="h-px flex-1 bg-border" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 sm:gap-5">{children}</div>
    </section>
  );
}
