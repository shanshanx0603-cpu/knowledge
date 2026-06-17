import { NextRequest, NextResponse } from "next/server";
import { initDb, queryOne, execute } from "@/lib/db";
import { hashPassword, validAccount, validPassword, sanitizeUser } from "@/lib/auth";

export async function POST(request: NextRequest) {
  await initDb();
  const { account, password } = await request.json().catch(() => ({}));

  if (!validAccount(account)) {
    return NextResponse.json({ error: "用户名必须为 2-20 个中文字符" }, { status: 400 });
  }
  if (!validPassword(password)) {
    return NextResponse.json({ error: "密码必须为英文+数字组合，且至少 8 个字符" }, { status: 400 });
  }

  const exists = queryOne("SELECT id FROM users WHERE account = ?", [account]);
  if (exists) {
    return NextResponse.json({ error: "该用户名已存在" }, { status: 409 });
  }

  const now = new Date().toISOString().slice(0, 10);
  execute(
    "INSERT INTO users (name, account, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
    [account, account, hashPassword(password), "user", "active", now],
  );

  const user = queryOne("SELECT * FROM users WHERE account = ?", [account]);
  return NextResponse.json({ ok: true, user: sanitizeUser(user!) }, { status: 201 });
}

export const runtime = "nodejs";
