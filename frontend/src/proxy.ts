import { NextResponse, type NextRequest } from "next/server";

// Vérification optimiste : présence du cookie de session. La validité réelle du token est
// contrôlée par FastAPI à chaque appel API (401 ⇒ redirection côté client).
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
  matcher: ["/((?!api|_next|favicon.ico).*)"],
};
