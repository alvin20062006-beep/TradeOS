function derivedBundleView(result) {
  const decision = result?.decision;
  if (!decision?.proposals?.length) {
    return [];
  }
  return decision.proposals.map((proposal) => ({
    strategy_id: proposal.strategy_id,
    aggregate_direction: proposal.aggregate_direction,
    aggregate_strength: proposal.aggregate_strength,
    aggregate_confidence: proposal.aggregate_confidence,
    portfolio_weight: proposal.portfolio_weight,
    bundle_count: (proposal.bundles || []).length,
  }));
}

export const strategyPoolView = {
  id: "strategy_pool",
  label: "策略池 Strategy Pool",
  shortLabel: "策略 Pool",
  initialState: {
    form: {
      portfolio_id: "NVDA-SP",
      symbol: "NVDA",
      weight_method: "equal",
      alpha_direction: "LONG",
      alpha_strength: 0.7,
      alpha_confidence: 0.78,
      alpha_weight: 0.6,
      hedge_direction: "FLAT",
      hedge_strength: 0.3,
      hedge_confidence: 0.45,
      hedge_weight: 0.4,
    },
    result: null,
  },
  render(ctx, page) {
    const { utils } = ctx;
    const decision = page.result?.decision;

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">Phase 9 入口 Phase 9 Surface</span>
          <h2>策略池 Strategy Pool</h2>
          <p>向当前策略池接口提交 proposal bundles，并按真实返回展示组合仲裁结果，不伪造任务状态。</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">POST /api/v1/strategy-pool/propose</span>
        </div>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">提案表单 Proposal Form</span>
            <h3>将两条策略组合成一个组合提案 Compose Two Strategies into One Portfolio Proposal</h3>
          </div>
        </div>
        <form data-strategy-pool-form class="form-grid">
          <label><span>组合 ID Portfolio ID</span><input name="portfolio_id" value="${utils.escapeHtml(page.form.portfolio_id)}" /></label>
          <label><span>标的 Symbol</span><input name="symbol" value="${utils.escapeHtml(page.form.symbol)}" /></label>
          <label>
            <span>权重方法 Weight Method</span>
            <select name="weight_method">
              ${["equal", "ir", "risk_parity", "manual"]
                .map((option) => `<option value="${option}" ${page.form.weight_method === option ? "selected" : ""}>${option}</option>`)
                .join("")}
            </select>
          </label>
          <label>
            <span>Alpha 方向 Alpha Direction</span>
            <select name="alpha_direction">
              ${["LONG", "SHORT", "FLAT"]
                .map((option) => `<option value="${option}" ${page.form.alpha_direction === option ? "selected" : ""}>${option}</option>`)
                .join("")}
            </select>
          </label>
          <label><span>Alpha 强度 Alpha Strength</span><input name="alpha_strength" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.form.alpha_strength)}" /></label>
          <label><span>Alpha 置信度 Alpha Confidence</span><input name="alpha_confidence" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.form.alpha_confidence)}" /></label>
          <label><span>Alpha 权重 Alpha Weight</span><input name="alpha_weight" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.form.alpha_weight)}" /></label>
          <label>
            <span>对冲方向 Hedge Direction</span>
            <select name="hedge_direction">
              ${["LONG", "SHORT", "FLAT"]
                .map((option) => `<option value="${option}" ${page.form.hedge_direction === option ? "selected" : ""}>${option}</option>`)
                .join("")}
            </select>
          </label>
          <label><span>对冲强度 Hedge Strength</span><input name="hedge_strength" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.form.hedge_strength)}" /></label>
          <label><span>对冲置信度 Hedge Confidence</span><input name="hedge_confidence" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.form.hedge_confidence)}" /></label>
          <label><span>对冲权重 Hedge Weight</span><input name="hedge_weight" type="number" min="0" max="1" step="0.01" value="${utils.escapeHtml(page.form.hedge_weight)}" /></label>
        </form>
        <div class="button-row">
          <button type="button" class="action-button primary" data-submit-strategy-pool>提交策略池提案 Submit Strategy Pool</button>
        </div>
      </section>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">提案结果 Proposal Result</span>
              <h3>组合决策卡 Portfolio Decision Card</h3>
            </div>
          </div>
          ${
            page.result
              ? utils.renderMetricCards([
                  {
                    label: "任务 Task",
                    value: page.result.task_id || "immediate",
                    sub: page.result.status || "done",
                  },
                  {
                    label: "偏置 Bias",
                    value: decision?.bias || "n/a",
                    sub: `置信度 Confidence ${utils.formatNumber(decision?.confidence)}`,
                  },
                  {
                    label: "组合方向 Composite Direction",
                    value: decision?.composite_direction || "n/a",
                    sub: `强度 Strength ${utils.formatNumber(decision?.composite_strength)}`,
                  },
                ]) +
                utils.renderKeyValueList([
                  { label: "消息 Message", value: page.result.message || "n/a" },
                  { label: "组合 ID Portfolio ID", value: decision?.portfolio_id || "n/a" },
                  { label: "已应用规则 Rules Applied", value: (decision?.rules_applied || []).join(", ") || "none" },
                ])
              : `<div class="empty-state compact">提交策略池提案后，这里会显示真实返回 bundle。 / Submit a strategy pool proposal to see the real response bundle.</div>`
          }
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">ArbitrationInputBundle 视图 Bundle View</span>
              <h3>只读派生 Bundle 展示 Derived Read-only Bundle Display</h3>
            </div>
          </div>
          ${utils.renderTable(
            [
              { key: "strategy_id", label: "策略 Strategy" },
              { key: "aggregate_direction", label: "方向 Direction" },
              {
                key: "aggregate_strength",
                label: "强度 Strength",
                render: (row) => utils.formatNumber(row.aggregate_strength),
              },
              {
                key: "aggregate_confidence",
                label: "置信度 Confidence",
                render: (row) => utils.formatNumber(row.aggregate_confidence),
              },
              {
                key: "portfolio_weight",
                label: "权重 Weight",
                render: (row) => utils.formatNumber(row.portfolio_weight),
              },
              { key: "bundle_count", label: "包数 Bundles" },
            ],
            derivedBundleView(page.result),
            { emptyText: "成功提交后，这里会显示返回的 proposal rows。 / Returned proposal rows will be shown here after a successful submit." },
          )}
        </article>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">返回提案 Returned Proposals</span>
            <h3>组合提案明细 Portfolio Proposal Rows</h3>
          </div>
        </div>
        ${utils.renderTable(
          [
            { key: "proposal_id", label: "提案 Proposal" },
            { key: "strategy_id", label: "策略 Strategy" },
            { key: "aggregate_direction", label: "方向 Direction" },
            {
              key: "aggregate_strength",
              label: "强度 Strength",
              render: (row) => utils.formatNumber(row.aggregate_strength),
            },
            {
              key: "aggregate_confidence",
              label: "置信度 Confidence",
              render: (row) => utils.formatNumber(row.aggregate_confidence),
            },
            {
              key: "portfolio_weight",
              label: "权重 Weight",
              render: (row) => utils.formatNumber(row.portfolio_weight),
            },
          ],
          decision?.proposals || [],
          { emptyText: "当前还没有返回提案。 / No returned proposals yet." },
        )}
      </section>

      ${utils.renderJsonPanel("策略池原始响应 Strategy Pool Raw Response", page.result)}
    `;
  },
  mount(ctx, page, root) {
    const form = root.querySelector("[data-strategy-pool-form]");
    const syncForm = () => {
      const data = new FormData(form);
      Object.keys(page.form).forEach((key) => {
        page.form[key] = data.get(key) ?? page.form[key];
      });
      ["alpha_strength", "alpha_confidence", "alpha_weight", "hedge_strength", "hedge_confidence", "hedge_weight"].forEach((key) => {
        page.form[key] = Number(page.form[key]);
      });
    };

    form?.addEventListener("input", syncForm);
    form?.addEventListener("change", syncForm);

    root.querySelector("[data-submit-strategy-pool]")?.addEventListener("click", async () => {
      syncForm();
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "提交策略池提案 Submitting Strategy Pool Proposal",
        message: "正在调用真实策略池接口。",
        detail: "POST /api/v1/strategy-pool/propose",
      });

      const payload = {
        portfolio_id: page.form.portfolio_id,
        symbol: page.form.symbol,
        weight_method: page.form.weight_method,
        proposals: [
          {
            proposal_id: "alpha-proposal",
            strategy_id: "alpha_core",
            aggregate_direction: page.form.alpha_direction,
            aggregate_strength: page.form.alpha_strength,
            aggregate_confidence: page.form.alpha_confidence,
            portfolio_weight: page.form.alpha_weight,
            bundles: [
              {
                bundle_id: "alpha-bundle",
                source_strategy_id: "alpha_core",
                symbol: page.form.symbol,
                direction: page.form.alpha_direction,
                strength: page.form.alpha_strength,
                confidence: page.form.alpha_confidence,
              },
            ],
          },
          {
            proposal_id: "hedge-proposal",
            strategy_id: "hedge_overlay",
            aggregate_direction: page.form.hedge_direction,
            aggregate_strength: page.form.hedge_strength,
            aggregate_confidence: page.form.hedge_confidence,
            portfolio_weight: page.form.hedge_weight,
            bundles: [
              {
                bundle_id: "hedge-bundle",
                source_strategy_id: "hedge_overlay",
                symbol: page.form.symbol,
                direction: page.form.hedge_direction,
                strength: page.form.hedge_strength,
                confidence: page.form.hedge_confidence,
              },
            ],
          },
        ],
      };

      const result = await ctx.api.post("/api/v1/strategy-pool/propose", payload);
      page.result = result.data;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "策略池提案完成 Strategy Pool Proposal Completed",
          message: result.data?.message || "后端已返回真实决策 bundle。",
          detail: result.data?.decision?.decision_id || "decision id unavailable",
        });
        ctx.toast("策略池提案完成 / Strategy pool proposal completed.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "策略池提案失败 Strategy Pool Proposal Failed",
          message: result.error?.message || "后端返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("策略池提案失败 / Strategy pool proposal failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    });
  },
};
