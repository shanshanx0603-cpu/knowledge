"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import AppLayout from "@/components/AppLayout";

function DetailContent() {
  const params = useSearchParams();
  const type = params.get("type") || "documents";

  return (
    <AppLayout activeType={type}>
      <div style={{ padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>
          {type === "documents" ? "文档知识库" : type === "videos" ? "视频知识库" : "图片知识库"}
        </h2>
        <p style={{ color: "#888", marginTop: 8 }}>文件列表区域 — 待接数据。</p>
      </div>
    </AppLayout>
  );
}

export default function DetailPage() {
  return <Suspense fallback={null}><DetailContent /></Suspense>;
}
