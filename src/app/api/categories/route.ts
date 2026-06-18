import { NextRequest, NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/api-utils";
import { initDb, queryAll, execute } from "@/lib/db";

export async function GET() {
  await initDb();
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const rows = queryAll(
    "SELECT * FROM categories WHERE user_id = ? ORDER BY sort_order, id",
    [user.user_id],
  );
  return NextResponse.json(rows);
}

export async function POST(request: NextRequest) {
  await initDb();
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const { name, description } = await request.json().catch(() => ({}));
  if (!name?.trim()) return NextResponse.json({ error: "分类名不能为空" }, { status: 400 });

  const exists = queryAll("SELECT id FROM categories WHERE user_id = ? AND name = ?", [user.user_id, name.trim()]);
  if (exists.length > 0) return NextResponse.json({ error: "该分类已存在" }, { status: 409 });

  const now = new Date().toISOString().slice(0, 19).replace("T", " ");
  const maxOrder = queryAll("SELECT COALESCE(MAX(sort_order),0)+1 as n FROM categories WHERE user_id = ?", [user.user_id]);
  const sortOrder = (maxOrder[0] as any)?.n ?? 1;

  execute(
    "INSERT INTO categories (user_id, name, description, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
    [user.user_id, name.trim(), description || "", sortOrder, now, now],
  );
  const rows = queryAll("SELECT * FROM categories WHERE user_id = ? ORDER BY sort_order, id", [user.user_id]);
  return NextResponse.json(rows, { status: 201 });
}

export const runtime = "nodejs";
