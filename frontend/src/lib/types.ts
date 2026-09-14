// Types miroirs des schémas Pydantic (backend/app/schemas). À compléter phase par phase.

export type User = {
  id: string;
  email: string;
};

export type JobStatus = "pending" | "running" | "done" | "failed";

export type Job = {
  id: string;
  type: string;
  status: JobStatus;
  entity_kind: string | null;
  entity_id: string | null;
  progress: number;
  message: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

/** Enveloppe de toutes les listes paginées de l'API. */
export type Page<T> = { items: T[]; total: number; page: number; size: number };

// ---- Entreprise (Phase 2) -------------------------------------------------------------------------

export type SkillCategory = "expertise" | "service" | "savoir_faire";
export type TechnologyCategory = "language" | "framework" | "database" | "cloud" | "tool" | "other";
export type CertificationCategory = "technique" | "qualite" | "securite" | "autre";

type Timestamps = { created_at: string; updated_at: string };

export type CompanyProfile = {
  id: string;
  legal_name: string;
  trade_name: string | null;
  description: string | null;
  country: string | null;
  city: string | null;
  address: string | null;
  website: string | null;
  email: string | null;
  phone: string | null;
  sectors: string[];
  positioning: string | null;
  ai_summary: string | null;
  ai_summary_updated_at: string | null;
  counts: Record<string, number>;
  updated_at: string;
};

export type Skill = Timestamps & {
  id: string;
  name: string;
  category: SkillCategory;
  level: string | null;
  description: string | null;
};

export type Technology = Timestamps & {
  id: string;
  name: string;
  category: TechnologyCategory;
  level: string | null;
  years_experience: number | null;
};

export type Certification = Timestamps & {
  id: string;
  name: string;
  issuer: string | null;
  category: CertificationCategory;
  issued_at: string | null;
  expires_at: string | null;
  document_id: string | null;
  is_valid: boolean;
};

export type Expert = Timestamps & {
  id: string;
  full_name: string;
  role: string | null;
  years_experience: number | null;
  skills: string[];
  bio: string | null;
  cv_document_id: string | null;
};

export type Project = Timestamps & {
  id: string;
  title: string;
  client: string | null;
  sector: string | null;
  country: string | null;
  start_date: string | null;
  end_date: string | null;
  budget: number | null;
  currency: string | null;
  technologies: string[];
  description: string | null;
  results: string | null;
  is_reference: boolean;
};

export type Reference = Timestamps & {
  id: string;
  client_name: string;
  project_id: string | null;
  sector: string | null;
  description: string | null;
  contact_name: string | null;
  contact_email: string | null;
  document_id: string | null;
};

// ---- Documents (Phase 2) --------------------------------------------------------------------------

export type DocumentCategory =
  | "presentation"
  | "certification"
  | "attestation"
  | "reference"
  | "cv"
  | "administratif"
  | "financier"
  | "juridique"
  | "template"
  | "autre";
export type DocumentStatus = "draft" | "valid" | "expired" | "archived";
export type ExtractionStatus = "pending" | "done" | "failed" | "skipped";

export type CompanyDocument = Timestamps & {
  id: string;
  company_id: string;
  name: string;
  category: DocumentCategory;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  version: number;
  status: DocumentStatus;
  issued_at: string | null;
  expires_at: string | null;
  description: string | null;
  tags: string[];
  extraction_status: ExtractionStatus;
  is_expired: boolean;
  is_usable: boolean;
};

export type DocumentVersion = {
  id: string;
  document_id: string;
  version_number: number;
  sha256: string;
  author: string | null;
  changelog: string | null;
  created_at: string;
};
