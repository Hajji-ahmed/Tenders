"use client";

import { CircleCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { LoginForm, type LoginValues } from "@/components/auth/LoginForm";
import { LogoFull, LogoMark } from "@/components/brand/Logo";
import { ApiError } from "@/lib/api";
import { useLogin } from "@/lib/queries/auth";

const PILLARS = ["Veille multi-sources", "Qualification Go / No-Go", "Préparation des candidatures"];

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
      {/* Panneau de marque : vert encre + motif disque/arcs (classe .brand-hero de globals.css) */}
      <section
        data-surface="inverse"
        className="brand-hero hidden flex-col justify-between px-12 py-10 lg:flex"
      >
        <LogoFull width={340} priority />

        <div className="max-w-md space-y-5">
          <div aria-hidden className="h-1 w-12 rounded-full bg-brand-yellow" />
          <h1 className="text-3xl font-semibold leading-tight tracking-tight">
            Leading territories decarbonisation in Africa
          </h1>
          <p className="text-sm leading-relaxed text-white/85">
            Plateforme interne de veille et de réponse aux appels d&apos;offres : recherche, qualification,
            analyse documentaire et préparation des candidatures, avec validation humaine à chaque étape.
          </p>
          <ul className="space-y-2 text-sm text-white">
            {PILLARS.map((item) => (
              <li key={item} className="flex items-center gap-2.5">
                <CircleCheck className="size-4 shrink-0 text-brand-yellow" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-white/75">
          Innovative &amp; Sustainable Solutions · Rabat, Maroc · innosustain.africa
        </p>
      </section>

      {/* Panneau de connexion : filet jaune vertical 4 px contre le panneau vert ; filet haut sur mobile */}
      <section className="relative flex items-center justify-center bg-background px-6 py-12 lg:border-l-4 lg:border-brand-yellow">
        <span aria-hidden className="absolute inset-x-0 top-0 h-[3px] bg-brand-green lg:hidden" />

        <div className="w-full max-w-sm space-y-8">
          <div className="lg:hidden">
            <LogoFull width={260} priority />
          </div>
          <div className="flex items-center gap-3">
            <LogoMark size={40} className="hidden lg:block" />
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-brand-green-dark">Connexion</h2>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-blue-dark">Espace appels d&apos;offres</p>
            </div>
          </div>
          <LoginForm onSubmit={handleSubmit} error={error} />
          <p className="flex items-center gap-2.5 text-xs text-muted-foreground">
            <span aria-hidden className="brand-dot" />
            Accès réservé. Les documents et données de l&apos;entreprise sont protégés.
          </p>
        </div>
      </section>
    </main>
  );
}
