import { ChevronDown } from "lucide-react";
import * as React from "react";
import { cn } from "cn";

export type SelectOption = { value: string; label: string };

type Props = React.ComponentProps<"select"> & { options: SelectOption[]; placeholder?: string };

/**
 * Liste déroulante native stylée comme `Input` : fiable dans les formulaires (react-hook-form),
 * accessible au clavier, testable. Le composant `Select` (Base UI) reste réservé aux filtres.
 */
export function NativeSelect({ options, placeholder, className, ...props }: Props) {
  return (
    <div className="relative">
      <select
        className={cn(
          "h-8 w-full appearance-none rounded-lg border border-input bg-card py-1 pr-8 pl-2.5 text-sm text-foreground transition-colors outline-none hover:border-brand-gray focus-visible:border-brand-green focus-visible:ring-3 focus-visible:ring-brand-green/25 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive",
          className,
        )}
        {...props}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  );
}
