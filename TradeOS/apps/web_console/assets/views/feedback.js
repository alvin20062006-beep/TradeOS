export const feedbackView = {
  id: "feedback",
  label: "反馈 Feedback",
  shortLabel: "任务 Tasks",
  initialState: {
    submitForm: {
      feedback_type: "all",
      symbol: "AAPL",
    },
    taskId: "",
    submitResult: null,
    statusResult: null,
    historyResult: null,
    historySymbol: "",
    historyLimit: 10,
  },
  render(ctx, page) {
    const { utils } = ctx;
    const historyRows = page.historyResult?.items || [];
    const statusRows = page.statusResult?.feedbacks || [];

    return `
      <section class="page-head">
        <div>
          <span class="section-eyebrow">任务式反馈 Task-style Feedback</span>
          <h2>反馈 Feedback</h2>
          <p>提交反馈扫描任务、轮询任务状态，并查看真实反馈结果或诚实空状态。</p>
        </div>
        <div class="head-actions">
          <span class="endpoint-pill">POST /api/v1/audit/feedback/tasks</span>
          <span class="endpoint-pill">GET /api/v1/audit/feedback/tasks/{task_id}</span>
          <span class="endpoint-pill">GET /api/v1/audit/feedback</span>
        </div>
      </section>

      <section class="panel-grid two-up">
        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">任务提交 Task Submit</span>
              <h3>提交反馈扫描 Submit Feedback Scan</h3>
            </div>
          </div>
          <form data-feedback-submit class="form-grid compact-grid">
            <label>
              <span>反馈类型 Feedback Type</span>
              <select name="feedback_type">
                ${["all", "loss_amplification", "win_fade", "regime_mismatch", "confidence_mismatch", "low_signal_count"]
                  .map((option) => `<option value="${option}" ${page.submitForm.feedback_type === option ? "selected" : ""}>${option}</option>`)
                  .join("")}
              </select>
            </label>
            <label>
              <span>标的 Symbol</span>
              <input name="symbol" value="${utils.escapeHtml(page.submitForm.symbol)}" />
            </label>
          </form>
          <div class="button-row">
            <button type="button" class="action-button primary" data-submit-feedback-task>提交反馈扫描 Submit Feedback Scan</button>
          </div>
          ${
            page.submitResult
              ? utils.renderKeyValueList([
                  { label: "任务 ID Task ID", value: page.submitResult.task_id || "n/a" },
                  { label: "状态 Status", value: page.submitResult.status || "n/a" },
                  { label: "提交时间 Submitted", value: utils.formatDate(page.submitResult.submitted_at) },
                  { label: "消息 Message", value: page.submitResult.message || "n/a" },
                ])
              : `<div class="empty-state compact">请先提交任务。本页不会伪造“直接写入成功”。 / Submit a task first. This page never fakes direct write success.</div>`
          }
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">任务状态 Task Status</span>
              <h3>轮询反馈任务 Poll Feedback Task</h3>
            </div>
          </div>
          <form data-feedback-status class="compact-form">
            <input name="task_id" placeholder="任务 ID Task ID" value="${utils.escapeHtml(page.taskId || page.submitResult?.task_id || "")}" />
            <button type="button" class="action-button small" data-load-feedback-status>加载状态 Load Status</button>
          </form>
          ${
            page.statusResult
              ? utils.renderMetricCards([
                  {
                    label: "任务状态 Task Status",
                    value: page.statusResult.status || "n/a",
                    sub: utils.shortText(page.statusResult.task_id || "n/a", 18),
                  },
                  {
                    label: "反馈数量 Feedback Count",
                    value: String(page.statusResult.feedback_count ?? "0"),
                    sub: page.statusResult.summary || "No summary",
                  },
                  {
                    label: "完成时间 Completed At",
                    value: utils.formatDate(page.statusResult.completed_at),
                    sub: "任务式只读回查 / Task-style readback only",
                  },
                ])
              : `<div class="empty-state compact">加载一个任务状态后，这里会显示后端结果。 / Load a task status to see the backend result here.</div>`
          }
        </article>
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">任务结果 Task Results</span>
            <h3>反馈结果或空状态 Feedback Result or Empty State</h3>
          </div>
        </div>
        ${utils.renderTable(
          [
            { key: "feedback_id", label: "反馈 ID Feedback ID" },
            { key: "symbol", label: "标的 Symbol" },
            { key: "feedback_type", label: "类型 Type" },
            { key: "severity", label: "严重度 Severity" },
            { key: "description", label: "描述 Description" },
          ],
          statusRows,
          { emptyText: "当前任务还没有返回反馈记录。 / This task returned no feedback rows yet." },
        )}
      </section>

      <section class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">只读历史 Read-only History</span>
            <h3>反馈注册表快照 Feedback Registry Snapshot</h3>
          </div>
        </div>
        <form data-feedback-history class="compact-form compact-form-wide">
          <input name="history_symbol" placeholder="标的过滤 Symbol filter" value="${utils.escapeHtml(page.historySymbol)}" />
          <input name="history_limit" type="number" min="1" max="100" value="${utils.escapeHtml(page.historyLimit)}" />
          <button type="button" class="action-button small" data-load-feedback-history>加载历史 Load History</button>
        </form>
        ${utils.renderTable(
          [
            { key: "feedback_id", label: "反馈 ID Feedback ID" },
            { key: "symbol", label: "标的 Symbol" },
            { key: "feedback_type", label: "类型 Type" },
            { key: "severity", label: "严重度 Severity" },
            {
              key: "created_at",
              label: "创建时间 Created",
              render: (row) => utils.formatDate(row.created_at),
            },
          ],
          historyRows,
          { emptyText: "可加载反馈历史，也允许诚实保持空状态。 / Load feedback history or leave this as an honest empty state." },
        )}
      </section>

      ${utils.renderJsonPanel("反馈任务提交原始响应 Feedback Task Submit Raw Response", page.submitResult)}
      ${utils.renderJsonPanel("反馈任务状态原始响应 Feedback Task Status Raw Response", page.statusResult)}
    `;
  },
  mount(ctx, page, root) {
    const syncSubmit = () => {
      const data = new FormData(root.querySelector("[data-feedback-submit]"));
      page.submitForm.feedback_type = String(data.get("feedback_type") || "all");
      page.submitForm.symbol = String(data.get("symbol") || "").trim();
    };

    const syncStatus = () => {
      const data = new FormData(root.querySelector("[data-feedback-status]"));
      page.taskId = String(data.get("task_id") || "").trim();
    };

    const syncHistory = () => {
      const data = new FormData(root.querySelector("[data-feedback-history]"));
      page.historySymbol = String(data.get("history_symbol") || "").trim();
      page.historyLimit = Number(data.get("history_limit") || 10);
    };

    root.querySelector("[data-feedback-submit]")?.addEventListener("input", syncSubmit);
    root.querySelector("[data-feedback-submit]")?.addEventListener("change", syncSubmit);
    root.querySelector("[data-feedback-status]")?.addEventListener("input", syncStatus);
    root.querySelector("[data-feedback-history]")?.addEventListener("input", syncHistory);

    root.querySelector("[data-submit-feedback-task]")?.addEventListener("click", async () => {
      syncSubmit();
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "提交反馈扫描 Submitting Feedback Scan",
        message: "正在创建任务式反馈扫描请求。",
        detail: "POST /api/v1/audit/feedback/tasks",
      });
      const payload = { feedback_type: page.submitForm.feedback_type };
      if (page.submitForm.symbol) {
        payload.symbol = page.submitForm.symbol;
      }
      const result = await ctx.api.post("/api/v1/audit/feedback/tasks", payload);
      page.submitResult = result.data;
      page.taskId = result.data?.task_id || page.taskId;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "反馈扫描已接受 Feedback Scan Accepted",
          message: result.data?.message || "后端已接受任务。",
          detail: result.data?.task_id || "task id unavailable",
        });
        ctx.toast("反馈扫描任务已接受 / Feedback scan task accepted.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "反馈扫描失败 Feedback Scan Failed",
          message: result.error?.message || "后端返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("反馈扫描失败 / Feedback scan failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    });

    root.querySelector("[data-load-feedback-status]")?.addEventListener("click", async () => {
      syncStatus();
      if (!page.taskId) {
        ctx.toast("请先输入任务 ID / Enter a task ID first.", "info");
        return;
      }
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "加载任务状态 Loading Task Status",
        message: "正在轮询当前任务状态接口。",
        detail: "GET /api/v1/audit/feedback/tasks/{task_id}",
      });
      const result = await ctx.api.get(`/api/v1/audit/feedback/tasks/${encodeURIComponent(page.taskId)}`);
      page.statusResult = result.data;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "任务状态已加载 Task Status Loaded",
          message: `任务状态为 ${result.data?.status || "n/a"}。`,
          detail: `${result.data?.feedback_count || 0} feedback rows`,
        });
        ctx.toast("反馈任务状态已加载 / Feedback task status loaded.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "任务状态失败 Task Status Failed",
          message: result.error?.message || "后端返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("反馈任务状态失败 / Feedback task status failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    });

    root.querySelector("[data-load-feedback-history]")?.addEventListener("click", async () => {
      syncHistory();
      ctx.setLoading(true);
      ctx.setPageStatus(this.id, {
        tone: "loading",
        title: "加载反馈历史 Loading Feedback History",
        message: "正在读取 append-only 反馈注册表。",
        detail: "GET /api/v1/audit/feedback",
      });
      const result = await ctx.api.get("/api/v1/audit/feedback", {
        symbol: page.historySymbol,
        limit: page.historyLimit,
      });
      page.historyResult = result.data;
      if (result.ok) {
        ctx.setPageStatus(this.id, {
          tone: "success",
          title: "反馈历史已加载 Feedback History Loaded",
          message: "反馈注册表快照已刷新。",
          detail: `${result.data?.total || 0} total rows`,
        });
        ctx.toast("反馈历史已加载 / Feedback history loaded.", "success");
      } else {
        ctx.setPageStatus(this.id, {
          tone: "error",
          title: "反馈历史失败 Feedback History Failed",
          message: result.error?.message || "后端返回错误。",
          detail: `${result.status || "network"} / ${result.url}`,
        });
        ctx.toast("反馈历史失败 / Feedback history failed.", "error");
      }
      ctx.setLoading(false);
      ctx.rerender();
    });
  },
};
