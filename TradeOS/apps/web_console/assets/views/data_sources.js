const CATEGORY_LABELS = {
  market: "Market Data / 行情数据",
  fundamental: "Fundamental / 基本面",
  macro: "Macro / 宏观数据",
  news: "News / 新闻数据",
  orderflow: "OrderFlow / 订单流",
  sentiment: "Sentiment / 情绪",
  execution: "Execution / 执行",
};

const PROFILE_FIELDS = [
  ["market_provider", "Market Data / 行情数据", "market"],
  ["fundamental_provider", "Fundamental / 基本面", "fundamental"],
  ["macro_provider", "Macro / 宏观数据", "macro"],
  ["news_provider", "News / 新闻数据", "news"],
  ["orderflow_provider", "OrderFlow / 订单流", "orderflow"],
  ["sentiment_provider", "Sentiment / 情绪", "sentiment"],
  ["execution_provider", "Execution / 执行", "execution"],
];

function clone(value) {
  return structuredClone(value);
}

function statusTone(status) {
  if (status === "REAL") return "success";
  if (status === "PROXY") return "warn";
  if (status === "PLACEHOLDER") return "neutral";
  return "danger";
}

function providersFor(capabilities, category) {
  return capabilities.filter((cap) => cap.category === category);
}

function renderProviderSelect(page, utils, field, label, category) {
  const options = providersFor(page.capabilities, category);
  return `
    <label>
      <span>${utils.escapeHtml(label)}</span>
      <select name="${utils.escapeHtml(field)}">
        ${options
          .map(
            (cap) => `
              <option value="${utils.escapeHtml(cap.provider_id)}" ${page.profile[field] === cap.provider_id ? "selected" : ""}>
                ${utils.escapeHtml(cap.display_name)} - ${utils.escapeHtml(cap.status)}
              </option>
            `,
          )
          .join("")}
      </select>
    </label>
  `;
}

function renderCapabilityCard(cap, page, utils) {
  const result = page.testResults[cap.provider_id];
  return `
    <article class="module-card">
      <div class="module-head">
        <h4>${utils.escapeHtml(cap.display_name)}</h4>
        <span class="pill pill-${statusTone(cap.status)}">${utils.escapeHtml(cap.status)}</span>
      </div>
      <dl class="mini-stats">
        <div><dt>Provider</dt><dd>${utils.escapeHtml(cap.provider)}</dd></div>
        <div><dt>Adapter</dt><dd>${utils.escapeHtml(cap.adapter)}</dd></div>
        <div><dt>Testable</dt><dd>${cap.testable ? "yes" : "no"}</dd></div>
      </dl>
      ${cap.notes?.length ? `<p class="card-note">${utils.escapeHtml(cap.notes.join(" | "))}</p>` : ""}
      <div class="button-row compact">
        <button type="button" class="action-button" data-test-provider="${utils.escapeHtml(cap.provider_id)}">
          Test Connection / 测试连接
        </button>
      </div>
      ${
        result
          ? `<div class="status-box tone-${result.ok ? "success" : "error"} compact">
              <strong>${utils.escapeHtml(result.status)} @ ${utils.formatDate(result.tested_at)}</strong>
              <p>${utils.escapeHtml(result.message)}</p>
              ${result.detail?.error ? `<code>${utils.escapeHtml(result.detail.error)}</code>` : ""}
            </div>`
          : ""
      }
    </article>
  `;
}

function renderCategory(category, caps, page, utils) {
  return `
    <section class="panel-card">
      <div class="panel-head">
        <div>
          <span class="panel-kicker">${utils.escapeHtml(category.toUpperCase())}</span>
          <h3>${utils.escapeHtml(CATEGORY_LABELS[category] || category)}</h3>
        </div>
      </div>
      <div class="card-grid three-up">
        ${caps.map((cap) => renderCapabilityCard(cap, page, utils)).join("")}
      </div>
    </section>
  `;
}

