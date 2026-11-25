const $ = (sel, root = document) => root.querySelector(sel);

const state = {
  token: localStorage.getItem("pr_token") || "",
  user: null,
  view: "login",
  kbs: [],
  currentKb: null,
  docs: [],
  conversations: [],
  activeConversationId: null,
  pollTimers: new Map(),
};

const app = $("#app");
const topnav = $("#topnav");
const userbox = $("#userbox");
const username = $("#username");
const toastEl = $("#toast");

function toast(message, kind = "") {
  toastEl.textContent = message;
  toastEl.className = "toast " + kind;
  toastEl.hidden = false;
  setTimeout(() => { toastEl.hidden = true; }, 3000);
}

async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const opts = Object.assign({}, options, { headers });
  const resp = await fetch(path, opts);
  if (resp.status === 401) {
    logout();
    throw new Error("登录已过期，请重新登录");
  }
  if (!resp.ok) {
    let detail = "请求失败（" + resp.status + "）";
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch (e) { /* ignore */ }
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function logout() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("pr_token");
  state.view = "login";
  state.kbs = [];
  state.docs = [];
  state.activeConversationId = null;
  clearPolling();
  render();
}

function clearPolling() {
  state.pollTimers.forEach((timer) => clearInterval(timer));
  state.pollTimers.clear();
}

function setView(view) {
  state.view = view;
  if (view === "chat") loadChat();
  if (view === "kb-list") loadKbList();
  if (view === "kb-detail" && state.currentKb) loadKbDetail(state.currentKb.id);
  render();
}

function render() {
  topnav.hidden = !state.user;
  userbox.hidden = !state.user;
  if (state.user) username.textContent = state.user.email;

  Array.from(topnav.querySelectorAll("button")).forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === state.view);
  });

  if (!state.user) return renderLogin();
  if (state.view === "kb-list") return renderKbList();
  if (state.view === "kb-detail") return renderKbDetail();
  if (state.view === "chat") return renderChat();
}

/* ---------- 登录页 ---------- */
function renderLogin() {
  app.innerHTML = `
    <div class="card" style="max-width:420px;margin:32px auto;">
      <h1>登录 PolicyRAG</h1>
      <p class="sub">企业制度文档权限感知问答系统</p>
      <form id="login-form">
        <label for="login-email">邮箱</label>
        <input id="login-email" type="email" autocomplete="username" required />
        <label for="login-password">密码</label>
        <input id="login-password" type="password" autocomplete="current-password" required />
        <div style="height:6px"></div>
        <button class="primary" type="submit" style="width:100%">登录</button>
      </form>
    </div>`;
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = $("#login-email").value.trim();
    const password = $("#login-password").value;
    try {
      const data = await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      state.token = data.access_token;
      localStorage.setItem("pr_token", state.token);
      await loadMe();
      setView("kb-list");
    } catch (err) {
      toast(err.message, "error");
    }
  });
}

async function loadMe() {
  const user = await api("/auth/me");
  state.user = user;
}

/* ---------- 知识库列表 ---------- */
async function loadKbList() {
  app.innerHTML = `<div class="loading">正在加载知识库…</div>`;
  try {
    state.kbs = await api("/knowledge-bases");
  } catch (err) {
    renderError(err.message);
    return;
  }
  renderKbList();
}

function renderKbList() {
  const isAdmin = state.user && state.user.role === "admin";
  const kbs = state.kbs || [];
  app.innerHTML = `
    <div class="spread row" style="margin-bottom:14px;">
      <h1>知识库</h1>
    </div>
    ${isAdmin ? `
      <div class="card">
        <h2>新建知识库</h2>
        <form id="kb-create-form" class="row">
          <input id="kb-name" placeholder="知识库名称" style="flex:1;min-width:180px;" required />
          <select id="kb-visibility">
            <option value="org">组织内可见</option>
            <option value="restricted">受限（需授权）</option>
          </select>
          <button class="primary" type="submit">创建</button>
        </form>
      </div>` : ""}
    ${kbs.length === 0 ? `<div class="empty">还没有可访问的知识库</div>` : `
      <div class="grid">
        ${kbs.map((kb) => `
          <div class="card kb-card" data-kb="${kb.id}">
            <h3>${escapeHtml(kb.name)}</h3>
            <span class="badge ${kb.visibility === "org" ? "org" : "restr"}">${kb.visibility === "org" ? "组织可见" : "受限"}</span>
          </div>`).join("")}
      </div>`}`;

  const form = $("#kb-create-form");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = $("#kb-name").value.trim();
      const visibility = $("#kb-visibility").value;
      try {
        await api("/knowledge-bases", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, visibility }),
        });
        toast("知识库已创建", "ok");
        loadKbList();
      } catch (err) {
        toast(err.message, "error");
      }
    });
  }

  app.querySelectorAll(".kb-card").forEach((el) => {
    el.addEventListener("click", () => {
      const id = el.dataset.kb;
      state.currentKb = state.kbs.find((kb) => kb.id === id);
      setView("kb-detail");
    });
  });
}

