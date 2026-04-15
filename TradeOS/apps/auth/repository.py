"""
apps/auth/repository.py — 用户与审计存储（SQLite）

首批方案：单一 SQLite 文件，不依赖外部数据库。
路径由 AppSettings.feedback_registry_path 同级目录管理。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from apps.auth.models import AuditEntry, OperatorRole, User


class AuthRepository:
    """
    SQLite 用户存储 + 审计记录。

    表结构：
      users          — id / username / role / created_at / is_active / description
      audit_entries  — id / timestamp / user_id / action / resource / detail / result / note
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            base = Path.home() / ".ai-trading-tool"
            base.mkdir(parents=True, exist_ok=True)
            db_path = base / "auth.db"

        self._db_path = db_path
        self._init_db()

    # ── 初始化 ─────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    description TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_entries (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    detail TEXT,
                    result TEXT NOT NULL,
                    note TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_entries(timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user
                    ON audit_entries(user_id)
            """)
            conn.commit()

        # 初始化默认用户（dev 环境）
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        """dev 环境默认用户（auth_enabled=False 时仍可创建）。"""
        defaults = [
            User(
                id="system",
                username="system",
                role=OperatorRole.OPERATOR,
                description="Internal system calls",
            ),
            User(
                id="viewer",
                username="viewer",
                role=OperatorRole.VIEWER,
                description="Read-only monitoring",
            ),
            User(
                id="operator",
                username="operator",
                role=OperatorRole.OPERATOR,
                description="Standard operator (suggestion-only)",
            ),
            User(
                id="admin",
                username="admin",
                role=OperatorRole.ADMIN,
                description="Admin with review/confirm rights",
            ),
        ]
        with sqlite3.connect(self._db_path) as conn:
            for u in defaults:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users
                        (id, username, role, created_at, is_active, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        u.id,
                        u.username,
                        u.role.value,
                        u.created_at.isoformat(),
                        1,
                        u.description,
                    ),
                )
            conn.commit()

    # ── 用户查询 ───────────────────────────────────────────

    def get_user(self, user_id: str) -> Optional[User]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return User(
            id=row["id"],
            username=row["username"],
            role=OperatorRole(row["role"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            is_active=bool(row["is_active"]),
            description=row["description"],
        )

    def list_users(self) -> list[User]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM users WHERE is_active = 1 ORDER BY created_at"
            ).fetchall()

        return [
            User(
                id=r["id"],
                username=r["username"],
                role=OperatorRole(r["role"]),
                created_at=datetime.fromisoformat(r["created_at"]),
                is_active=bool(r["is_active"]),
                description=r["description"],
            )
            for r in rows
        ]

    # ── 审计记录 ───────────────────────────────────────────

    def log_audit(
        self,
        user_id: str,
        action: str,
        resource: str,
        detail: Optional[dict] = None,
        result: str = "accepted",
        note: Optional[str] = None,
    ) -> AuditEntry:
        """追加一条审计记录（append-only）。"""
        entry = AuditEntry(
            id=f"audit-{uuid.uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            user_id=user_id,
            action=action,
            resource=resource,
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
            result=result,
            note=note,
        )

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_entries
                    (id, timestamp, user_id, action, resource, detail, result, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.timestamp.isoformat(),
                    entry.user_id,
                    entry.action,
                    entry.resource,
                    entry.detail,
                    entry.result,
                    entry.note,
                ),
            )
            conn.commit()

        return entry

    def query_audit(
        self,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row

            sql = "SELECT * FROM audit_entries WHERE 1=1"
            params: list = []

            if user_id:
                sql += " AND user_id = ?"
                params.append(user_id)
            if resource:
                sql += " AND resource = ?"
                params.append(resource)

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

        return [
            AuditEntry(
                id=r["id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                user_id=r["user_id"],
                action=r["action"],
                resource=r["resource"],
                detail=r["detail"],
                result=r["result"],
                note=r["note"],
            )
            for r in rows
        ]
