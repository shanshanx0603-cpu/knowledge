/**
 * 认证工具 — 密码哈希 + 校验
 */
import crypto from "node:crypto";

export function hashPassword(password: string): string {
  return crypto.createHash("sha256").update(password).digest("hex");
}

export function validAccount(name: string): boolean {
  return /^[一-鿿]{2,20}$/.test(name);
}

export function validPassword(pw: string): boolean {
  if (pw.length < 8) return false;
  return /[A-Za-z]/.test(pw) && /\d/.test(pw) && /^[A-Za-z\d]+$/.test(pw);
}

export function sanitizeUser(user: Record<string, unknown>) {
  const { password_hash, ...rest } = user;
  return rest;
}
