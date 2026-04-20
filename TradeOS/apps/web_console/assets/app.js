import { api } from "./api.js";
import { dashboardView } from "./views/dashboard.js";
import { pipelineView } from "./views/pipeline.js";
import { arbitrationView } from "./views/arbitration.js";
import { strategyPoolView } from "./views/strategy_pool.js";
import { auditView } from "./views/audit.js";
import { feedbackView } from "./views/feedback.js";

const views = {
  dashboard: dashboardView,
  pipeline: pipelineView,
  arbitration: arbitrationView,
  strategy_pool: strategyPoolView,
  audit: auditView,
  feedback: feedbackView,
};

const initialState = {
  activeView: "dashboard",
  loadingCount: 0,
  toasts: [],
  pageStatus: {},
  pages: {},
};

const pageDefaults = {
  dashboard: dashboardView.initialState,
  pipeline: pipelineView.initialState,
  arbitration: arbitrationView.initialState,
  strategy_pool: strategyPoolView.initialState,
  audit: auditView.initialState,
  feedback: feedbackView.initialState,
};

const state = structuredClone(initialState);
const appRoot = document.getElementById("app");

function clone(value) {
  return structuredClone(value);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  const number = Number(value);
  if (Number.isNaN(number)) {
    return escapeHtml(value);
  }
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: number % 1 === 0 ? 0 : Math.min(digits, 2),
  }).format(number);
}

function formatDate(value) {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return escapeHtml(value);
  }
  return date.toLocaleString();
}

function formatJson(value) {
  if (value === null || value === undefined) {
    return "";
  }
  try {
    return escapeHtml(JSON.stringify(value, null, 2));
  } catch (error) {
    return escapeHtml(String(value));
  }
}

function shortText(value, length = 16) {
  if (!value) {
    return "n/a";
  }
  const text = String(value);
  return text.length > length ? `${text.slice(0, length)}...` : text;
}

function bi(cn, en) {
  return `${cn} / ${en}`;
}

function toneLabel(tone) {
  if (tone === "success") return bi("成功", "Success");
  if (tone === "error") return bi("失败", "Error");
  if (tone === "loading") return bi("运行中", "Running");
  return bi("提示", "Info");
}

function renderStatusBox(status) {
  if (!status) {
    return `
      <section class="status-box tone-neutral">
        <div class="status-head">
          <span class="status-chip">${escapeHtml(bi("就绪", "Ready"))}</span>
          <strong>${escapeHtml(bi("尚未发起请求", "No request yet"))}</strong>
        </div>
        <p>${escapeHtml(bi("点击任一页面动作以调用真实 FastAPI 接口。", "Select a page action to call a real FastAPI endpoint."))}</p>
      </section>
    `;
  }
  return `
    <section class="status-box tone-${escapeHtml(status.tone || "neutral")}">
      <div class="status-head">
        <span class="status-chip">${escapeHtml(toneLabel(status.tone))}</span>
        <strong>${escapeHtml(status.title || bi("状态更新", "Status update"))}</strong>
      </div>
      <p>${escapeHtml(status.message || "")}</p>
      ${status.detail ? `<code>${escapeHtml(status.detail)}</code>` : ""}
    </section>
  `;
}

