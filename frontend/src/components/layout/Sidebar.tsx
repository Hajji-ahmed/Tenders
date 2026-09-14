"use client";

import {
  BarChart3,
  Bell,
  Briefcase,
  Building2,
  FileText,
  History,
  LayoutDashboard,
  Leaf,
  Rss,
  Search,
  Settings,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "cn";

import { LogoMark } from "@/components/brand/Logo";

/** `count` : compteur jaune (notifications non lues, échéances) — absent = rien ne s'affiche. */
export type NavItem = { href: string; label: string; icon: LucideIcon; count?: number };
export type NavGroup = { title?: string; items: NavItem[] };

export const NAV: NavGroup[] = [
  {
    title: "Dashboard",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/tenders", label: "Opportunités", icon: Briefcase },
    ],
  },
  {
    title: "Recherche",
    items: [
      { href: "/search-profiles", label: "Paramètres de recherche", icon: SlidersHorizontal },
      { href: "/sources", label: "Sources", icon: Rss },
    ],
  },
  {
    title: "Entreprise",
    items: [
      { href: "/company", label: "Profil entreprise", icon: Building2 },
      { href: "/documents", label: "Documents", icon: FileText },
      { href: "/search", label: "Recherche interne", icon: Search },
    ],
  },
  {
    title: "Pilotage",
    items: [
      { href: "/notifications", label: "Notifications", icon: Bell },
      { href: "/history", label: "Historique", icon: History },
      { href: "/stats", label: "Statistiques", icon: BarChart3 },
      { href: "/settings", label: "Paramètres", icon: Settings },
    ],
  },
];

export const SIDEBAR_WIDTH = "w-[272px]";

export function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

/** Bloc logo + nom (haut de la barre latérale et du menu mobile). */
export function SidebarBrand() {
  return (
    <Link
      href="/dashboard"
      className="flex items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
    >
      <span className="flex size-10 items-center justify-center rounded-xl bg-white shadow-sm">
        <LogoMark size={28} priority />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-[15px] font-semibold text-white">InnoSustain</span>
        <span className="text-xs text-sidebar-foreground/70">Appels d&apos;offres</span>
      </span>
    </Link>
  );
}

/** Liste de navigation (groupes + éléments), partagée par la barre latérale et le menu mobile. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Navigation principale" className="space-y-6">
      {NAV.map((group) => (
        <div key={group.title}>
          {group.title && (
            <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-sidebar-foreground/55">
              {group.title}
            </p>
          )}
          <ul className="space-y-1">
            {group.items.map(({ href, label, icon: Icon, count }) => {
              const active = isActivePath(pathname, href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group/nav relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm outline-none transition-colors duration-200",
                      "focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                      active
                        ? "bg-sidebar-primary font-semibold text-white"
                        : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-white",
                    )}
                  >
                    {active && (
                      // Indicateur latéral : jaune du logo
                      <span aria-hidden className="absolute inset-y-2 left-0 w-1 rounded-r-full bg-brand-yellow" />
                    )}
                    <Icon
                      className={cn(
                        "size-[18px] shrink-0 transition-colors",
                        active ? "text-white" : "text-sidebar-foreground/65 group-hover/nav:text-white",
                      )}
                    />
                    <span className="truncate">{label}</span>
                    {typeof count === "number" && count > 0 && (
                      <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-yellow px-1.5 text-[10px] font-semibold tabular-nums text-brand-yellow-ink">
                        {count > 99 ? "99+" : count}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** Carte de marque discrète en bas de la barre latérale. */
export function SidebarBrandCard() {
  return (
    <div className="rounded-xl border border-sidebar-border bg-white/6 p-3.5">
      <div className="flex items-start gap-2.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-yellow/15 text-brand-yellow">
          <Leaf className="size-4" aria-hidden />
        </span>
        <div className="min-w-0 text-[11px] leading-relaxed">
          <p className="font-semibold text-white">Innovative &amp; Sustainable Solutions</p>
          <p className="text-sidebar-foreground/65">Leading territories decarbonisation in Africa</p>
        </div>
      </div>
    </div>
  );
}

/** Barre latérale fixe (desktop) : vert foncé, logo, navigation, carte de marque. */
export function Sidebar() {
  return (
    <aside
      className={cn(
        SIDEBAR_WIDTH,
        "hidden h-screen shrink-0 flex-col bg-sidebar text-sidebar-foreground lg:flex",
        "sticky top-0",
      )}
    >
      <div className="px-5 pt-6 pb-4">
        <SidebarBrand />
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <SidebarNav />
      </div>
      <div className="px-3 pb-4 pt-2">
        <SidebarBrandCard />
      </div>
    </aside>
  );
}
