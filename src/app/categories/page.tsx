"use client";

import { useEffect, useState, useCallback } from "react";
import Sidebar from "@/components/Sidebar";

interface Category {
  id: number;
  name: string;
  description: string;
  sort_order: number;
  created_at: string;
}

export default function CategoriesPage() {
  const [cats, setCats] = useState<Category[]>([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [editId, setEditId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    const res = await fetch("/api/categories");
    if (res.ok) setCats(await res.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("分类名不能为空"); return; }
    setError("");
    setLoading(true);
    try {
      if (editId) {
        await fetch(`/api/categories/${editId}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim(), description: desc }),
        });
      } else {
        const res = await fetch("/api/categories", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim(), description: desc }),
        });
        if (!res.ok) { const d = await res.json(); setError(d.error); return; }
      }
      setName(""); setDesc(""); setEditId(null);
      await load();
    } catch { setError("操作失败"); }
    setLoading(false);
  }

  async function handleDelete(id: number) {
    await fetch(`/api/categories/${id}`, { method: "DELETE" });
    await load();
  }

  function edit(c: Category) {
    setEditId(c.id); setName(c.name); setDesc(c.description || "");
  }

  return (
    <Sidebar activeType="categories">
      <div style={{ padding: 24, maxWidth: 600 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#333", marginBottom: 16 }}>分类管理</h2>

        <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          <input value={name} onChange={e => setName(e.target.value)}
            placeholder="分类名称" style={{ flex: 1, padding: "8px 12px", border: "1px solid #ddd", borderRadius: 6, fontSize: 14 }} />
          <input value={desc} onChange={e => setDesc(e.target.value)}
            placeholder="描述（可选）" style={{ flex: 2, padding: "8px 12px", border: "1px solid #ddd", borderRadius: 6, fontSize: 14 }} />
          <button type="submit" disabled={loading}
            style={{ padding: "8px 16px", background: "#1378ff", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer" }}>
            {editId ? "保存" : "添加"}
          </button>
          {editId && <button type="button" onClick={() => { setEditId(null); setName(""); setDesc(""); }}
            style={{ padding: "8px 12px", background: "#eee", border: "none", borderRadius: 6, cursor: "pointer" }}>取消</button>}
        </form>
        {error && <p style={{ color: "red", fontSize: 13, marginBottom: 12 }}>{error}</p>}

        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #eee", textAlign: "left" }}>
              <th style={{ padding: "8px 12px", fontSize: 13, color: "#666" }}>分类名</th>
              <th style={{ padding: "8px 12px", fontSize: 13, color: "#666" }}>描述</th>
              <th style={{ padding: "8px 12px", fontSize: 13, color: "#666" }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {cats.length === 0 ? (
              <tr><td colSpan={3} style={{ padding: 20, textAlign: "center", color: "#999" }}>暂无分类</td></tr>
            ) : cats.map(c => (
              <tr key={c.id} style={{ borderBottom: "1px solid #f5f5f5" }}>
                <td style={{ padding: "8px 12px", fontSize: 14 }}>{c.name}</td>
                <td style={{ padding: "8px 12px", fontSize: 13, color: "#888" }}>{c.description || "—"}</td>
                <td style={{ padding: "8px 12px", display: "flex", gap: 8 }}>
                  <button onClick={() => edit(c)} style={{ padding: "4px 10px", fontSize: 12, border: "1px solid #ddd", borderRadius: 4, background: "#fff", cursor: "pointer" }}>编辑</button>
                  <button onClick={() => handleDelete(c.id)} style={{ padding: "4px 10px", fontSize: 12, border: "1px solid #ddd", borderRadius: 4, background: "#fff", color: "#e04444", cursor: "pointer" }}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Sidebar>
  );
}
