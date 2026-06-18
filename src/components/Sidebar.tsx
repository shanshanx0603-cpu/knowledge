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

      {children}
    </main>
  );
}
