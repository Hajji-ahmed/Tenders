"use client";

import { Bell, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "cn";

import { NAV } from "@/components/layout/Sidebar";
import { Button, buttonVariants } from "@/components/ui/button";
import { useLogout, useMe } from "@/lib/queries/auth";

export function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const { data: me } = useMe();
  const logout = useLogout();

  // Fil d'Ariane léger : groupe · section courante (dérivé de la navigation)
  const current = NAV.flatMap((g) => g.items.map((item) => ({ ...item, group: g.title }))).find(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
  );
  const initial = (me?.email?.[0] ?? "·").toUpperCase();

  async function handleLogout() {
    await logout.mutateAsync();
    router.replace("/login");
  }

  return (
    // Blanc + filet vert 2 px aligné sur celui du bloc logo de la sidebar
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b-2 border-brand-green bg-white px-6">
      <p className="flex min-w-0 items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        <span className="truncate text-brand-blue-dark">{current?.group ?? "Appels d'offres"}</span>
        <span aria-hidden className="text-brand-yellow">·</span>
        <span className="truncate text-brand-green-dark">{current?.label ?? "InnoSustain"}</span>
      </p>

      <div className="flex items-center gap-2">
        <Link
          href="/notifications"
          aria-label="Notifications"
          className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }), "relative text-brand-green-dark")}
        >
          <Bell />
          {/* Quand la query « non lues » existera :
          <span aria-hidden className="absolute top-1 right-1 size-2 rounded-full bg-brand-yellow ring-2 ring-white" /> */}
        </Link>

        <span aria-hidden className="mx-1 h-5 w-px bg-border" />

        {/* Disque jaune + initiale brun foncé : écho direct du disque du logo (10,19:1) */}
        <span
          aria-hidden
          className="flex size-7 items-center justify-center rounded-full bg-brand-yellow text-xs font-semibold text-brand-yellow-ink"
        >
          {initial}
        </span>
        <span className="hidden text-sm text-muted-foreground md:inline">{me?.email ?? "…"}</span>

        <Button variant="ghost" size="sm" onClick={handleLogout} disabled={logout.isPending}>
          <LogOut className="size-4" />
          Déconnexion
        </Button>
      </div>
    </header>
  );
}