/* ---------- 知识库详情 ---------- */
async function loadKbDetail(kbId) {
  app.innerHTML = `<div class="loading">正在加载文档…</div>`;
  try {
    state.docs = await api(`/knowledge-bases/${kbId}/documents`);
  } catch (err) {
    renderError(err.message);
    return;
  }
  renderKbDetail();
}

function renderKbDetail() {
  const kb = state.currentKb;
  const isAdmin = state.user && state.user.role === "admin";
  app.innerHTML = `
    <div class="row spread" style="margin-bottom:12px;">
      <button class="ghost" id="back-to-kbs">← 返回</button>
      <h1 style="margin:0;font-size:20px;">${escapeHtml(kb.name)}</h1>
      <span class="badge ${kb.visibility === "org" ? "org" : "restr"}">${kb.visibility === "org" ? "组织可见" : "受限"}</span>
    </div>

    ${isAdmin ? `
      <div class="card">
        <h2>上传文档</h2>
        <p class="sub">支持 PDF 和 Markdown（.md / .markdown），单文件不超过 20 MB</p>
        <form id="upload-form" class="row">
          <input id="upload-file" type="file" accept=".pdf,.md,.markdown" required />
          <button class="primary" type="submit">上传</button>
        </form>
        <div id="upload-status" class="muted"></div>
      </div>` : ""}

    <div class="card">
      <h2>文档</h2>
      ${state.docs.length === 0 ? `<div class="empty">还没有文档</div>` : `
        <ul class="list">
          ${state.docs.map((doc) => `
            <li>
              <div>
                <div class="doc-name">${escapeHtml(doc.original_filename)}</div>
                <div class="muted">${doc.file_format === "pdf" ? "PDF" : "Markdown"} · ${doc.page_count != null ? doc.page_count + " 页" : "—"}</div>
                ${doc.error_message ? `<div class="error-text">${escapeHtml(doc.error_message)}</div>` : ""}
              </div>
              ${statusBadge(doc.status)}
            </li>`).join("")}
        </ul>`}
    </div>

    ${isAdmin ? `
      <div class="card">
        <h2>成员授权</h2>
        <p class="sub">受限知识库只对授权成员可见；组织可见知识库全员可读。</p>
        <form id="grant-form" class="row">
          <input id="grant-email" type="email" placeholder="成员邮箱" style="flex:1;min-width:180px;" required />
          <button class="primary" type="submit">授予读取</button>
        </form>
        <div id="permission-list" class="muted" style="margin-top:8px;">加载中…</div>
      </div>` : ""}`;

  $("#back-to-kbs").addEventListener("click", () => setView("kb-list"));

  const uploadForm = $("#upload-form");
  if (uploadForm) {
    uploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fileInput = $("#upload-file");
      if (!fileInput.files.length) return;
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      $("#upload-status").textContent = "正在上传并解析…";
      try {
        const doc = await api(`/knowledge-bases/${kb.id}/documents`, {
          method: "POST",
          body: formData,
        });
        const statusEl = $("#upload-status");
        if (doc.status === "ready") {
          statusEl.textContent = "已就绪";
          toast("文档已就绪", "ok");
        } else if (doc.status === "failed") {
          statusEl.textContent = "处理失败：" + (doc.error_message || "未知错误");
          statusEl.className = "error-text";
        } else {
          statusEl.textContent = "处理中…";
          startPolling(doc.id);
        }
        loadKbDetail(kb.id);
      } catch (err) {
        toast(err.message, "error");
      }
    });
  }

  if (isAdmin) {
    loadPermissions(kb.id);
    $("#grant-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = $("#grant-email").value.trim();
      try {
        await api(`/knowledge-bases/${kb.id}/permissions`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_email: email, access_level: "read" }),
        });
        toast("授权成功", "ok");
        loadPermissions(kb.id);
      } catch (err) {
        toast(err.message, "error");
      }
    });
  }

  state.docs.forEach((doc) => {
    if (doc.status === "uploaded" || doc.status === "processing") startPolling(doc.id);
  });
}

