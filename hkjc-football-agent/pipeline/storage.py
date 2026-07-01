"""JSON / JSONL record storage with idempotent upsert."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import DEFAULT_RECORDS_JSON, DEFAULT_RECORDS_JSONL


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def load_records(path: Path = DEFAULT_RECORDS_JSON) -> dict[str, Any]:
    if not path.exists():
        return {"recorded_at": None, "match_count": 0, "matches": []}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def upsert_record(
    record: dict[str, Any],
    *,
    json_path: Path = DEFAULT_RECORDS_JSON,
    jsonl_path: Path = DEFAULT_RECORDS_JSONL,
    date_range: str | None = None,
    json_only: bool = False,
) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if json_only:
        return

    json_path.parent.mkdir(parents=True, exist_ok=True)
    data = load_records(json_path)
    matches: list[dict[str, Any]] = data.get("matches") or []
    mid = record["match_id"]
    replaced = False
    for i, existing in enumerate(matches):
        if existing.get("match_id") == mid:
            matches[i] = record
            replaced = True
            break
    if not replaced:
        matches.append(record)

    matches.sort(key=lambda m: (m.get("date", ""), m.get("match_id", "")))
    payload = {
        "date_range": date_range or data.get("date_range"),
        "recorded_at": _now_iso(),
        "match_count": len(matches),
        "matches": matches,
    }
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def merge_jsonl_files(
    jsonl_paths: list[Path],
    *,
    json_path: Path = DEFAULT_RECORDS_JSON,
    date_range: str | None = None,
) -> dict[str, Any]:
    """Merge worker JSONL shards into one records.json (latest line per match_id wins)."""
    by_id: dict[str, dict[str, Any]] = {}
    for path in jsonl_paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                by_id[rec["match_id"]] = rec

    if json_path.exists():
        for rec in load_records(json_path).get("matches") or []:
            mid = rec.get("match_id")
            if mid and mid not in by_id:
                by_id[mid] = rec

    matches = sorted(by_id.values(), key=lambda m: (m.get("date", ""), m.get("match_id", "")))
    payload = {
        "date_range": date_range,
        "recorded_at": _now_iso(),
        "match_count": len(matches),
        "matches": matches,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return payload
