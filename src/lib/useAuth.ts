"use client";

import { useEffect, useState } from "react";

export function useAuth() {
  const [user, setUser] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem("session");
    if (raw) setUser(JSON.parse(raw));
  }, []);

  return user;
}
