/**
 * 认证工具 — 密码哈希 + 校验
 */
import crypto from "node:crypto";

/** 登录 cookie 配置 */
export const SESSION_COOKIE = {
  name: "session",
  opts: { httpOnly: true, path: "/", maxAge: 86400 * 7 },
} as const;

export function hashPassword(password: string): string {
  return crypto.createHash("sha256").update(password).digest("hex");
}

export function validAccount(name: string): boolean {
  return /^[一-鿿]{2,20}$/.test(name) || /^[a-zA-Z0-9_-]{2,30}$/.test(name);
}

export function validPassword(pw: string): boolean {
  if (pw.length < 8) return false;
  return /[A-Za-z]/.test(pw) && /\d/.test(pw) && /^[A-Za-z\d]+$/.test(pw);
}

export function sanitizeUser(user: Record<string, unknown>) {
  const { password_hash, ...rest } = user;
  return rest;
}
