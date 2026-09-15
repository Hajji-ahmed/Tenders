import type { SourceConfig, SourceKind, TenderSource } from "@/lib/types";

export const SOURCE_KIND_LABELS: Record<SourceKind, string> = {
  search_engine: "Moteur de recherche",
  rss: "Flux RSS",
  portal: "Portail d'appels d'offres",
  website: "Site web",
  api: "API (bientôt)",
};

export const SOURCE_KIND_OPTIONS = (Object.keys(SOURCE_KIND_LABELS) as SourceKind[]).map((value) => ({
  value,
  label: SOURCE_KIND_LABELS[value],
}));

/** Champs de formulaire à plat : l'utilisateur ne saisit jamais de JSON. */
export type SourceConfigFields = {
  include_domains: string[];
  max_results: number | null;
  listing_paths: string[];
  link_pattern: string;
  render_js: boolean;
  max_links: number | null;
};

export function configToFields(config: SourceConfig | null | undefined): SourceConfigFields {
  const c = config ?? {};
  return {
    include_domains: c.include_domains ?? [],
    max_results: c.max_results ?? null,
    listing_paths: c.listing_paths ?? [],
    link_pattern: c.link_pattern ?? "",
    render_js: Boolean(c.render_js),
    max_links: c.max_links ?? null,
  };
}

/** Ne conserve que les clés qui ont un sens pour le type de source, et seulement si renseignées. */
export function fieldsToConfig(kind: SourceKind, f: SourceConfigFields): SourceConfig {
  const out: SourceConfig = {};
  if (kind === "search_engine") {
    if (f.include_domains.length) out.include_domains = f.include_domains;
    if (f.max_results) out.max_results = f.max_results;
  } else if (kind === "portal" || kind === "website") {
    if (f.listing_paths.length) out.listing_paths = f.listing_paths;
    if (f.link_pattern.trim()) out.link_pattern = f.link_pattern.trim();
    if (f.render_js) out.render_js = true;
    if (f.max_links) out.max_links = f.max_links;
  }
  return out;
}

type FormValues = Record<string, unknown>;

/** Valeurs du formulaire (à plat, cf. EntityDialog) → corps API { name, kind, base_url, priority, is_enabled, config }. */
export function toSourcePayload(values: FormValues): Record<string, unknown> {
  const kind = String(values.kind) as SourceKind;
  const fields: SourceConfigFields = {
    include_domains: (values.include_domains as string[]) ?? [],
    max_results: (values.max_results as number | null) ?? null,
    listing_paths: (values.listing_paths as string[]) ?? [],
    link_pattern: (values.link_pattern as string | null) ?? "",
    render_js: Boolean(values.render_js),
    max_links: (values.max_links as number | null) ?? null,
  };
  return {
    name: values.name,
    kind,
    base_url: values.base_url ?? null,
    priority: (values.priority as number | null) ?? 100,
    is_enabled: Boolean(values.is_enabled),
    config: fieldsToConfig(kind, fields),
  };
}

/** Source API → valeurs du formulaire (config aplatie). */
export function toSourceForm(s: TenderSource): FormValues {
  return {
    name: s.name,
    kind: s.kind,
    base_url: s.base_url,
    priority: s.priority,
    is_enabled: s.is_enabled,
    ...configToFields(s.config),
  };
}
