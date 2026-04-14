"""
apps/cli.py — 命令行入口（轻量 CLI，不重写任何 Phase 逻辑）

用法:
    python -m apps.cli --help
    python -m apps.cli pipeline run-full --symbol AAPL --direction LONG
    python -m apps.cli arbitration run --symbol AAPL --direction LONG
    python -m apps.cli status
    python -m apps.cli audit trail --limit 20
    python -m apps.cli feedback scan --symbol AAPL
    python -m apps.cli feedback result --task-id <id>
"""

from __future__ import annotations

# Windows cmd 默认 cp1252，强制 UTF-8 输出避免 UnicodeEncodeError
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import sys
from datetime import datetime
from typing import Optional

import click


# ── API 客户端（内部 import）────────────────────────────────

_API_BASE = "http://localhost:8000"


def _get(path: str) -> dict:
    import requests

    r = requests.get(f"{_API_BASE}{path}", timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path: str, data: dict) -> dict:
    import requests

    r = requests.post(f"{_API_BASE}{path}", json=data, timeout=30)
    r.raise_for_status()
    return r.json()


# ── 辅助格式工具 ────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
DIM = "\033[2m"


def _ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"{YELLOW}⚠{RESET} {msg}")


def _section(title: str) -> None:
    print(f"\n{DIM}{'─' * 48}{RESET}")
    print(f"  {title}")
    print(f"{DIM}{'─' * 48}{RESET}")


