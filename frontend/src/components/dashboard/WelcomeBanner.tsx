import { ArrowRight, Target } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

type Props = {
  title: string;
  text: string;
  primary: { label: string; href: string };
  secondary?: { label: string; href: string };
};

/** Carte de bienvenue : fond vert très clair, icône cible, deux actions alignées à droite. */
export function WelcomeBanner({ title, text, primary, secondary }: Props) {
  return (
    <section
      aria-labelledby="welcome-title"
      className="flex flex-col gap-6 rounded-2xl border border-brand-green/15 bg-brand-green-tint/70 p-6 sm:p-8 lg:flex-row lg:items-center lg:justify-between"
    >
      <div className="flex items-start gap-4">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-white text-brand-green shadow-sm ring-1 ring-brand-green/20">
          <Target className="size-6" aria-hidden />
        </span>
        <div className="space-y-1.5">
          <h2 id="welcome-title" className="text-lg font-semibold text-brand-green-dark sm:text-xl">
            {title}
          </h2>
          <p className="max-w-2xl text-sm leading-relaxed text-foreground/75 sm:text-[15px]">{text}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3 lg:shrink-0">
        <Link href={primary.href} className={buttonVariants({ size: "lg" })}>
          {primary.label}
          <ArrowRight data-icon="inline-end" aria-hidden />
        </Link>
        {secondary && (
          <Link href={secondary.href} className={buttonVariants({ variant: "outline", size: "lg" })}>
            {secondary.label}
          </Link>
        )}
      </div>
    </section>
  );
}
