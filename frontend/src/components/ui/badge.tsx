import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-4xl border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-all focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground [a]:hover:bg-brand-green-dark",
        secondary:
          "bg-brand-green-tint text-brand-green-dark [a]:hover:bg-brand-green-tint-strong",
        destructive:
          "bg-destructive/10 text-destructive focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:focus-visible:ring-destructive/40 [a]:hover:bg-destructive/20",
        outline:
          "border-border text-foreground [a]:hover:border-brand-green/50 [a]:hover:text-brand-green-dark",
        ghost: "hover:bg-brand-green-tint hover:text-brand-green-dark dark:hover:bg-muted/50",
        link: "text-primary underline-offset-4 hover:underline",
        // ---- Statuts métier InnoSustain ----
        // Positif / validé : teinte verte + vert foncé (5,7:1)
        success:
          "border-brand-green/30 bg-brand-green-tint text-brand-green-dark [a]:hover:bg-brand-green-tint-strong",
        // Signal fort : jaune plein + brun foncé (10,19:1) — nouveau, échéance proche. Un seul par ligne
        warning:
          "bg-brand-yellow font-semibold text-brand-yellow-ink [a]:hover:bg-brand-yellow-hover",
        // Attention douce : teinte jaune + texte brun (10,19:1) — à qualifier, en attente
        "warning-soft":
          "border-brand-yellow/70 bg-brand-yellow-tint text-brand-yellow-ink",
        // Ossature : statut figé (déposé, en cours de traitement) — vert encre plein
        inverse: "bg-brand-green-ink text-white [a]:hover:bg-brand-ink-soft",
        // Clôturé / inactif
        muted: "bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
