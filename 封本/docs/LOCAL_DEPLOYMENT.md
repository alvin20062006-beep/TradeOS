# 本地部署指南（Windows）

当前机器系统：Windows

本项目本地交付后的唯一推荐启动体系：

- 一键启动：`start.ps1` 或 `start.bat`
- API 单独启动：`python run.py api`
- Console 单独启动：`python run.py console`
- CLI live 全链检查：`python run.py pipeline-live --symbol AAPL`

不再把 `uvicorn ...`、`streamlit run ...` 作为主文档中的正式启动方式，它们只保留给排障时使用。

## 1. 安装依赖

在项目根目录执行：

```powershell
cd "C:\Users\Alvin\Desktop\AI交易TradeOS\封本"
python -m pip install -r requirements-local.txt
```

## 2. 初始化环境变量

如果需要自定义配置：

```powershell
Copy-Item .env.example .env
```

默认本地模式无需额外密钥即可运行基础 API、Console、CLI 和 live 数据链。

## 3. 启动 API

```powershell
python run.py api
```

启动后验证：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

## 4. 启动 Console

Console 依赖 API，先启动 API，再新开终端执行：

```powershell
python run.py console
```

访问：

- API: `http://127.0.0.1:8000`
- API Docs: `http://127.0.0.1:8000/docs`
- Console: `http://localhost:8501`

## 5. 一键启动

Windows 正式交付入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

或：

```bat
start.bat
```

## 6. CLI 入口

状态检查：

```powershell
python run.py status
```

真实数据 live pipeline：

```powershell
python run.py pipeline-live --symbol AAPL --timeframe 1d --lookback 90
python -m apps.cli pipeline run-live --symbol CL=F --timeframe 1d --lookback 120
```

## 7. 桌面快捷方式

生成方式：

```powershell
powershell -ExecutionPolicy Bypass -File .\_make_shortcut.ps1
```

放置位置：

- `%USERPROFILE%\Desktop\TradeOS Console.lnk`

快捷方式目标：

- `[项目根目录]\start.bat`

## 8. 常见报错排查

### 8.1 `Python not found`

原因：Python 未安装或未加入 `PATH`。

处理：

- 安装 Python 3.10+
- 勾选 “Add Python to PATH”

### 8.2 `ModuleNotFoundError`

原因：依赖未安装。

处理：

```powershell
python -m pip install -r requirements-local.txt
```

### 8.3 `Address already in use`

原因：8000 或 8501 端口被占用。

处理：

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :8501
taskkill /PID <pid> /F
```

### 8.4 `streamlit` / `numpy` / `yfinance` 缺失

原因：本地运行依赖不完整。

处理：

```powershell
python -m pip install -r requirements-local.txt
```

### 8.5 Yahoo / FRED 实时数据短暂失败

原因：外部公共数据源偶发限流、超时或返回空数据。

处理：

- 重新执行一次 live 命令
- 先确认网络可访问 Yahoo Finance / FRED
- 如只影响单个模块，检查 `/api/v1/pipeline/run-live` 返回中的 `modules[].notes`

## 9. 交付后最终文件树（核心）

```text
封本/
├── apps/
│   ├── api/
│   ├── cli.py
│   ├── console/
│   └── dto/api/live.py
├── core/
│   ├── analysis/
│   ├── arbitration/
│   ├── audit/
│   ├── data/live/
│   └── risk/
├── docs/
│   ├── LOCAL_DEPLOYMENT.md
│   └── SIX_MODULE_LIVE_MATRIX.md
├── requirements-local.txt
├── run.py
├── start.bat
├── start.ps1
└── _make_shortcut.ps1
```
