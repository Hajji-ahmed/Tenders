"use client"

import * as React from "react"
import { cn } from "cn"

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      // Encadré seul ; nu s'il est déjà posé dans une Card (évite le double cadre, la Card rogne les coins du thead)
      className="relative w-full overflow-x-auto rounded-xl bg-card ring-1 ring-foreground/10 in-data-[slot=card]:rounded-none in-data-[slot=card]:bg-transparent in-data-[slot=card]:ring-0"
    >
      <table
        data-slot="table"
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({
  className,
  variant = "default",
  ...props
}: React.ComponentProps<"thead"> & { variant?: "default" | "inverse" }) {
  return (
    <thead
      data-slot="table-header"
      data-variant={variant}
      // Filet vert 2 px sous l'en-tête dans les deux variantes. `inverse` (thead vert encre) : une seule table par page.
      className={cn(
        "group/thead [&_tr]:border-b-2 [&_tr]:border-brand-green [&_tr]:hover:bg-transparent",
        variant === "inverse" ? "bg-brand-green-ink" : "bg-muted/60",
        className
      )}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  )
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "border-t-2 border-brand-green bg-muted/50 font-medium text-brand-green-dark [&>tr]:last:border-b-0",
        className
      )}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      // Survol : teinte verte. Sélection : teinte verte + barre jaune 3 px à gauche (signal)
      className={cn(
        "border-b transition-colors hover:bg-brand-green-tint/50 has-aria-expanded:bg-brand-green-tint/50 data-[state=selected]:bg-brand-green-tint data-[state=selected]:shadow-[inset_3px_0_0_0_var(--brand-yellow)]",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      // Libellés vert foncé en petites capitales ; sur thead vert encre : blanc/90, colonne triée (aria-sort) en jaune
      className={cn(
        "h-9 px-3 text-left align-middle text-xs font-semibold uppercase tracking-wide whitespace-nowrap text-brand-green-dark aria-[sort]:text-brand-green-ink group-data-[variant=inverse]/thead:text-white/90 group-data-[variant=inverse]/thead:aria-[sort]:text-brand-yellow [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-3 py-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