function renderMetricCards(items) {
  return `
    <section class="metric-grid">
      ${items
        .map(
          (item) => `
            <article class="metric-card">
              <span class="metric-label">${escapeHtml(item.label)}</span>
              <strong class="metric-value">${escapeHtml(item.value)}</strong>
              <p class="metric-sub">${escapeHtml(item.sub || "")}</p>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderPillList(items, tone = "neutral") {
  if (!items || !items.length) {
    return `<span class="pill pill-${tone}">none</span>`;
  }
  return items
    .map((item) => `<span class="pill pill-${tone}">${escapeHtml(item)}</span>`)
    .join("");
}

function renderKeyValueList(items) {
  return `
    <dl class="key-value-list">
      ${items
        .map(
          (item) => `
            <div>
              <dt>${escapeHtml(item.label)}</dt>
              <dd>${escapeHtml(item.value ?? "n/a")}</dd>
            </div>
          `,
        )
        .join("")}
    </dl>
  `;
}

function renderJsonPanel(title, data, emptyText = "No response yet.") {
  return `
    <details class="json-panel">
      <summary>${escapeHtml(title)}</summary>
      ${
        data === null || data === undefined
          ? `<div class="empty-state compact">${escapeHtml(emptyText)}</div>`
          : `<pre>${formatJson(data)}</pre>`
      }
    </details>
  `;
}

function renderTable(columns, rows, options = {}) {
  const emptyText = options.emptyText || bi("没有返回记录。", "No rows returned.");
  if (!rows || !rows.length) {
    return `<div class="empty-state compact">${escapeHtml(emptyText)}</div>`;
  }
  return `
    <div class="table-shell">
      <table class="data-table">
        <thead>
          <tr>
            ${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${rows
            .map((row, rowIndex) => {
              return `
                <tr>
                  ${columns
                    .map((column) => {
                      const content = column.render
                        ? column.render(row, rowIndex)
                        : escapeHtml(row[column.key] ?? "n/a");
                      return `<td>${content}</td>`;
                    })
                    .join("")}
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function getPageState(viewId) {
  if (!state.pages[viewId]) {
    state.pages[viewId] = clone(pageDefaults[viewId] || {});
  }
  return state.pages[viewId];
}

function setPageStatus(viewId, status) {
  state.pageStatus[viewId] = status;
  render();
}

function pushToast(message, tone = "info") {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  state.toasts.push({ id, message, tone });
  renderToasts();
  window.setTimeout(() => {
    state.toasts = state.toasts.filter((toast) => toast.id !== id);
    renderToasts();
  }, 3200);
}

function setLoading(active) {
  state.loadingCount = Math.max(0, state.loadingCount + (active ? 1 : -1));
  renderLoading();
}

function updateUrl(viewId) {
  const url = new URL(window.location.href);
  url.searchParams.set("view", viewId);
  window.history.replaceState({}, "", url);
}

function switchView(viewId) {
  if (!views[viewId]) {
    return;
  }
  state.activeView = viewId;
  updateUrl(viewId);
  render();
}

function renderLoading() {
  const loading = state.loadingCount > 0;
  const bar = document.querySelector("[data-loading-bar]");
  if (bar) {
    bar.hidden = !loading;
  }
  document.body.classList.toggle("is-loading", loading);
}

function renderToasts() {
  const container = document.querySelector("[data-toast-stack]");
  if (!container) {
    return;
  }
  container.innerHTML = state.toasts
    .map(
      (toast) => `
        <div class="toast tone-${escapeHtml(toast.tone)}">
          <strong>${escapeHtml(toneLabel(toast.tone))}</strong>
          <span>${escapeHtml(toast.message)}</span>
        </div>
      `,
    )
    .join("");
}

function readInitialView() {
  const url = new URL(window.location.href);
  const requested = url.searchParams.get("view");
  state.activeView = views[requested] ? requested : "dashboard";
}

function bindShellEvents() {
  document.querySelectorAll("[data-nav-view]").forEach((button) => {
    button.addEventListener("click", () => {
      switchView(button.getAttribute("data-nav-view"));
    });
  });
}

function createContext() {
  return {
    api,
    state,
    views,
    utils: {
      escapeHtml,
      bi,
      formatNumber,
      formatDate,
      formatJson,
      shortText,
      renderMetricCards,
      renderPillList,
      renderKeyValueList,
      renderJsonPanel,
      renderTable,
    },
    getPageState,
    setPageStatus,
    toast: pushToast,
    setLoading,
    rerender: render,
    switchView,
  };
}

function renderShell(view) {
  const nav = Object.values(views)
    .map(
      (entry) => `
        <button
          type="button"
          class="nav-tab ${entry.id === state.activeView ? "active" : ""}"
          data-nav-view="${escapeHtml(entry.id)}"
        >
          <span>${escapeHtml(entry.label)}</span>
          <small>${escapeHtml(entry.shortLabel || entry.label)}</small>
        </button>
      `,
    )
    .join("");

  return `
    <div class="app-shell">
      <div class="ambient ambient-left"></div>
      <div class="ambient ambient-right"></div>
      <header class="hero-shell">
        <div class="hero-copy">
          <span class="hero-eyebrow">${escapeHtml(bi("TradeOS 产品操作台", "TradeOS Product Surface"))}</span>
          <h1>${escapeHtml(bi("交易操作台", "Web Console"))}</h1>
          <p>
            ${escapeHtml(bi(
              "这里承接产品化外观，但所有按钮仍只调用当前 Python/FastAPI 后端，不做假写入、不做影子逻辑、不引入第二套后端。",
              "This console carries the productized look while every button still talks only to the current Python/FastAPI backend. No mock writes, no shadow logic, and no second backend.",
            ))}
          </p>
        </div>
        <div class="hero-meta">
          <div>
            <span class="meta-label">${escapeHtml(bi("接口基址", "API Base"))}</span>
            <strong>${escapeHtml(api.base)}</strong>
          </div>
          <div>
            <span class="meta-label">${escapeHtml(bi("模式", "Mode"))}</span>
            <strong>${escapeHtml(bi("仅真实 FastAPI 接口", "Real FastAPI endpoints only"))}</strong>
          </div>
          <div>
            <span class="meta-label">${escapeHtml(bi("旧入口", "Legacy"))}</span>
            <strong>${escapeHtml(bi("Streamlit 仅保留为回退入口", "Streamlit kept as fallback only"))}</strong>
          </div>
        </div>
      </header>
      <nav class="tab-bar">
        ${nav}
      </nav>
      <div class="shell-meta">
        <span>${escapeHtml(bi("首屏覆盖 Dashboard、Pipeline、Arbitration、Strategy Pool、Audit、Feedback 六个核心页面。", "The first screen covers Dashboard, Pipeline, Arbitration, Strategy Pool, Audit, and Feedback."))}</span>
        <span>${escapeHtml(bi("当前页面", "Current page"))}: <strong>${escapeHtml(view.label)}</strong></span>
      </div>
      <div class="loading-bar" data-loading-bar hidden></div>
      ${renderStatusBox(state.pageStatus[state.activeView])}
      <main id="view-root" class="view-root"></main>
      <div class="toast-stack" data-toast-stack></div>
    </div>
  `;
}

function mountView(view, context) {
  const root = document.getElementById("view-root");
  const pageState = getPageState(view.id);
  root.innerHTML = view.render(context, pageState);
  view.mount(context, pageState, root);
}

function render() {
  const context = createContext();
  const view = views[state.activeView];
  appRoot.innerHTML = renderShell(view);
  bindShellEvents();
  mountView(view, context);
  renderToasts();
  renderLoading();
}

readInitialView();
render();
