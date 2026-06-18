"use client";

import Link from "next/link";
import "./sidebar.css";

interface Props {
  activeType?: string;
  children: React.ReactNode;
}

export default function Sidebar({ activeType, children }: Props) {
  return (
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
  );
}