def _json(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


# ── 状态 ──────────────────────────────────────────────────

@click.group()
def cli():
    """AI Trading Tool — 命令行工具（suggestion-only）"""
    pass


@cli.command("status")
def status():
    """系统状态概览（/system/status + /health）"""
    _section(f"系统状态  [{_ts()}]")
    try:
        health = _get("/health")
        print(f"\n  API 状态:   {GREEN}在线{RESET}  ({health.get('environment','?')})")
        print(f"  版本:       {health.get('version','?')}")
        print(f"  环境:       {health.get('environment','?')}")
        svcs = health.get("services", {})
        for name, state in svcs.items():
            tag = f"{GREEN}✓{RESET}" if state == "ok" else f"{YELLOW}⚠{RESET}"
            print(f"  {tag} {name}: {state}")
        print(f"\n  时间:       {health.get('timestamp','')}")
    except Exception as e:
        _fail(f"无法连接 API: {e}")
        sys.exit(1)


# ── Pipeline ───────────────────────────────────────────────

@cli.group("pipeline")
def pipeline():
    """全链路 Pipeline 操作"""
    pass


@pipeline.command("run-full")
@click.option("--symbol", required=True, help="标的代码，如 AAPL")
@click.option("--direction", default="LONG", help="LONG | SHORT | FLAT")
@click.option("--confidence", default=0.75, type=float, help="信号置信度 0~1")
@click.option("--strength", default=0.6, type=float, help="信号强度 0~1")
@click.option("--regime", default="trending_up", help="市场状态")
@click.option("--json", "as_json", is_flag=True, help="输出原始 JSON")
def pipeline_run(symbol, direction, confidence, strength, regime, as_json):
    """运行全链路 Pipeline（Phase 5 → 6 → 7）"""
    _section(f"Pipeline run-full  {symbol}  [{_ts()}]")
    print(f"  symbol:     {symbol}")
    print(f"  direction:  {direction}")
    print(f"  confidence: {confidence}")
    print(f"  regime:     {regime}")
    print()
    try:
        result = _post("/api/v1/pipeline/run-full", {
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "strength": strength,
            "regime": regime,
        })
        if as_json:
            _json(result)
            return

        print(f"  状态:       {result.get('status')}")
        for p in result.get("phases", []):
            tag = f"{GREEN}✓{RESET}" if p["ok"] else f"{RED}✗{RESET}"
            err = f"  → {p.get('error','')}" if p.get("error") else ""
            detail = p.get("detail", {}) or {}
            print(f"  {tag} {p['phase']:12s}  {p.get('duration_ms',0):.1f}ms  {err}")
            if detail:
                for k, v in detail.items():
                    if k not in ("skipped",):
                        print(f"      {k}: {v}")

        dec = result.get("decision")
        if dec:
            print(f"\n  仲裁决策:")
            print(f"    bias:       {dec.get('bias')}")
            print(f"    confidence: {dec.get('confidence')}")
            print(f"    rules:      {', '.join(dec.get('rules_applied',[]) or ['—'])}")

        plan = result.get("plan")
        if plan:
            veto = f"{RED}veto!{RESET}" if plan.get("veto_triggered") else f"{GREEN}通过{RESET}"
            print(f"\n  风控计划:")
            print(f"    plan_id:    {plan.get('plan_id')}")
            print(f"    direction:  {plan.get('direction')}")
            print(f"    qty:        {plan.get('final_quantity', 0):.4f}")
            print(f"    风控:       {veto}")
        else:
            _warn("无仓位计划")

        if result.get("error"):
            _fail(f"Pipeline error: {result['error']}")

    except Exception as e:
        _fail(f"请求失败: {e}")
        sys.exit(1)


# ── Arbitration ────────────────────────────────────────────

@pipeline.command("run-live")
@click.option("--symbol", required=True, help="标的代码，如 AAPL 或 CL=F")
@click.option("--timeframe", default="1d", help="1m | 5m | 15m | 30m | 1h | 4h | 1d | 1w")
@click.option("--lookback", default=180, type=int, help="历史 bar 数")
@click.option("--news-limit", default=10, type=int, help="新闻条数上限")
@click.option("--json", "as_json", is_flag=True, help="输出原始 JSON")
def pipeline_run_live(symbol, timeframe, lookback, news_limit, as_json):
    """运行真实数据 live pipeline（六模块 -> Phase 6 -> Phase 7 -> Phase 8）。"""
    _section(f"Pipeline run-live  {symbol}  [{_ts()}]")
    print(f"  symbol:      {symbol}")
    print(f"  timeframe:   {timeframe}")
    print(f"  lookback:    {lookback}")
    print(f"  news_limit:  {news_limit}")
    print()
    try:
        result = _post("/api/v1/pipeline/run-live", {
            "symbol": symbol,
            "timeframe": timeframe,
            "lookback": lookback,
            "news_limit": news_limit,
        })
        if as_json:
            _json(result)
            return

        data = result.get("data", {})
        print(f"  bars:        {data.get('bar_count')}")
        print(f"  intraday:    {data.get('intraday_bar_count')}")
        print(f"  latest:      {data.get('latest_timestamp')}")

        print("\n  六模块:")
        for item in result.get("modules", []):
            status = item.get("status", "?")
            tag = f"{GREEN}OK{RESET}" if status == "ok" else f"{YELLOW}{status}{RESET}"
            print(f"    {tag:10s} {item.get('module','?'):12s} {item.get('provider','?')} / {item.get('adapter','?')}")

        decision = result.get("decision", {})
        print("\n  仲裁:")
        print(f"    bias:        {decision.get('bias')}")
        print(f"    confidence:  {decision.get('confidence')}")
        print(f"    rules:       {', '.join(decision.get('rules_applied', [])) or '-'}")

        plan = result.get("plan", {})
        print("\n  风控:")
        print(f"    plan_id:     {plan.get('plan_id')}")
        print(f"    direction:   {plan.get('direction')}")
        print(f"    qty:         {plan.get('final_quantity')}")
        print(f"    veto:        {plan.get('veto_triggered')}")

        audit = result.get("audit", {})
        feedback = result.get("feedback", {})
        print("\n  审计/反馈:")
        print(f"    decision:    {audit.get('decision_record_id')}")
        print(f"    risk:        {audit.get('risk_audit_id')}")
        print(f"    feedbacks:   {feedback.get('count')}")

    except Exception as e:
        _fail(f"请求失败: {e}")
        sys.exit(1)


@cli.group("arbitration")
def arbitration():
    """仲裁引擎操作"""
    pass


@arbitration.command("run")
@click.option("--symbol", required=True)
@click.option("--direction", default="LONG")
@click.option("--confidence", default=0.75, type=float)
@click.option("--strength", default=0.6, type=float)
@click.option("--regime", default="trending_up")
@click.option("--json", "as_json", is_flag=True)
def arbitration_run(symbol, direction, confidence, strength, regime, as_json):
    """运行仲裁引擎（Phase 6）"""
    _section(f"Arbitration  {symbol}  [{_ts()}]")
    try:
        result = _post("/api/v1/arbitration/run", {
            "symbol": symbol,
            "direction": direction.upper(),
            "confidence": confidence,
            "strength": strength,
            "regime": regime,
        })
        if as_json:
            _json(result)
            return

        dec = result.get("decision", {})
        ok = result.get("ok", False)
        if ok:
            _ok("Arbitration completed")
        else:
            _warn("Arbitration returned no decision")

        print(f"  decision_id:  {dec.get('decision_id','?')}")
        print(f"  bias:         {dec.get('bias','?')}")
        print(f"  confidence:   {dec.get('confidence','?')}")
        print(f"  signal_count: {dec.get('signal_count','?')}")
        rules = dec.get("rules_applied", []) or []
        print(f"  rules:        {', '.join(rules) if rules else '—'}")

    except Exception as e:
        _fail(f"请求失败: {e}")
        sys.exit(1)


# ── Strategy Pool ──────────────────────────────────────────

@cli.group("strategy-pool")
def strategy_pool():
    """策略池操作"""
    pass


@strategy_pool.command("propose")
@click.option("--portfolio-id", required=True)
@click.option("--symbol", required=True)
@click.option("--strategy-id", default="manual")
@click.option("--direction", default="LONG")
@click.option("--strength", default=0.7, type=float)
@click.option("--confidence", default=0.8, type=float)
@click.option("--weight", "portfolio_weight", default=0.5, type=float)
@click.option("--json", "as_json", is_flag=True)
def strategy_pool_propose(portfolio_id, symbol, strategy_id, direction,
                           strength, confidence, portfolio_weight, as_json):
    """提交策略提案（Phase 9 → Phase 6 仲裁）"""
    _section(f"Strategy Pool propose  [{_ts()}]")
    try:
        result = _post("/api/v1/strategy-pool/propose", {
            "portfolio_id": portfolio_id,
            "symbol": symbol,
            "proposals": [{
                "proposal_id": f"{strategy_id}-{symbol}-{datetime.utcnow().strftime('%H%M%S')}",
                "strategy_id": strategy_id,
                "aggregate_direction": direction.upper(),
                "aggregate_strength": strength,
                "aggregate_confidence": confidence,
                "portfolio_weight": portfolio_weight,
                "bundles": [{
                    "bundle_id": f"b-{datetime.utcnow().strftime('%H%M%S')}",
                    "source_strategy_id": strategy_id,
                    "symbol": symbol,
                    "direction": direction.upper(),
                    "strength": strength,
                    "confidence": confidence,
                }],
            }],
        })
        if as_json:
            _json(result)
            return

        if result.get("status") == "done":
            _ok("策略池仲裁完成")
        else:
            _warn(f"status: {result.get('status')}")

        dec = result.get("decision", {})
        print(f"  bias:          {dec.get('bias','?')}")
        print(f"  confidence:    {dec.get('confidence','?')}")
        print(f"  portfolio_id:  {dec.get('portfolio_id','?')}")

    except Exception as e:
        _fail(f"请求失败: {e}")
        sys.exit(1)


# ── Audit ──────────────────────────────────────────────────

@cli.group("audit")
def audit():
    """审计查询（只读）"""
    pass


@audit.command("decisions")
@click.option("--symbol", default=None)
@click.option("--limit", default=20, type=int)
@click.option("--json", "as_json", is_flag=True)
def audit_decisions(symbol, limit, as_json):
    """查询仲裁决策记录"""
    _section(f"Audit decisions  [{_ts()}]")
    params = f"?limit={limit}" + (f"&symbol={symbol}" if symbol else "")
    try:
        result = _get(f"/api/v1/audit/decisions{params}")
        if as_json:
            _json(result)
            return

        items = result.get("items", [])
        total = result.get("total", 0)
        _ok(f"查询到 {len(items)} 条记录（总计 {total}）")
        for item in items:
            ts = item.get("timestamp", "?").split("T")[1][:8]
            print(f"  [{ts}] {item.get('decision_id','?')[:20]:20s} "
                  f"{item.get('symbol','?'):8s} {item.get('bias','?'):12s} "
                  f"conf={item.get('confidence','?')}")

    except Exception as e:
        _fail(f"查询失败: {e}")
        sys.exit(1)


@audit.command("trail")
@click.option("--user-id", default=None)
@click.option("--resource", default=None)
@click.option("--limit", default=50, type=int)
@click.option("--json", "as_json", is_flag=True)
def audit_trail(user_id, resource, limit, as_json):
    """查询操作审计轨迹（只读）"""
    _section(f"Audit trail  [{_ts()}]")
    params = f"?limit={limit}"
    if user_id:
        params += f"&user_id={user_id}"
    if resource:
        params += f"&resource={resource}"
    try:
        result = _get(f"/api/v1/auth/audit{params}")
        if as_json:
            _json(result)
            return

        entries = result.get("entries", [])
        _ok(f"查询到 {len(entries)} 条记录")
        for e in entries:
            ts = e.get("timestamp", "?").split("T")[1][:8]
            result_tag = f"{GREEN}{e.get('result','?')}{RESET}"
            print(f"  [{ts}] {result_tag:12s} {e.get('user_id','?'):12s} "
                  f"{e.get('action','?'):30s} {e.get('resource','?')}")

    except Exception as e:
        _fail(f"查询失败: {e}")
        sys.exit(1)


# ── Feedback ────────────────────────────────────────────────

@cli.group("feedback")
def feedback():
    """Feedback 扫描操作"""
    pass


@feedback.command("scan")
@click.option("--feedback-type", default="all",
              type=click.Choice(["all", "loss_amplification", "win_fade",
                                  "regime_mismatch", "confidence_mismatch",
                                  "low_signal_count"]))
@click.option("--symbol", default=None)
@click.option("--json", "as_json", is_flag=True)
def feedback_scan(feedback_type, symbol, as_json):
    """提交 Feedback 扫描任务"""
    _section(f"Feedback scan  [{_ts()}]")
    data = {"feedback_type": feedback_type}
    if symbol:
        data["symbol"] = symbol
    try:
        result = _post("/api/v1/audit/feedback/tasks", data)
        if as_json:
            _json(result)
            return

        _ok("Feedback 扫描任务已提交")
        print(f"  task_id:   {result.get('task_id')}")
        print(f"  status:    {result.get('status')}")
        print(f"  message:   {result.get('message','')}")
        print(f"\n  查询结果: python -m apps.cli feedback result --task-id {result.get('task_id')}")

    except Exception as e:
        _fail(f"请求失败: {e}")
        sys.exit(1)


@feedback.command("result")
@click.option("--task-id", required=True)
@click.option("--poll", is_flag=True, help="持续轮询直到完成")
def feedback_result(task_id, poll):
    """查询 Feedback 扫描结果"""
    import time
    _section(f"Feedback result  {task_id}  [{_ts()}]")
    try:
        while True:
            result = _get(f"/api/v1/audit/feedback/tasks/{task_id}")
            status = result.get("status", "?")
            print(f"  status:         {status}")
            print(f"  feedback_count: {result.get('feedback_count', 0)}")

            if status == "done":
                _ok("扫描完成")
                fbs = result.get("feedbacks", [])
                for fb in fbs[:10]:
                    sev = fb.get("severity", "?")
                    tag = (f"{RED}{sev}{RESET}" if sev == "critical"
                           else f"{YELLOW}{sev}{RESET}" if sev == "warning"
                           else f"{GREEN}{sev}{RESET}")
                    print(f"  {tag:12s} {fb.get('feedback_type','?'):25s} "
                          f"{fb.get('description','?')[:60]}")
                if len(fbs) > 10:
                    print(f"  ... 还有 {len(fbs)-10} 条")
                break
            elif status == "error":
                _fail(f"扫描出错: {result.get('error','')}")
                break
            else:
                print(f"  正在处理...")
                if not poll:
                    break
                time.sleep(2)

    except Exception as e:
        _fail(f"查询失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
