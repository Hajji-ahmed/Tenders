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

/**
 * Barre latérale : vert très clair (teinte de la marque), logo sur blanc, élément actif en vert encre
 * avec liseré jaune, titres de groupe en bleu lagon. Le filet vert 2 px du bloc logo prolonge celui
 * de l'en-tête.
 */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-brand-green/20 bg-sidebar text-sidebar-foreground">
      <Link
        href="/dashboard"
        className="flex h-16 items-center gap-3 border-b-2 border-brand-green bg-white px-4 outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-green"
      >
        <LogoMark size={36} priority />
        <span className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-brand-green-dark">InnoSustain</span>
          <span className="text-[11px] text-muted-foreground">Appels d&apos;offres</span>
        </span>
      </Link>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV.map((group, i) => (
          <div key={i} className="mb-5">
            {group.title && (
              <p className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-brand-blue-dark">
                {group.title}
              </p>
            )}
            <ul className="space-y-1">
              {group.items.map(({ href, label, icon: Icon, count }) => {
                const active = pathname === href || pathname.startsWith(href + "/");
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group/nav relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors outline-none",
                        "focus-visible:ring-2 focus-visible:ring-brand-green/50",
                        active
                          ? "bg-brand-green-ink font-medium text-white shadow-sm"
                          : "text-brand-green-dark hover:bg-white hover:shadow-sm",
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
                          "size-4 shrink-0 transition-colors",
                          active ? "text-brand-yellow" : "text-brand-green group-hover/nav:text-brand-green-ink",
                        )}
                      />
                      <span className="truncate">{label}</span>
                      {typeof count === "number" && count > 0 && (
                        // Compteur JAUNE + texte brun foncé (10,19:1)
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

      {/* Pied : logo miniature CSS + raison sociale */}
      <div className="border-t border-brand-green/20 bg-white/60 px-4 py-3 text-[11px] leading-relaxed">
        <span className="flex items-center gap-2.5 font-medium text-brand-green-dark">
          <span aria-hidden className="brand-dot" />
          Innovative &amp; Sustainable Solutions
        </span>
        <span className="block pl-[22px] text-muted-foreground">Leading territories decarbonisation in Africa</span>
      </div>
    </aside>
  );
}
