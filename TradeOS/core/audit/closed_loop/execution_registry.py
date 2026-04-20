"""Append-only persistence for ExecutionRecord objects."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.audit.schemas.execution_record import ExecutionRecord


class ExecutionRegistry:
    """Persist and query ExecutionRecord snapshots as append-only JSONL."""

    def __init__(self, base_path: str | None = None) -> None:
        if base_path:
            base = Path(base_path)
        else:
            try:
                from infra.config.settings import get_settings

                base = get_settings().app_data_dir / "audit" / "execution_registry"
            except Exception:
                base = Path(__file__).resolve().parents[3] / ".runtime" / "audit" / "execution_registry"
        self._base = base
        self._base.mkdir(parents=True, exist_ok=True)

    def append(self, record: ExecutionRecord) -> None:
        if not isinstance(record, ExecutionRecord):
            raise TypeError(
                f"ExecutionRegistry.append() requires ExecutionRecord, got {type(record).__name__}."
            )
        with open(self._path_for_today(), "a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    def read_all(
        self,
        *,
        symbol: str | None = None,
        decision_id: str | None = None,
        since: datetime | None = None,
    ) -> list[ExecutionRecord]:
        records: list[ExecutionRecord] = []
        for path in sorted(self._base.glob("*.jsonl"), reverse=True):
            if since and not self._date_might_match(path, since):
                continue
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = ExecutionRecord.model_validate_json(line)
                    except Exception:
                        continue
                    if symbol and record.symbol != symbol:
                        continue
                    if decision_id and record.decision_id != decision_id:
                        continue
                    if since and record.timestamp < since:
                        continue
                    records.append(record)
        records.sort(key=lambda item: item.timestamp, reverse=True)
        return records

    def _path_for_today(self) -> Path:
        return self._base / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"

    def _date_might_match(self, path: Path, since: datetime) -> bool:
        try:
            file_date = datetime.strptime(path.stem, "%Y-%m-%d")
        except ValueError:
            return True
        return file_date >= since.replace(hour=0, minute=0, second=0, microsecond=0)
