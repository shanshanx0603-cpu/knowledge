"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import "./style.css";

export default function ProfilePage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [msgType, setMsgType] = useState<"error" | "success" | "">("");
  const router = useRouter();

  useEffect(() => {
    const session = localStorage.getItem("session");
    if (session) router.replace("/dashboard");
  }, [router]);

  function validChinese(v: string) { return /^[一-鿿]{2,20}$/.test(v); }
  function validPw(v: string) { return /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/.test(v); }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(""); setMsgType("");
    const a = account.trim();
    if (mode === "register") {
      if (!validChinese(a)) { setMessage("用户名必须为 2-20 个中文字符"); setMsgType("error"); return; }
      if (!validPw(password)) { setMessage("密码必须为英文+数字组合，且至少 8 个字符"); setMsgType("error"); return; }
      if (password !== confirm) { setMessage("两次输入的密码不一致"); setMsgType("error"); return; }
    }
    try {
      const res = await fetch(mode === "register" ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account: a, password }),
      });
      const data = await res.json();
      if (!res.ok) { setMessage(data.error || "登录失败"); setMsgType("error"); return; }
      localStorage.setItem("session", JSON.stringify(data.user));
      setMessage(mode === "register" ? "注册成功" : "登录成功");
      setMsgType("success");
      setTimeout(() => router.replace("/dashboard"), 600);
    } catch {
      setMessage("接口暂时不可用"); setMsgType("error");
    }
  }

  return (
    <main className="login-shell">
      <div className="brand">
        <img className="brand-logo" src="/assets/logo.png" alt="数智云工" />
      </div>
      <h1>登录管理</h1>
      <p className="sub">请输入账号密码进入知识库中台。管理员可查看全部内容，普通用户仅查看自己上传的文件。</p>
      <div className="mode-tabs" role="tablist">
        <button className={`mode-tab${mode === "login" ? " active" : ""}`} onClick={() => setMode("login")}>登录</button>
        <button className={`mode-tab${mode === "register" ? " active" : ""}`} onClick={() => setMode("register")}>注册</button>
      </div>
      <form onSubmit={handleSubmit}>
        <label>用户名<input value={account} onChange={e => setAccount(e.target.value)} placeholder={mode === "register" ? "请输入中文用户名" : "请输入用户名"} required /></label>
        <label>密码<input value={password} onChange={e => setPassword(e.target.value)} type="password" placeholder={mode === "register" ? "请输入英文+数字密码" : "请输入密码"} required /></label>
        {mode === "register" && (
          <>
            <label>确认密码<input value={confirm} onChange={e => setConfirm(e.target.value)} type="password" placeholder="请再次输入密码" required /></label>
            <div className="hint">注册用户名必须为中文；密码必须为英文+数字组合，且至少 8 个字符。</div>
          </>
        )}
        <div className={`message${msgType === "success" ? " success" : ""}`}>{message}</div>
        <button className="login-btn" type="submit">{mode === "register" ? "注册并登录" : "登录"}</button>
      </form>
      <div className="meta">当前已配置账号：管理员 admin；用户可自行注册中文用户名账号。</div>
    </main>
  );
}
