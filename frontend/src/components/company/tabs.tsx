"use client";

import { ResourceTab } from "@/components/company/ResourceTab";
import { Badge } from "@/components/ui/badge";
import type { Certification, Expert, Project, Reference, Skill, Technology } from "@/lib/types";

const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleDateString("fr-FR") : "—");
const fmtMoney = (n: number | null, currency: string | null) =>
  n === null ? "—" : new Intl.NumberFormat("fr-FR", { style: "currency", currency: currency || "MAD", maximumFractionDigits: 0 }).format(n);

const SKILL_CATEGORIES = [
  { value: "expertise", label: "Domaine d'expertise" },
  { value: "service", label: "Service proposé" },
  { value: "savoir_faire", label: "Savoir-faire" },
];
const TECH_CATEGORIES = [
  { value: "language", label: "Langage" },
  { value: "framework", label: "Framework" },
  { value: "database", label: "Base de données" },
  { value: "cloud", label: "Cloud" },
  { value: "tool", label: "Outil" },
  { value: "other", label: "Autre" },
];
const CERT_CATEGORIES = [
  { value: "technique", label: "Technique" },
  { value: "qualite", label: "Qualité" },
  { value: "securite", label: "Sécurité" },
  { value: "autre", label: "Autre" },
];
const labelOf = (options: { value: string; label: string }[], value: string) =>
  options.find((o) => o.value === value)?.label ?? value;

export function SkillsTab() {
  return (
    <ResourceTab<"skills">
      entity="skills"
      description="Domaines d'expertise, services et savoir-faire."
      labels={{ singular: "Compétence", empty: "Aucune compétence renseignée", addButton: "Ajouter une compétence", nameOf: (r: Skill) => r.name }}
      columns={[
        { key: "name", label: "Compétence", render: (r) => <span className="font-medium text-foreground">{r.name}</span> },
        { key: "category", label: "Type", render: (r) => labelOf(SKILL_CATEGORIES, r.category) },
        { key: "level", label: "Niveau" },
        { key: "description", label: "Description" },
      ]}
      fields={[
        { name: "name", label: "Compétence", type: "text", required: true },
        { name: "category", label: "Type", type: "select", options: SKILL_CATEGORIES, required: true },
        { name: "level", label: "Niveau", type: "text", placeholder: "débutant, confirmé, expert…" },
        { name: "description", label: "Description", type: "textarea" },
      ]}
    />
  );
}

export function TechnologiesTab() {
  return (
    <ResourceTab<"technologies">
      entity="technologies"
      description="Langages, frameworks, bases de données, cloud et outils maîtrisés."
      labels={{ singular: "Technologie", empty: "Aucune technologie renseignée", addButton: "Ajouter une technologie", nameOf: (r: Technology) => r.name }}
      columns={[
        { key: "name", label: "Technologie", render: (r) => <span className="font-medium text-foreground">{r.name}</span> },
        { key: "category", label: "Catégorie", render: (r) => labelOf(TECH_CATEGORIES, r.category) },
        { key: "level", label: "Niveau" },
        { key: "years_experience", label: "Années", render: (r) => (r.years_experience === null ? "—" : `${r.years_experience} an${r.years_experience > 1 ? "s" : ""}`) },
      ]}
      fields={[
        { name: "name", label: "Technologie", type: "text", required: true },
        { name: "category", label: "Catégorie", type: "select", options: TECH_CATEGORIES, required: true },
        { name: "level", label: "Niveau", type: "text" },
        { name: "years_experience", label: "Années d'expérience", type: "number" },
      ]}
    />
  );
}

export function CertificationsTab() {
  return (
    <ResourceTab<"certifications">
      entity="certifications"
      description="Certifications techniques, qualité et sécurité — une certification expirée n'est jamais utilisée automatiquement."
      labels={{ singular: "Certification", empty: "Aucune certification renseignée", addButton: "Ajouter une certification", nameOf: (r: Certification) => r.name }}
      columns={[
        { key: "name", label: "Certification", render: (r) => <span className="font-medium text-foreground">{r.name}</span> },
        { key: "issuer", label: "Organisme" },
        { key: "category", label: "Catégorie", render: (r) => labelOf(CERT_CATEGORIES, r.category) },
        { key: "expires_at", label: "Expire le", render: (r) => fmtDate(r.expires_at) },
        {
          key: "is_valid",
          label: "Statut",
          render: (r) => (r.is_valid ? <Badge variant="success">Valide</Badge> : <Badge variant="warning">Expirée</Badge>),
        },
      ]}
      fields={[
        { name: "name", label: "Certification", type: "text", required: true, placeholder: "ISO 14001" },
        { name: "issuer", label: "Organisme", type: "text" },
        { name: "category", label: "Catégorie", type: "select", options: CERT_CATEGORIES, required: true },
        { name: "issued_at", label: "Délivrée le", type: "date" },
        { name: "expires_at", label: "Expire le", type: "date" },
      ]}
    />
  );
}

