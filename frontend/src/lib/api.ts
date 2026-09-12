export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const FALLBACK_MESSAGES: Record<number, string> = {
  401: "Session expirée, veuillez vous reconnecter.",
  403: "Accès refusé.",
  404: "Ressource introuvable.",
  422: "Données invalides.",
  429: "Trop de tentatives, réessayez dans une minute.",
  502: "Le serveur est momentanément indisponible.",
  503: "Le serveur est momentanément indisponible.",
};

/** Construit l'erreur à partir du corps `{error: {code, message}}` — ou d'un corps inattendu (texte, HTML, vide). */
export function toApiError(status: number, body: unknown, statusText = ""): ApiError {
  const err = body && typeof body === "object" ? (body as { error?: unknown }).error : undefined;
  const code =
    err && typeof err === "object" && typeof (err as { code?: unknown }).code === "string"
      ? (err as { code: string }).code
      : status === 429
        ? "rate_limited"
        : "error";
  const message =
    typeof err === "string"
      ? err
      : err && typeof err === "object" && typeof (err as { message?: unknown }).message === "string"
        ? (err as { message: string }).message
        : FALLBACK_MESSAGES[status] ?? statusText ?? "";
  return new ApiError(status, code, message || `Erreur HTTP ${status}`);
}

/**
 * Appel à l'API FastAPI via le relais same-origin `/api/v1`.
 * - envoie le cookie de session
 * - lève ApiError({status, code, message}) sur toute réponse non 2xx
 * - sur 401 hors /login : purge la session côté serveur puis recharge sur /login
 */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const res = await fetch(`/api/v1${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(init.headers ?? {}),
    },
  });

  if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
    // Le cookie httpOnly ne peut pas être effacé en JS : on passe par /auth/logout, sinon le
    // proxy renverrait /login → /dashboard en boucle. Rechargement complet volontaire ensuite.
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => undefined);
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    location.href = "/login";
  }

  if (!res.ok) {
    const body = await res.json().catch(() => undefined);
    throw toApiError(res.status, body, res.statusText);
  }

  return res.status === 204 ? (undefined as T) : res.json();
}
