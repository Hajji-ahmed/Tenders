"use client";

import {
  BarChart3,
  Bell,
  Briefcase,
  Building2,
  FileText,
  History,
  LayoutDashboard,
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
type NavItem = { href: string; label: string; icon: LucideIcon; count?: number };
type NavGroup = { title?: string; items: NavItem[] };

export const NAV: NavGroup[] = [
  {
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

export function Sidebar() {
  const pathname = usePathname();

  return (
    // Pas de border-r : la sidebar et le Header forment un bandeau noir continu (« L »)
    <aside
      data-surface="dark"
      className="flex h-screen w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground"
    >
      {/* Bloc logo : même hauteur (h-16) et même filet vert 2 px que le Header => ligne verte continue */}
      <Link
        href="/dashboard"
        className="flex h-16 items-center gap-3 border-b-2 border-brand-green px-4 outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sidebar-ring"
      >
        <LogoMark size={36} priority />
        <span className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-white">InnoSustain</span>
          <span className="text-[11px] text-sidebar-foreground/70">Appels d&apos;offres</span>
        </span>
      </Link>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {NAV.map((group, i) => (
          <div key={i} className="mb-4">
            {group.title && (
              // Titres de groupe en vert marque : 4,94:1 sur noir (AA). Ne pas réduire l'opacité (/80 = 3,5:1)
              <p className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-brand-green">
                {group.title}
              </p>
            )}
            <ul className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon, count }) => {
                const active = pathname === href || pathname.startsWith(href + "/");
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group/nav relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors outline-none",
                        "focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                        active
                          ? "bg-white/7 font-medium text-white"
                          : "text-sidebar-foreground/75 hover:bg-white/5 hover:text-white",
                      )}
                    >
                      {active && (
                        // Liseré JAUNE = signal « vous êtes ici »
                        <span
                          aria-hidden
                          className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-brand-yellow"
                        />
                      )}
                      <Icon
                        className={cn(
                          "size-4 transition-colors",
                          active
                            ? "text-brand-green"
                            : "text-sidebar-foreground/55 group-hover/nav:text-brand-green",
                        )}
                      />
                      <span className="truncate">{label}</span>
                      {typeof count === "number" && count > 0 && (
                        // Compteur JAUNE + texte noir (12,79:1)
                        <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-yellow px-1.5 text-[10px] font-semibold tabular-nums text-brand-black">
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

      {/* Pied : logo miniature CSS + raison sociale. Opacités ≥ /55 (4,79:1) */}
      <div className="border-t border-sidebar-border px-4 py-3 text-[11px] leading-relaxed">
        <span className="flex items-center gap-2 text-sidebar-foreground/75">
          <span aria-hidden className="brand-dot" />
          Innovative &amp; Sustainable Solutions
        </span>
        <span className="block pl-[18px] text-sidebar-foreground/55">
          Leading territories decarbonisation in Africa
        </span>
      </div>
    </aside>
  );
}
