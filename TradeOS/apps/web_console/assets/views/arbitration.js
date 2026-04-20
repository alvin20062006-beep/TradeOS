function renderDecisionSummary(result, utils, emptyText) {
  if (!result) {
    return `<div class="empty-state compact">${utils.escapeHtml(emptyText)}</div>`;
  }
  return `
    ${utils.renderMetricCards([
      {
        label: "偏置 Bias",
        value: result.bias || "n/a",
        sub: `Decision ${utils.shortText(result.decision_id, 18)}`,
      },
      {
        label: "置信度 Confidence",
        value: utils.formatNumber(result.confidence),
        sub: `信号数量 Signal Count ${result.signal_count ?? "n/a"}`,
      },
      {
        label: "来源 Source",
        value: result.source || "n/a",
        sub: `Latency ${utils.formatNumber(result.arbitration_latency_ms, 1)} ms`,
      },
    ])}
    <div class="mini-card">
      <span class="mini-label">已应用规则 Rules Applied</span>
      <div class="pill-row">${utils.renderPillList(result.rules_applied || [], "success")}</div>
    </div>
  `;
}

export const arbitrationView = {
  id: "arbitration",
  label: "仲裁 Arbitration",
  shortLabel: "决策 Bias",
  initialState: {
    singleForm: {
      symbol: "AAPL",
      direction: "LONG",
      confidence: 0.8,
      strength: 0.6,
      regime: "trending_up",
    },
    portfolioForm: {
      portfolio_id: "AAPL-SP",
      symbol: "AAPL",
      trend_direction: "LONG",
      trend_strength: 0.72,
      trend_confidence: 0.76,
      trend_weight: 0.55,
      mean_direction: "FLAT",
      mean_strength: 0.35,
      mean_confidence: 0.48,
      mean_weight: 0.45,
    },
    singleResult: null,
    portfolioResult: null,
  },
  render(ctx, page) {
    const { utils } = ctx;
    const rationale = page.singleResult?.rationale || [];

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">决策层 Decision Layer</span>
          <h2>仲裁 Arbitration</h2>
          <p>单标的仲裁与组合仲裁都直接调用当前后端。单标的表单只提交后端当前真正接受的 DTO 字段。</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">POST /api/v1/arbitration/run</span>
          <span class="endpoint-pill">POST /api/v1/arbitration/run-portfolio</span>
        </div>
      </section>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">单标的 Single Symbol</span>
              <h3>运行仲裁 Run Arbitration</h3>
            </div>
            <span class="helper-copy">提交字段与后端 ArbitrationRunRequest 保持一致：symbol、direction、confidence、strength、regime。</span>
          </div>
          <form data-single-form class="form-grid">
            <label><span>标的 Symbol</span><input name="symbol" value="${utils.escapeHtml(page.singleForm.symbol)}" /></label>
            <label>
              <span>方向 Direction</span>
              <select name="direction">
                ${["LONG", "SHORT", "FLAT"]
                  .map((option) => `<option value="${option}" ${page.singleForm.direction === option ? "selected" : ""}>${option}</option>`)
                  .join("")}
              </select>
            </label>
            <label>
              <span>市场状态 Regime</span>
              <select name="regime">
                ${["trending_up", "trending_down", "ranging", "volatile", "unknown"]
                  .map((option) => `<option value="${option}" ${page.singleForm.regime === option ? "selected" : ""}>${option}</option>`)
                  .join("")}
              </select>
            </label>
            <label><span>置信度 Confidence</span><input name="confidence" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.singleForm.confidence)}" /></label>
            <label><span>强度 Strength</span><input name="strength" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.singleForm.strength)}" /></label>
          </form>
          <div class="button-row">
            <button type="button" class="action-button primary" data-run-single>运行单标的仲裁 Run Arbitration</button>
          </div>
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">组合入口 Portfolio Entry</span>
              <h3>运行组合仲裁 Run Portfolio Arbitration</h3>
            </div>
          </div>
          <form data-portfolio-form class="form-grid">
            <label><span>组合 ID Portfolio ID</span><input name="portfolio_id" value="${utils.escapeHtml(page.portfolioForm.portfolio_id)}" /></label>
            <label><span>标的 Symbol</span><input name="symbol" value="${utils.escapeHtml(page.portfolioForm.symbol)}" /></label>
            <label>
              <span>趋势方向 Trend Direction</span>
              <select name="trend_direction">
                ${["LONG", "SHORT", "FLAT"]
                  .map((option) => `<option value="${option}" ${page.portfolioForm.trend_direction === option ? "selected" : ""}>${option}</option>`)
                  .join("")}
              </select>
            </label>
            <label><span>趋势强度 Trend Strength</span><input name="trend_strength" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.portfolioForm.trend_strength)}" /></label>
            <label><span>趋势置信度 Trend Confidence</span><input name="trend_confidence" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.portfolioForm.trend_confidence)}" /></label>
            <label><span>趋势权重 Trend Weight</span><input name="trend_weight" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.portfolioForm.trend_weight)}" /></label>
            <label>
              <span>均值方向 Mean Direction</span>
              <select name="mean_direction">
                ${["LONG", "SHORT", "FLAT"]
                  .map((option) => `<option value="${option}" ${page.portfolioForm.mean_direction === option ? "selected" : ""}>${option}</option>`)
                  .join("")}
              </select>
            </label>
            <label><span>均值强度 Mean Strength</span><input name="mean_strength" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.portfolioForm.mean_strength)}" /></label>
            <label><span>均值置信度 Mean Confidence</span><input name="mean_confidence" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.portfolioForm.mean_confidence)}" /></label>
            <label><span>均值权重 Mean Weight</span><input name="mean_weight" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.portfolioForm.mean_weight)}" /></label>
          </form>
          <div class="button-row">
            <button type="button" class="action-button primary" data-run-portfolio>运行组合仲裁 Run Portfolio Arbitration</button>
          </div>
        </article>
      </section>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">单标的结果 Single Result</span>
              <h3>决策卡片 Decision Card</h3>
            </div>
          </div>
          ${renderDecisionSummary(page.singleResult, utils, "提交单标的表单后，这里会显示真实仲裁结果。 / Submit the single-symbol form to see a live arbitration result.")}
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">组合结果 Portfolio Result</span>
              <h3>决策卡片 Decision Card</h3>
            </div>
          </div>
          ${renderDecisionSummary(page.portfolioResult, utils, "提交组合表单后，这里会显示返回的组合仲裁结果。 / Submit the portfolio form to see the returned portfolio arbitration decision.")}
        </article>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">规则与理由 Rules and Rationale</span>
            <h3>单标的理由明细 Single-symbol Rationale Rows</h3>
          </div>
        </div>
        ${utils.renderTable(
          [
            { key: "signal_name", label: "信号 Signal" },
            { key: "direction", label: "方向 Direction" },
            {
              key: "confidence",
              label: "置信度 Confidence",
              render: (row) => utils.formatNumber(row.confidence),
            },
            {
              key: "contribution",
              label: "贡献值 Contribution",
              render: (row) => utils.formatNumber(row.contribution),
            },
            {
              key: "rule_adjustments",
              label: "规则调整 Adjustments",
              render: (row) => utils.escapeHtml((row.rule_adjustments || []).join(", ") || "none"),
            },
          ],
          rationale,
          { emptyText: "单标的仲裁完成后，这里会显示理由行。 / Rationale rows appear after a single-symbol arbitration run." },
        )}
      </section>

      ${utils.renderJsonPanel("单标的仲裁原始响应 Single Arbitration Raw Response", page.singleResult)}
      ${utils.renderJsonPanel("组合仲裁原始响应 Portfolio Arbitration Raw Response", page.portfolioResult)}
    `;
  },
  mount(ctx, page, root) {
    const syncSingle = () => {
      const data = new FormData(root.querySelector("[data-single-form]"));
      Object.keys(page.singleForm).forEach((key) => {
        page.singleForm[key] = data.get(key) ?? page.singleForm[key];
      });
      ["confidence", "strength"].forEach((key) => {
        page.singleForm[key] = Number(page.singleForm[key]);
      });
    };

    const syncPortfolio = () => {
      const data = new FormData(root.querySelector("[data-portfolio-form]"));
      Object.keys(page.portfolioForm).forEach((key) => {
        page.portfolioForm[key] = data.get(key) ?? page.portfolioForm[key];
      });
      ["trend_strength", "trend_confidence", "trend_weight", "mean_strength", "mean_confidence", "mean_weight"].forEach((key) => {
        page.portfolioForm[key] = Number(page.portfolioForm[key]);
      });
    };

    root.querySelector("[data-single-form]")?.addEventListener("input", syncSingle);
    root.querySelector("[data-single-form]")?.addEventListener("change", syncSingle);
    root.querySelector("[data-portfolio-form]")?.addEventListener("input", syncPortfolio);
    root.querySelector("[data-portfolio-form]")?.addEventListener("change", syncPortfolio);

    root.querySelector("[data-run-single]")?.addEventListener("click", async () => {
      syncSingle();
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "运行单标的仲裁 Running Arbitration",
        message: "正在提交单标的仲裁请求。",
        detail: "POST /api/v1/arbitration/run",
      });
      const result = await ctx.api.post("/api/v1/arbitration/run", page.singleForm);
      page.singleResult = result.data;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "单标的仲裁完成 Single-symbol Arbitration Completed",
          message: `当前后端已返回决策 ${result.data?.bias || "n/a"}。`,
          detail: result.data?.decision_id || "decision id unavailable",
        });
        ctx.toast("单标的仲裁完成 / Single-symbol arbitration completed.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "单标的仲裁失败 Single-symbol Arbitration Failed",
          message: result.error?.message || "后端返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("单标的仲裁失败 / Single-symbol arbitration failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    });

    root.querySelector("[data-run-portfolio]")?.addEventListener("click", async () => {
      syncPortfolio();
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "运行组合仲裁 Running Portfolio Arbitration",
        message: "正在提交组合仲裁请求。",
        detail: "POST /api/v1/arbitration/run-portfolio",
      });
      const result = await ctx.api.post("/api/v1/arbitration/run-portfolio", {
        portfolio_id: page.portfolioForm.portfolio_id,
        symbol: page.portfolioForm.symbol,
        proposals: [
          {
            proposal_id: "trend-proposal",
            strategy_id: "trend",
            aggregate_direction: page.portfolioForm.trend_direction,
            aggregate_strength: page.portfolioForm.trend_strength,
            aggregate_confidence: page.portfolioForm.trend_confidence,
            portfolio_weight: page.portfolioForm.trend_weight,
            bundle_count: 1,
          },
          {
            proposal_id: "mean-reversion-proposal",
            strategy_id: "mean_reversion",
            aggregate_direction: page.portfolioForm.mean_direction,
            aggregate_strength: page.portfolioForm.mean_strength,
            aggregate_confidence: page.portfolioForm.mean_confidence,
            portfolio_weight: page.portfolioForm.mean_weight,
            bundle_count: 1,
          },
        ],
      });
      page.portfolioResult = result.data;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "组合仲裁完成 Portfolio Arbitration Completed",
          message: `组合仲裁已成功返回 ${result.data?.bias || "n/a"}。`,
          detail: result.data?.decision_id || "decision id unavailable",
        });
        ctx.toast("组合仲裁完成 / Portfolio arbitration completed.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "组合仲裁失败 Portfolio Arbitration Failed",
          message: result.error?.message || "后端返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("组合仲裁失败 / Portfolio arbitration failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    });
  },
};
