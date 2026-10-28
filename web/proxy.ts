import { NextResponse, type NextRequest } from "next/server";

// Optimistic check only: no cookie means not signed in, so skip straight to
// the login page. Whether the session is valid, and what the user may do, is
// decided by the API on every request.
export function proxy(request: NextRequest) {
  const signedIn = request.cookies.has("gat_session");
  const onLogin = request.nextUrl.pathname === "/login";
  if (!signedIn && !onLogin) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