export function ExpertsTab() {
  return (
    <ResourceTab<"experts">
      entity="experts"
      description="Profils mobilisables sur les candidatures : rôle, expérience, compétences."
      labels={{ singular: "Expert", empty: "Aucun expert renseigné", addButton: "Ajouter un expert", nameOf: (r: Expert) => r.full_name }}
      columns={[
        { key: "full_name", label: "Nom", render: (r) => <span className="font-medium text-foreground">{r.full_name}</span> },
        { key: "role", label: "Rôle" },
        { key: "years_experience", label: "Expérience", render: (r) => (r.years_experience === null ? "—" : `${r.years_experience} ans`) },
        { key: "skills", label: "Compétences" },
      ]}
      fields={[
        { name: "full_name", label: "Nom complet", type: "text", required: true },
        { name: "role", label: "Rôle", type: "text", placeholder: "Chef de projet, ingénieur…" },
        { name: "years_experience", label: "Années d'expérience", type: "number" },
        { name: "skills", label: "Compétences", type: "tags", help: "Séparées par des virgules" },
        { name: "bio", label: "Présentation", type: "textarea" },
      ]}
    />
  );
}

export function ProjectsTab() {
  return (
    <ResourceTab<"projects">
      entity="projects"
      description="Projets réalisés : clients, secteurs, dates, budgets, technologies et résultats."
      labels={{ singular: "Projet", empty: "Aucun projet renseigné", addButton: "Ajouter un projet", nameOf: (r: Project) => r.title }}
      columns={[
        { key: "title", label: "Projet", render: (r) => <span className="font-medium text-foreground">{r.title}</span> },
        { key: "client", label: "Client" },
        { key: "sector", label: "Secteur" },
        { key: "start_date", label: "Début", render: (r) => fmtDate(r.start_date) },
        { key: "budget", label: "Budget", render: (r) => fmtMoney(r.budget, r.currency) },
        { key: "is_reference", label: "Référence", render: (r) => (r.is_reference ? <Badge variant="success">Oui</Badge> : <span className="text-muted-foreground">—</span>) },
      ]}
      fields={[
        { name: "title", label: "Titre", type: "text", required: true, full: true },
        { name: "client", label: "Client", type: "text" },
        { name: "sector", label: "Secteur", type: "text" },
        { name: "country", label: "Pays (code ISO)", type: "text", placeholder: "MA" },
        { name: "currency", label: "Devise", type: "text", placeholder: "MAD" },
        { name: "start_date", label: "Début", type: "date" },
        { name: "end_date", label: "Fin", type: "date" },
        { name: "budget", label: "Budget", type: "number" },
        { name: "is_reference", label: "Utilisable comme référence", type: "checkbox" },
        { name: "technologies", label: "Technologies", type: "tags", help: "Séparées par des virgules" },
        { name: "description", label: "Description", type: "textarea" },
        { name: "results", label: "Résultats obtenus", type: "textarea" },
      ]}
    />
  );
}

export function ReferencesTab() {
  return (
    <ResourceTab<"references">
      entity="references"
      description="Références commerciales et contacts vérifiables."
      labels={{ singular: "Référence", empty: "Aucune référence renseignée", addButton: "Ajouter une référence", nameOf: (r: Reference) => r.client_name }}
      columns={[
        { key: "client_name", label: "Client", render: (r) => <span className="font-medium text-foreground">{r.client_name}</span> },
        { key: "sector", label: "Secteur" },
        { key: "contact_name", label: "Contact" },
        { key: "contact_email", label: "Email" },
      ]}
      fields={[
        { name: "client_name", label: "Client", type: "text", required: true },
        { name: "sector", label: "Secteur", type: "text" },
        { name: "contact_name", label: "Contact", type: "text" },
        { name: "contact_email", label: "Email du contact", type: "text" },
        { name: "description", label: "Description", type: "textarea" },
      ]}
    />
  );
}
