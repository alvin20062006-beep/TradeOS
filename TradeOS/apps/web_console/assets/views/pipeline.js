const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"];
const MARKET_TYPES = ["auto", "equity", "commodity", "crypto", "fx", "index"];

function coverageTone(status) {
  if (status === "REAL") return "success";
  if (status === "PROXY") return "warn";
  if (status === "PLACEHOLDER") return "neutral";
  return "danger";
}

function parseRawJson(value) {
  if (!value || !value.trim()) return {};
  return JSON.parse(value);
}

function moduleMetric(module, utils) {
  return `
    <article class="module-card">
      <div class="module-head">
        <h4>${utils.escapeHtml(module.module)}</h4>
        <span class="pill pill-${coverageTone(module.coverage_status)}">${utils.escapeHtml(module.coverage_status)}</span>
      </div>
      <dl class="mini-stats">
        <div><dt>Input / 输入</dt><dd>${utils.escapeHtml((module.input_data || []).join(", ") || "n/a")}</dd></div>
        <div><dt>Provider</dt><dd>${utils.escapeHtml(module.provider || "n/a")}</dd></div>
        <div><dt>Adapter</dt><dd>${utils.escapeHtml(module.adapter || "n/a")}</dd></div>
        <div><dt>Latest / 最新</dt><dd>${utils.escapeHtml(module.latest_data_time ? utils.formatDate(module.latest_data_time) : "n/a")}</dd></div>
        <div><dt>Rows / 条数</dt><dd>${utils.escapeHtml(module.data_count ?? "n/a")}</dd></div>
        <div><dt>Direction / 方向</dt><dd>${utils.escapeHtml(module.output_direction || "n/a")}</dd></div>
        <div><dt>Confidence</dt><dd>${utils.escapeHtml(module.confidence === null || module.confidence === undefined ? "n/a" : utils.formatNumber(module.confidence))}</dd></div>
      </dl>
      ${module.placeholder_fields?.length ? `<p class="card-note">Gaps / 缺口: ${utils.escapeHtml(module.placeholder_fields.join(", "))}</p>` : ""}
      ${module.notes?.length ? `<p class="card-note">${utils.escapeHtml(module.notes.join(" | "))}</p>` : ""}
      ${utils.renderJsonPanel(`Raw ${module.module} / 原始响应`, module.raw_response, "No raw response.")}
    </article>
  `;
}

function renderModuleCards(modules, utils) {
  if (!modules?.length) {
    return `<div class="empty-state">Run Six-Module Analysis or Full TradeOS Loop to see module results. / 运行六模块分析或完整闭环后查看结果。</div>`;
  }
  const preferred = ["Fundamental", "Macro", "Technical", "Chan", "OrderFlow", "Sentiment"];
  const ordered = preferred
    .map((name) => modules.find((module) => module.module === name))
    .filter(Boolean);
  return `<div class="card-grid three-up">${ordered.map((module) => moduleMetric(module, utils)).join("")}</div>`;
}

function renderSection(title, subtitle, body) {
  return `
    <article class="panel-card">
      <div class="panel-head">
        <div>
          <span class="panel-kicker">${subtitle}</span>
          <h3>${title}</h3>
        </div>
      </div>
      ${body}
    </article>
  `;
}

