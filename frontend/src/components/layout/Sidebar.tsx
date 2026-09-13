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

type NavItem = { href: string; label: string; icon: LucideIcon };
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
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <Link
        href="/dashboard"
        className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
      >
        <LogoMark className="size-9" />
        <span className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-white">InnoSustain</span>
          <span className="text-[11px] text-sidebar-foreground/70">Appels d&apos;offres</span>
        </span>
      </Link>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {NAV.map((group, i) => (
          <div key={i} className="mb-4">
            {group.title && (
              <p className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-sidebar-foreground/50">
                {group.title}
              </p>
            )}
            <ul className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || pathname.startsWith(href + "/");
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors outline-none",
                        "focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                        active
                          ? "bg-sidebar-primary/15 font-medium text-white"
                          : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-white",
                      )}
                    >
                      <Icon className={cn("size-4", active ? "text-brand-green" : "text-sidebar-foreground/60")} />
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border px-4 py-3 text-[11px] text-sidebar-foreground/50">
        Innovative &amp; Sustainable Solutions
      </div>
    </aside>
  );
}
