"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";

import { FileDropZone } from "@/components/documents/FileDropZone";
import { NativeSelect } from "@/components/common/NativeSelect";
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
import { buildUploadForm, CATEGORY_OPTIONS, fileProblem, type UploadMeta } from "@/lib/documents";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Reçoit le corps multipart prêt pour POST /documents. */
  onSubmit: (form: FormData) => Promise<void> | void;
};

type FormValues = Required<Pick<UploadMeta, "category" | "name" | "description" | "issued_at" | "expires_at" | "tags">>;

const EMPTY: FormValues = { category: CATEGORY_OPTIONS[0].value, name: "", description: "", issued_at: "", expires_at: "", tags: "" };

/** Nom d'affichage proposé : le nom du fichier sans son extension. */
export function nameFromFile(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return (dot > 0 ? filename.slice(0, dot) : filename).trim();
}

/** Dépôt d'un nouveau document : fichier (glisser-déposer) + métadonnées (catégorie, dates, étiquettes). */
export function UploadDialog({ open, onOpenChange, onSubmit }: Props) {
  const { register, handleSubmit, reset, getValues, setValue, formState } = useForm<FormValues>({ defaultValues: EMPTY });
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function changeFile(next: File | null) {
    setFile(next);
    setFileError(next ? fileProblem(next) : null);
    if (next && !getValues("name").trim()) setValue("name", nameFromFile(next.name));
  }

  function close(next: boolean) {
    if (!next) {
      reset(EMPTY);
      setFile(null);
      setFileError(null);
      setSubmitError(null);
    }
    onOpenChange(next);
  }

  async function submit(values: FormValues) {
    setSubmitError(null);
    if (!file) {
      setFileError("Choisissez un fichier à déposer.");
      return;
    }
    if (fileError) return;
    try {
      await onSubmit(buildUploadForm(values, file));
      close(false);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Dépôt impossible.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Déposer un document</DialogTitle>
          <DialogDescription>
            Attestation, certification, CV, référence… Un document expiré n&apos;est jamais réutilisé automatiquement.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(submit)} className="grid gap-4 sm:grid-cols-2" noValidate>
          <div className="sm:col-span-2">
            <FileDropZone id="upload-file" file={file} onChange={changeFile} error={fileError} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="upload-name">Nom</Label>
            <Input id="upload-name" placeholder="Attestation fiscale 2026" {...register("name")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="upload-category">Catégorie</Label>
            <NativeSelect id="upload-category" options={CATEGORY_OPTIONS} {...register("category")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="upload-issued">Délivré le</Label>
            <Input id="upload-issued" type="date" {...register("issued_at")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="upload-expires">Expire le</Label>
            <Input id="upload-expires" type="date" {...register("expires_at")} />
            <p className="text-xs text-muted-foreground">Passé cette date, le document est marqué « Expiré » (RB-007).</p>
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="upload-tags">Étiquettes</Label>
            <Input id="upload-tags" placeholder="fiscal, 2026, obligatoire" {...register("tags")} />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="upload-description">Description</Label>
            <Textarea id="upload-description" rows={2} {...register("description")} />
          </div>

          {submitError && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive sm:col-span-2">
              {submitError}
            </p>
          )}

          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => close(false)} disabled={formState.isSubmitting}>
              Annuler
            </Button>
            <Button type="submit" variant="accent" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Dépôt…" : "Déposer"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
