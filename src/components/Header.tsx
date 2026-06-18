"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import "./header.css";

interface Props {
  user: Record<string, unknown>;
}

export default function Header({ user }: Props) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  return (
    <header className="page-header">
      <a className="brand" href="/dashboard">
        <img className="brand-logo" src="/assets/logo.png" alt="数智云工" />
      </a>
      <h1 className="header-title"><span className="dot" />知识库中台<span className="dot" /></h1>
      <div className="user-menu-wrap">
        <button className="user-btn" onClick={() => setOpen(!open)}>
          <span className="avatar" />
          <span>{user.name as string}</span>
          <span className="chev" />
        </button>
        {open && (
          <div className="user-dropdown">
            <button onClick={() => { localStorage.removeItem("session"); router.replace("/profile"); }}>
              退出登录
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
