# 权限说明

## 技术选型

- **存储**: SQLite（`~/.ai-trading-tool/auth.db`）
- **用户**: 本地 users（无外部身份提供商）
- **认证**: dev 旁路 / prod X-User-ID header
- **审计**: append-only audit trail

## 角色枚举

| 角色 | 值 | 说明 |
|------|:--:|------|
| VIEWER | `viewer` | 只读监控 |
| OPERATOR | `operator` | 可写 suggestion-only |
| ADMIN | `admin` | 含人工复盘确认权限 |

## 权限矩阵

| 操作 | viewer | operator | admin |
|------|:------:|:--------:|:-----:|
| GET 端点（只读查询） | ✅ | ✅ | ✅ |
| POST /analysis/run（suggestion） | ❌ | ✅ | ✅ |
| POST /arbitration/*（suggestion） | ❌ | ✅ | ✅ |
| POST /risk/calculate（suggestion） | ❌ | ✅ | ✅ |
| POST /audit/feedback/tasks（task） | ❌ | ✅ | ✅ |
| POST /strategy-pool/propose（suggestion） | ❌ | ✅ | ✅ |
| POST /pipeline/run-full（suggestion） | ❌ | ✅ | ✅ |
| ReviewManager.apply（人工确认） | ❌ | ❌ | ✅ |

## 环境行为

### dev 模式（`APP_AUTH_ENABLED=false`）
- 所有请求自动返回 `operator` 角色
- 无需传 `X-User-ID` header
- 审计日志仍记录（user_id = `dev-operator`）

### prod 模式（`APP_AUTH_ENABLED=true`）
- 必须传 `X-User-ID` header
- 查询 SQLite 用户表校验角色
- 401：用户不存在 / 未传 header
- 403：权限不足

## 默认用户（SQLite seed）

| ID | 用户名 | 角色 | 说明 |
|----|--------|------|------|
| system | system | operator | 内部系统调用 |
| viewer | viewer | viewer | 只读监控 |
| operator | operator | operator | 标准操作员 |
| admin | admin | admin | 管理员（含 review） |

## 审计轨迹

所有写操作自动记录审计日志：
- user_id / action / resource / detail / result / timestamp
- append-only，不可修改或删除
- 查询：`GET /api/v1/auth/audit`

## 写权限约束

```
✅ AI / Operator 可做：
  - POST suggestion-only 端点 → 输出决策/计划（不写 registry）
  - POST task-style 端点 → append-only 写入 FeedbackRegistry
  - GET 只读端点 → 查询历史

❌ 任何角色禁止：
  - 修改 Phase 1-4 registry 真值
  - 删除历史 DecisionRecord
  - 绕过 API 层直写核心对象
```
