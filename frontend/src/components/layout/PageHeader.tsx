import { cn } from "cn";

type Props = {
  title: string;
  description?: string;
  /** Surtitre bleu lagon (ex. « Pilotage », « Veille ») */
  eyebrow?: string;
  /** Compteur jaune à côté du titre (ex. nombre d'opportunités) */
  count?: number;
  actions?: React.ReactNode;
  className?: string;
};

/** En-tête de page : surtitre, titre vert foncé (+ compteur jaune), sous-titre, actions ; filet bas discret. */
export function PageHeader({ title, description, eyebrow, count, actions, className }: Props) {
  return (
    <div
      className={cn("flex flex-wrap items-end justify-between gap-4 border-b border-border pb-4", className)}
    >
      <div className="space-y-1">
        {eyebrow && (
          <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-blue-dark">{eyebrow}</p>
        )}
        <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight text-brand-green-dark">
          {title}
          {typeof count === "number" && (
            <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-brand-yellow px-2 text-xs font-semibold tabular-nums text-brand-yellow-ink">
              {count}
            </span>
          )}
        </h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
