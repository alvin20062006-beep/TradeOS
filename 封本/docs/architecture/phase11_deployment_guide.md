# 产品化层部署指南

## 快速开始（3 步）

```bash
# 1. 克隆并安装
git clone <repo> && cd ai-trading-tool
pip install -e .

# 2. 启动 API
python run.py api

# 3. 启动 Console（另一个终端）
python run.py console
```

打开浏览器访问 `http://localhost:8501`

## 启动方式

### 方式 1：run.py（推荐）

```bash
python run.py api        # 启动 API（uvicorn，端口 8000）
python run.py console    # 启动 Console（Streamlit，端口 8501）
python run.py all        # 同时启动 API + Console
```

### 方式 2：直接命令

```bash
# API
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload

# Console
streamlit run apps/console/main.py --server.port 8501
```

### 方式 3：Docker

```bash
cd ai-trading-tool
docker compose -f infra/docker/docker-compose.yml up api
docker compose -f infra/docker/docker-compose.yml up console
```

## 环境配置

### 环境变量

复制模板并修改：
```bash
cp .env.example .env
```

### 三个环境

| 环境 | APP_ENV | AUTH | 说明 |
|------|---------|------|------|
| dev | `dev` | 关闭 | 本地开发，无 auth |
| test | `test` | 关闭 | CI/CD 测试 |
| prod | `prod` | 开启 | 生产部署，local auth |

### 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | `dev` | 当前环境 |
| `APP_API_HOST` | `127.0.0.1` | API 监听地址 |
| `APP_API_PORT` | `8000` | API 端口 |
| `APP_AUTH_ENABLED` | `false` | 是否启用认证 |
| `APP_AUTH_SECRET_KEY` | `dev-secret-...` | 认证密钥（prod 必须替换） |
| `APP_DB_URL` | `sqlite:///./ai_trading_tool.db` | 数据库连接 |
| `APP_LOG_LEVEL` | `INFO` | 日志级别 |
| `APP_RISK_MAX_POSITION_PCT` | `0.1` | 风控最大仓位占比 |
| `APP_RISK_DEFAULT_REGIME` | `trending_up` | 风控默认 regime |

## 健康检查验证

```bash
# API 健康
curl http://localhost:8000/health
# → {"status": "ok", "version": "1.0.0", ...}

# 模块就绪
curl http://localhost:8000/system/modules
# → {"ok": true, "modules": [...]}  (6/6 ready)

# 版本
curl http://localhost:8000/version
# → {"version": "1.0.0", "api": "productization-layer"}
```

## Docker 部署

```bash
# 构建并启动
docker compose -f infra/docker/docker-compose.yml up -d

# 查看日志
docker compose -f infra/docker/docker-compose.yml logs -f

# 停止
docker compose -f infra/docker/docker-compose.yml down
```

## 已知限制

1. **非生产级交易系统**：本系统为研究框架，不连接真实经纪商
2. **Streamlit 为过渡方案**：后续可替换为正式 Web 前端
3. **Task 存储为内存**：`/audit/feedback/tasks` 结果存储在进程内存中，重启后丢失
4. **Auth 为本地 SQLite**：不做 OAuth/JWT/Keycloak，仅适合单机部署
