"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/useAuth";
import "./sidebar.css";

interface Props {
  activeType?: string;
  children: React.ReactNode;
}

export default function Sidebar({ activeType, children }: Props) {
  const user = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const router = useRouter();

  if (!user) return null;

  return (
    <main className="page">
      <header>
        <Link className="brand" href="/dashboard">
          <img className="brand-logo" src="/assets/logo.png" alt="数智云工" />
        </Link>
        <h1 className="title"><span>知识库中台</span></h1>
        <div style={{ justifySelf: "end", position: "relative", zIndex: 10 }}>
          <a className="user" onClick={() => setMenuOpen(!menuOpen)} style={{ cursor: "pointer" }}>
            <span className="avatar" />
            <span>{user.name as string}</span>
            <span className="chev" />
          </a>
          {menuOpen && (
            <div className="user-dropdown" style={{ position: "absolute", top: "110%", right: 0, minWidth: 120, background: "#fff", border: "1px solid rgba(49,96,166,0.12)", borderRadius: 10, boxShadow: "0 12px 30px rgba(44,85,147,0.14)", padding: 4, overflow: "hidden" }}>
              <button onClick={() => { fetch("/api/auth/logout", { method: "POST" }).finally(() => { localStorage.removeItem("session"); router.replace("/profile"); }); }} style={{ width: "100%", padding: "8px 12px", border: 0, borderRadius: 7, background: "transparent", color: "#4d5d78", fontSize: 12, fontWeight: 700, textAlign: "left", cursor: "pointer" }}
                onMouseEnter={e => { e.currentTarget.style.background = "#f4f7fc"; e.currentTarget.style.color = "#e04444"; }}
                onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#4d5d78"; }}>
                退出登录
              </button>
            </div>
          )}
        </div>
      </header>

      <section className="workspace">
        <aside className="side">
          <nav className="nav">
            <Link href="/overview" className={activeType === "overview" ? "active" : ""}>
              <svg viewBox="0 0 24 24" fill="none"><path d="M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z" stroke="currentColor" strokeWidth="2"/></svg>
              全部概览
            </Link>
            <Link href="/detail?type=documents" className={activeType === "documents" ? "active" : ""}>
              <svg viewBox="0 0 24 24" fill="none"><path d="M6 3h9l3 3v15H6V3Z" fill="currentColor"/><path d="M9 11h6M9 15h5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/></svg>
              文档知识库
            </Link>
            <Link href="/detail?type=videos" className={activeType === "videos" ? "active" : ""}>
              <svg viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="2"/><path d="m10 9 5 3-5 3V9Z" fill="currentColor"/></svg>
              视频知识库
            </Link>
            <Link href="/detail?type=images" className={activeType === "images" ? "active" : ""}>
              <svg viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="2"/><path d="m7 17 4-5 3 3.5 2-2.5 2 4H7Z" fill="currentColor"/></svg>
              图片知识库
            </Link>
            <Link href="/categories" className={activeType === "categories" ? "active" : ""}>
              <svg viewBox="0 0 24 24" fill="none"><path d="M4 6h7v7H4V6Zm9 0h7v7h-7V6ZM4 15h7v3H4v-3Zm9 0h7v3h-7v-3Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/></svg>
              分类管理
            </Link>
          </nav>
          <Link className="upload" href="/upload">
            <svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m0 0 5 5m-5-5-5 5M5 16v4h14v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            上传文件
          </Link>
        </aside>
        <section className="main">{children}</section>
      </section>
    </main>
  );
}
