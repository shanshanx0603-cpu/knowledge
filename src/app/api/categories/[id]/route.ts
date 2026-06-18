import { NextRequest, NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/api-utils";
import { initDb, queryOne, execute, queryAll } from "@/lib/db";

export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  await initDb();
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const { id } = await params;
  const cat = queryOne("SELECT * FROM categories WHERE id = ? AND user_id = ?", [id, user.user_id]);
  if (!cat) return NextResponse.json({ error: "分类不存在" }, { status: 404 });

  const { name, description, sort_order } = await request.json().catch(() => ({}));
  const now = new Date().toISOString().slice(0, 19).replace("T", " ");

  if (name?.trim()) execute("UPDATE categories SET name = ?, updated_at = ? WHERE id = ?", [name.trim(), now, id]);
  if (description !== undefined) execute("UPDATE categories SET description = ?, updated_at = ? WHERE id = ?", [description, now, id]);
  if (sort_order !== undefined) execute("UPDATE categories SET sort_order = ?, updated_at = ? WHERE id = ?", [sort_order, now, id]);

  const updated = queryOne("SELECT * FROM categories WHERE id = ?", [id]);
  return NextResponse.json(updated);
}

export async function DELETE(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  await initDb();
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const { id } = await params;
  const cat = queryOne("SELECT * FROM categories WHERE id = ? AND user_id = ?", [id, user.user_id]);
  if (!cat) return NextResponse.json({ error: "分类不存在" }, { status: 404 });

  execute("DELETE FROM categories WHERE id = ?", [id]);
  const rows = queryAll("SELECT * FROM categories WHERE user_id = ? ORDER BY sort_order, id", [user.user_id]);
  return NextResponse.json(rows);
}

export const runtime = "nodejs";
