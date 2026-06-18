"use client";

import Sidebar from "@/components/Sidebar";

export default function OverviewPage() {
  return (
    <Sidebar activeType="overview">
      <div style={{ padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>全部概览</h2>
        <p style={{ color: "#888", marginTop: 8 }}>概览统计区域 — 待接数据。</p>
      </div>
    </Sidebar>
  );
}
