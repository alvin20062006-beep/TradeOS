const TEMPLATES = [
  {
    id: "health",
    label: "Health / 健康检查",
    method: "GET",
    path: "/health",
    body: "",
  },
  {
    id: "system_status",
    label: "System Status / 系统状态",
    method: "GET",
    path: "/system/status",
    body: "",
  },
  {
    id: "analysis_run",
    label: "Analysis Run / 分析 DTO",
    method: "POST",
    path: "/api/v1/analysis/run",
    body: JSON.stringify({ symbol: "AAPL", direction: "LONG", confidence: 0.7, score: 0.6, alpha: 0.0 }, null, 2),
  },
  {
    id: "risk_calculate",
    label: "Risk Calculate / 风控计算",
    method: "POST",
    path: "/api/v1/risk/calculate",
    body: JSON.stringify({ symbol: "AAPL", decision_id: "manual-check", bias: "long_bias", confidence: 0.7, portfolio_value: 100000, current_price: 190, regime: "trending_up" }, null, 2),
  },
  {
    id: "pipeline_live",
    label: "Pipeline Live / 实时闭环",
    method: "POST",
    path: "/api/v1/pipeline/run-live",
    body: JSON.stringify({ symbol: "AAPL", market_type: "equity", timeframe: "1d", lookback: 30, profile_id: "default-live", news_limit: 3 }, null, 2),
  },
  {
    id: "arbitration_run",
    label: "Arbitration Run / 仲裁",
    method: "POST",
    path: "/api/v1/arbitration/run",
    body: JSON.stringify({ symbol: "AAPL", direction: "LONG", confidence: 0.7, strength: 0.6, regime: "trending_up" }, null, 2),
  },
  {
    id: "strategy_pool",
    label: "Strategy Pool Propose / 策略池",
    method: "POST",
    path: "/api/v1/strategy-pool/propose",
    body: JSON.stringify({ symbol: "AAPL", strategy_id: "manual-trend", direction: "LONG", strength: 0.7, confidence: 0.75, portfolio_weight: 1.0 }, null, 2),
  },
  {
    id: "audit_decisions",
    label: "Audit Decisions / 决策审计",
    method: "GET",
    path: "/api/v1/audit/decisions",
    body: "",
  },
  {
    id: "audit_risk",
    label: "Audit Risk / 风控审计",
    method: "GET",
    path: "/api/v1/audit/risk",
    body: "",
  },
  {
    id: "audit_feedback",
    label: "Audit Feedback / 反馈审计",
    method: "GET",
    path: "/api/v1/audit/feedback",
    body: "",
  },
];

function selectedTemplate(page) {
  return TEMPLATES.find((template) => template.id === page.template_id) || TEMPLATES[0];
}

function buildCurl(base, method, path, body) {
  const url = `${base}${path}`;
  if (method === "GET") {
    return `curl -X GET "${url}" -H "Accept: application/json"`;
  }
  const payload = body && body.trim() ? body.trim().replaceAll("'", "'\\''") : "{}";
  return `curl -X ${method} "${url}" -H "Accept: application/json" -H "Content-Type: application/json" --data '${payload}'`;
}

