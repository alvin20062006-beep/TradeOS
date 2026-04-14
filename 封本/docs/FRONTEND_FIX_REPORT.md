# 前端修复结果

生成时间：2026-04-15
目录基准：`封本`

## A. 修改了哪些前端文件
- `apps/console/main.py`
- `apps/console/ui_app.py`

## B. 首屏现在有哪些肉眼可见的模块
首屏顶部导航直接可见以下 6 个模块：
- Dashboard
- Pipeline
- Arbitration
- Strategy Pool
- Audit
- Feedback

## C. 每个面板对应哪些后端端点
- Dashboard
  - `GET /health`
  - `GET /version`
  - `GET /system/modules`
  - `GET /api/v1/auth/users`
- Pipeline
  - `POST /api/v1/pipeline/run-full`
  - `POST /api/v1/pipeline/run-live`
- Arbitration
  - `POST /api/v1/arbitration/run`
  - `POST /api/v1/arbitration/run-portfolio`
- Strategy Pool
  - `POST /api/v1/strategy-pool/propose`
- Audit
  - `GET /api/v1/audit/decisions`
  - `GET /api/v1/audit/risk`
  - `GET /api/v1/audit/feedback`
  - `GET /api/v1/auth/audit`
  - `GET /api/v1/auth/users`
- Feedback
  - `POST /api/v1/audit/feedback/tasks`
  - `GET /api/v1/audit/feedback/tasks/{task_id}`

## D. 每个面板有哪些按钮 / 输入区 / 结果区
- Dashboard
  - 可见内容：状态卡片、模块表格、用户表格
  - 作用：只读查看，无假操作按钮
- Pipeline
  - 输入区：symbol、direction、regime、confidence、strength、timeframe、lookback、news_limit
  - 按钮：`Run Pipeline`、`Run Live Pipeline`
  - 结果区：summary、phase table、six-module matrix、raw response
- Arbitration
  - 输入区：单信号仲裁参数 + portfolio proposals 参数
  - 按钮：`Run Arbitration`、`Run Portfolio Arbitration`
  - 结果区：decision summary、rules applied、rationale rows、raw response
- Strategy Pool
  - 输入区：portfolio_id、symbol、weight_method、alpha/hedge 参数
  - 按钮：`Submit Strategy Pool`
  - 结果区：submit result、returned proposals、raw response
- Audit
  - 输入区：filter 和 limit
  - 按钮：`Load decision records`、`Load risk records`、`Load feedback records`、`Load auth audit + users`
  - 结果区：只读表格、raw response
- Feedback
  - 输入区：feedback_type、symbol、task_id
  - 按钮：`Submit Feedback Scan`、`Load task status`
  - 结果区：submit result、status result、feedback table、raw response

## E. 双击快捷方式后的真实行为
- 桌面快捷方式：`C:\Users\Alvin\Desktop\TradeOS Console.lnk`
- 目标：`封本\start.bat`
- `start.bat` -> `python run.py start`
- `run.py start` 会并行启动 API 与 Console
- `apps.run_console` 会检查 API，如未启动则后台拉起 API，然后自动打开浏览器

## F. 自动打开的最终 URL
- 默认 URL：`http://localhost:8501`
- 若 8501 被占用，`apps.run_console` 会自动切到 `8502/8503/8510/8511/8512`

## G. 真实界面截图
- 首屏：`docs/screenshots/dashboard_clean.png`
- Pipeline 面板：`docs/screenshots/pipeline_clean.png`
- Arbitration 面板：`docs/screenshots/arbitration_clean.png`
- Strategy Pool 面板：`docs/screenshots/strategy_pool_clean.png`
- Audit 面板：`docs/screenshots/audit_clean.png`
- Feedback 面板：`docs/screenshots/feedback_clean.png`

## H. 这次前端修复的关键收口
- 移除了对后端返回结构的想象，尤其是 Arbitration 不再假设嵌套 `decision`
- Strategy Pool 按真实同步返回渲染，不再伪装成 task 流
- Feedback 明确采用 submit + status 的 task-style UI
- Audit / Auth 全部保持只读查询，不制造假写入口
- 首屏直接展示 6 个模块导航，用户无需猜哪里可以点
