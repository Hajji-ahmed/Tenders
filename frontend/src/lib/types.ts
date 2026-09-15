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

// ---- Recherche & opportunités (Phase 3) -------------------------------------------------------

export type SourceKind = "search_engine" | "rss" | "portal" | "website" | "api";

export type SearchProfile = Timestamps & {
  id: string;
  name: string;
  countries: string[];
  regions: string[];
  sectors: string[];
  domains: string[];
  keywords: string[];
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  organization_types: string[];
  market_types: string[];
  technologies: string[];
  skills: string[];
  certifications: string[];
  experience_level: string | null;
  deadline_min_days: number | null;
  deadline_max_days: number | null;
  is_active: boolean;
  last_run_at: string | null;
};

/** `config` d'une source, selon son type (voir backend TenderSource). */
export type SourceConfig = {
  include_domains?: string[];
  max_results?: number;
  listing_paths?: string[];
  link_pattern?: string;
  render_js?: boolean;
  max_links?: number;
};

export type TenderSource = Timestamps & {
  id: string;
  name: string;
  kind: SourceKind;
  base_url: string | null;
  config: SourceConfig;
  is_enabled: boolean;
  priority: number;
  last_run_at: string | null;
  last_status: "ok" | "error" | "skipped" | null;
  last_error: string | null;
};

export type TenderCandidate = {
  is_tender: boolean;
  confidence: number;
  title: string;
  organization: string | null;
  country: string | null;
  sector: string | null;
  deadline_at: string | null;
  source_url: string;
  document_urls: string[];
};

/** Résultat de POST /sources/{id}/test. */
export type SourceTestReport = {
  status: "ok" | "error" | "skipped";
  error: string | null;
  found: number;
  skipped_known: number;
  fetched: number;
  errors: number;
  extracted: number;
  queries: string[];
  candidates: TenderCandidate[];
};

export type TenderStatus =
  | "NOUVEAU"
  | "A_ANALYSER"
  | "GO"
  | "NO_GO"
  | "PREPARATION"
  | "VALIDATION"
  | "PRET"
  | "SOUMIS"
  | "GAGNE"
  | "PERDU"
  | "ARCHIVE";
export type Urgency = "none" | "low" | "medium" | "high" | "critical";

export type Tender = Timestamps & {
  id: string;
  reference: string | null;
  title: string;
  organization: string | null;
  organization_type: string | null;
  country: string | null;
  region: string | null;
  sector: string | null;
  market_type: string | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  published_at: string | null;
  deadline_at: string | null;
  questions_deadline_at: string | null;
  source_url: string | null;
  description: string | null;
  summary: string | null;
  status: TenderStatus;
  urgency: Urgency;
  is_active: boolean;
  search_profile_id: string | null;
  days_left: number | null;
  source_count: number;
  document_count: number;
  score_total: number | null;
};

export type TenderSourceLink = {
  id: string;
  source_id: string | null;
  source_name: string | null;
  url: string;
  title_seen: string | null;
  collected_at: string;
};

export type TenderDocumentRef = Timestamps & {
  id: string;
  name: string;
  source_url: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  download_status: "pending" | "done" | "failed" | "skipped";
  extraction_status: string;
  page_count: number | null;
  error: string | null;
};

export type TenderDetail = Tender & {
  extra: Record<string, unknown>;
  source_links: TenderSourceLink[];
  documents: TenderDocumentRef[];
};
