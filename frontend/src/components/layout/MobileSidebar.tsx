"use client";

import { Menu } from "lucide-react";
import { useState } from "react";

import { SidebarBrand, SidebarBrandCard, SidebarNav } from "@/components/layout/Sidebar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

/** Menu mobile (< lg) : la même navigation que la barre latérale, dans un panneau latéral. */
export function MobileSidebar() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button variant="ghost" size="icon" aria-label="Ouvrir le menu" className="lg:hidden" />}>
        <Menu />
      </SheetTrigger>
      <SheetContent side="left" className="w-[272px] gap-0 bg-sidebar p-0 text-sidebar-foreground">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="px-5 pt-6 pb-4">
          <SidebarBrand />
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-2">
          <SidebarNav onNavigate={() => setOpen(false)} />
        </div>
        <div className="px-3 pb-4 pt-2">
          <SidebarBrandCard />
        </div>
      </SheetContent>
    </Sheet>
  );
}
