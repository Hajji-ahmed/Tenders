import { Leaf } from "lucide-react";
import { cn } from "cn";

type Props = {
  title: string;
  description?: string;
  /** Surtitre (ex. « Pilotage », « Veille ») */
  eyebrow?: string;
  /** Compteur jaune à côté du titre (ex. nombre d'opportunités) */
  count?: number;
  actions?: React.ReactNode;
  /** Motif feuille très discret à droite (pages d'accueil). */
  art?: boolean;
  className?: string;
};

/** En-tête de page : surtitre, grand titre (+ compteur jaune), sous-titre, actions. */
export function PageHeader({ title, description, eyebrow, count, actions, art = false, className }: Props) {
  return (
    <div className={cn("relative flex flex-wrap items-end justify-between gap-4", className)}>
      {art && (
        <Leaf
          aria-hidden
          strokeWidth={1}
          className="pointer-events-none absolute -top-4 right-0 hidden size-28 text-brand-green/10 lg:block"
        />
      )}
      <div className="relative space-y-1.5">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-green-dark/70">{eyebrow}</p>
        )}
        <h1 className="flex items-center gap-3 text-[2rem] font-bold leading-tight tracking-tight text-brand-green-dark">
          {title}
          {typeof count === "number" && (
            <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-brand-yellow px-2.5 text-sm font-semibold tabular-nums text-brand-yellow-ink">
              {count}
            </span>
          )}
        </h1>
        {description && <p className="text-base text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="relative flex items-center gap-2">{actions}</div>}
    </div>
  );
}
