"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const [user, setUser] = useState<Record<string, unknown> | null>(null);
  const router = useRouter();

  useEffect(() => {
    const raw = localStorage.getItem("session");
    if (!raw) { router.replace("/login"); return; }
    setUser(JSON.parse(raw));
  }, [router]);

  if (!user) return null;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="shrink-0 bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-800">Knowledge</h1>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span>{user.name as string}</span>
          <button onClick={() => { localStorage.removeItem("session"); router.replace("/login"); }}
            className="text-xs text-slate-400 hover:text-red-500 transition-colors">退出</button>
        </div>
      </header>
      <main className="flex-1 flex items-center justify-center">
        <p className="text-slate-400 text-lg">欢迎使用 Knowledge 知识库管理平台</p>
      </main>
    </div>
  );
}
