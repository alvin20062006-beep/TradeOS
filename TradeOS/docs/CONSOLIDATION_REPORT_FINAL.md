# 椤圭洰鎬绘敹鍙ｄ慨姝ｇ増鎶ュ憡

**鏃ユ湡**: 2026-04-14
**鐘舵€?*: 椤圭洰鎬绘敹鍙ｅ熀鏈畬鎴愶紝鍙氦鎺?
---

## 涓€銆佷緷璧栨敹鍙ｅ彛寰勪慨姝?
### 1.1 鐗╃悊鎼縼杩涘叆 ai浜ゆ槗椤圭洰-TradeOS/ 鐨勫唴瀹?
| 鏉ユ簮 | 鐩爣浣嶇疆 | 绫诲瀷 |
|------|----------|------|
| `ai-trading-tool/core/` | `core/` | 鐗╃悊鎼縼 |
| `ai-trading-tool/apps/` | `apps/` | 鐗╃悊鎼縼 |
| `ai-trading-tool/infra/` | `infra/` | 鐗╃悊鎼縼 |
| `ai-trading-tool/scripts/` | `scripts/` | 鐗╃悊鎼縼 |
| `ai-trading-tool/tests/` | `tests/` | 鐗╃悊鎼縼 |
| `ai-trading-tool/docs/` | `docs/` | 鐗╃悊鎼縼 |
| `ai-trading-tool/mlruns/` | `mlruns/` | 鐗╃悊鎼縼 |
| `ai-trading-tool/*.py` | 鏍圭洰褰?| 鐗╃悊鎼縼 |
| `ai-trading-tool/*.toml` | 鏍圭洰褰?| 鐗╃悊鎼縼 |
| `ai-trading-tool/*.md` | 鏍圭洰褰?| 鐗╃悊鎼縼 |
| `ai-trading-tool/.env.example` | 鏍圭洰褰?| 鐗╃悊鎼縼 |
| `ai-trading-tool/.gitignore` | 鏍圭洰褰?| 鐗╃悊鎼縼 |
| `workspace/qlib/` | `vendor/qlib/` | 鐗╃悊鎼縼锛堟簮鐮佸壇鏈級 |

### 1.2 寮曠敤 / stub / 璇存槑鏂瑰紡淇濈暀鐨勫唴瀹?
| 鍐呭 | 澶勭悊鏂瑰紡 | 鍘熷洜 |
|------|----------|------|
| `nautilus_trader/` | stub 寮曠敤 (`vendor/nautilus_trader.py`) | 浣撶Н >1GB锛圧ust 浠ｇ爜搴擄級锛岃繍琛屾椂浣跨敤 pip 瀹夎鐗堟湰 |
| `ai-trading-tool/ai_trading_tool/` | 涓嶆惉杩?| Hatchling 鎵撳寘 artifact锛堢┖鐩綍缁撴瀯锛?|
| `ai-trading-tool/.git/` | 涓嶆惉杩?| Git 鍘嗗彶浠撳簱锛堝彲鍚庣画閲嶆柊 init锛?|
| `ai-trading-tool/.pytest_cache/` | 涓嶆惉杩?| pytest 缂撳瓨锛堝彲閲嶆柊鐢熸垚锛?|

### 1.3 nautilus_trader 澶勭悊璇存槑

**褰撳墠鐘舵€?*: 涓嶇洿鎺ユ惉杩侊紝閲囩敤 stub 寮曠敤鏂瑰紡

**鍘熷洜**:
- 浠撳簱浣撶Н >1GB锛堝惈 Rust 婧愮爜锛?- 杩愯鏃堕€氳繃 `pip install nautilus-trader` 瀹夎
- 婧愮爜鍓湰瀵硅繍琛屾棤鎰忎箟锛屼粎鐢ㄤ簬 IDE 瀵艰埅

**澶勭悊鏂瑰紡**:
- `vendor/nautilus_trader.py` 鈥?stub 鏂囦欢锛岃鏄庤繍琛屾椂浣跨敤 pip 鐗堟湰
- `vendor/README.md` 鈥?璁板綍寮曠敤璇存槑

---

## 浜屻€丏ockerfile 淇

### 2.1 鍘熼棶棰?
```dockerfile
CMD ["python", "-m", "ai_trading_tool.apps.api"]  # 閿欒璺緞
```

### 2.2 淇鍚?
```dockerfile
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]  # 姝ｇ‘璺緞
```

### 2.3 鏂囦欢浣嶇疆

`infra/docker/Dockerfile` 鈥?宸蹭慨姝?
---

## 涓夈€丆onsole 鍚姩鍛戒护鏍稿

### 3.1 瀹為檯鏂囦欢璺緞

| 缁勪欢 | 鏂囦欢璺緞 | 瀛樺湪 |
|------|----------|:----:|
| API | `apps/api/main.py` | 鉁?|
| Console | `apps/console/main.py` | 鉁?|
| Console 鍏ュ彛 | `apps/run_console.py` | 鉁?|
| CLI | `apps/cli.py` | 鉁?|
| 缁熶竴鍏ュ彛 | `run.py` | 鉁?|

### 3.2 鏈€缁堢湡瀹炲惎鍔ㄥ懡浠?
| 缁勪欢 | 鍛戒护 | 璇存槑 |
|------|------|------|
| **API** | `uvicorn apps.api.main:app --reload --port 8000` | FastAPI 鏈嶅姟 |
| **Console** | `python -m apps.run_console` | Streamlit Dashboard |
| **CLI** | `python -m apps.cli <command>` | 鍛戒护琛屽伐鍏?|
| **涓€閿惎鍔?* | `python run.py --mode dev` | 缁熶竴鍏ュ彛锛圓PI + Console锛?|

