"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  Certification,
  CompanyProfile,
  Expert,
  Page,
  Project,
  Reference,
  Skill,
  Technology,
} from "@/lib/types";

/** Sous-ressources du profil exposées par /company/{name} (CRUD générique côté API). */
export type EntityName = "skills" | "technologies" | "certifications" | "experts" | "projects" | "references";

export type EntityMap = {
  skills: Skill;
  technologies: Technology;
  certifications: Certification;
  experts: Expert;
  projects: Project;
  references: Reference;
};

export const companyKeys = {
  profile: ["company", "profile"] as const,
  list: (name: EntityName) => ["company", name] as const,
};

export function useCompanyProfile() {
  return useQuery({ queryKey: companyKeys.profile, queryFn: () => api<CompanyProfile>("/company/profile") });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: Partial<CompanyProfile>) =>
      api<CompanyProfile>("/company/profile", { method: "PUT", body: JSON.stringify(values) }),
    onSuccess: (profile) => qc.setQueryData(companyKeys.profile, profile),
  });
}

/** Liste complète d'une sous-ressource (l'API plafonne à 100 par page ; largement suffisant pour un profil). */
export function useEntityList<N extends EntityName>(name: N) {
  return useQuery({
    queryKey: companyKeys.list(name),
    queryFn: () => api<Page<EntityMap[N]>>(`/company/${name}?page=1&size=100`),
  });
}

function useInvalidate(name: EntityName) {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: companyKeys.list(name) }),
      qc.invalidateQueries({ queryKey: companyKeys.profile }), // les compteurs du profil changent
    ]);
}

export function useCreateEntity<N extends EntityName>(name: N) {
  const invalidate = useInvalidate(name);
  return useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      api<EntityMap[N]>(`/company/${name}`, { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateEntity<N extends EntityName>(name: N) {
  const invalidate = useInvalidate(name);
  return useMutation({
    mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) =>
      api<EntityMap[N]>(`/company/${name}/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
    onSuccess: () => invalidate(),
  });
}

export function useDeleteEntity(name: EntityName) {
  const invalidate = useInvalidate(name);
  return useMutation({
    mutationFn: (id: string) => api<void>(`/company/${name}/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  });
}
