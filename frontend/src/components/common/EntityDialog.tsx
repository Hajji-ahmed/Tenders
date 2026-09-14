"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { NativeSelect, type SelectOption } from "@/components/common/NativeSelect";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export type FieldType = "text" | "textarea" | "date" | "number" | "select" | "tags" | "checkbox";

export type FieldSpec = {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: SelectOption[];
  placeholder?: string;
  help?: string;
  /** Champ sur toute la largeur (par défaut : demi-largeur sur écran large). */
  full?: boolean;
};

export type EntityValues = Record<string, unknown>;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  fields: FieldSpec[];
  defaultValues?: EntityValues;
  onSubmit: (values: EntityValues) => Promise<void> | void;
  submitLabel?: string;
};

/** Valeurs du formulaire (toutes en chaînes / booléens) construites depuis les valeurs de l'entité. */
function toFormValues(fields: FieldSpec[], values: EntityValues = {}): Record<string, string | boolean> {
  const out: Record<string, string | boolean> = {};
  for (const f of fields) {
    const v = values[f.name];
    if (f.type === "checkbox") out[f.name] = Boolean(v);
    else if (f.type === "tags") out[f.name] = Array.isArray(v) ? v.join(", ") : "";
    else out[f.name] = v === null || v === undefined ? "" : String(v);
  }
  return out;
}

/** Valeurs typées pour l'API : "" → null, nombres, listes d'étiquettes nettoyées. */
function toEntityValues(fields: FieldSpec[], form: Record<string, string | boolean>): EntityValues {
  const out: EntityValues = {};
  for (const f of fields) {
    const raw = form[f.name];
    switch (f.type) {
      case "checkbox":
        out[f.name] = Boolean(raw);
        break;
      case "number": {
        const s = String(raw ?? "").trim();
        out[f.name] = s === "" ? null : Number(s);
        break;
      }
      case "tags": {
        const list = String(raw ?? "")
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
        out[f.name] = Array.from(new Set(list));
        break;
      }
      default: {
        const s = String(raw ?? "").trim();
        out[f.name] = s === "" ? null : s;
      }
    }
  }
  return out;
}

/**
 * Fenêtre de création / édition générique pilotée par une liste de champs (`FieldSpec`).
 * Utilisée par tous les onglets du profil entreprise ; les pages n'écrivent aucun formulaire.
 */
export function EntityDialog({
  open,
  onOpenChange,
  title,
  description,
  fields,
  defaultValues,
  onSubmit,
  submitLabel = "Enregistrer",
}: Props) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Record<string, string | boolean>>({ defaultValues: toFormValues(fields, defaultValues) });
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Rouvrir la fenêtre sur une autre entité : repartir des nouvelles valeurs.
  useEffect(() => {
    if (open) reset(toFormValues(fields, defaultValues));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultValues]);

  function close(next: boolean) {
    if (!next) setSubmitError(null);
    onOpenChange(next);
  }

  async function submit(form: Record<string, string | boolean>) {
    setSubmitError(null);
    try {
      await onSubmit(toEntityValues(fields, form));
      close(false);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Enregistrement impossible.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        <form onSubmit={handleSubmit(submit)} className="grid gap-4 sm:grid-cols-2" noValidate>
          {fields.map((f) => {
            const id = `field-${f.name}`;
            const error = errors[f.name]?.message as string | undefined;
            const common = {
              id,
              "aria-invalid": !!error,
              "aria-describedby": error ? `${id}-error` : undefined,
            };
            const rules = f.required ? { required: `${f.label} : champ requis` } : {};
            const wide = f.full || f.type === "textarea" || f.type === "tags";
            return (
              <div key={f.name} className={wide ? "space-y-2 sm:col-span-2" : "space-y-2"}>
                {f.type === "checkbox" ? (
                  <label htmlFor={id} className="flex items-center gap-2 text-sm font-medium">
                    <input
                      id={id}
                      type="checkbox"
                      className="size-4 rounded border-input accent-brand-green"
                      {...register(f.name)}
                    />
                    {f.label}
                  </label>
                ) : (
                  <>
                    <Label
                      htmlFor={id}
                      // Astérisque en CSS : le nom accessible du champ reste le libellé seul.
                      className={f.required ? "after:ml-0.5 after:text-destructive after:content-['*']" : undefined}
                    >
                      {f.label}
                    </Label>
                    {f.type === "textarea" && (
                      <Textarea rows={3} placeholder={f.placeholder} {...common} {...register(f.name, rules)} />
                    )}
                    {f.type === "select" && (
                      <NativeSelect
                        options={f.options ?? []}
                        placeholder={f.required ? undefined : "—"}
                        {...common}
                        {...register(f.name, rules)}
                      />
                    )}
                    {(f.type === "text" || f.type === "tags") && (
                      <Input type="text" placeholder={f.placeholder} {...common} {...register(f.name, rules)} />
                    )}
                    {f.type === "number" && (
                      <Input type="number" inputMode="numeric" placeholder={f.placeholder} {...common} {...register(f.name, rules)} />
                    )}
                    {f.type === "date" && <Input type="date" {...common} {...register(f.name, rules)} />}
                  </>
                )}
                {f.help && !error && <p className="text-xs text-muted-foreground">{f.help}</p>}
                {error && (
                  <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
                    {error}
                  </p>
                )}
              </div>
            );
          })}

          {submitError && (
            <p
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive sm:col-span-2"
            >
              {submitError}
            </p>
          )}

          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => close(false)} disabled={isSubmitting}>
              Annuler
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Enregistrement…" : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