export const dataSourcesView = {
  id: "data_sources",
  label: "Data Sources / 数据源",
  shortLabel: "Sources",
  initialState: {
    loaded: false,
    loading: false,
    symbol: "AAPL",
    profile: {
      profile_id: "default-live",
      market_provider: "yahoo_market",
      fundamental_provider: "yahoo_fundamentals",
      macro_provider: "fred_macro",
      news_provider: "yahoo_news",
      orderflow_provider: "intraday_bars_proxy",
      sentiment_provider: "news_sentiment",
      execution_provider: "simulation_execution",
      enabled: true,
      notes: "Default local profile.",
    },
    profiles: [],
    capabilities: [],
    testResults: {},
    lastSave: null,
  },
  render(ctx, page) {
    const { utils } = ctx;
    const capsByCategory = page.capabilities.reduce((acc, cap) => {
      acc[cap.category] = acc[cap.category] || [];
      acc[cap.category].push(cap);
      return acc;
    }, {});

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">Provider Profiles / 数据源配置</span>
          <h2>Data Sources / 数据源</h2>
          <p>
            Configure the provider profile used by live pipeline. REAL providers can be tested;
            PROXY and PLACEHOLDER providers are shown explicitly so reserved integrations are not
            presented as completed capabilities.
          </p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">GET /api/v1/data-sources/capabilities</span>
          <span class="endpoint-pill">POST /api/v1/data-sources/test</span>
          <span class="endpoint-pill">POST /api/v1/data-sources/profiles</span>
        </div>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Profile / 配置档</span>
            <h3>Live Pipeline Data Source Profile / 实时流水线数据源配置</h3>
          </div>
          <span class="helper-copy">Pipeline can now send symbol, timeframe, market type, and profile_id.</span>
        </div>
        <form data-source-profile-form class="form-grid">
          <label>
            <span>Profile ID / 配置 ID</span>
            <input name="profile_id" value="${utils.escapeHtml(page.profile.profile_id)}" />
          </label>
          <label>
            <span>Test Symbol / 测试标的</span>
            <input name="symbol" value="${utils.escapeHtml(page.symbol)}" />
          </label>
          ${PROFILE_FIELDS.map(([field, label, category]) => renderProviderSelect(page, utils, field, label, category)).join("")}
          <label>
            <span>Enabled / 启用</span>
            <select name="enabled">
              <option value="true" ${page.profile.enabled ? "selected" : ""}>true</option>
              <option value="false" ${!page.profile.enabled ? "selected" : ""}>false</option>
            </select>
          </label>
          <label class="full-span">
            <span>Notes / 备注</span>
            <textarea name="notes" rows="3">${utils.escapeHtml(page.profile.notes || "")}</textarea>
          </label>
        </form>
        <div class="button-row">
          <button type="button" class="action-button primary" data-save-profile>Save Profile / 保存配置</button>
          <button type="button" class="action-button" data-set-default>Set Default / 设为默认</button>
          <button type="button" class="action-button" data-refresh-sources>Refresh / 刷新</button>
        </div>
        ${
          page.lastSave
            ? `<div class="status-box tone-success compact"><strong>Saved / 已保存</strong><p>${utils.escapeHtml(page.lastSave.profile_id)}</p></div>`
            : ""
        }
      </section>

      ${Object.entries(CATEGORY_LABELS)
        .map(([category]) => renderCategory(category, capsByCategory[category] || [], page, utils))
        .join("")}

      ${utils.renderJsonPanel("Profiles Raw Response / 配置原始响应", page.profiles)}
      ${utils.renderJsonPanel("Capabilities Raw Response / 能力边界原始响应", page.capabilities)}
    `;
  },
  mount(ctx, page, root) {
    const syncForm = () => {
      const form = root.querySelector("[data-source-profile-form]");
      if (!form) return;
      const data = new FormData(form);
      page.symbol = String(data.get("symbol") || "AAPL").trim();
      page.profile.profile_id = String(data.get("profile_id") || "default-live").trim();
      PROFILE_FIELDS.forEach(([field]) => {
        page.profile[field] = String(data.get(field) || page.profile[field]);
      });
      page.profile.enabled = String(data.get("enabled") || "true") === "true";
      page.profile.notes = String(data.get("notes") || "");
    };

    const loadSources = async () => {
      if (page.loading) return;
      page.loading = true;
      ctx.setLoading(true);
      const [profilesResult, capabilitiesResult] = await Promise.all([
        ctx.api.get("/api/v1/data-sources/profiles"),
        ctx.api.get("/api/v1/data-sources/capabilities"),
      ]);
      if (profilesResult.ok) {
        page.profiles = profilesResult.data.profiles || [];
        const current =
          page.profiles.find((item) => item.profile_id === page.profile.profile_id) ||
          page.profiles.find((item) => item.profile_id === profilesResult.data.default_profile_id);
        if (current) {
          page.profile = clone(current);
        }
      }
      if (capabilitiesResult.ok) {
        page.capabilities = capabilitiesResult.data.capabilities || [];
      }
      page.loaded = true;
      page.loading = false;
      ctx.setLoading(false);
      ctx.setPageStatus(this.id, {
        tone: profilesResult.ok && capabilitiesResult.ok ? "success" : "error",
        title: profilesResult.ok && capabilitiesResult.ok ? "Data sources loaded" : "Data sources load failed",
        message: profilesResult.ok && capabilitiesResult.ok
          ? "Provider profiles and capability boundaries are loaded from the real API."
          : "One or more data source API calls failed.",
        detail: "/api/v1/data-sources/*",
      });
      ctx.rerender();
    };

    root.querySelector("[data-source-profile-form]")?.addEventListener("input", syncForm);
    root.querySelector("[data-source-profile-form]")?.addEventListener("change", syncForm);
    root.querySelector("[data-refresh-sources]")?.addEventListener("click", loadSources);

    root.querySelector("[data-save-profile]")?.addEventListener("click", async () => {
      syncForm();
      ctx.setLoading(true);
      const result = await ctx.api.post("/api/v1/data-sources/profiles", page.profile);
      ctx.setLoading(false);
      if (result.ok) {
        page.lastSave = result.data.profile;
        ctx.toast("Profile saved / 配置已保存", "success");
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "Profile saved / 配置已保存",
          message: `Saved ${result.data.profile.profile_id}`,
          detail: "POST /api/v1/data-sources/profiles",
        });
      } else {
        ctx.toast("Profile save failed / 配置保存失败", "error");
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "Profile save failed / 配置保存失败",
          message: result.error?.message || String(result.error || "Save failed"),
          detail: "POST /api/v1/data-sources/profiles",
        });
      }
      ctx.rerender();
    });

    root.querySelector("[data-set-default]")?.addEventListener("click", async () => {
      syncForm();
      page.profile.profile_id = "default-live";
      const result = await ctx.api.post("/api/v1/data-sources/profiles", page.profile);
      if (result.ok) {
        page.lastSave = result.data.profile;
        ctx.toast("Default profile updated / 默认配置已更新", "success");
      } else {
        ctx.toast("Default update failed / 默认配置更新失败", "error");
      }
      ctx.rerender();
    });

    root.querySelectorAll("[data-test-provider]").forEach((button) => {
      button.addEventListener("click", async () => {
        syncForm();
        const providerId = button.getAttribute("data-test-provider");
        ctx.setLoading(true);
        const result = await ctx.api.post("/api/v1/data-sources/test", {
          provider_id: providerId,
          symbol: page.symbol || "AAPL",
        });
        ctx.setLoading(false);
        if (result.data?.result) {
          page.testResults[providerId] = result.data.result;
        }
        ctx.setPageStatus(this.id, {
          tone: result.ok ? "success" : "error",
          title: result.ok ? "Connection test passed" : "Connection test did not pass",
          message: result.data?.result?.message || result.error?.message || "No response body.",
          detail: `POST /api/v1/data-sources/test provider=${providerId}`,
        });
        ctx.rerender();
      });
    });

    if (!page.loaded) {
      loadSources();
    }
  },
};
