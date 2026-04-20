function summarizeItems(items) {
  return Array.isArray(items) ? items : [];
}

export const auditView = {
  id: "audit",
  label: "审计 Audit",
  shortLabel: "只读 Read",
  initialState: {
    decisions: null,
    risk: null,
    feedback: null,
    authAudit: null,
    authUsers: null,
    userDetail: null,
    decisionFilter: { symbol: "", limit: 10 },
    riskFilter: { symbol: "", limit: 10 },
    feedbackFilter: { symbol: "", limit: 10 },
    authFilter: { resource: "", user_id: "", limit: 20, detail_user_id: "viewer-001" },
    detail: null,
  },
  render(ctx, page) {
    const { utils } = ctx;
    const decisionRows = summarizeItems(page.decisions?.items);
    const riskRows = summarizeItems(page.risk?.items);
    const feedbackRows = summarizeItems(page.feedback?.items);
    const authRows = summarizeItems(page.authAudit?.entries);
    const authUsers = summarizeItems(page.authUsers?.users);
    const detail = page.detail || page.userDetail;

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">追加只读回查 Append-only Readback</span>
          <h2>审计 Audit</h2>
          <p>对 decisions、risk、feedback、auth 做只读查询。这里不会暗示任何写权限，也不会伪装可变历史。</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">GET /api/v1/audit/*</span>
          <span class="endpoint-pill">GET /api/v1/auth/*</span>
        </div>
      </section>

      <div class="button-row">
        <button type="button" class="action-button" data-audit-refresh-all>刷新全部分区 Refresh All Sections</button>
      </div>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">决策审计 Decision Audit</span>
              <h3>决策历史 Decision History</h3>
            </div>
            <span class="endpoint-pill">GET /api/v1/audit/decisions</span>
          </div>
          <form data-decision-filter class="compact-form">
            <input name="symbol" placeholder="标的过滤 Symbol filter" value="${utils.escapeHtml(page.decisionFilter.symbol)}" />
            <input name="limit" type="number" min="1" max="100" value="${utils.escapeHtml(page.decisionFilter.limit)}" />
            <button type="button" class="action-button small" data-load-decisions>刷新 Refresh</button>
          </form>
          ${utils.renderTable(
            [
              { key: "decision_id", label: "决策 Decision" },
              { key: "symbol", label: "标的 Symbol" },
              { key: "bias", label: "偏置 Bias" },
              {
                key: "confidence",
                label: "置信度 Confidence",
                render: (row) => utils.formatNumber(row.confidence),
              },
              {
                key: "inspect",
                label: "详情 Detail",
                render: (_row, index) => `<button type="button" class="link-button" data-inspect-section="decisions" data-inspect-index="${index}">查看 Inspect</button>`,
              },
            ],
            decisionRows,
            { emptyText: "从真实 append-only 决策存储中加载记录。 / Load decision audit rows from the real append-only store." },
          )}
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">风控审计 Risk Audit</span>
              <h3>风控历史 Risk History</h3>
            </div>
            <span class="endpoint-pill">GET /api/v1/audit/risk</span>
          </div>
          <form data-risk-filter class="compact-form">
            <input name="symbol" placeholder="标的过滤 Symbol filter" value="${utils.escapeHtml(page.riskFilter.symbol)}" />
            <input name="limit" type="number" min="1" max="100" value="${utils.escapeHtml(page.riskFilter.limit)}" />
            <button type="button" class="action-button small" data-load-risk>刷新 Refresh</button>
          </form>
          ${utils.renderTable(
            [
              { key: "plan_id", label: "计划 Plan" },
              { key: "symbol", label: "标的 Symbol" },
              {
                key: "final_quantity",
                label: "数量 Quantity",
                render: (row) => utils.formatNumber(row.final_quantity),
              },
              {
                key: "veto_triggered",
                label: "否决 Veto",
                render: (row) => String(row.veto_triggered),
              },
              {
                key: "inspect",
                label: "详情 Detail",
                render: (_row, index) => `<button type="button" class="link-button" data-inspect-section="risk" data-inspect-index="${index}">查看 Inspect</button>`,
              },
            ],
            riskRows,
            { emptyText: "从 append-only 风控注册表中加载记录。 / Load risk audit rows from the append-only registry." },
          )}
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">反馈审计 Feedback Audit</span>
              <h3>反馈历史 Feedback History</h3>
            </div>
            <span class="endpoint-pill">GET /api/v1/audit/feedback</span>
          </div>
          <form data-feedback-filter class="compact-form">
            <input name="symbol" placeholder="标的过滤 Symbol filter" value="${utils.escapeHtml(page.feedbackFilter.symbol)}" />
            <input name="limit" type="number" min="1" max="100" value="${utils.escapeHtml(page.feedbackFilter.limit)}" />
            <button type="button" class="action-button small" data-load-feedback>刷新 Refresh</button>
          </form>
          ${utils.renderTable(
            [
              { key: "feedback_id", label: "反馈 Feedback" },
              { key: "symbol", label: "标的 Symbol" },
              { key: "feedback_type", label: "类型 Type" },
              { key: "severity", label: "严重度 Severity" },
              {
                key: "inspect",
                label: "详情 Detail",
                render: (_row, index) => `<button type="button" class="link-button" data-inspect-section="feedback" data-inspect-index="${index}">查看 Inspect</button>`,
              },
            ],
            feedbackRows,
            { emptyText: "反馈允许为空，这里必须诚实展示空状态。 / Feedback is allowed to be empty. This state must stay honest." },
          )}
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">权限只读 Auth Read-only</span>
              <h3>审计轨迹与用户 Audit Trail and Users</h3>
            </div>
            <span class="endpoint-pill">GET /api/v1/auth/audit /users /users/{id}</span>
          </div>
          <form data-auth-filter class="compact-form compact-form-wide">
            <input name="resource" placeholder="资源过滤 Resource filter" value="${utils.escapeHtml(page.authFilter.resource)}" />
            <input name="user_id" placeholder="用户过滤 User filter" value="${utils.escapeHtml(page.authFilter.user_id)}" />
            <input name="limit" type="number" min="1" max="200" value="${utils.escapeHtml(page.authFilter.limit)}" />
            <button type="button" class="action-button small" data-load-auth>刷新 Refresh</button>
          </form>
          <div class="split-panel">
            <div>
              <h4 class="subheading">权限审计 Auth Audit</h4>
              ${utils.renderTable(
                [
                  { key: "id", label: "条目 Entry" },
                  { key: "user_id", label: "用户 User" },
                  { key: "resource", label: "资源 Resource" },
                  { key: "result", label: "结果 Result" },
                  {
                    key: "inspect",
                    label: "详情 Detail",
                    render: (_row, index) => `<button type="button" class="link-button" data-inspect-section="authAudit" data-inspect-index="${index}">查看 Inspect</button>`,
                  },
                ],
                authRows,
                { emptyText: "从后端加载权限审计记录。 / Load auth audit rows from the backend." },
              )}
            </div>
            <div>
              <h4 class="subheading">用户 Users</h4>
              ${utils.renderTable(
                [
                  { key: "id", label: "用户 ID User ID" },
                  { key: "username", label: "用户名 Username" },
                  { key: "role", label: "角色 Role" },
                  {
                    key: "inspect",
                    label: "详情 Detail",
                    render: (_row, index) => `<button type="button" class="link-button" data-inspect-section="authUsers" data-inspect-index="${index}">查看 Inspect</button>`,
                  },
                ],
                authUsers,
                { emptyText: "当前还没有加载用户记录。 / No user rows loaded yet." },
              )}
            </div>
          </div>
          <form data-user-detail-form class="compact-form">
            <input name="detail_user_id" placeholder="用户 ID 详情查询 User ID detail lookup" value="${utils.escapeHtml(page.authFilter.detail_user_id)}" />
            <button type="button" class="action-button small" data-load-user-detail>加载用户 Load User</button>
          </form>
        </article>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">只读详情 Read-only Detail</span>
            <h3>已选记录详情 Selected Record Detail</h3>
          </div>
        </div>
        ${
          detail
            ? `<pre class="detail-pre">${utils.formatJson(detail)}</pre>`
            : `<div class="empty-state">点击任意一行的查看按钮，即可在这里查看只读详情。 / Pick any row via Inspect to see a read-only detail payload here.</div>`
        }
      </section>
    `;
  },
  mount(ctx, page, root) {
    const syncFilters = () => {
      const decision = new FormData(root.querySelector("[data-decision-filter]"));
      page.decisionFilter.symbol = String(decision.get("symbol") || "").trim();
      page.decisionFilter.limit = Number(decision.get("limit") || 10);

      const risk = new FormData(root.querySelector("[data-risk-filter]"));
      page.riskFilter.symbol = String(risk.get("symbol") || "").trim();
      page.riskFilter.limit = Number(risk.get("limit") || 10);

      const feedback = new FormData(root.querySelector("[data-feedback-filter]"));
      page.feedbackFilter.symbol = String(feedback.get("symbol") || "").trim();
      page.feedbackFilter.limit = Number(feedback.get("limit") || 10);

      const auth = new FormData(root.querySelector("[data-auth-filter]"));
      page.authFilter.resource = String(auth.get("resource") || "").trim();
      page.authFilter.user_id = String(auth.get("user_id") || "").trim();
      page.authFilter.limit = Number(auth.get("limit") || 20);

      const detail = new FormData(root.querySelector("[data-user-detail-form]"));
      page.authFilter.detail_user_id = String(detail.get("detail_user_id") || "").trim();
    };

    const setSectionStatus = (tone, title, message, detail) => {
      ctx.setPageStatus(this.id, { tone, title, message, detail });
    };

    const loadDecisions = async () => {
      syncFilters();
      ctx.setLoading(true);
      setSectionStatus("loading", "刷新决策审计 Refreshing Decisions", "正在加载决策审计记录。", "GET /api/v1/audit/decisions");
      const result = await ctx.api.get("/api/v1/audit/decisions", page.decisionFilter);
      page.decisions = result.data;
      setSectionStatus(
        result.ok ? "success" : "error",
        result.ok ? "决策审计已加载 Decision Audit Loaded" : "决策审计失败 Decision Audit Failed",
        result.ok ? "决策记录已从 append-only registry 刷新。" : result.error?.message || "后端返回错误。",
        result.ok ? `${result.data?.total || 0} records` : `${result.status || "network"} / ${result.url}`,
      );
      ctx.setLoading(false);
      ctx.rerender();
    };

    const loadRisk = async () => {
      syncFilters();
      ctx.setLoading(true);
      setSectionStatus("loading", "刷新风控审计 Refreshing Risk", "正在加载风控审计记录。", "GET /api/v1/audit/risk");
      const result = await ctx.api.get("/api/v1/audit/risk", page.riskFilter);
      page.risk = result.data;
      setSectionStatus(
        result.ok ? "success" : "error",
        result.ok ? "风控审计已加载 Risk Audit Loaded" : "风控审计失败 Risk Audit Failed",
        result.ok ? "风控记录已从 append-only registry 刷新。" : result.error?.message || "后端返回错误。",
        result.ok ? `${result.data?.total || 0} records` : `${result.status || "network"} / ${result.url}`,
      );
      ctx.setLoading(false);
      ctx.rerender();
    };

    const loadFeedback = async () => {
      syncFilters();
      ctx.setLoading(true);
      setSectionStatus("loading", "刷新反馈 Refreshing Feedback", "正在加载反馈历史。", "GET /api/v1/audit/feedback");
      const result = await ctx.api.get("/api/v1/audit/feedback", page.feedbackFilter);
      page.feedback = result.data;
      setSectionStatus(
        result.ok ? "success" : "error",
        result.ok ? "反馈历史已加载 Feedback History Loaded" : "反馈历史失败 Feedback History Failed",
        result.ok ? "反馈记录已从 append-only registry 刷新。" : result.error?.message || "后端返回错误。",
        result.ok ? `${result.data?.total || 0} records` : `${result.status || "network"} / ${result.url}`,
      );
      ctx.setLoading(false);
      ctx.rerender();
    };

    const loadAuth = async () => {
      syncFilters();
      ctx.setLoading(true);
      setSectionStatus("loading", "刷新权限回读 Refreshing Auth", "正在加载权限审计与用户记录。", "GET /api/v1/auth/audit /users");
      const [auditResult, usersResult] = await Promise.all([
        ctx.api.get("/api/v1/auth/audit", {
          limit: page.authFilter.limit,
          resource: page.authFilter.resource,
          user_id: page.authFilter.user_id,
        }),
        ctx.api.get("/api/v1/auth/users"),
      ]);
      page.authAudit = auditResult.data;
      page.authUsers = usersResult.data;
      const failed = [auditResult, usersResult].find((item) => !item.ok);
      setSectionStatus(
        failed ? "error" : "success",
        failed ? "权限回读失败 Auth Readback Failed" : "权限回读已加载 Auth Readback Loaded",
        failed ? failed.error?.message || "后端返回错误。" : "权限审计轨迹与用户已成功刷新。",
        failed ? `${failed.status || "network"} / ${failed.url}` : `${page.authAudit?.total || 0} audit entries / ${(page.authUsers?.users || []).length} users`,
      );
      ctx.setLoading(false);
      ctx.rerender();
    };

    const loadUserDetail = async () => {
      syncFilters();
      if (!page.authFilter.detail_user_id) {
        ctx.toast("请先输入用户 ID / Enter a user ID first.", "info");
        return;
      }
      ctx.setLoading(true);
      setSectionStatus("loading", "加载用户详情 Loading User Detail", "正在拉取单个用户详情视图。", "GET /api/v1/auth/users/{user_id}");
      const result = await ctx.api.get(`/api/v1/auth/users/${encodeURIComponent(page.authFilter.detail_user_id)}`);
      page.userDetail = result.data;
      page.detail = result.data;
      setSectionStatus(
        result.ok ? "success" : "error",
        result.ok ? "用户详情已加载 User Detail Loaded" : "用户详情失败 User Detail Failed",
        result.ok ? `用户 ${page.authFilter.detail_user_id} 已成功加载。` : result.error?.message || "后端返回错误。",
        result.ok ? result.data?.role || "n/a" : `${result.status || "network"} / ${result.url}`,
      );
      ctx.setLoading(false);
      ctx.rerender();
    };

    const inspectMap = {
      decisions: () => page.decisions?.items || [],
      risk: () => page.risk?.items || [],
      feedback: () => page.feedback?.items || [],
      authAudit: () => page.authAudit?.entries || [],
      authUsers: () => page.authUsers?.users || [],
    };

    root.querySelector("[data-load-decisions]")?.addEventListener("click", loadDecisions);
    root.querySelector("[data-load-risk]")?.addEventListener("click", loadRisk);
    root.querySelector("[data-load-feedback]")?.addEventListener("click", loadFeedback);
    root.querySelector("[data-load-auth]")?.addEventListener("click", loadAuth);
    root.querySelector("[data-load-user-detail]")?.addEventListener("click", loadUserDetail);
    root.querySelector("[data-audit-refresh-all]")?.addEventListener("click", async () => {
      await loadDecisions();
      await loadRisk();
      await loadFeedback();
      await loadAuth();
    });

    root.querySelectorAll("[data-inspect-section]").forEach((button) => {
      button.addEventListener("click", () => {
        const section = button.getAttribute("data-inspect-section");
        const index = Number(button.getAttribute("data-inspect-index"));
        const rows = inspectMap[section]?.() || [];
        page.detail = rows[index] || null;
        ctx.rerender();
      });
    });
  },
};
