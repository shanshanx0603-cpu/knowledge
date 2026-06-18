import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/profile", "/api/auth/login", "/api/auth/register", "/api/auth/logout"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 公开路径直接放行
  if (PUBLIC_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // 检查登录 cookie
  const session = request.cookies.get("session");
  if (!session?.value) {
    return NextResponse.redirect(new URL("/profile", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|assets|favicon).*)"],
};
