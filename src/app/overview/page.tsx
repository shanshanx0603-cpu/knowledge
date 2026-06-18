"use client";

import Sidebar from "@/components/Sidebar";
import NavSidebar from "@/components/NavSidebar";

export default function OverviewPage() {
  return (
    <Sidebar>
      <section className="workspace">
        <NavSidebar activeType="overview" />
        <section className="main">
          <div style={{ padding: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: "#333" }}>全部概览</h2>
            <p style={{ color: "#888", marginTop: 8 }}>概览统计区域 — 待接数据。</p>
          </div>
        </section>
      </section>
    </Sidebar>
  );
}
