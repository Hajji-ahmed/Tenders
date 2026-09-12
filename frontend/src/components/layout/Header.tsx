"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useLogout, useMe } from "@/lib/queries/auth";

export function Header() {
  const router = useRouter();
  const { data: me } = useMe();
  const logout = useLogout();

  async function handleLogout() {
    await logout.mutateAsync();
    router.replace("/login");
  }

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-6">
      <div />
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{me?.email ?? "…"}</span>
        <Button variant="ghost" size="sm" onClick={handleLogout} disabled={logout.isPending}>
          <LogOut className="size-4" />
          Déconnexion
        </Button>
      </div>
    </header>
  );
}
