import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // Action principale : vert encre #047a36 (5,47:1 avec blanc), hover vert foncé charte
        default: "bg-primary text-primary-foreground hover:bg-brand-green-dark",
        // Signal : jaune + texte noir (12,79:1). UN SEUL bouton accent par écran (l'action qui lance / crée)
        accent:
          "bg-brand-yellow font-semibold text-brand-black hover:bg-brand-yellow-hover focus-visible:border-brand-black/60 focus-visible:ring-brand-yellow/40",
        // Ossature : noir, texte blanc. Usage rare (Exporter, Archiver)
        dark: "bg-brand-black text-white hover:bg-brand-black-soft focus-visible:border-brand-green focus-visible:ring-brand-green/40",
        // Fantôme SUR surface noire (Header, héros) : focus jaune comme dans la sidebar
        "ghost-dark":
          "text-white/80 hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white focus-visible:border-brand-yellow/60 focus-visible:ring-brand-yellow/30",
        // Contour SUR surface noire : action secondaire d'un héros
        "outline-dark":
          "border-white/25 text-white hover:border-brand-yellow hover:bg-white/5 aria-expanded:bg-white/10 focus-visible:border-brand-yellow focus-visible:ring-brand-yellow/30",
        // Contour : hover vert (bordure + teinte)
        outline:
          "border-border bg-background text-foreground hover:border-brand-green hover:bg-brand-green-tint hover:text-brand-green-dark aria-expanded:bg-brand-green-tint aria-expanded:text-brand-green-dark dark:border-input dark:bg-input/30 dark:hover:bg-input/50",
        // Teinte verte pleine : actions tertiaires
        secondary:
          "bg-brand-green-tint text-brand-green-dark hover:bg-brand-green-tint-strong aria-expanded:bg-brand-green-tint-strong",
        ghost:
          "text-foreground hover:bg-brand-green-tint hover:text-brand-green-dark aria-expanded:bg-brand-green-tint aria-expanded:text-brand-green-dark dark:hover:bg-muted/50",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:border-destructive/40 focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:hover:bg-destructive/30 dark:focus-visible:ring-destructive/40",
        link: "text-primary underline-offset-4 hover:text-brand-green-dark hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
