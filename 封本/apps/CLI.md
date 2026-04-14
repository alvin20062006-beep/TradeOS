# CLI 使用说明

## 启动

```bash
cd ai-trading-tool
python -m apps.cli           # 或
python apps/cli.py
```

## 命令清单

### status — 系统状态

```bash
python -m apps.cli status
python -m apps.cli status --format json
python -m apps.cli status --format tree
```

### pipeline — 全链路编排（Phase 5→6→7）

```bash
# 完整流水线
python -m apps.cli run full-pipeline --symbol AAPL --direction LONG --confidence 0.8

# 指定 regime
python -m apps.cli run full-pipeline --symbol TSLA --direction SHORT --confidence 0.7 --regime trending_down

# JSON 输出
python -m apps.cli run full-pipeline --symbol AAPL --direction LONG --confidence 0.8 --format json
```

### arbitration — 仲裁

```bash
# 旧入口（Phase 5 信号）
python -m apps.cli run arbitration --symbol AAPL --direction LONG --confidence 0.85

# 策略池入口（Phase 9）
python -m apps.cli run arbitration --symbol AAPL --strategy-pool --portfolio-id AAPL-SP
```

### strategy-pool — 策略池

```bash
python -m apps.cli run strategy-pool --symbol AAPL --strategies trend,mean_reversion --direction LONG --confidence 0.75
```

### audit — 审计查询

```bash
# 查询决策历史
python -m apps.cli audit query --type decisions --symbol AAPL --limit 20

# 查询风控审计
python -m apps.cli audit query --type risk

# Feedback 扫描
python -m apps.cli audit feedback --scan --type loss_amplification

# 查询扫描结果
python -m apps.cli audit feedback --result task-abc123

# 审计轨迹（操作日志）
python -m apps.cli audit trail --limit 50
```

### feedback — Feedback 处理

```bash
python -m apps.cli audit feedback --scan --type all --symbol AAPL
```

### 通用选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--format` | 输出格式：`detail` / `json` / `table` / `tree` | `detail` |
| `--api-url` | API 地址 | `http://localhost:8000` |
| `--symbol` | 标的代码 | 必填（部分命令） |
| `--direction` | 信号方向：`LONG` / `SHORT` / `FLAT` | `LONG` |
| `--confidence` | 置信度 0.0-1.0 | `0.75` |
| `--regime` | 市场状态 | `trending_up` |
| `--limit` | 查询条数 | `20` |

### 错误处理

CLI 通过 HTTP 调用 API，错误信息包含：
- HTTP 状态码
- API 错误类型（`error`）
- 人类可读消息（`message`）
