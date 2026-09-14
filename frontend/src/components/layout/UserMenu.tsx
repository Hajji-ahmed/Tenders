"use client";

import { ChevronDown, LogOut, Settings, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout, useMe } from "@/lib/queries/auth";

/** Avatar (disque jaune + initiale), email et menu : profil, paramètres, déconnexion. */
export function UserMenu() {
  const router = useRouter();
  const { data: me } = useMe();
  const logout = useLogout();
  const email = me?.email ?? "…";
  const initial = (me?.email?.[0] ?? "·").toUpperCase();

  async function handleLogout() {
    await logout.mutateAsync();
    router.replace("/login");
  }

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" size="lg" className="h-10 gap-2.5 px-2 text-foreground" aria-label="Menu utilisateur" />
          }
        >
          <span
            aria-hidden
            className="flex size-8 items-center justify-center rounded-full bg-brand-yellow text-sm font-semibold text-brand-yellow-ink"
          >
            {initial}
          </span>
          <span className="hidden max-w-[200px] truncate text-sm text-foreground md:inline">{email}</span>
          <ChevronDown aria-hidden className="size-4 text-muted-foreground" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel className="truncate">{email}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem render={<Link href="/company" />}>
            <UserRound />
            Profil entreprise
          </DropdownMenuItem>
          <DropdownMenuItem render={<Link href="/settings" />}>
            <Settings />
            Paramètres
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onClick={handleLogout} disabled={logout.isPending}>
            <LogOut />
            Déconnexion
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <span aria-hidden className="mx-1 hidden h-6 w-px bg-border sm:block" />

      <Button variant="ghost" size="sm" onClick={handleLogout} disabled={logout.isPending} className="text-muted-foreground">
        <LogOut />
        <span className="hidden sm:inline">Déconnexion</span>
      </Button>
    </div>
  );
}
