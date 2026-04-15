# 产品化层 API 参考

**版本**: 1.0.0  
**Base URL**: `http://localhost:8000`  
**前缀**: 无（health/version/system）或 `/api/v1`（业务端点）

---

## 端点清单

### 1. 系统端点（无前缀）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 无 |
| GET | `/version` | 系统版本 | 无 |
| GET | `/system/status` | 统一状态面板（含模块就绪探测） | 无 |
| GET | `/system/modules` | Phase 1-10 模块就绪探测 | 无 |

### 2. 分析端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/analysis/run` | 触发 Phase 5 分析 | suggest |

### 3. 仲裁端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/arbitration/run` | 旧入口仲裁（Phase 5 信号） | suggest |
| POST | `/api/v1/arbitration/run-portfolio` | 新入口仲裁（Phase 9 策略池） | suggest |

### 4. 风控端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/risk/calculate` | Phase 7 风控计算 | suggest |

### 5. 审计端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/audit/decisions` | 查询决策历史 | read |
| GET | `/api/v1/audit/risk` | 查询风控审计历史 | read |
| GET | `/api/v1/audit/feedback` | 查询 Feedback 历史 | read |
| POST | `/api/v1/audit/feedback/tasks` | 提交 Feedback 扫描任务（task-style） | task |
| GET | `/api/v1/audit/feedback/tasks/{task_id}` | 查询扫描任务结果 | read |

### 6. 策略池端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/strategy-pool/propose` | 策略池提案（Phase 9 → Phase 6） | suggest |

### 7. 全链路编排端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/pipeline/run-full` | 串联 Phase 5→6→7 | suggest |

### 8. 权限与审计端点

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/auth/users` | 查询用户列表 | read |
| GET | `/api/v1/auth/audit` | 查询操作审计轨迹 | read |

---

## 权限体系

| 角色 | read | suggest | task | review |
|------|:----:|:-------:|:----:|:------:|
| viewer | ✅ | ❌ | ❌ | ❌ |
| operator | ✅ | ✅ | ✅ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ |

- **dev 模式**: `APP_AUTH_ENABLED=false`，所有请求默认 operator 角色
- **prod 模式**: `APP_AUTH_ENABLED=true`，需传 `X-User-ID` header

---

## Task-Style 端点语义

`POST /api/v1/audit/feedback/tasks` 是操作型端点：

```bash
# 1. 提交任务
curl -X POST http://localhost:8000/api/v1/audit/feedback/tasks \
  -H "Content-Type: application/json" \
  -d '{"feedback_type": "loss_amplification", "symbol": "AAPL"}'
# → {"ok": true, "task_id": "task-abc123", "status": "accepted", ...}

# 2. 轮询结果
curl http://localhost:8000/api/v1/audit/feedback/tasks/task-abc123
# → {"task_id": "task-abc123", "status": "done", "feedback_count": 1, ...}
```

---

## 错误格式

所有端点错误响应统一为：

```json
{
  "ok": false,
  "error": {
    "error": "error_type_code",
    "message": "Human readable message",
    "detail": {},
    "request_id": "optional-trace-id"
  }
}
```

HTTP 状态码：401（未认证）、403（权限不足）、404（资源不存在）、422（参数校验失败）

---

## 写权限约束

| 可写 | 不可写 |
|------|--------|
| ✅ POST /analysis/run → 输出 AnalysisSignal | ❌ 修改 Phase 1-4 registry 真值 |
| ✅ POST /arbitration/* → 输出 ArbitrationDecision | ❌ 删除历史 DecisionRecord |
| ✅ POST /risk/calculate → 输出 PositionPlan | ❌ 修改核心算法 / 风控阈值 |
| ✅ POST /audit/feedback/tasks → append-only | ❌ AI 直写 registry |
| ✅ POST /strategy-pool/propose → suggestion-only | ❌ 前端耦合核心内部对象 |
