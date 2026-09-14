import { Bell } from "lucide-react";
import Link from "next/link";
import { cn } from "cn";

import { buttonVariants } from "@/components/ui/button";

/** Accès aux notifications ; `count` (non lues) affichera une pastille jaune quand l'API existera (Phase 11). */
export function NotificationButton({ count = 0 }: { count?: number }) {
  return (
    <Link
      href="/notifications"
      aria-label={count > 0 ? `Notifications (${count} non lues)` : "Notifications"}
      className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "relative text-muted-foreground")}
    >
      <Bell />
      {count > 0 && (
        <span aria-hidden className="absolute top-1.5 right-1.5 size-2 rounded-full bg-brand-yellow ring-2 ring-white" />
      )}
    </Link>
  );
}
