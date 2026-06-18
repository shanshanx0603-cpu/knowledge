"use client";

import AppLayout from "@/components/AppLayout";

export default function OverviewPage() {
  return (
    <AppLayout activeType="overview">
      <div style={{ padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>全部概览</h2>
        <p style={{ color: "#888", marginTop: 8 }}>概览统计区域 — 待接数据。</p>
      </div>
    </AppLayout>
  );
}
