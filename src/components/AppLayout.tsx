"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "./Header";
import Sidebar from "./Sidebar";

interface Props {
  activeType?: string;
  children: React.ReactNode;
}

export default function AppLayout({ activeType, children }: Props) {
  const [user, setUser] = useState<Record<string, unknown> | null>(null);
  const router = useRouter();

  useEffect(() => {
    const raw = localStorage.getItem("session");
    if (!raw) { router.replace("/profile"); return; }
    setUser(JSON.parse(raw));
  }, [router]);

  if (!user) return null;

  return (
    <main className="page">
      <Header user={user} />
      <Sidebar activeType={activeType}>{children}</Sidebar>
    </main>
  );
}