export const pipelineView = {
  id: "pipeline",
  label: "Pipeline / 流水线",
  shortLabel: "Pipeline",
  initialState: {
    form: {
      symbol: "AAPL",
      market_type: "equity",
      timeframe: "1d",
      lookback: 90,
      profile_id: "default-live",
      news_limit: 6,
      execution_mode: "simulation",
      direction: "LONG",
      confidence: 0.75,
      strength: 0.6,
      regime: "trending_up",
      raw_json: "",
    },
    analysisResult: null,
    loopResult: null,
    sourceTestResult: null,
    lastAction: "",
  },
  render(ctx, page) {
    const { utils } = ctx;
    const analysis = page.analysisResult;
    const loop = page.loopResult;
    const data = loop?.data || analysis?.data || {};
    const modules = loop?.modules || analysis?.modules || [];
    const decision = loop?.decision || {};
    const plan = loop?.plan || {};
    const execution = loop?.execution || {};
    const audit = loop?.audit || {};
    const feedback = loop?.feedback || {};
    const suggestions = loop?.suggestions || [];
    const explanation = loop?.explanation || {};
    const watchPlan = loop?.watch_plan || {};
    const dataStatus = loop?.data_status || {};

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">Target-first workflow / 目标驱动工作流</span>
          <h2>Pipeline / 流水线</h2>
          <p>Users choose a target and data profile; TradeOS pulls data, runs six modules, arbitrates, plans risk, simulates execution, audits, and returns feedback. No manual signal fabrication is required.</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">POST /api/v1/analysis/run-live</span>
          <span class="endpoint-pill">POST /api/v1/pipeline/run-live</span>
          <span class="endpoint-pill">POST /api/v1/data-sources/test</span>
        </div>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Inputs / 输入</span>
            <h3>Run by target, not by hand-made signals / 输入目标，不手造信号</h3>
          </div>
        </div>
        <form data-pipeline-form class="form-grid">
          <label>
            <span>Symbol / 标的</span>
            <input name="symbol" value="${utils.escapeHtml(page.form.symbol)}" />
          </label>
          <label>
            <span>Market Type / 市场类型</span>
            <select name="market_type">
              ${MARKET_TYPES.map((option) => `<option value="${option}" ${page.form.market_type === option ? "selected" : ""}>${option}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Timeframe / 周期</span>
            <select name="timeframe">
              ${TIMEFRAMES.map((option) => `<option value="${option}" ${page.form.timeframe === option ? "selected" : ""}>${option}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>Lookback / 回看</span>
            <input name="lookback" type="number" min="30" max="1000" value="${utils.escapeHtml(page.form.lookback)}" />
          </label>
          <label>
            <span>Data Source Profile / 数据源 Profile</span>
            <input name="profile_id" value="${utils.escapeHtml(page.form.profile_id)}" />
          </label>
          <label>
            <span>News Limit / 新闻数量</span>
            <input name="news_limit" type="number" min="1" max="30" value="${utils.escapeHtml(page.form.news_limit)}" />
          </label>
          <label>
            <span>Execution Mode / 执行模式</span>
            <select name="execution_mode">
              <option value="simulation" ${page.form.execution_mode === "simulation" ? "selected" : ""}>simulation</option>
            </select>
          </label>
          <details class="json-panel full-span">
            <summary>Advanced manual DTO fields / 高级手工字段</summary>
            <div class="form-grid nested-form">
              <label>
                <span>Direction</span>
                <select name="direction">
                  ${["LONG", "SHORT", "FLAT"].map((option) => `<option value="${option}" ${page.form.direction === option ? "selected" : ""}>${option}</option>`).join("")}
                </select>
              </label>
              <label>
                <span>Confidence</span>
                <input name="confidence" type="number" step="0.01" min="0" max="1" value="${utils.escapeHtml(page.form.confidence)}" />
              </label>
              <label>
                <span>Strength</span>
                <input name="strength" type="number" step="0.01" min="0" max="1" value="${utils.escapeHtml(page.form.strength)}" />
              </label>
              <label>
                <span>Regime</span>
                <select name="regime">
                  ${["trending_up", "trending_down", "ranging", "volatile", "unknown"].map((option) => `<option value="${option}" ${page.form.regime === option ? "selected" : ""}>${option}</option>`).join("")}
                </select>
              </label>
              <label class="full-span">
                <span>Raw JSON override / 原始 JSON 覆盖</span>
                <textarea name="raw_json" rows="5" placeholder='{"symbol":"AAPL"}'>${utils.escapeHtml(page.form.raw_json)}</textarea>
              </label>
            </div>
          </details>
        </form>
        <div class="chip-row">
          ${["AAPL", "NVDA", "MSFT", "SPY", "CL=F", "BTC-USD"].map((symbol) => `<button type="button" class="chip-button" data-symbol-chip="${symbol}">${symbol}</button>`).join("")}
        </div>
        <div class="button-row">
          <button type="button" class="action-button primary" data-run-analysis>Run Six-Module Analysis / 运行六模块分析</button>
          <button type="button" class="action-button" data-run-loop>Run Full TradeOS Loop / 运行完整闭环</button>
          <button type="button" class="action-button" data-test-sources>Test Data Sources / 只测试数据源</button>
        </div>
      </section>

      ${utils.renderMetricCards([
        { label: "Latest Action / 最近动作", value: page.lastAction || "none", sub: "The most recent real API call." },
        { label: "Profile / 数据源", value: data.profile_id || page.form.profile_id, sub: `market_type=${data.market_type || page.form.market_type}` },
        { label: "Decision / 仲裁", value: decision.bias || "n/a", sub: `confidence=${utils.formatNumber(decision.confidence)}` },
        { label: "Execution / 执行", value: execution.status || "n/a", sub: `mode=${execution.mode || page.form.execution_mode}` },
      ])}

      <section class="panel-grid two-up">
        ${renderSection(
          "Data Summary / 数据摘要",
          "Data",
          data.symbol
            ? utils.renderKeyValueList([
                { label: "Symbol", value: data.symbol },
                { label: "Market Type", value: data.market_type },
                { label: "Timeframe", value: data.timeframe },
                { label: "Lookback", value: data.lookback },
                { label: "Bars", value: data.bar_count },
                { label: "Intraday Bars", value: data.intraday_bar_count },
                { label: "Latest Timestamp", value: utils.formatDate(data.latest_timestamp) },
              ])
            : `<div class="empty-state compact">No live data response yet.</div>`,
        )}
        ${renderSection(
          "Arbitration Decision / 仲裁决策",
          "Phase 6",
          decision.decision_id
            ? utils.renderKeyValueList([
                { label: "Decision ID", value: decision.decision_id },
                { label: "Bias", value: decision.bias },
                { label: "Direction", value: decision.bias_direction },
                { label: "Confidence", value: utils.formatNumber(decision.confidence) },
                { label: "Signal Count", value: decision.signal_count },
              ])
            : `<div class="empty-state compact">Run the full loop to see arbitration.</div>`,
        )}
        ${renderSection(
          "Risk Plan / 风控计划",
          "Phase 7",
          plan.plan_id
            ? utils.renderKeyValueList([
                { label: "Plan ID", value: plan.plan_id },
                { label: "Direction", value: plan.direction },
                { label: "Final Quantity", value: utils.formatNumber(plan.final_quantity) },
                { label: "Veto", value: String(plan.veto_triggered) },
              ])
            : `<div class="empty-state compact">Run the full loop to see risk planning.</div>`,
        )}
        ${renderSection(
          "Execution Simulation / 执行仿真",
          "Execution",
          execution.status
            ? utils.renderKeyValueList([
                { label: "Mode", value: execution.mode },
                { label: "Status", value: execution.status },
                { label: "Fill Count", value: execution.fill_count },
                { label: "Filled Qty", value: utils.formatNumber(execution.total_filled_qty) },
                { label: "Avg Price", value: utils.formatNumber(execution.avg_execution_price) },
                { label: "Execution Audit", value: execution.execution_record_id },
              ])
            : `<div class="empty-state compact">Execution is simulation-only in the default product profile.</div>`,
        )}
        ${renderSection(
          "Audit Records / 审计记录",
          "Append-only",
          audit.decision_record_id
            ? utils.renderKeyValueList([
                { label: "Decision Record", value: audit.decision_record_id },
                { label: "Risk Audit", value: audit.risk_audit_id },
                { label: "Execution Record", value: audit.execution_record_id },
                { label: "Feedback Appended", value: String(audit.feedback_registry_appended) },
              ])
            : `<div class="empty-state compact">Run the full loop to write audit records.</div>`,
        )}
        ${renderSection(
          "Feedback Suggestions / 反馈建议",
          "Feedback",
          feedback.items?.length
            ? utils.renderTable(
                [
                  { key: "feedback_id", label: "ID" },
                  { key: "feedback_type", label: "Type" },
                  { key: "severity", label: "Severity" },
                ],
                feedback.items,
              )
            : `<div class="empty-state compact">No feedback suggestions returned yet.</div>`,
        )}
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Six Modules / 六大模块</span>
            <h3>Module Inputs and Outputs / 模块输入与输出</h3>
          </div>
        </div>
        ${renderModuleCards(modules, utils)}
      </section>

      ${utils.renderJsonPanel("Data Source Test Raw / 数据源测试原始响应", page.sourceTestResult)}
      ${utils.renderJsonPanel("Six-Module Analysis Raw / 六模块分析原始响应", analysis)}
      ${utils.renderJsonPanel("Full TradeOS Loop Raw / 完整闭环原始响应", loop)}
    `;
  },
  mount(ctx, page, root) {
    const form = root.querySelector("[data-pipeline-form]");

    const syncForm = () => {
      const data = new FormData(form);
      page.form.symbol = String(data.get("symbol") || "").trim();
      page.form.market_type = String(data.get("market_type") || "auto");
      page.form.timeframe = String(data.get("timeframe") || "1d");
      page.form.lookback = Number(data.get("lookback") || 90);
      page.form.profile_id = String(data.get("profile_id") || "default-live").trim();
      page.form.news_limit = Number(data.get("news_limit") || 6);
      page.form.execution_mode = String(data.get("execution_mode") || "simulation");
      page.form.direction = String(data.get("direction") || "LONG");
      page.form.confidence = Number(data.get("confidence") || 0.75);
      page.form.strength = Number(data.get("strength") || 0.6);
      page.form.regime = String(data.get("regime") || "trending_up");
      page.form.raw_json = String(data.get("raw_json") || "");
    };

    const livePayload = () => ({
      symbol: page.form.symbol,
      market_type: page.form.market_type,
      timeframe: page.form.timeframe,
      lookback: page.form.lookback,
      profile_id: page.form.profile_id,
      news_limit: page.form.news_limit,
      ...parseRawJson(page.form.raw_json),
    });

    form?.addEventListener("input", syncForm);
    form?.addEventListener("change", syncForm);

    root.querySelectorAll("[data-symbol-chip]").forEach((button) => {
      button.addEventListener("click", () => {
        page.form.symbol = button.getAttribute("data-symbol-chip") || page.form.symbol;
        ctx.rerender();
      });
    });

    root.querySelector("[data-run-analysis]")?.addEventListener("click", async () => {
      try {
        syncForm();
        ctx.setLoading(true);
        ctx.setPageStatus(this.id, {
          tone: "loading",
          title: "Running six-module analysis",
          message: "Calling the real live analysis endpoint with target and data profile.",
          detail: "POST /api/v1/analysis/run-live",
        });
        const result = await ctx.api.post("/api/v1/analysis/run-live", livePayload());
        page.lastAction = "analysis/run-live";
        page.analysisResult = result.data;
        ctx.setPageStatus(this.id, {
          tone: result.ok ? "success" : "error",
          title: result.ok ? "Six-module analysis completed" : "Six-module analysis failed",
          message: result.ok ? "Module results came from the backend live analysis path." : (result.error?.message || "Request failed."),
          detail: result.url,
        });
      } catch (error) {
        ctx.setPageStatus(this.id, { tone: "error", title: "Invalid advanced JSON", message: String(error), detail: "raw_json" });
      } finally {
        ctx.setLoading(false);
        ctx.rerender();
      }
    });

    root.querySelector("[data-run-loop]")?.addEventListener("click", async () => {
      try {
        syncForm();
        ctx.setLoading(true);
        ctx.setPageStatus(this.id, {
          tone: "loading",
          title: "Running full TradeOS loop",
          message: "Calling Data -> Analysis -> Arbitration -> Risk -> Execution(simulation) -> Audit -> Feedback.",
          detail: "POST /api/v1/pipeline/run-live",
        });
        const result = await ctx.api.post("/api/v1/pipeline/run-live", livePayload());
        page.lastAction = "pipeline/run-live";
        page.loopResult = result.data;
        ctx.setPageStatus(this.id, {
          tone: result.ok ? "success" : "error",
          title: result.ok ? "Full TradeOS loop completed" : "Full TradeOS loop failed",
          message: result.ok ? "The full backend loop returned decision, risk, execution, audit, and feedback objects." : (result.error?.message || "Request failed."),
          detail: result.url,
        });
      } catch (error) {
        ctx.setPageStatus(this.id, { tone: "error", title: "Invalid advanced JSON", message: String(error), detail: "raw_json" });
      } finally {
        ctx.setLoading(false);
        ctx.rerender();
      }
    });

    root.querySelector("[data-test-sources]")?.addEventListener("click", async () => {
      syncForm();
      ctx.setLoading(true);
      const profilesResult = await ctx.api.get("/api/v1/data-sources/profiles");
      const profile =
        profilesResult.data?.profiles?.find((item) => item.profile_id === page.form.profile_id) ||
        profilesResult.data?.profiles?.find((item) => item.profile_id === "default-live");
      const providerIds = profile
        ? [
            profile.market_provider,
            profile.fundamental_provider,
            profile.macro_provider,
            profile.news_provider,
            profile.orderflow_provider,
            profile.sentiment_provider,
            profile.execution_provider,
          ]
        : [];
      const tests = [];
      for (const providerId of [...new Set(providerIds)]) {
        tests.push(await ctx.api.post("/api/v1/data-sources/test", { provider_id: providerId, symbol: page.form.symbol }));
      }
      page.lastAction = "data-sources/test";
      page.sourceTestResult = { profile, tests: tests.map((item) => item.data?.result || item.error) };
      ctx.setLoading(false);
      ctx.setPageStatus(this.id, {
        tone: tests.every((item) => item.ok) ? "success" : "error",
        title: "Data source tests completed",
        message: "Every result is returned by /api/v1/data-sources/test; PLACEHOLDER providers intentionally do not pass.",
        detail: "POST /api/v1/data-sources/test",
      });
      ctx.rerender();
    });
  },
};
