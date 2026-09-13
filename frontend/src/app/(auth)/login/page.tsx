"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { LoginForm, type LoginValues } from "@/components/auth/LoginForm";
import { LogoFull, LogoMark } from "@/components/brand/Logo";
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
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* Panneau de marque — fond sombre comme le logo, accent jaune discret */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-brand-black px-12 py-10 text-white lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-40 -top-40 size-[520px] rounded-full border-[56px] border-brand-green/15"
        />
        <div aria-hidden className="pointer-events-none absolute -bottom-24 -left-24 size-72 rounded-full bg-brand-yellow/10" />

        <LogoFull width={340} priority className="relative" />

        <div className="relative max-w-md space-y-5">
          <div className="h-1 w-12 rounded-full bg-brand-yellow" />
          <h1 className="text-3xl font-semibold leading-tight tracking-tight">
            Leading territories decarbonisation in Africa
          </h1>
          <p className="text-sm leading-relaxed text-white/70">
            Plateforme interne de veille et de réponse aux appels d&apos;offres : recherche, qualification,
            analyse documentaire et préparation des candidatures, avec validation humaine à chaque étape.
          </p>
        </div>

        <p className="relative text-xs text-white/40">
          Innovative &amp; Sustainable Solutions · Rabat, Maroc · innosustain.africa
        </p>
      </section>

      {/* Panneau de connexion */}
      <section className="flex items-center justify-center bg-background px-6 py-12">
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-4 lg:hidden">
            <LogoFull width={260} priority />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <LogoMark size={40} className="hidden lg:block" />
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">Connexion</h2>
                <p className="text-sm text-muted-foreground">Espace appels d&apos;offres InnoSustain</p>
              </div>
            </div>
          </div>
          <LoginForm onSubmit={handleSubmit} error={error} />
          <p className="text-xs text-muted-foreground">
            Accès réservé. Les documents et données de l&apos;entreprise sont protégés.
          </p>
        </div>
      </section>
    </main>
  );
}
