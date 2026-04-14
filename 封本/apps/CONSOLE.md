# Streamlit Console 使用说明

## 启动

```bash
cd ai-trading-tool

# 方式 1：直接启动
streamlit run apps/console/main.py --server.port 8501

# 方式 2：通过 run.py
python run.py console
```

浏览器打开 `http://localhost:8501`

## 技术说明

- Streamlit = **首批控制台方案**（first console implementation）
- 后续可替换为正式 Web 前端（React/Vue + REST API）
- 当前目标：可运行、可交接、可工程排查
- **Console 不直接 import 核心内部对象**，全部通过 HTTP 调用 API 层

## 面板说明

### 1. Dashboard（首页 `/`）
- 系统版本与环境
- API 连接状态
- 各模块就绪状态（6 个 Phase 模块探测）
- 最新审计记录摘要

### 2. Pipeline（全链路）
- 输入：symbol / direction / confidence / regime
- 触发 `POST /api/v1/pipeline/run-full`
- 展示：Phase 5→6→7 各阶段结果、耗时、最终决策

### 3. Arbitration（仲裁）
- 旧入口：symbol + direction + confidence
- 新入口（策略池）：portfolio_id + 多策略提案
- 触发 `POST /api/v1/arbitration/run` 或 `/run-portfolio`
- 展示：bias / confidence / rules_applied / rationale

### 4. Strategy Pool（策略池）
- 输入：symbol + strategies 列表 + direction + confidence
- 触发 `POST /api/v1/strategy-pool/propose`
- 展示：组合聚合方向 / 各策略信号 / 最终仲裁结果

### 5. Audit（审计查询）
- Tab 1：Decision History（决策历史）
- Tab 2：Risk Audit（风控审计）
- Tab 3：Feedback（Feedback 扫描 + 结果查询）
- Tab 4：Audit Trail（操作轨迹）
- 所有查询均为只读，不允许修改或删除

### 6. Feedback（Feedback 管理）
- 提交扫描任务（task-style）
- 轮询任务结果
- 查看历史 Feedback

## 侧边栏配置

- **API URL**: Console 连接的 API 地址（默认 `http://localhost:8000`）
- 刷新间隔：自动刷新仪表板数据
