import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Knowledge 知识库",
  description: "文档管理与 RAG 预处理平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="h-screen bg-slate-50">{children}</body>
    </html>
  );
}
