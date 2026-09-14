"use client";

import { FileCheck2, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "cn";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ACCEPT_ATTRIBUTE, formatBytes, MAX_UPLOAD_MB } from "@/lib/documents";

type Props = {
  id: string;
  file: File | null;
  onChange: (file: File | null) => void;
  error?: string | null;
  label?: string;
};

/**
 * Zone de dépôt : glisser-déposer ou « Parcourir ». L'`<input type="file">` reste dans le DOM
 * (masqué visuellement) et porte le libellé : accessible au clavier, aux lecteurs d'écran et aux tests.
 */
export function FileDropZone({ id, file, onChange, error, label = "Fichier" }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function pick(list: FileList | null) {
    onChange(list && list.length > 0 ? list[0] : null);
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={ACCEPT_ATTRIBUTE}
        className="sr-only"
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(e) => pick(e.target.files)}
      />
      <div
        role="group"
        aria-label="Zone de dépôt"
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          pick(e.dataTransfer.files);
        }}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm transition-colors",
          over ? "border-brand-green bg-brand-green-tint" : "border-brand-green/30 bg-muted/40",
          error && "border-destructive/60",
        )}
      >
        {file ? (
          <>
            <FileCheck2 aria-hidden className="size-6 text-brand-green" />
            <p className="max-w-full truncate font-medium text-foreground">{file.name}</p>
            <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange(null)}>
              <X />
              Retirer
            </Button>
          </>
        ) : (
          <>
            <Upload aria-hidden className="size-6 text-brand-blue" />
            <p className="text-muted-foreground">
              Glissez-déposez un fichier ici, ou{" "}
              <Button type="button" variant="link" className="h-auto p-0" onClick={() => inputRef.current?.click()}>
                parcourez vos fichiers
              </Button>
            </p>
            <p className="text-xs text-muted-foreground">PDF, DOCX, XLSX, TXT, ZIP — {MAX_UPLOAD_MB} Mo max</p>
          </>
        )}
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
