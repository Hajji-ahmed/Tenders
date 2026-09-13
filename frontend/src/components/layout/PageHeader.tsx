import { cn } from "cn";

type Props = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
};

/** En-tête de page standard : titre, sous-titre et zone d'actions à droite. */
export function PageHeader({ title, description, actions, className }: Props) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
