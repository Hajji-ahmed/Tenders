"use client";

import { useState } from "react";

import { FileDropZone } from "@/components/documents/FileDropZone";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fileProblem } from "@/lib/documents";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  documentName: string;
  /** Reçoit le corps multipart (`file`, `changelog`) pour POST /documents/{id}/versions. */
  onSubmit: (form: FormData) => Promise<void> | void;
};

/** Remplacement du fichier d'un document existant : l'historique des versions est conservé côté API. */
export function NewVersionDialog({ open, onOpenChange, documentName, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [changelog, setChangelog] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function changeFile(next: File | null) {
    setFile(next);
    setFileError(next ? fileProblem(next) : null);
  }

  function close(next: boolean) {
    if (!next) {
      setFile(null);
      setChangelog("");
      setFileError(null);
      setSubmitError(null);
    }
    onOpenChange(next);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    if (!file) {
      setFileError("Choisissez le nouveau fichier.");
      return;
    }
    if (fileError) return;
    const form = new FormData();
    form.set("file", file);
    if (changelog.trim()) form.set("changelog", changelog.trim());
    setPending(true);
    try {
      await onSubmit(form);
      close(false);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Envoi impossible.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle version</DialogTitle>
          <DialogDescription>
            Remplace le fichier de « {documentName} ». Les versions précédentes restent consultables.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-4" noValidate>
          <FileDropZone id="version-file" file={file} onChange={changeFile} error={fileError} label="Nouveau fichier" />
          <div className="space-y-2">
            <Label htmlFor="version-changelog">Quoi de neuf ?</Label>
            <Textarea
              id="version-changelog"
              rows={2}
              placeholder="Renouvellement 2026, correction du montant…"
              value={changelog}
              onChange={(e) => setChangelog(e.target.value)}
            />
          </div>
          {submitError && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {submitError}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => close(false)} disabled={pending}>
              Annuler
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? "Envoi…" : "Enregistrer la version"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
