function renderModuleCards(modules, utils) {
  if (!modules?.length) {
    return `<div class="empty-state">先运行实时流水线以查看六大模块结果卡片。 / Run the live pipeline to see six module result cards here.</div>`;
  }
  return `
    <div class="card-grid three-up">
      ${modules
        .map(
          (module) => `
            <article class="module-card">
              <div class="module-head">
                <h4>${utils.escapeHtml(module.module)}</h4>
                <span class="pill pill-${module.status === "ok" || module.status === "ready" ? "success" : "warn"}">${utils.escapeHtml(module.status)}</span>
              </div>
              <dl class="mini-stats">
                <div><dt>Provider</dt><dd>${utils.escapeHtml(module.provider)}</dd></div>
                <div><dt>Adapter</dt><dd>${utils.escapeHtml(module.adapter)}</dd></div>
                <div><dt>Coverage</dt><dd>${utils.escapeHtml(module.coverage_status || module.real_coverage)}</dd></div>
              </dl>
              ${
                module.notes?.length
                  ? `<p class="card-note">${utils.escapeHtml(module.notes.join(" | "))}</p>`
                  : ""
              }
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderPhaseCards(phases, utils) {
  if (!phases?.length) {
    return `<div class="empty-state compact">先运行完整流水线以查看逐阶段结果。 / Run the full pipeline to see phase-by-phase results.</div>`;
  }
  return `
    <div class="card-grid three-up">
      ${phases
        .map(
          (phase) => `
            <article class="phase-card ${phase.ok ? "ok" : "fail"}">
              <span class="mini-label">${utils.escapeHtml(phase.phase)}</span>
              <strong>${phase.ok ? "已完成 Completed" : "失败 Failed"}</strong>
              <p>${utils.formatNumber(phase.duration_ms, 1)} ms</p>
              ${
                phase.error
                  ? `<code>${utils.escapeHtml(phase.error)}</code>`
                  : `<p class="card-note">${utils.escapeHtml(JSON.stringify(phase.detail || {}))}</p>`
              }
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

export const pipelineView = {
  id: "pipeline",
  label: "流水线 Pipeline",
  shortLabel: "运行 Run",
  initialState: {
    form: {
      symbol: "CL=F",
      timeframe: "1d",
      lookback: 90,
      news_limit: 6,
      direction: "LONG",
      confidence: 0.75,
      strength: 0.6,
      regime: "trending_up",
    },
    liveResult: null,
    fullResult: null,
    lastAction: "",
  },
  render(ctx, page) {
    const { utils } = ctx;
    const live = page.liveResult;
    const full = page.fullResult;
    const liveDecision = live?.decision || {};
    const livePlan = live?.plan || {};
    const liveAudit = live?.audit || {};
    const fullDecision = full?.decision || {};
    const fullPlan = full?.plan || {};

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">执行入口 Execution Surface</span>
          <h2>流水线 Pipeline</h2>
          <p>一个表单，两条真实能力：实时流水线读取六大模块市场数据，完整流水线调用当前 Phase 5、6、7 DTO 编排链。</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">POST /api/v1/pipeline/run-live</span>
          <span class="endpoint-pill">POST /api/v1/pipeline/run-full</span>
        </div>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">输入区 Inputs</span>
            <h3>运行实时或完整 TradeOS 流水线 Run TradeOS Live or Full Pipeline</h3>
          </div>
          <span class="helper-copy">实时模式使用 symbol、timeframe、lookback；完整模式使用 direction、regime、confidence 等后端 DTO 字段。</span>
        </div>
        <form data-pipeline-form class="form-grid">
          <label>
            <span>标的 Symbol</span>
            <input name="symbol" value="${utils.escapeHtml(page.form.symbol)}" />
          </label>
          <label>
            <span>周期 Timeframe</span>
            <select name="timeframe">
              ${["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
                .map((option) => `<option value="${option}" ${page.form.timeframe === option ? "selected" : ""}>${option}</option>`)
                .join("")}
            </select>
          </label>
          <label>
            <span>回看长度 Lookback</span>
            <input name="lookback" type="number" min="30" max="1000" value="${utils.escapeHtml(page.form.lookback)}" />
          </label>
          <label>
            <span>新闻数量 News Limit</span>
            <input name="news_limit" type="number" min="1" max="30" value="${utils.escapeHtml(page.form.news_limit)}" />
          </label>
          <label>
            <span>方向 Direction</span>
            <select name="direction">
              ${["LONG", "SHORT", "FLAT"]
                .map((option) => `<option value="${option}" ${page.form.direction === option ? "selected" : ""}>${option}</option>`)
                .join("")}
            </select>
          </label>
          <label>
            <span>市场状态 Regime</span>
            <select name="regime">
              ${["trending_up", "trending_down", "ranging", "volatile", "unknown"]
                .map((option) => `<option value="${option}" ${page.form.regime === option ? "selected" : ""}>${option}</option>`)
                .join("")}
            </select>
          </label>
          <label>
            <span>置信度 Confidence</span>
            <input name="confidence" type="number" step="0.01" min="0" max="1" value="${utils.escapeHtml(page.form.confidence)}" />
          </label>
          <label>
            <span>强度 Strength</span>
            <input name="strength" type="number" step="0.01" min="0" max="1" value="${utils.escapeHtml(page.form.strength)}" />
          </label>
        </form>
        <div class="chip-row">
          ${["AAPL", "NVDA", "MSFT", "SPY", "CL=F", "BTC-USD"]
            .map((symbol) => `<button type="button" class="chip-button" data-symbol-chip="${symbol}">${symbol}</button>`)
            .join("")}
        </div>
        <div class="button-row">
          <button type="button" class="action-button primary" data-run-live>运行实时流水线 Run Live Pipeline</button>
          <button type="button" class="action-button" data-run-full>运行完整流水线 Run Full Pipeline</button>
        </div>
      </section>

      ${utils.renderMetricCards([
        {
          label: "最近动作 Latest Action",
          value: page.lastAction || "none",
          sub: "最近一次调用的流水线接口 / Most recent pipeline endpoint called",
        },
        {
          label: "实时偏置 Live Bias",
          value: liveDecision.bias || "n/a",
          sub: `置信度 Confidence ${utils.formatNumber(liveDecision.confidence)}`,
        },
        {
          label: "完整状态 Full Status",
          value: full?.status || "n/a",
          sub: `任务 Task ${full?.task_id || "n/a"}`,
        },
        {
          label: "最终数量 Final Quantity",
          value: utils.formatNumber(livePlan.final_quantity ?? fullPlan.final_quantity),
          sub: `风控否决 Veto ${String(livePlan.veto_triggered ?? fullPlan.veto_triggered ?? "n/a")}`,
        },
      ])}

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">实时流水线 Live Pipeline</span>
              <h3>摘要 Summary</h3>
            </div>
          </div>
          ${
            live
              ? utils.renderKeyValueList([
                  { label: "标的 Symbol", value: live.data?.symbol || "n/a" },
                  { label: "周期 Timeframe", value: live.data?.timeframe || "n/a" },
                  { label: "K 线数量 Bars", value: live.data?.bar_count ?? "n/a" },
                  { label: "偏置 Bias", value: liveDecision.bias || "n/a" },
                  { label: "方向 Direction", value: liveDecision.bias_direction || "n/a" },
                  { label: "决策审计 Decision Record", value: liveAudit.decision_record_id || "n/a" },
                ])
              : `<div class="empty-state compact">运行实时流水线后，这里会显示市场摘要、决策、计划、审计与六模块输出。 / Run the live pipeline to populate live market summary, decision, plan, audit, and six-module output.</div>`
          }
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">完整流水线 Full Pipeline</span>
              <h3>摘要 Summary</h3>
            </div>
          </div>
          ${
            full
              ? utils.renderKeyValueList([
                  { label: "标的 Symbol", value: full.symbol || "n/a" },
                  { label: "状态 Status", value: full.status || "n/a" },
                  { label: "决策偏置 Decision Bias", value: fullDecision.bias || "n/a" },
                  { label: "决策置信度 Decision Confidence", value: utils.formatNumber(fullDecision.confidence) },
                  { label: "计划数量 Plan Quantity", value: utils.formatNumber(fullPlan.final_quantity) },
                  { label: "风控否决 Veto Triggered", value: String(fullPlan.veto_triggered ?? "n/a") },
                ])
              : `<div class="empty-state compact">运行完整流水线后，这里会显示当前 DTO 编排链的同步输出。 / Run the full pipeline to see synchronous orchestration output from the current DTO path.</div>`
          }
        </article>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">六大模块 Six Modules</span>
            <h3>实时模块卡片 Live Module Cards</h3>
          </div>
          <span class="helper-copy">这些卡片直接来自 /api/v1/pipeline/run-live 的真实返回。</span>
        </div>
        ${renderModuleCards(live?.modules, utils)}
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">阶段追踪 Phase Trace</span>
            <h3>完整流水线阶段卡片 Full Pipeline Phase Cards</h3>
          </div>
        </div>
        ${renderPhaseCards(full?.phases, utils)}
      </section>

      ${utils.renderJsonPanel("实时流水线原始响应 Live Pipeline Raw Response", live)}
      ${utils.renderJsonPanel("完整流水线原始响应 Full Pipeline Raw Response", full)}
    `;
  },
  mount(ctx, page, root) {
    const form = root.querySelector("[data-pipeline-form]");

    const syncForm = () => {
      const data = new FormData(form);
      page.form.symbol = String(data.get("symbol") || "").trim();
      page.form.timeframe = String(data.get("timeframe") || "1d");
      page.form.lookback = Number(data.get("lookback") || 90);
      page.form.news_limit = Number(data.get("news_limit") || 6);
      page.form.direction = String(data.get("direction") || "LONG");
      page.form.regime = String(data.get("regime") || "trending_up");
      page.form.confidence = Number(data.get("confidence") || 0.75);
      page.form.strength = Number(data.get("strength") || 0.6);
    };

    form?.addEventListener("input", syncForm);
    form?.addEventListener("change", syncForm);

    root.querySelectorAll("[data-symbol-chip]").forEach((button) => {
      button.addEventListener("click", () => {
        page.form.symbol = button.getAttribute("data-symbol-chip") || page.form.symbol;
        ctx.rerender();
      });
    });

    const runLive = async () => {
      syncForm();
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "运行实时流水线 Running Live Pipeline",
        message: "正在用真实市场数据输入调用实时流水线。",
        detail: "POST /api/v1/pipeline/run-live",
      });

      const result = await ctx.api.post("/api/v1/pipeline/run-live", {
        symbol: page.form.symbol,
        timeframe: page.form.timeframe,
        lookback: page.form.lookback,
        news_limit: page.form.news_limit,
      });

      page.lastAction = "run-live";
      page.liveResult = result.data;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "实时流水线完成 Live Pipeline Completed",
          message: `实时流水线已返回 ${result.data?.decision?.bias || "n/a"} 决策，标的 ${page.form.symbol}。`,
          detail: "下方结果均来自实时 FastAPI 接口。",
        });
        ctx.toast("实时流水线已完成 / Live pipeline completed.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "实时流水线失败 Live Pipeline Failed",
          message: result.error?.message || "实时接口返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("实时流水线失败 / Live pipeline failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    };

    const runFull = async () => {
      syncForm();
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "运行完整流水线 Running Full Pipeline",
        message: "正在调用当前 Phase 5、6、7 的同步 DTO 编排路径。",
        detail: "POST /api/v1/pipeline/run-full",
      });

      const result = await ctx.api.post("/api/v1/pipeline/run-full", {
        symbol: page.form.symbol,
        direction: page.form.direction,
        confidence: page.form.confidence,
        strength: page.form.strength,
        regime: page.form.regime,
      });

      page.lastAction = "run-full";
      page.fullResult = result.data;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "完整流水线完成 Full Pipeline Completed",
          message: `完整流水线已返回当前后端状态 ${result.data?.status || "done"}。`,
          detail: `任务 Task ${result.data?.task_id || "immediate"} 同步完成。`,
        });
        ctx.toast("完整流水线已完成 / Full pipeline completed.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "完整流水线失败 Full Pipeline Failed",
          message: result.error?.message || "完整流水线接口返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("完整流水线失败 / Full pipeline failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    };

    root.querySelector("[data-run-live]")?.addEventListener("click", runLive);
    root.querySelector("[data-run-full]")?.addEventListener("click", runFull);
  },
};