export const diagnosticsView = {
  id: "diagnostics",
  label: "Diagnostics / Advanced API",
  shortLabel: "Advanced",
  initialState: {
    template_id: "health",
    method: "GET",
    path: "/health",
    body: "",
    response: null,
    error: null,
    history: [],
  },
  render(ctx, page) {
    const { utils } = ctx;
    const curl = buildCurl(ctx.api.base, page.method, page.path, page.body);
    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">Advanced users only / 高级用户</span>
          <h2>Diagnostics / Advanced API</h2>
          <p>This page exposes raw API templates, JSON requests, response bodies, request history, curl copy, and detailed errors. It is intentionally separate from the normal product workflow.</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">No fake success</span>
          <span class="endpoint-pill">Real FastAPI only</span>
        </div>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Templates / 模板</span>
            <h3>Choose API Template / 选择 API 模板</h3>
          </div>
        </div>
        <form data-diagnostics-form class="form-grid">
          <label>
            <span>Template / 模板</span>
            <select name="template_id">
              ${TEMPLATES.map((template) => `<option value="${template.id}" ${page.template_id === template.id ? "selected" : ""}>${utils.escapeHtml(template.label)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Method</span>
            <select name="method">
              ${["GET", "POST"].map((method) => `<option value="${method}" ${page.method === method ? "selected" : ""}>${method}</option>`).join("")}
            </select>
          </label>
          <label class="full-span">
            <span>Path / 路径</span>
            <input name="path" value="${utils.escapeHtml(page.path)}" />
          </label>
          <label class="full-span">
            <span>JSON Body / JSON 请求体</span>
            <textarea name="body" rows="10" placeholder='{"symbol":"AAPL"}'>${utils.escapeHtml(page.body)}</textarea>
          </label>
        </form>
        <div class="button-row">
          <button type="button" class="action-button primary" data-send-api>Send Request / 发送</button>
          <button type="button" class="action-button" data-copy-curl>Copy curl / 复制 curl</button>
        </div>
      </section>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">curl</span>
              <h3>Generated curl / 生成命令</h3>
            </div>
          </div>
          <pre class="detail-pre">${utils.escapeHtml(curl)}</pre>
        </article>
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">History / 历史</span>
              <h3>Request History / 请求历史</h3>
            </div>
          </div>
          ${
            page.history.length
              ? utils.renderTable(
                  [
                    { key: "time", label: "Time", render: (row) => utils.escapeHtml(utils.formatDate(row.time)) },
                    { key: "method", label: "Method" },
                    { key: "path", label: "Path" },
                    { key: "status", label: "Status" },
                  ],
                  page.history.slice(-8).reverse(),
                )
              : `<div class="empty-state compact">No requests sent yet.</div>`
          }
        </article>
      </section>

      ${utils.renderJsonPanel("Response / 响应", page.response)}
      ${utils.renderJsonPanel("Error Detail / 错误详情", page.error)}
    `;
  },
  mount(ctx, page, root) {
    const form = root.querySelector("[data-diagnostics-form]");
    const syncForm = () => {
      const data = new FormData(form);
      const oldTemplate = page.template_id;
      page.template_id = String(data.get("template_id") || "health");
      if (page.template_id !== oldTemplate) {
        const template = selectedTemplate(page);
        page.method = template.method;
        page.path = template.path;
        page.body = template.body;
        ctx.rerender();
        return;
      }
      page.method = String(data.get("method") || "GET").toUpperCase();
      page.path = String(data.get("path") || "/health").trim();
      page.body = String(data.get("body") || "");
    };

    form?.addEventListener("input", syncForm);
    form?.addEventListener("change", syncForm);

    root.querySelector("[data-copy-curl]")?.addEventListener("click", async () => {
      syncForm();
      const curl = buildCurl(ctx.api.base, page.method, page.path, page.body);
      try {
        await navigator.clipboard.writeText(curl);
        ctx.toast("curl copied / curl 已复制", "success");
      } catch {
        ctx.toast("Clipboard unavailable / 剪贴板不可用", "error");
      }
    });

    root.querySelector("[data-send-api]")?.addEventListener("click", async () => {
      syncForm();
      ctx.setLoading(true);
      let result;
      try {
        if (page.method === "GET") {
          result = await ctx.api.get(page.path);
        } else {
          const body = page.body.trim() ? JSON.parse(page.body) : {};
          result = await ctx.api.post(page.path, body);
        }
      } catch (error) {
        result = {
          ok: false,
          status: 0,
          url: page.path,
          data: null,
          error: { message: String(error) },
        };
      }
      page.response = result.data;
      page.error = result.error;
      page.history.push({
        time: new Date().toISOString(),
        method: page.method,
        path: page.path,
        status: result.status,
      });
      ctx.setLoading(false);
      ctx.setPageStatus(this.id, {
        tone: result.ok ? "success" : "error",
        title: result.ok ? "Request completed" : "Request failed",
        message: result.ok ? "The response is from the real API." : (result.error?.message || "API returned an error."),
        detail: result.url,
      });
      ctx.rerender();
    });
  },
};
