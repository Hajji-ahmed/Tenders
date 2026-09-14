import type { DocumentCategory, DocumentStatus } from "@/lib/types";

/** Formats acceptés par l'API (miroir de `ALLOWED_MIMES` côté backend) : extension → type MIME attendu. */
export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".txt", ".zip"] as const;
export const ACCEPT_ATTRIBUTE = ALLOWED_EXTENSIONS.join(",");
export const MAX_UPLOAD_MB = 50;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

/** Ordre = fréquence d'usage dans les dossiers de candidature (première valeur = défaut du sélecteur). */
export const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  attestation: "Attestation",
  certification: "Certification",
  cv: "CV",
  reference: "Référence",
  presentation: "Présentation",
  administratif: "Administratif",
  financier: "Financier",
  juridique: "Juridique",
  template: "Modèle",
  autre: "Autre",
};

export const CATEGORY_OPTIONS = (Object.keys(CATEGORY_LABELS) as DocumentCategory[]).map((value) => ({
  value,
  label: CATEGORY_LABELS[value],
}));

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  draft: "Brouillon",
  valid: "Valide",
  expired: "Expiré",
  archived: "Archivé",
};

export const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as DocumentStatus[]).map((value) => ({
  value,
  label: STATUS_LABELS[value],
}));

const MIME_KINDS: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
  "text/plain": "TXT",
  "application/zip": "ZIP",
  "application/x-zip-compressed": "ZIP",
};

/** Type de fichier lisible (« PDF », « DOCX »…) à partir du MIME enregistré par l'API. */
export function fileKind(mime: string): string {
  return MIME_KINDS[mime] ?? "Fichier";
}

/** Taille lisible en français : « 1,5 Ko », « 2 Mo » (une décimale au plus, jamais de « .0 »). */
export function formatBytes(bytes: number): string {
  const units = ["o", "Ko", "Mo", "Go"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  const rounded = Math.round(value * 10) / 10;
  return `${rounded.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ${units[i]}`;
}

/** Contrôle côté client avant l'envoi (extension, taille) ; `null` si le fichier convient. */
export function fileProblem(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext as (typeof ALLOWED_EXTENSIONS)[number])) {
    return "Type de fichier non autorisé (PDF, DOCX, XLSX, TXT, ZIP)";
  }
  if (file.size > MAX_UPLOAD_BYTES) return `Fichier trop volumineux (max ${MAX_UPLOAD_MB} Mo)`;
  return null;
}

export type UploadMeta = {
  category: DocumentCategory | string;
  name?: string;
  description?: string;
  issued_at?: string;
  expires_at?: string;
  /** Étiquettes séparées par des virgules (nettoyées avant envoi). */
  tags?: string;
};

/** Nettoie une saisie « a, b,,a » → ["a", "b"] (espaces retirés, vides ignorés, doublons supprimés). */
export function cleanTags(input: string): string[] {
  return Array.from(new Set(input.split(",").map((t) => t.trim()).filter(Boolean)));
}

/** Corps multipart de POST /documents : le fichier, la catégorie et les seules métadonnées renseignées. */
export function buildUploadForm(meta: UploadMeta, file: File): FormData {
  const form = new FormData();
  form.set("file", file);
  form.set("category", meta.category);
  const optional: Array<keyof UploadMeta> = ["name", "description", "issued_at", "expires_at"];
  for (const key of optional) {
    const value = meta[key]?.trim();
    if (value) form.set(key, value);
  }
  const tags = cleanTags(meta.tags ?? "");
  if (tags.length) form.set("tags", tags.join(", "));
  return form;
}

/** Lien de téléchargement same-origin (relais /api/v1 → API), utilisable dans un `<a href>`. */
export function documentDownloadUrl(id: string): string {
  return `/api/v1/documents/${id}/download`;
}
