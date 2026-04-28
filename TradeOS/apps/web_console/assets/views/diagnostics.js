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
          <span class="section-eyebrow">高级诊断 / Advanced diagnostics</span>
          <h2>Diagnostics / Advanced API</h2>
          <p>这里集中放置原始 API 模板、JSON 请求体、响应体、请求历史、curl 复制与错误详情。它刻意与普通产品工作流分离，用于调试、审计与高级排障。</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">真实请求状态 / Real request status</span>
          <span class="endpoint-pill">仅真实 FastAPI / Real FastAPI only</span>
        </div>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">模板 / Templates</span>
            <h3>选择 API 模板 / Choose API Template</h3>
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
            <span>请求方法 / Method</span>
            <select name="method">
              ${["GET", "POST"].map((method) => `<option value="${method}" ${page.method === method ? "selected" : ""}>${method}</option>`).join("")}
            </select>
          </label>
          <label class="full-span">
            <span>Path / 路径</span>
            <input name="path" value="${utils.escapeHtml(page.path)}" />
          </label>
          <label class="full-span">
            <span>JSON 请求体 / JSON Body</span>
            <textarea name="body" rows="10" placeholder='{"symbol":"AAPL"}'>${utils.escapeHtml(page.body)}</textarea>
          </label>
        </form>
        <div class="button-row">
          <button type="button" class="action-button primary" data-send-api>发送请求 / Send Request</button>
          <button type="button" class="action-button" data-copy-curl>复制 curl / Copy curl</button>
        </div>
      </section>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">curl</span>
              <h3>生成命令 / Generated curl</h3>
            </div>
          </div>
          <pre class="detail-pre">${utils.escapeHtml(curl)}</pre>
        </article>
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">历史 / History</span>
              <h3>请求历史 / Request History</h3>
            </div>
          </div>
          ${
            page.history.length
              ? utils.renderTable(
                  [
                    { key: "time", label: "时间 Time", render: (row) => utils.escapeHtml(utils.formatDate(row.time)) },
                    { key: "method", label: "方法 Method" },
                    { key: "path", label: "路径 Path" },
                    { key: "status", label: "状态 Status" },
                  ],
                  page.history.slice(-8).reverse(),
                )
              : `<div class="empty-state compact">尚未发送请求。 / No requests sent yet.</div>`
          }
        </article>
      </section>

      ${utils.renderJsonPanel("响应 / Response", page.response)}
      ${utils.renderJsonPanel("错误详情 / Error Detail", page.error)}
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
        ctx.toast("curl 已复制 / curl copied", "success");
      } catch {
        ctx.toast("剪贴板不可用 / Clipboard unavailable", "error");
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
        title: result.ok ? "请求完成 / Request completed" : "请求失败 / Request failed",
        message: result.ok ? "响应直接来自真实 API。 / The response came from the real API." : (result.error?.message || "API 返回错误。 / API returned an error."),
        detail: result.url,
      });
      ctx.rerender();
    });
  },
};
