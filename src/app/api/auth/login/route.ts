import { NextRequest, NextResponse } from "next/server";
import { initDb, queryOne } from "@/lib/db";
import { hashPassword, sanitizeUser } from "@/lib/auth";

export async function POST(request: NextRequest) {
  await initDb();
  const { account, password } = await request.json().catch(() => ({}));
  if (!account || !password) {
    return NextResponse.json({ error: "请输入账号和密码" }, { status: 400 });
  }

  const user = queryOne("SELECT * FROM users WHERE account = ? AND status = 'active'", [account]);
  if (!user || user.password_hash !== hashPassword(password)) {
    return NextResponse.json({ error: "账号或密码错误" }, { status: 401 });
  }

  const now = new Date().toISOString().slice(0, 10);
  const { execute } = await import("@/lib/db");
  execute("UPDATE users SET last_login = ? WHERE id = ?", [now, user.id]);

  return NextResponse.json({ ok: true, user: sanitizeUser(user) });
}

export const runtime = "nodejs";
