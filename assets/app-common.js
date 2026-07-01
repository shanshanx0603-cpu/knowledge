(function () {
  const adminNavItem = {
    key: "users",
    href: "profile.html",
    text: "用户管理",
    icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M16 11a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z" stroke="currentColor" stroke-width="2"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  };

  const profileNavItem = {
    key: "profile",
    href: "profile.html?view=profile",
    text: "个人信息",
    icon: '<svg viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="14" rx="2.5" stroke="currentColor" stroke-width="2"/><path d="M9 10.2a2.1 2.1 0 1 0 4.2 0 2.1 2.1 0 0 0-4.2 0Z" stroke="currentColor" stroke-width="1.8"/><path d="M7.6 16.2a4.5 4.5 0 0 1 7.8 0M16.5 9h1.2M16.5 12h1.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'
  };

  const navItems = [
    {
      key: "overview",
      href: "overview.html",
      text: "全部概览",
      icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z" stroke="currentColor" stroke-width="2"/></svg>'
    },
    {
      key: "categories",
      href: "categories.html",
      text: "分类管理",
      icon: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 6h7v7H4V6Zm9 0h7v7h-7V6ZM4 15h7v3H4v-3Zm9 0h7v3h-7v-3Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>'
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
      key: "chat",
      href: "chat.html",
      text: "知识库调试",
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
    localStorage.setItem("accountType", user.account_type || "user");
    syncCurrentUser(user.name);
    renderNav();
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
      return path;
    }
    return `${path}${separator}user=${encodeURIComponent(name)}&token=${encodeURIComponent(token)}`;
  }

  function clearCurrentUser() {
    localStorage.removeItem("currentUser");
    localStorage.removeItem("sessionToken");
    localStorage.removeItem("accountType");
    localStorage.removeItem("adminToken");
    syncCurrentUser("");
    renderNav();
  }

  function pageKey() {
    const path = location.pathname.split("/").pop() || "knowledge-dashboard.html";
    const params = new URLSearchParams(location.search);
    if (path === "profile.html") return params.get("view") === "profile" ? "profile" : "users";
    if (path === "overview.html") return "overview";
    if (path === "categories.html") return "categories";
    if (path === "chat.html") return "chat";
    if (path === "upload.html") return "upload";
    if (path === "detail.html") return params.get("type") || "documents";
    return "";
  }

  function renderNav() {
    const isAdmin = localStorage.getItem("accountType") === "admin" || getCurrentUser().name === "中台管理员";
    const active = pageKey() === "users" && !isAdmin ? "profile" : pageKey();
    const visibleNavItems = isAdmin ? [adminNavItem, ...navItems, profileNavItem] : [...navItems, profileNavItem];
    document.querySelectorAll(".side .nav").forEach((nav) => {
      nav.innerHTML = visibleNavItems.map((item) => (
        `<a class="${item.key === active ? "active" : ""}" href="${item.href}" data-nav-key="${item.key}">${item.icon}${item.text}</a>`
      )).join("");
    });

    document.querySelectorAll(".side .upload").forEach((upload) => {
      if (localStorage.getItem("accountType") === "admin" || getCurrentUser().name === "中台管理员") {
        upload.style.display = "none";
        return;
      }
      upload.style.display = "";
      upload.classList.toggle("active", active === "upload");
      upload.innerHTML = `${uploadIcon}上传文件`;
    });
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

  function ensureUserPopover() {
    let popover = document.getElementById("userPopover");
    if (popover) return popover;
    popover = document.createElement("section");
    popover.id = "userPopover";
    popover.className = "user-popover";
    popover.innerHTML = `
      <div data-popover-view="login">
        <h3>账号登录</h3>
        <form id="quickLoginForm">
          <label>账号<input id="quickLoginAccount" name="account" autocomplete="username" /></label>
          <label>密码<input id="quickLoginPassword" name="password" type="password" autocomplete="current-password" /></label>
          <div class="popover-actions">
            <button class="primary" id="quickLoginButton" type="submit">登录</button>
            <button class="secondary" type="button" data-close-popover>取消</button>
          </div>
          <div class="message" id="quickLoginMessage"></div>
        </form>
      </div>
      <div data-popover-view="profile" hidden>
        <h3>个人信息</h3>
        <div class="profile-card">
          <div class="profile-row"><span>用户名</span><strong id="quickProfileName">-</strong></div>
          <div class="profile-row"><span>账号类型</span><strong id="quickProfileType">-</strong></div>
          <div class="profile-row"><span>权限范围</span><strong id="quickProfileScope">-</strong></div>
        </div>
        <div class="popover-actions">
          <a class="profile-link" href="profile.html?view=profile">个人信息</a>
          <button class="danger" id="quickLogoutButton" type="button">退出登录</button>
        </div>
        <div class="message" id="quickProfileMessage"></div>
      </div>
    `;
    document.body.appendChild(popover);

    popover.querySelector("[data-close-popover]").addEventListener("click", closeUserPopover);
    popover.querySelector("#quickLogoutButton").addEventListener("click", () => {
      clearCurrentUser();
      renderUserPopover();
      openUserPopover("login");
    });
    popover.querySelector("#quickLoginForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const account = popover.querySelector("#quickLoginAccount").value.trim();
      const password = popover.querySelector("#quickLoginPassword").value;
      const button = popover.querySelector("#quickLoginButton");
      const message = popover.querySelector("#quickLoginMessage");
      message.className = "message";
      message.textContent = "";
      try {
        setButtonLoading(button, true, "登录中");
        const response = await fetch(KnowledgeApp.apiUrl("/api/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account, password })
        });
        const data = await response.json();
        if (!response.ok) {
          message.textContent = data.error || "登录失败";
          return;
        }
        setCurrentUser(data.user);
        renderNav();
        message.className = "message success";
        message.textContent = "登录成功";
        renderUserPopover(data.user);
        setTimeout(() => openUserPopover("profile"), 250);
      } catch (error) {
        message.textContent = "登录接口暂时不可用";
        console.warn("Quick login failed", error);
      } finally {
        setButtonLoading(button, false);
      }
    });
    return popover;
  }

  async function renderUserPopover(userData) {
    const popover = ensureUserPopover();
    const user = userData || null;
    const current = getCurrentUser();
    if (!user && (!current.name || !current.token)) {
      popover.querySelector('[data-popover-view="login"]').hidden = false;
      popover.querySelector('[data-popover-view="profile"]').hidden = true;
      return;
    }
    let profile = user;
    if (!profile) {
      try {
        const response = await fetch(apiUrl("/api/profile"));
        const data = await response.json();
        if (response.ok && data.user) profile = data.user;
      } catch (error) {
        console.warn("Quick profile unavailable", error);
      }
    }
    if (!profile) {
      clearCurrentUser();
      popover.querySelector('[data-popover-view="login"]').hidden = false;
      popover.querySelector('[data-popover-view="profile"]').hidden = true;
      return;
    }
    popover.querySelector('[data-popover-view="login"]').hidden = true;
    popover.querySelector('[data-popover-view="profile"]').hidden = false;
    popover.querySelector("#quickProfileName").textContent = profile.name || profile.login_account || "-";
    popover.querySelector("#quickProfileType").textContent = profile.account_type === "admin" ? "管理员" : "普通用户";
    popover.querySelector("#quickProfileScope").textContent = profile.permission_scope || (profile.account_type === "admin" ? "全部知识库" : "仅本人上传");
    const profileLink = popover.querySelector(".profile-link");
    if (profileLink) {
      profileLink.textContent = profile.account_type === "admin" ? "用户管理" : "个人信息";
      profileLink.href = profile.account_type === "admin" ? "profile.html" : "profile.html?view=profile";
    }
  }

  function closeUserPopover() {
    const popover = document.getElementById("userPopover");
    if (popover) popover.classList.remove("open");
  }

  async function openUserPopover(view) {
    const popover = ensureUserPopover();
    await renderUserPopover();
    if (view === "login") {
      popover.querySelector('[data-popover-view="login"]').hidden = false;
      popover.querySelector('[data-popover-view="profile"]').hidden = true;
    }
    popover.classList.add("open");
  }

  function bindUserEntrypoint() {
    document.querySelectorAll("a.user").forEach((node) => {
      if (node.dataset.userPopoverBound) return;
      node.dataset.userPopoverBound = "1";
      node.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openUserPopover();
      });
    });
    document.addEventListener("click", (event) => {
      const popover = document.getElementById("userPopover");
      if (!popover || !popover.classList.contains("open")) return;
      if (popover.contains(event.target) || event.target.closest("a.user")) return;
      closeUserPopover();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeUserPopover();
    });
  }

  const appApi = {
    apiUrl,
    getCurrentUser,
    setCurrentUser,
    clearCurrentUser,
    syncCurrentUser,
    openUserPopover,
    closeUserPopover,
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
      bindUserEntrypoint();
    });
  } else {
    renderNav();
    syncCurrentUser();
    bindUserEntrypoint();
  }
})();