function statusBadge(status) {
  if (status === "ready") return `<span class="badge ok">ready</span>`;
  if (status === "failed") return `<span class="badge err">failed</span>`;
  if (status === "processing") return `<span class="badge warn">processing</span>`;
  return `<span class="badge">uploaded</span>`;
}

function startPolling(docId) {
  if (state.pollTimers.has(docId)) return;
  const timer = setInterval(async () => {
    let doc;
    try {
      doc = await api(`/documents/${docId}`);
    } catch (err) {
      clearInterval(timer);
      state.pollTimers.delete(docId);
      return;
    }
    if (doc.status === "ready" || doc.status === "failed") {
      clearInterval(timer);
      state.pollTimers.delete(docId);
      if (state.view === "kb-detail") loadKbDetail(state.currentKb.id);
    }
  }, 2000);
  state.pollTimers.set(docId, timer);
}

async function loadPermissions(kbId) {
  const box = $("#permission-list");
  if (!box) return;
  try {
    const permissions = await api(`/knowledge-bases/${kbId}/permissions`);
    box.className = "";
    if (!permissions.length) {
      box.textContent = "暂无显式授权成员";
      return;
    }
    box.innerHTML = `<ul class="list">${permissions.map((p) => `
      <li>
        <span>${escapeHtml(p.email)} · ${p.access_level}</span>
        <button data-revoke="${p.user_id}">移除</button>
      </li>`).join("")}</ul>`;
    box.querySelectorAll("[data-revoke]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api(`/knowledge-bases/${kbId}/permissions/${btn.dataset.revoke}`, { method: "DELETE" });
          toast("已移除授权", "ok");
          loadPermissions(kbId);
        } catch (err) {
          toast(err.message, "error");
        }
      });
    });
  } catch (err) {
    box.textContent = err.message;
  }
}

/* ---------- 提问 ---------- */
async function loadChat() {
  app.innerHTML = `<div class="loading">正在加载…</div>`;
  try {
    state.conversations = await api("/chat/conversations");
  } catch (err) {
    state.conversations = [];
  }
  renderChat();
}

function renderChat() {
  const kbs = state.kbs || [];
  app.innerHTML = `
    <div class="row spread" style="margin-bottom:14px;">
      <h1>提问</h1>
      <button class="ghost" id="refresh-chat">刷新</button>
    </div>

    <div class="card">
      <h2>提出问题</h2>
      <form id="ask-form">
        <label for="ask-question">问题</label>
        <textarea id="ask-question" required placeholder="例如：员工每年有几天年假？"></textarea>
        <label>检索范围（可多选，留空表示全部授权知识库）</label>
        <div class="checkboxes">
          ${kbs.length === 0 ? `<span class="muted">没有可用的知识库</span>` : kbs.map((kb) => `
            <label><input type="checkbox" value="${kb.id}" /> ${escapeHtml(kb.name)}</label>`).join("")}
        </div>
        <button class="primary" type="submit" style="margin-top:10px;">提交问题</button>
      </form>
      <div id="answer-area"></div>
    </div>

    <div class="card">
      <h2>历史对话</h2>
      <div id="conversation-list">
        ${state.conversations.length === 0 ? `<div class="empty">暂无历史对话</div>` : `
          <ul class="list">
            ${state.conversations.map((c) => `
              <li>
                <span>${escapeHtml(c.preview || "(空会话)")}</span>
                <button data-conversation="${c.id}">查看</button>
              </li>`).join("")}
          </ul>`}
      </div>
    </div>`;

  $("#refresh-chat").addEventListener("click", loadChat);

  $("#ask-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = $("#ask-question").value.trim();
    const checkedKbs = Array.from(app.querySelectorAll(".checkboxes input:checked")).map((el) => el.value);
    const area = $("#answer-area");
    area.innerHTML = `<div class="loading">正在检索并组织回答…</div>`;
    try {
      const data = await api("/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, kb_ids: checkedKbs.length ? checkedKbs : null }),
      });
      renderAnswer(area, data);
      loadChat();
    } catch (err) {
      area.innerHTML = `<div class="error-state">${escapeHtml(err.message)}</div>`;
    }
  });

  app.querySelectorAll("[data-conversation]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.conversation;
      try {
        const messages = await api(`/chat/conversations/${id}/messages`);
        renderHistory(messages);
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });
}

