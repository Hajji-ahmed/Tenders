"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export const authKeys = { me: ["auth", "me"] as const };

export function useMe() {
  return useQuery({ queryKey: authKeys.me, queryFn: () => api<User>("/auth/me") });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: { email: string; password: string }) =>
      api<User>("/auth/login", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: (user) => qc.setQueryData(authKeys.me, user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSuccess: () => qc.clear(),
  });
}
