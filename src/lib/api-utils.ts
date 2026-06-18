/**
 * API 工具 — 从 cookie 获取当前用户
 */
import { cookies } from "next/headers";
import { queryOne } from "@/lib/db";

export async function getCurrentUser() {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get("session")?.value;
  if (!sessionId) return null;
  return queryOne("SELECT * FROM users WHERE id = ?", [sessionId]) ?? null;
}