function renderAnswer(area, data) {
  if (data.status === "refused") {
    area.innerHTML = `
      <div class="answer-box">${escapeHtml(data.answer)}</div>
      <div class="muted">状态：拒答（证据不足）</div>`;
    return;
  }
  if (data.status === "failed") {
    area.innerHTML = `
      <div class="error-state">${escapeHtml(data.error_message || "回答失败")}</div>`;
    return;
  }
  const citations = data.citations || [];
  area.innerHTML = `
    <div class="answer-box">${escapeHtml(data.answer)}</div>
    <div class="muted">${data.mode === "extractive" ? "提取式回答" : "模型回答"} · 耗时 ${data.latency_ms} ms</div>
    ${citations.length ? `<h3 style="margin-top:14px;">来源</h3><div class="sources">${citations.map((c) => `
      <div class="source">
        <div class="loc">[${escapeHtml(c.label)}] ${locatorText(c.locator)}</div>
        <button data-citation="${c.id}">查看原文并校验权限</button>
        <div class="citation-detail" data-detail="${c.id}"></div>
      </div>`).join("")}</div>` : ""}`;
  area.querySelectorAll("[data-citation]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.citation;
      const box = area.querySelector(`[data-detail="${id}"]`);
      box.innerHTML = `<span class="muted">加载中…</span>`;
      try {
        const c = await api(`/citations/${id}`);
        box.innerHTML = `
          <div class="muted">文档：${escapeHtml(c.document.name)} · ${locatorText(c.locator)}</div>
          <blockquote>${escapeHtml(c.content)}</blockquote>`;
      } catch (err) {
        box.innerHTML = `<div class="error-text">${escapeHtml(err.message)}</div>`;
      }
    });
  });
}

function renderHistory(messages) {
  const area = $("#answer-area");
  area.innerHTML = `
    <h3>历史问答</h3>
    ${messages.map((m) => `
      <div class="card" style="margin-bottom:10px;">
        <div class="muted">${m.role === "user" ? "我" : "系统"} · ${m.status}</div>
        <div class="answer-box" style="margin:8px 0;">${escapeHtml(m.content)}</div>
        ${(m.citations || []).map((c) => `
          <div class="source">
            <div class="loc">[${escapeHtml(c.label)}] ${locatorText(c.locator)}</div>
            <button data-citation="${c.id}">查看原文并校验权限</button>
            <div class="citation-detail" data-detail="${c.id}"></div>
          </div>`).join("")}
      </div>`).join("")}`;
  area.querySelectorAll("[data-citation]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.citation;
      const box = area.querySelector(`[data-detail="${id}"]`);
      box.innerHTML = `<span class="muted">加载中…</span>`;
      try {
        const c = await api(`/citations/${id}`);
        box.innerHTML = `
          <div class="muted">文档：${escapeHtml(c.document.name)} · ${locatorText(c.locator)}</div>
          <blockquote>${escapeHtml(c.content)}</blockquote>`;
      } catch (err) {
        box.innerHTML = `<div class="error-text">${escapeHtml(err.message)}</div>`;
      }
    });
  });
}

function locatorText(locator) {
  const loc = locator || {};
  const parts = [];
  if (loc.page_number) parts.push("第 " + loc.page_number + " 页");
  if (loc.section_path && loc.section_path.length) parts.push(loc.section_path.join(" / "));
  return parts.length ? parts.join(" · ") : "原文定位";
}

function renderError(message) {
  app.innerHTML = `<div class="error-state">${escapeHtml(message)}</div>`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

/* ---------- 启动 ---------- */
(async function boot() {
  $("#logout").addEventListener("click", logout);
  topnav.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  });
  if (state.token) {
    try {
      await loadMe();
      setView("kb-list");
      return;
    } catch (err) {
      state.token = "";
      localStorage.removeItem("pr_token");
    }
  }
  render();
})();