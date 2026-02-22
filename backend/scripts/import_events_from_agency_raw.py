from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Stats:
    tables: int = 0
    read: int = 0
    inserted: int = 0


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def _list_tables(conn: sqlite3.Connection, prefix: str) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY name",
        (f"{prefix}%",),
    ).fetchall()
    return [r[0] for r in rows]


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cols = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return {c[1] for c in cols}


def _safe_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _status_from_row(r: sqlite3.Row) -> str:
    state_is_over = r.get("StateIsOverProcess")
    state_event = r.get("StateEvent")
    state_name = _safe_str(r.get("StateName"))
    name_state = _safe_str(r.get("NameState"))

    is_over = bool(state_is_over) if state_is_over is not None else False
    if is_over:
        return "resolved"
    if state_event is not None or state_name or name_state:
        return "pending"
    return "active"


def _build_description(r: sqlite3.Row) -> str:
    date_key = r.get("Date_Key")
    event_id = r.get("Event_id")
    panel_id = _safe_str(r.get("Panel_id"))

    code = _safe_str(r.get("Code"))
    code_text = _safe_str(r.get("CodeText"))
    zone = r.get("Zone")
    line = _safe_str(r.get("Line"))
    result_text = _safe_str(r.get("Result_Text"))
    meter_count = _safe_str(r.get("MeterCount"))

    state_event = r.get("StateEvent")
    state_name = _safe_str(r.get("StateName"))
    name_state = _safe_str(r.get("NameState"))

    person = _safe_str(r.get("PersonName"))
    gbr = _safe_str(r.get("GrResponseName"))

    parts: list[str] = []
    if event_id is not None:
        parts.append(f"Event_id: {event_id}")
    if date_key is not None:
        parts.append(f"Date_Key: {date_key}")
    if panel_id:
        parts.append(f"Panel_id: {panel_id}")

    if code:
        if code_text:
            parts.append(f"Код: {code} — {code_text}")
        else:
            parts.append(f"Код: {code}")
    if zone is not None:
        parts.append(f"Зона: {zone}")
    if line:
        parts.append(f"Шлейф: {line}")

    if state_event is not None or state_name or name_state:
        st_id = str(state_event) if state_event is not None else ""
        st_label = state_name or name_state or ""
        if st_id and st_label:
            parts.append(f"Статус: {st_label} (StateEvent={st_id})")
        elif st_label:
            parts.append(f"Статус: {st_label}")
        elif st_id:
            parts.append(f"StateEvent: {st_id}")

    if person:
        parts.append(f"Оператор: {person}")
    if gbr:
        parts.append(f"ГБР: {gbr}")
    if result_text:
        parts.append(result_text)
    if meter_count:
        parts.append(f"Параметр: {meter_count}")

    return "\n".join(parts)


