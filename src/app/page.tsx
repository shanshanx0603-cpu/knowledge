"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const raw = localStorage.getItem("session");
    router.replace(raw ? "/dashboard" : "/profile");
  }, [router]);
  return null;
}
