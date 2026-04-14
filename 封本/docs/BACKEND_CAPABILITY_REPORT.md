# 后端真实能力报告

生成时间：2026-04-15
目录基准：`封本`

## A. 当前后端端点总表

| 端点 | 方法 | 真实能力 | 成功条件 | 失败条件 |
| --- | --- | --- | --- | --- |
| `/health` | GET | API 健康检查 | 返回 `status/version/environment/services` | 服务异常时返回非 200 |
| `/version` | GET | 版本信息 | 返回 `version/environment/api` | 启动失败时不可达 |
| `/system/status` | GET | 系统状态摘要 | 返回 `ok/modules` | 启动失败时不可达 |
| `/system/modules` | GET | 模块就绪明细 | 返回 `ok/modules[]` | 模块 import 失败会体现在 `modules[].status=error` |
| `/api/v1/analysis/run` | POST | DTO 分析入口 | 返回 `signal` | 参数越界返回 422 |
| `/api/v1/analysis/run-live` | POST | 真实数据分析入口 | 返回 `data/modules/signal_summary` | timeframe/lookback/news_limit 非法返回 422 |
| `/api/v1/arbitration/run` | POST | 旧仲裁入口 | 返回扁平 decision 字段 | 枚举或分值非法返回 422 |
| `/api/v1/arbitration/run-portfolio` | POST | 策略池仲裁入口 | 返回扁平 decision 字段 | `proposals=[]` 返回 422 |
| `/api/v1/risk/calculate` | POST | 风控计算 | 返回 `plan_id/final_quantity/limit_checks/execution_plan` | bias/confidence/price 非法返回 422 |
| `/api/v1/audit/decisions` | GET | 决策审计查询 | 返回 append-only 决策记录 | 查询参数非法返回 422 |
| `/api/v1/audit/risk` | GET | 风控审计查询 | 返回 append-only 风控记录 | 查询参数非法返回 422 |
| `/api/v1/audit/feedback` | GET | 反馈记录查询 | 返回反馈列表或空列表 | 查询参数非法返回 422 |
| `/api/v1/audit/feedback/tasks` | POST | feedback task 提交 | 返回 `task_id/status/message` | 请求体非法返回 422 |
| `/api/v1/audit/feedback/tasks/{task_id}` | GET | feedback task 查询 | 返回 `status/feedback_count/feedbacks` | task 不存在返回 404 |
| `/api/v1/auth/audit` | GET | auth 审计只读查询 | 返回 `entries[]` | 鉴权失败时 401/403 |
| `/api/v1/auth/users` | GET | 用户列表只读查询 | 返回 `users[]` | 鉴权失败时 401/403 |
| `/api/v1/auth/users/{user_id}` | GET | 单用户只读查询 | 返回用户视图 | 用户不存在返回 404 |
| `/api/v1/strategy-pool/propose` | POST | 策略池提案 | 返回 `task_id=status=immediate/done` 和 `decision` | `proposals=[]` 返回 422 |
| `/api/v1/pipeline/run-full` | POST | DTO 全链编排 | 返回 `phases/decision/plan` | 参数非法返回 422 |
| `/api/v1/pipeline/run-live` | POST | 真实数据全链编排 | 返回 `data/modules/decision/plan/audit/feedback` | 参数非法返回 422 |

## B. 每个端点真实请求/返回摘要

### 系统与状态
- `/health`
  - 请求：无
  - 返回：`status/timestamp/version/environment/services`
  - 前端展示：顶部状态卡片
- `/version`
  - 请求：无
  - 返回：`version/environment/api`
  - 前端展示：版本卡片
- `/system/status`
  - 请求：无
  - 返回：`ok/timestamp/version/environment/modules`
  - 前端展示：Dashboard 摘要或高级详情
- `/system/modules`
  - 请求：无
  - 返回：`ok/modules[]`
  - 前端展示：表格
  - 当前边界：本机主运行环境下 `qlib_data` 仍会显示 `status=error detail=No module named 'qlib'`，这是系统状态事实，不应被前端美化掉

### Analysis
- `/api/v1/analysis/run`
  - 请求：`symbol/score/alpha/confidence/direction`
  - 返回：`ok/signal/source`
  - 前端展示：按钮触发后的摘要结果
- `/api/v1/analysis/run-live`
  - 请求：`symbol/timeframe/lookback/news_limit`
  - 返回：`data/modules/signal_summary`
  - 前端展示：真实数据摘要 + 六模块表格

### Arbitration
- `/api/v1/arbitration/run`
  - 请求：`symbol/direction/confidence/strength/regime/fundamental_score/macro_score/sentiment_score/orderflow_score`
  - 返回：扁平结构 `decision_id/symbol/bias/confidence/signal_count/rules_applied/rationale/timestamp/arbitration_latency_ms/source`
  - 前端展示：
    - 摘要卡片：`bias/confidence/signal_count/source`
    - 结果详情：`rules_applied`
    - 高级详情：`rationale[]`
