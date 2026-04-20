"""Append-only persistence for DecisionRecord objects."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.audit.schemas.decision_record import DecisionRecord


class DecisionRegistry:
    """Persist and query DecisionRecord snapshots as append-only JSONL."""

    def __init__(self, base_path: str | None = None) -> None:
        if base_path:
            base = Path(base_path)
        else:
            try:
                from infra.config.settings import get_settings

                base = get_settings().app_data_dir / "audit" / "decision_registry"
            except Exception:
                base = Path(__file__).resolve().parents[3] / ".runtime" / "audit" / "decision_registry"
        self._base = base
        self._base.mkdir(parents=True, exist_ok=True)

    def append(self, record: DecisionRecord) -> None:
        if not isinstance(record, DecisionRecord):
            raise TypeError(f"DecisionRegistry.append() requires DecisionRecord, got {type(record).__name__}.")
        with open(self._path_for_today(), "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def read_all(self, *, symbol: str | None = None, since: datetime | None = None) -> list[DecisionRecord]:
        records: list[DecisionRecord] = []
        for path in sorted(self._base.glob("*.jsonl"), reverse=True):
            if since and not self._date_might_match(path, since):
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = DecisionRecord.model_validate_json(line)
                    except Exception:
                        continue
                    if symbol and record.symbol != symbol:
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
            return datetime.strptime(path.stem, "%Y-%m-%d") >= since.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            return True
