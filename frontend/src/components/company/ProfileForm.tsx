"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CompanyProfile } from "@/lib/types";

const optional = z.string().trim().max(255).optional();

const schema = z.object({
  legal_name: z.string().trim().min(1, "La raison sociale est requise").max(255),
  trade_name: optional,
  description: z.string().trim().optional(),
  country: z
    .string()
    .trim()
    .toUpperCase()
    .regex(/^([A-Z]{2})?$/, "Code pays sur 2 lettres (ex. MA)")
    .optional(),
  city: optional,
  address: z.string().trim().optional(),
  website: z.string().trim().max(255).optional(),
  email: z.string().trim().email("Adresse email invalide").or(z.literal("")).optional(),
  phone: optional,
  sectors: z.string().optional(),
  positioning: z.string().trim().optional(),
});

type FormValues = z.infer<typeof schema>;

/** Valeurs envoyées à PUT /company/profile (partiel : "" → null, secteurs en liste). */
export type ProfileValues = Partial<CompanyProfile>;

type Props = {
  profile: CompanyProfile;
  onSubmit: (values: ProfileValues) => Promise<void> | void;
};

function toForm(p: CompanyProfile): FormValues {
  return {
    legal_name: p.legal_name ?? "",
    trade_name: p.trade_name ?? "",
    description: p.description ?? "",
    country: p.country ?? "",
    city: p.city ?? "",
    address: p.address ?? "",
    website: p.website ?? "",
    email: p.email ?? "",
    phone: p.phone ?? "",
    sectors: (p.sectors ?? []).join(", "),
    positioning: p.positioning ?? "",
  };
}

function toApi(v: FormValues): ProfileValues {
  const nullable = (s?: string) => (s && s.trim() ? s.trim() : null);
  return {
    legal_name: v.legal_name.trim(),
    trade_name: nullable(v.trade_name),
    description: nullable(v.description),
    country: nullable(v.country),
    city: nullable(v.city),
    address: nullable(v.address),
    website: nullable(v.website),
    email: nullable(v.email),
    phone: nullable(v.phone),
    sectors: Array.from(new Set((v.sectors ?? "").split(",").map((s) => s.trim()).filter(Boolean))),
    positioning: nullable(v.positioning),
  };
}

type FieldProps = { id: keyof FormValues; label: string; error?: string; children: React.ReactNode; help?: string };

function Field({ id, label, error, help, children }: FieldProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {help && !error && <p className="text-xs text-muted-foreground">{help}</p>}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

/** Informations générales de l'entreprise (Module 1) : identité, coordonnées, secteurs, positionnement. */
export function ProfileForm({ profile, onSubmit }: Props) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
    reset,
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: toForm(profile) });
  const [submitError, setSubmitError] = useState<string | null>(null);

  const field = (id: keyof FormValues) => ({
    id,
    "aria-invalid": !!errors[id],
    "aria-describedby": errors[id] ? `${id}-error` : undefined,
    ...register(id),
  });

  async function submit(values: FormValues) {
    setSubmitError(null);
    try {
      const payload = toApi(values);
      await onSubmit(payload);
      reset(values); // l'état « modifié » repart de la version enregistrée
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Enregistrement impossible.");
    }
  }

  return (
    <form onSubmit={handleSubmit(submit)} noValidate>
      <Card accent="green">
        <CardHeader>
          <CardTitle>Identité</CardTitle>
          <CardDescription>Raison sociale, coordonnées et secteurs : la base du matching et des documents générés.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          <Field id="legal_name" label="Raison sociale" error={errors.legal_name?.message}>
            <Input {...field("legal_name")} />
          </Field>
          <Field id="trade_name" label="Nom commercial" error={errors.trade_name?.message}>
            <Input {...field("trade_name")} placeholder="InnoSustain" />
          </Field>
          <div className="md:col-span-2">
            <Field id="description" label="Description" error={errors.description?.message}>
              <Textarea rows={3} {...field("description")} placeholder="Activité, expertises, valeurs…" />
            </Field>
          </div>
          <Field id="country" label="Pays (code ISO)" error={errors.country?.message} help="2 lettres, ex. MA">
            <Input maxLength={2} className="uppercase" {...field("country")} />
          </Field>
          <Field id="city" label="Ville" error={errors.city?.message}>
            <Input {...field("city")} />
          </Field>
          <div className="md:col-span-2">
            <Field id="address" label="Adresse" error={errors.address?.message}>
              <Input {...field("address")} />
            </Field>
          </div>
          <Field id="website" label="Site web" error={errors.website?.message}>
            <Input type="url" placeholder="https://" {...field("website")} />
          </Field>
          <Field id="email" label="Email de contact" error={errors.email?.message}>
            <Input type="email" {...field("email")} />
          </Field>
          <Field id="phone" label="Téléphone" error={errors.phone?.message}>
            <Input type="tel" {...field("phone")} />
          </Field>
          <Field
            id="sectors"
            label="Secteurs d'activité"
            error={errors.sectors?.message}
            help="Séparés par des virgules — utilisés par le score de pertinence"
          >
            <Input {...field("sectors")} placeholder="Environnement, Énergie, Conseil" />
          </Field>
          <div className="md:col-span-2">
            <Field id="positioning" label="Positionnement" error={errors.positioning?.message} help="Une phrase : ce que l'entreprise fait de mieux (réutilisée par l'IA)">
              <Textarea rows={2} {...field("positioning")} />
            </Field>
          </div>
          {submitError && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive md:col-span-2">
              {submitError}
            </p>
          )}
        </CardContent>
        <CardFooter className="justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => reset(toForm(profile))} disabled={!isDirty || isSubmitting}>
            Annuler
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Enregistrement…" : "Enregistrer"}
          </Button>
        </CardFooter>
      </Card>
    </form>
  );
}
