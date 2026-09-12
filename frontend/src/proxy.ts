import { NextResponse, type NextRequest } from "next/server";

// Vérification optimiste : présence du cookie de session. La validité réelle du token est
// contrôlée par FastAPI à chaque appel API ; un 401 efface le cookie côté serveur, ce qui
// évite toute boucle /login ⇄ /dashboard.
export function proxy(req: NextRequest) {
  const hasToken = req.cookies.has("access_token");
  const { pathname } = req.nextUrl;
  const isLogin = pathname.startsWith("/login");

  if (!hasToken && !isLogin) return NextResponse.redirect(new URL("/login", req.url));
  if (hasToken && isLogin) return NextResponse.redirect(new URL("/dashboard", req.url));
  if (pathname === "/") return NextResponse.redirect(new URL("/dashboard", req.url));
  return NextResponse.next();
}

export const config = {
  // Exclut l'API, les internals Next et les fichiers statiques (images, polices…) de public/.
  matcher: ["/((?!api|_next|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff2?|txt|xml)$).*)"],
};
