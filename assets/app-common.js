(function () {
  const navItems = [
    {
      key: "overview",
      href: "overview.html",
      text: "全部概览",
      icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z" stroke="currentColor" stroke-width="2"/></svg>'
    },
    {
      key: "documents",
      href: "detail.html?type=documents",
      text: "文档知识库",
      icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M6 3h9l3 3v15H6V3Z" fill="currentColor"/><path d="M9 11h6M9 15h5" stroke="white" stroke-width="1.8" stroke-linecap="round"/></svg>'
    },
    {
      key: "videos",
      href: "detail.html?type=videos",
      text: "视频知识库",
      icon: '<svg viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="14" rx="2" stroke="currentColor" stroke-width="2"/><path d="m10 9 5 3-5 3V9Z" fill="currentColor"/></svg>'
    },
    {
      key: "images",
      href: "detail.html?type=images",
      text: "图片知识库",
      icon: '<svg viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="14" rx="2" stroke="currentColor" stroke-width="2"/><path d="m7 17 4-5 3 3.5 2-2.5 2 4H7Z" fill="currentColor"/></svg>'
    },
    {
      key: "categories",
      href: "categories.html",
      text: "分类管理",
      icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 6h7v7H4V6Zm9 0h7v7h-7V6ZM4 15h7v3H4v-3Zm9 0h7v3h-7v-3Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>'
    },
    {
      key: "chat",
      href: "chat.html",
      text: "AI 对话",
      icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 5.8A3.8 3.8 0 0 1 8.8 2h6.4A3.8 3.8 0 0 1 19 5.8v5.4a3.8 3.8 0 0 1-3.8 3.8H11l-4.6 4v-4.2A3.8 3.8 0 0 1 5 11.2V5.8Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M9 8h6M9 11h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
    }
  ];

  const uploadIcon = '<svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m0 0 5 5m-5-5-5 5M5 16v4h14v-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function getCurrentUser() {
    const name = localStorage.getItem("currentUser") || "";
    const token = localStorage.getItem("sessionToken") || "";
    return name && token ? { name, token } : { name: "", token: "" };
  }

  function setCurrentUser(user) {
    if (!user || !user.name || !user.sessionToken) return;
    localStorage.setItem("currentUser", user.name);
    localStorage.setItem("sessionToken", user.sessionToken);
    syncCurrentUser(user.name);
  }

  function syncCurrentUser(name) {
    const current = name || getCurrentUser().name || "登录";
    document.querySelectorAll("#currentUserName").forEach((node) => {
      node.textContent = current;
    });
  }

  function apiUrl(path) {
    const separator = path.includes("?") ? "&" : "?";
    const { name, token } = getCurrentUser();
    if (!name || !token) {
      location.href = "profile.html";
      return path;
    }
    return `${path}${separator}user=${encodeURIComponent(name)}&token=${encodeURIComponent(token)}`;
  }

  function pageKey() {
    const path = location.pathname.split("/").pop() || "knowledge-dashboard.html";
    const params = new URLSearchParams(location.search);
    if (path === "overview.html") return "overview";
    if (path === "categories.html") return "categories";
    if (path === "chat.html") return "chat";
    if (path === "upload.html") return "upload";
    if (path === "detail.html") return params.get("type") || "documents";
    return "";
  }

  function renderNav() {
    const nav = document.querySelector(".side .nav");
    if (!nav) return;
    const active = pageKey();
    nav.innerHTML = navItems.map((item) => (
      `<a class="${item.key === active ? "active" : ""}" href="${item.href}" data-nav-key="${item.key}">${item.icon}${item.text}</a>`
    )).join("");

    const upload = document.querySelector(".side .upload");
    if (upload) {
      upload.classList.toggle("active", active === "upload");
      upload.innerHTML = `${uploadIcon}上传文件`;
    }
  }

  function setButtonLoading(button, loading, text) {
    if (!button) return;
    if (loading) {
      button.dataset.originalText = button.textContent;
      if (text) button.textContent = text;
      button.disabled = true;
      button.classList.add("is-loading");
      return;
    }
    button.disabled = false;
    button.classList.remove("is-loading");
    if (button.dataset.originalText) {
      button.textContent = button.dataset.originalText;
      delete button.dataset.originalText;
    }
  }

  function showInlineMessage(node, text, type) {
    if (!node) return;
    node.className = type === "success" ? "message success" : "message";
    node.textContent = text || "";
  }

  const appApi = {
    apiUrl,
    getCurrentUser,
    setCurrentUser,
    syncCurrentUser,
    renderNav,
    setButtonLoading,
    showInlineMessage
  };
  window.KnowledgeApp = appApi;
  globalThis.KnowledgeApp = appApi;
  if (typeof self !== "undefined") self.KnowledgeApp = appApi;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      renderNav();
      syncCurrentUser();
    });
  } else {
    renderNav();
    syncCurrentUser();
  }
})();
