"use client";

import { useEffect, useState, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import NavSidebar from "@/components/NavSidebar";
import "./style.css";

interface Category {
  id: number;
  name: string;
  count?: number;
}

export default function CategoriesPage() {
  const [cats, setCats] = useState<Category[]>([]);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [msgOk, setMsgOk] = useState(false);
  const [loading, setLoading] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const res = await fetch("/api/categories");
    if (res.ok) {
      const data = await res.json();
      setCats(data.length > 0 ? data : [{ id: 0, name: "课程资料", count: 0 }, { id: -1, name: "学习资料", count: 0 }, { id: -2, name: "个人资料", count: 0 }]);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function addCategory(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const v = name.trim();
    if (!/^[\w一-鿿 ]{2,20}$/.test(v)) {
      setMessage("分类名称需为 2-20 个中文、英文、数字或空格"); setMsgOk(false); return;
    }
    setLoading(true); setMessage("");
    try {
      const url = editId ? `/api/categories/${editId}` : "/api/categories";
      const method = editId ? "PUT" : "POST";
      const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: v }) });
      const data = await res.json();
      if (!res.ok) { setMessage(data.error || "操作失败"); setMsgOk(false); return; }
      setName(""); setEditId(null);
      setMessage(editId ? "修改成功" : "添加成功"); setMsgOk(true);
      await load();
    } catch { setMessage("操作失败"); setMsgOk(false); }
    setLoading(false);
  }

  async function del(id: number) {
    await fetch(`/api/categories/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <Sidebar>
      <section className="cat-workspace">
        <NavSidebar activeType="categories" />
        <section className="cat-main">
          <div className="crumb">知识库中台&nbsp;&nbsp;/&nbsp;&nbsp;分类管理</div>
          <section className="panel">
            <div className="panel-head">
              <div><h2>分类管理</h2><p>上传文件时可选择文件所属分类，普通用户只统计自己上传的文件。</p></div>
              <form className="add-form" onSubmit={addCategory}>
                <input value={name} onChange={e => setName(e.target.value)} placeholder={editId ? "修改分类名称" : "输入新分类名称"} />
                <button type="submit" disabled={loading}>{loading ? "保存中" : editId ? "保存" : "添加"}</button>
                {editId && <button type="button" className="cancel-btn" onClick={() => { setEditId(null); setName(""); }}
                  style={{ height: 40, padding: "0 14px", border: "1px solid #ccc", borderRadius: 8, background: "#f5f5f5", cursor: "pointer", fontSize: 14 }}>取消</button>}
              </form>
            </div>
            <div className={`message${msgOk ? " success" : ""}`}>{message}</div>
            <div className="category-grid">
              {cats.map(item => (
                <article key={item.id} className="category-card">
                  <div className="category-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"/></svg>
                  </div>
                  <div className="category-name">{item.name}</div>
                  <div className="category-count"><strong>{Number(item.count || 0).toLocaleString("zh-CN")}</strong>个文件</div>
                  {item.id > 0 && (
                    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                      <button onClick={() => { setEditId(item.id); setName(item.name); }}
                        style={{ padding: "4px 12px", fontSize: 12, border: "1px solid #ddd", borderRadius: 6, background: "#fff", cursor: "pointer" }}>编辑</button>
                      <button onClick={() => del(item.id)}
                        style={{ padding: "4px 12px", fontSize: 12, border: "1px solid #ddd", borderRadius: 6, background: "#fff", color: "#e04444", cursor: "pointer" }}>删除</button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        </section>
      </section>
    </Sidebar>
  );
}
