export const dashboardView = {
  id: "dashboard",
  label: "仪表盘 Dashboard",
  shortLabel: "状态 Status",
  initialState: {
    loaded: false,
    loadingStarted: false,
    health: null,
    version: null,
    systemStatus: null,
    modules: null,
    users: null,
  },
  render(ctx, page) {
    const { utils } = ctx;
    const health = page.health || {};
    const version = page.version || {};
    const modules = page.modules?.modules || [];
    const readyModules = modules.filter((item) => item.status === "ready").length;
    const services = Object.values(health.services || {}).filter((status) => status === "ok").length;
    const users = page.users?.users || [];

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">实时总览 Live Overview</span>
          <h2>仪表盘 Dashboard</h2>
          <p>从当前后端刷新健康检查、版本、系统状态、模块就绪度，以及只读权限可见性。</p>
        </div>
        <button type="button" class="action-button" data-dashboard-refresh>刷新仪表盘 Refresh Dashboard</button>
      </section>

      ${utils.renderMetricCards([
        {
          label: "健康状态 Health",
          value: health.status || "n/a",
          sub: `环境 Environment ${health.environment || "n/a"}`,
        },
        {
          label: "版本 Version",
          value: version.version || "n/a",
          sub: version.api || "productization-layer",
        },
        {
          label: "模块就绪 Modules Ready",
          value: String(readyModules),
          sub: `${modules.length} 个模块探针返回`,
        },
        {
          label: "健康服务 Healthy Services",
          value: String(services),
          sub: `${users.length} 个权限用户可见`,
        },
      ])}

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">系统状态 System Status</span>
              <h3>健康与运行摘要 Health and Runtime Summary</h3>
            </div>
            <span class="endpoint-pill">GET /health /version /system/status</span>
          </div>
          ${utils.renderKeyValueList([
            { label: "健康状态 Health", value: health.status || "n/a" },
            { label: "版本 Version", value: version.version || "n/a" },
            { label: "环境 Environment", value: page.systemStatus?.environment || health.environment || "n/a" },
            { label: "时间戳 Timestamp", value: utils.formatDate(health.timestamp || page.systemStatus?.timestamp) },
          ])}
          <div class="sub-grid">
            <div class="mini-card">
              <span class="mini-label">核心服务 Core Services</span>
              <div class="pill-row">${utils.renderPillList(Object.entries(health.services || {}).map(([name, status]) => `${name}:${status}`), "success")}</div>
            </div>
            <div class="mini-card">
              <span class="mini-label">系统模块 System Modules</span>
              <div class="pill-row">${utils.renderPillList(Object.entries(page.systemStatus?.modules || {}).map(([name, status]) => `${name}:${status}`))}</div>
            </div>
          </div>
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">接口概览 API Surface</span>
              <h3>控制台总览 Console Overview</h3>
            </div>
            <span class="endpoint-pill">只读面板 Read-only Dashboard</span>
          </div>
          <div class="api-overview">
            <div class="api-item">
              <strong>Dashboard</strong>
              <span>/health /version /system/*</span>
            </div>
            <div class="api-item">
              <strong>Pipeline</strong>
              <span>/api/v1/pipeline/run-full /run-live</span>
            </div>
            <div class="api-item">
              <strong>Arbitration</strong>
              <span>/api/v1/arbitration/run /run-portfolio</span>
            </div>
            <div class="api-item">
              <strong>Strategy Pool</strong>
              <span>/api/v1/strategy-pool/propose</span>
            </div>
            <div class="api-item">
              <strong>Audit</strong>
              <span>/api/v1/audit/decisions /risk /feedback</span>
            </div>
            <div class="api-item">
              <strong>Feedback</strong>
              <span>/api/v1/audit/feedback/tasks + task status</span>
            </div>
          </div>
        </article>
      </section>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">模块探针 Modules</span>
              <h3>后端模块就绪度 Backend Module Readiness</h3>
            </div>
            <span class="endpoint-pill">GET /system/modules</span>
          </div>
          ${utils.renderTable(
            [
              { key: "name", label: "模块 Module" },
              {
                key: "status",
                label: "状态 Status",
                render: (row) => `<span class="pill pill-${row.status === "ready" ? "success" : "warn"}">${utils.escapeHtml(row.status)}</span>`,
              },
              { key: "message", label: "消息 Message" },
              {
                key: "detail",
                label: "详情 Detail",
                render: (row) => utils.escapeHtml(row.detail || row.message || "n/a"),
              },
            ],
            modules,
            { emptyText: "点击刷新以加载模块探针。 / Click refresh to load module probes." },
          )}
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">权限回读 Auth Readback</span>
              <h3>可见用户 Visible Users</h3>
            </div>
            <span class="endpoint-pill">GET /api/v1/auth/users</span>
          </div>
          ${utils.renderTable(
            [
              { key: "id", label: "用户 ID User ID" },
              { key: "username", label: "用户名 Username" },
              { key: "role", label: "角色 Role" },
              {
                key: "is_active",
                label: "启用 Active",
                render: (row) => (row.is_active ? "是 Yes" : "否 No"),
              },
            ],
            users,
            { emptyText: "当前没有返回权限用户。 / No auth users returned." },
          )}
        </article>
      </section>

      ${utils.renderJsonPanel("仪表盘原始响应 Dashboard Raw Bundle", {
        health: page.health,
        version: page.version,
        system_status: page.systemStatus,
        system_modules: page.modules,
        auth_users: page.users,
      })}
    `;
  },
  mount(ctx, page, root) {
    const refresh = async () => {
      if (page.loadingStarted) {
        return;
      }
      page.loadingStarted = true;
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "刷新仪表盘 Dashboard Refresh",
        message: "正在加载健康、版本、系统状态、模块探针与权限用户。",
        detail: "GET /health /version /system/status /system/modules /api/v1/auth/users",
      });

      const [health, version, systemStatus, modules, users] = await Promise.all([
        ctx.api.get("/health"),
        ctx.api.get("/version"),
        ctx.api.get("/system/status"),
        ctx.api.get("/system/modules"),
        ctx.api.get("/api/v1/auth/users"),
      ]);

      page.loaded = true;
      page.health = health.data;
      page.version = version.data;
      page.systemStatus = systemStatus.data;
      page.modules = modules.data;
      page.users = users.data;

      const failed = [health, version, systemStatus, modules, users].find((result) => !result.ok);
      if (failed) {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "仪表盘刷新失败 Dashboard Refresh Failed",
          message: failed.error?.message || "一个或多个仪表盘接口调用失败。",
          detail: `${failed.status || "network"} / ${failed.url}`,
        });
        ctx.toast("仪表盘刷新失败 / Dashboard refresh failed.", "error");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "仪表盘已刷新 Dashboard Refreshed",
          message: "所有仪表盘卡片均已显示实时后端数据。",
          detail: "五个仪表盘接口均已成功返回。",
        });
        ctx.toast("仪表盘已用真实 API 数据刷新 / Dashboard refreshed with live API data.", "success");
      }

      page.loadingStarted = false;
      ctx.setLoading(false);
      ctx.rerender();
    };

    root.querySelector("[data-dashboard-refresh]")?.addEventListener("click", refresh);

    if (!page.loaded && !page.loadingStarted) {
      refresh();
    }
  },
};