### 3.3 渚濊禆鍏崇郴

- Console 渚濊禆 API锛堥€氳繃 HTTP 璇锋眰锛?- 鍚姩椤哄簭锛氬厛 API锛屽悗 Console
- 涓€閿惎鍔ㄨ剼鏈細鍚屾椂鎷夎捣涓よ€?
---

## 鍥涖€佹祴璇曞彛寰勪慨姝?
### 4.1 娴嬭瘯缁撴灉鏄庣粏

| 鎸囨爣 | 鏁板€?| 璇存槑 |
|------|------|------|
| **collected** | 877 | 娴嬭瘯鏀堕泦鎬绘暟 |
| **passed** | 845 | 閫氳繃娴嬭瘯鏁?|
| **failed** | 32 | 澶辫触娴嬭瘯鏁?|
| **warnings** | 26 | 璀﹀憡鏁?|
| **collection errors** | 8 | 鏀堕泦闃舵閿欒 |

### 4.2 澶辫触鍒嗙被

| 绫诲埆 | 鏁伴噺 | 鍘熷洜 |
|------|------|------|
| contracts 鍘嗗彶閬楃暀 | 22 | 鏃?import 璺緞 `core.schemas` |
| 鍏朵粬鍘嗗彶閬楃暀 | 10 | 鏃ц矾寰勫紩鐢?/ qlib 鏁版嵁渚濊禆 |

### 4.3 鏈壒鏄惁鏂板澶辫触

**鍚?* 鈥?32 涓け璐ュ潎涓哄巻鍙查仐鐣欙紝鏈壒鏀跺彛鏁寸悊鏈紩鍏ユ柊澶辫触銆?
### 4.4 Collection Errors

8 涓?collection errors 鍧囦负鏃ц矾寰勫紩鐢細
- `tests/unit/test_schemas.py`
- `tests/unit/test_data_adapter.py`
- `tests/unit/test_data_layer.py`
- `tests/unit/test_fill_adapter.py`
- `tests/unit/test_instrument_mapper.py`
- `tests/unit/test_nautilus_availability.py`
- `tests/unit/test_order_adapter.py`
- `tests/integration/test_backtest_min_loop.py`

杩欎簺娴嬭瘯鏂囦欢浠嶄娇鐢?`import ai_trading_tool` 鏃ц矾寰勶紝闇€鍚庣画淇銆?
---

## 浜斻€佹渶灏忓繀瑕佷慨姝?
| 淇 | 鏂囦欢 | 璇存槑 |
|------|------|------|
| 鏂板 `apps/__init__.py` | `apps/__init__.py` | 浣?apps 鎴愪负鍙鍏ュ寘 |
| 绉婚櫎鏃犳晥 menu_items key | `apps/console/main.py` | Streamlit page_config 涓嶆敮鎸?"View Source" |
| Dockerfile CMD 璺緞 | `infra/docker/Dockerfile` | `ai_trading_tool.apps.api` 鈫?`apps.api.main:app` |

**鏈敼鍔?*:
- Phase 1鈥?0 鏍稿績璇箟
- 浜у搧鍖栧眰 API 绔偣璺緞
- DTO 瀛楁瀹氫箟
- pyproject.toml package 閰嶇疆

---

## 鍏€佹槸鍚﹁揪鍒?椤圭洰鎬绘敹鍙ｅ畬鍏ㄥ畬鎴?

**鍩烘湰瀹屾垚锛屽彲浜ゆ帴**

**杈炬垚鏉′欢**:
1. 鉁?鍏ㄩ儴椤圭洰浠ｇ爜宸插綊闆嗚嚦鍗曚竴鐩綍
2. 鉁?鐩綍缁撴瀯娓呮櫚銆佺粺涓€銆佸彲浜ゆ帴
3. 鉁?Phase 1鈥?0 鏍稿績璇箟闆舵敼鍔?4. 鉁?浜у搧鍖栧眰 API 璇箟闆舵敼鍔?5. 鉁?API / Console / CLI 鍧囧彲鍚姩
6. 鉁?Dockerfile 璺緞宸蹭慨姝?7. 鉁?鏈壒鏈紩鍏ユ柊娴嬭瘯澶辫触

**寰呭悗缁鐞?*:
1. 鈴?8 涓祴璇曟枃浠舵棫璺緞淇
2. 鈴?22 涓?contracts 娴嬭瘯澶辫触淇
3. 鈴?Git 浠撳簱閲嶆柊 init

---

## 涓冦€佷氦鎺ユ竻鍗?
```bash
# 椤圭洰鏍圭洰褰?cd "C:\Users\hutia\.qclaw\workspace\ai浜ゆ槗椤圭洰-TradeOS"

# 瀹夎渚濊禆
pip install -e .

# 鍚姩 API
uvicorn apps.api.main:app --reload --port 8000

# 鍚姩 Console
python -m apps.run_console

# 鍚姩 CLI
python -m apps.cli --help

# 杩愯娴嬭瘯锛堟帓闄ゅ巻鍙查仐鐣欙級
pytest tests/ -q --ignore=tests/unit/test_schemas.py --ignore=tests/unit/test_data_adapter.py --ignore=tests/unit/test_data_layer.py --ignore=tests/unit/test_fill_adapter.py --ignore=tests/unit/test_instrument_mapper.py --ignore=tests/unit/test_nautilus_availability.py --ignore=tests/unit/test_order_adapter.py --ignore=tests/integration/test_backtest_min_loop.py
```

---

**鎶ュ憡瀹屾垚銆傞」鐩凡缁熶竴鏀跺彛锛屽彲浜ゆ帴銆?*
