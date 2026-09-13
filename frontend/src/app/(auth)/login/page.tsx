"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { LoginForm, type LoginValues } from "@/components/auth/LoginForm";
import { LogoFull } from "@/components/brand/Logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { useLogin } from "@/lib/queries/auth";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(values: LoginValues) {
    setError(null);
    try {
      await login.mutateAsync(values);
      router.replace("/dashboard");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Connexion impossible. Réessayez.");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-brand-black px-4">
      <div className="w-full max-w-sm space-y-6">
        <LogoFull className="justify-center" />
        <Card>
          <CardHeader>
            <CardTitle>Connexion</CardTitle>
            <CardDescription>Plateforme de gestion des appels d&apos;offres</CardDescription>
          </CardHeader>
          <CardContent>
            <LoginForm onSubmit={handleSubmit} error={error} />
          </CardContent>
        </Card>
        <p className="text-center text-xs text-white/50">Accès réservé — InnoSustain</p>
      </div>
    </main>
  );
}