def import_events(
    agency_db: Path,
    svod_db: Path,
    *,
    from_date_key: int = 20230101,
    table_regex: str | None = None,
    commit_every: int = 5000,
) -> None:
    src = _connect(agency_db)
    dst = _connect(svod_db)

    try:
        tables = _list_tables(src, "archive")
        if table_regex:
            import re

            rx = re.compile(table_regex, flags=re.IGNORECASE)
            tables = [t for t in tables if rx.search(t)]

        if not tables:
            raise SystemExit("No archive* tables found in agency_raw.db")

        # Detect available columns in destination events table to keep script compatible.
        dst_event_cols = _table_columns(dst, "events")

        # Load local objects snapshot for name/client/address enrichment.
        obj_map: dict[str, tuple[str | None, str | None, str | None]] = {}
        try:
            for r in dst.execute("SELECT id, name, client_name, address FROM objects").fetchall():
                obj_map[str(r[0])] = (r[1], r[2], r[3])
        except Exception:
            obj_map = {}

        stats = Stats()
        last_changes = dst.total_changes

        def _insert_row(row: sqlite3.Row) -> tuple | None:
            try:
                date_key = int(row.get("Date_Key"))
                event_id = int(row.get("Event_id"))
            except Exception:
                return None
            if date_key < int(from_date_key):
                return None

            ts = row.get("TimeEvent")
            # In some dumps it can be a string. We keep ISO-ish strings as-is.
            if isinstance(ts, datetime):
                ts_val = ts.isoformat()
            else:
                ts_val = str(ts) if ts is not None else ""
                if not ts_val:
                    return None

            panel_id = _safe_str(row.get("Panel_id"))
            obj = obj_map.get(panel_id or "") if panel_id else None

            code = _safe_str(row.get("Code"))
            code_text = _safe_str(row.get("CodeText"))
            state_name = _safe_str(row.get("StateName"))
            state_is_over = row.get("StateIsOverProcess")
            result_text = _safe_str(row.get("Result_Text"))
            meter_count = _safe_str(row.get("MeterCount"))
            time_meter_count = row.get("TimeMeterCount")
            person = _safe_str(row.get("PersonName"))

            object_name = (obj[0] if obj and obj[0] else None) or panel_id or "Объект"
            client_name = (obj[1] if obj and obj[1] else None) or panel_id or "Не указан"
            address = (obj[2] if obj and obj[2] else None)

            eid = f"mssql:{date_key}:{event_id}"
            status = _status_from_row(row)
            desc = _build_description(row)

            # Build values in stable column order.
            values: dict[str, Any] = {
                "id": eid,
                "timestamp": ts_val,
                "type": "alarm",
                "object_id": panel_id,
                "object_name": object_name,
                "client_name": client_name,
                "severity": "info",
                "status": status,
                "code": code,
                "code_group": int(row.get("CodeGroup")) if row.get("CodeGroup") is not None else None,
                "code_text": code_text,
                "state_name": state_name,
                "state_is_over_process": bool(state_is_over) if state_is_over is not None else None,
                "description": desc,
                "result_text": result_text,
                "meter_count": meter_count,
                "time_meter_count": (
                    time_meter_count.isoformat() if isinstance(time_meter_count, datetime) else (
                        str(time_meter_count) if time_meter_count is not None else None
                    )
                ),
                "location": address,
                "operator_id": person,
            }

            cols = [c for c in values.keys() if c in dst_event_cols]
            if not cols:
                return None
            return tuple(values[c] for c in cols), cols

        # Prepare insert statement based on detected columns.
        cols_for_insert: list[str] | None = None
        insert_sql: str | None = None

        for t in tables:
            stats.tables += 1
            t_cols = _table_columns(src, t)
            required = {"Date_Key", "Event_id", "TimeEvent"}
            if not required.issubset(t_cols):
                print(f"Skip {t}: missing columns {sorted(required - t_cols)}")
                continue

            print(f"Importing {t} ...")
            cur = src.execute(f"SELECT * FROM '{t}' ORDER BY Date_Key, Event_id")

            batch: list[tuple] = []
            for row in cur:
                stats.read += 1
                out = _insert_row(row)
                if out is None:
                    continue
                vals, cols = out
                if cols_for_insert is None:
                    cols_for_insert = list(cols)
                    ph = ",".join(["?"] * len(cols_for_insert))
                    col_list = ",".join(cols_for_insert)
                    insert_sql = f"INSERT OR IGNORE INTO events ({col_list}) VALUES ({ph})"

                batch.append(vals)
                if len(batch) >= int(commit_every):
                    assert insert_sql is not None
                    dst.executemany(insert_sql, batch)
                    dst.commit()
                    delta = dst.total_changes - last_changes
                    if delta > 0:
                        stats.inserted += delta
                    last_changes = dst.total_changes
                    batch.clear()

            if batch:
                assert insert_sql is not None
                dst.executemany(insert_sql, batch)
                dst.commit()
                delta = dst.total_changes - last_changes
                if delta > 0:
                    stats.inserted += delta
                last_changes = dst.total_changes
                batch.clear()

        print(f"Done. tables={stats.tables} read={stats.read} inserted~={stats.inserted}")
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import archive events (archiveYYYYMM01) from agency_raw.db into backend/svod.db (events table)."
    )
    parser.add_argument("--agency", default=str(Path(__file__).resolve().parents[1] / "agency_raw.db"))
    parser.add_argument("--svod", default=str(Path(__file__).resolve().parents[1] / "svod.db"))
    parser.add_argument("--from-date-key", default="20230101", help="Minimum Date_Key to import (default: 20230101)")
    parser.add_argument("--table-regex", default=None, help="Optional regex to filter archive tables")
    parser.add_argument("--commit-every", default=5000, type=int)
    args = parser.parse_args()

    import_events(
        Path(args.agency).resolve(),
        Path(args.svod).resolve(),
        from_date_key=int(str(args.from_date_key)),
        table_regex=args.table_regex,
        commit_every=int(args.commit_every),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
