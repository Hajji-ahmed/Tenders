"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "cn";

import { NAV, isActivePath } from "@/components/layout/Sidebar";

export type Crumb = { label: string; href?: string };

/** Fil d'Ariane dérivé de la navigation : Accueil › Appels d'offres › Section courante. */
export function useBreadcrumb(): Crumb[] {
  const pathname = usePathname();
  const current = NAV.flatMap((g) => g.items).find((item) => isActivePath(pathname, item.href));
  return [
    { label: "Accueil", href: "/dashboard" },
    { label: "Appels d'offres" },
    { label: current?.label ?? "InnoSustain" },
  ];
}

export function Breadcrumb({ items, className }: { items?: Crumb[]; className?: string }) {
  const derived = useBreadcrumb();
  const crumbs = items ?? derived;
  const last = crumbs.length - 1;
  return (
    <nav aria-label="Fil d'Ariane" className={cn("min-w-0", className)}>
      <ol className="flex min-w-0 items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => (
          <li key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <ChevronRight aria-hidden className="size-3.5 shrink-0 text-muted-foreground/60" />}
            {c.href && i !== last ? (
              <Link
                href={c.href}
                className="truncate text-muted-foreground transition-colors hover:text-brand-green-dark"
              >
                {c.label}
              </Link>
            ) : (
              <span
                aria-current={i === last ? "page" : undefined}
                className={cn("truncate", i === last ? "font-semibold text-brand-green-dark" : "text-muted-foreground")}
              >
                {c.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
