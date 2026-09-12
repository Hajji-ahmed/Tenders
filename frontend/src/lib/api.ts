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

/**
 * Appel à l'API FastAPI via le relais same-origin `/api/v1`.
 * - envoie le cookie de session
 * - lève ApiError({status, code, message}) sur toute réponse non 2xx
 * - redirige vers /login sur 401 (sauf si on y est déjà)
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
    // Rechargement complet volontaire : la session a expiré, on repart d'un état client vierge.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    location.href = "/login";
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.error?.code ?? "error", body?.error?.message ?? res.statusText);
  }

  return res.status === 204 ? (undefined as T) : res.json();
}