- `/api/v1/arbitration/run-portfolio`
  - 请求：`portfolio_id/symbol/proposals[]`
  - 返回：同样是扁平 decision，不是嵌套 `decision`
  - 前端展示：表单提交后摘要卡片

### Risk
- `/api/v1/risk/calculate`
  - 请求：`decision_id/symbol/bias/confidence/portfolio_value/current_price/regime/existing_position/...`
  - 返回：`ok/plan_id/symbol/direction/exec_action/final_quantity/veto_triggered/limit_checks/execution_plan/timestamp`
  - 前端展示：
    - 摘要卡片：`direction/exec_action/final_quantity/veto_triggered`
    - 表格：`limit_checks[]`
    - 高级详情：`execution_plan`

### Audit / Feedback / Auth
- `/api/v1/audit/decisions`
  - 请求：`symbol?/limit/offset/since?`
  - 返回：`items[]/total/limit/offset/has_more`
  - 前端展示：只读表格
- `/api/v1/audit/risk`
  - 请求：同上
  - 返回：`items[]/total/limit/offset/has_more`
  - 前端展示：只读表格
- `/api/v1/audit/feedback`
  - 请求：同上
  - 返回：`items[]/total/limit/offset/has_more`
  - 前端展示：只读表格或空态
- `/api/v1/audit/feedback/tasks`
  - 请求：`feedback_type/symbol/since?`
  - 返回：`ok/task_id/status/message/submitted_at`
  - 前端展示：task submit 区
- `/api/v1/audit/feedback/tasks/{task_id}`
  - 请求：路径参数 `task_id`
  - 返回：`task_id/status/feedback_count/feedbacks/summary/error/started_at/completed_at`
  - 前端展示：task status 区
- `/api/v1/auth/audit`
  - 请求：`limit/user_id?/resource?`
  - 返回：`entries[]/total/limit`
  - 前端展示：只读表格
- `/api/v1/auth/users`
  - 请求：无
  - 返回：`users[]`
  - 前端展示：只读表格

### Strategy Pool
- `/api/v1/strategy-pool/propose`
  - 请求：`portfolio_id/symbol/weight_method/proposals[]`
  - 返回：`ok/task_id/status/message/decision`
  - 当前真实行为：同步立即完成，不是异步 task polling
  - 前端展示：
    - 输入区：组合提案表单
    - 结果区：`decision`
    - 表格：`decision.proposals[]`

### Pipeline
- `/api/v1/pipeline/run-full`
  - 请求：`symbol/direction/confidence/strength/regime`
  - 返回：`ok/task_id/status/symbol/phases/decision/plan/error`
  - 前端展示：
    - 摘要区：`status/task_id/decision/plan`
    - 表格：`phases[]`
- `/api/v1/pipeline/run-live`
  - 请求：`symbol/timeframe/lookback/news_limit/start?/end?`
  - 返回：`ok/data/modules/decision/plan/audit/feedback`
  - 前端展示：
    - 摘要卡片：`decision/plan/audit`
    - 表格：`modules[]`
    - 高级详情：完整 raw json

## C. 哪些字段适合前端展示

### 适合摘要卡片
- `status`
- `version`
- `bias`
- `confidence`
- `signal_count`
- `final_quantity`
- `veto_triggered`
- `decision_record_id`
- `task_id`

### 适合结果区主展示
- `decision.rules_applied`
- `pipeline.phases[]`
- `analysis_live.modules[]`
- `pipeline_live.modules[]`
- `strategy_pool.decision.proposals[]`
- `risk.limit_checks[]`
- `feedback task status`

### 适合只读表格
- `audit decisions.items[]`
- `audit risk.items[]`
- `audit feedback.items[]`
- `auth audit.entries[]`
- `auth users[]`
- `system modules[]`

### 适合高级详情
- `rationale[]`
- `execution_plan`
- `raw response json`
- `error/detail`

## D. 当前后端真实能力边界
- 前端不能把 `/api/v1/arbitration/run` 当成嵌套 `decision` 返回，它是真实扁平结构
- `/api/v1/strategy-pool/propose` 当前是真同步 `immediate/done`，前端不能做成假 task 状态流
- `/api/v1/audit/feedback/tasks` 才是 task-style，前端应拆成 submit + status 查询
- `/api/v1/audit/*` 与 `/api/v1/auth/*` 都是只读查询，不应做可编辑表单
- `/system/modules` 当前会真实暴露主运行环境下的 `qlib_data` 不可用状态，这个状态应如实展示
- 产品层当前没有新增真值写入口，前端只应消费 DTO 和只读查询结果
