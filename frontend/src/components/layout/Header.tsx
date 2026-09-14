"use client";

import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { MobileSidebar } from "@/components/layout/MobileSidebar";
import { NotificationButton } from "@/components/layout/NotificationButton";
import { UserMenu } from "@/components/layout/UserMenu";

/** En-tête blanc : menu mobile, fil d'Ariane à gauche ; notifications, utilisateur, déconnexion à droite. */
export function Header() {
  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border bg-white/95 px-4 backdrop-blur supports-backdrop-filter:bg-white/80 sm:px-6 lg:px-8">
      <div className="flex min-w-0 items-center gap-2">
        <MobileSidebar />
        <Breadcrumb className="hidden sm:block" />
      </div>
      <div className="flex items-center gap-1 sm:gap-2">
        <NotificationButton />
        <UserMenu />
      </div>
    </header>
  );
}
