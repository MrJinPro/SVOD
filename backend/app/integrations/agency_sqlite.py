from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class SQLiteConnInfo:
    path: Path


def _month_table_suffix(d: date) -> str:
    # В агентской БД таблицы архивов называются как archiveYYYYMM01 / eventserviceYYYYMM01
    return d.strftime("%Y%m01")


def parse_sqlite_url(url: str) -> SQLiteConnInfo:
    # Accept:
    # - sqlite:///C:/path/to/agency_raw.db
    # - sqlite:////absolute/unix/path
    # - sqlite+aiosqlite:///...
    u = urlparse(url)
    scheme = (u.scheme or "").lower()
    if not scheme.startswith("sqlite"):
        raise ValueError("agency_database_url must be a SQLite URL")

    # urlparse for sqlite:///C:/x yields path '/C:/x'
    raw_path = unquote(u.path or "")
    if not raw_path:
        raise ValueError("agency_database_url must include DB path")

    p = Path(raw_path.lstrip("/")) if raw_path.startswith("/") and ":" in raw_path[:4] else Path(raw_path)
    p = p.expanduser().resolve()
    return SQLiteConnInfo(path=p)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def _rows_to_dicts(cur) -> list[dict[str, Any]]:
    rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out


def _parse_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # Common SQL Server dump format: "YYYY-MM-DD HH:MM:SS[.ms]"
        try:
            return datetime.fromisoformat(s.replace(" ", "T", 1))
        except Exception:
            return None
    return None


def fetch_objects_snapshot(sqlite_url: str) -> dict[str, Any]:
    """Снимает снапшот объектов/групп/ответственных из SQLite-слепка агентской БД.

    Ожидается база, полученная из дампов через backend/scripts/import_agency_sql.py
    (например agency_raw.db).
    """

    info = parse_sqlite_url(sqlite_url)
    if not info.path.exists():
        raise FileNotFoundError(f"Agency SQLite DB not found: {info.path}")

    with _connect(info.path) as conn:
        objects = _rows_to_dicts(
            conn.execute(
                """
                SELECT
                  p.Panel_id,
                  p.Disabled,
                  p.Remarks,
                  p.AdditionalTechnicalInformation,
                  p.Latitude,
                  p.Longtitude,
                  p.CreateDate,
                  p.DateLastChange,
                  c.CompanyName,
                  c.address AS CompanyAddress,
                  c.Memo AS CompanyMemo
                FROM Panel p
                LEFT JOIN (
                  SELECT Panel_id, MAX(CompanyID) AS CompanyID
                  FROM Groups
                  GROUP BY Panel_id
                ) g ON g.Panel_id = p.Panel_id
                LEFT JOIN Company c ON c.ID = g.CompanyID
                """
            )
        )

        groups = _rows_to_dicts(
            conn.execute(
                """
                SELECT
                  Panel_id,
                  Group_ AS GroupNo,
                  Message AS GroupName,
                  IsOpen,
                  TimeEvent
                FROM Groups
                """
            )
        )

        responsibles = _rows_to_dicts(
            conn.execute(
                """
                SELECT
                  r.panel_id AS Panel_id,
                  r.Group_ AS GroupNo,
                  r.Responsible_Number AS OrderNo,
                  rl.ResponsiblesList_id AS ListId,
                  rl.Responsible_Name AS ResponsibleName,
                  rl.Responsible_Address AS ResponsibleAddress
                FROM Responsibles r
                INNER JOIN ResponsiblesList rl
                  ON rl.ResponsiblesList_id = r.ResponsiblesList_id
                """
            )
        )

        phones = _rows_to_dicts(
            conn.execute(
                """
                SELECT
                  ResponsiblesList_id AS ListId,
                  PhoneNo,
                  TypeTel_id AS TypeId
                FROM ResponsibleTel
                """
            )
        )

    # Coerce some timestamps when present.
    for o in objects:
        o["CreateDate"] = _parse_dt(o.get("CreateDate"))
        o["DateLastChange"] = _parse_dt(o.get("DateLastChange"))
    for g in groups:
        g["TimeEvent"] = _parse_dt(g.get("TimeEvent"))

    return {
        "objects": objects,
        "groups": groups,
        "responsibles": responsibles,
        "phones": phones,
    }


def fetch_archive_events_since(
    sqlite_url: str,
    *,
    cursor_date_key: int,
    cursor_event_id: int,
    limit: int,
    until_date_key: int | None = None,
) -> list[dict[str, Any]]:
    """Читает события из archiveYYYYMM01 в SQLite-слепке агентской БД.

    Возвращает события в порядке (Date_Key, Event_id).
    """

    if limit <= 0:
        return []

    info = parse_sqlite_url(sqlite_url)
    if not info.path.exists():
        raise FileNotFoundError(f"Agency SQLite DB not found: {info.path}")

    if until_date_key is None:
        until_date_key = int(date.today().strftime("%Y%m%d"))

    start_date = datetime.strptime(str(cursor_date_key), "%Y%m%d").date()
    end_date = datetime.strptime(str(until_date_key), "%Y%m%d").date()

    months: list[date] = []
    d = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while d <= end_month:
        months.append(d)
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)

    out: list[dict[str, Any]] = []
    with _connect(info.path) as conn:
        for m in months:
            if len(out) >= limit:
                break

            suffix = _month_table_suffix(m)
            archive_table = f"archive{suffix}"
            service_table = f"eventservice{suffix}"

            remaining = limit - len(out)
            sql = f"""
            SELECT
              a.Event_id,
              a.Event_Parent_id,
              a.Date_Key,
              a.Panel_id,
              a.Group_ AS GroupNo,
              a.Line,
              a.Zone,
              a.Code,
              a.CodeGroup,
              a.TimeEvent,
              a.MeterCount,
              a.TimeMeterCount,
              a.Result_Text,
              a.StateEvent,
              (
                SELECT s.NameState
                FROM {service_table} s
                WHERE s.Event_id = a.Event_id AND s.Date_Key = a.Date_Key
                ORDER BY s.OperationTime DESC
                LIMIT 1
              ) AS NameState,
              (
                SELECT s.PersonName
                FROM {service_table} s
                WHERE s.Event_id = a.Event_id AND s.Date_Key = a.Date_Key
                ORDER BY s.OperationTime DESC
                LIMIT 1
              ) AS PersonName,
              (
                SELECT s.GrResponseName
                FROM {service_table} s
                WHERE s.Event_id = a.Event_id AND s.Date_Key = a.Date_Key
                ORDER BY s.OperationTime DESC
                LIMIT 1
              ) AS GrResponseName,
              (
                SELECT s.OperationTime
                FROM {service_table} s
                WHERE s.Event_id = a.Event_id AND s.Date_Key = a.Date_Key
                ORDER BY s.OperationTime DESC
                LIMIT 1
              ) AS OperationTime,
              st.StateName AS StateName,
              st.isOverProcess AS StateIsOverProcess,
              COALESCE(ct.CodeMes_RU, ct.Message) AS CodeText
            FROM {archive_table} a
            LEFT JOIN States st
              ON st.State_id = a.StateEvent
            LEFT JOIN Code_T ct
              ON ct.Code = a.Code AND ct.CodeGroup = a.CodeGroup
            WHERE a.Date_Key BETWEEN ? AND ?
              AND (
                a.Date_Key > ?
                OR (a.Date_Key = ? AND a.Event_id > ?)
              )
            ORDER BY a.Date_Key ASC, a.Event_id ASC
            LIMIT {int(remaining)}
            """

            params = [cursor_date_key, until_date_key, cursor_date_key, cursor_date_key, cursor_event_id]
            try:
                rows = _rows_to_dicts(conn.execute(sql, params))
            except Exception:
                # If monthly tables are missing, just skip.
                continue

            # Coerce timestamps (sqlite stores them as TEXT).
            for r in rows:
                r["TimeEvent"] = _parse_dt(r.get("TimeEvent"))
                r["TimeMeterCount"] = _parse_dt(r.get("TimeMeterCount"))
                r["OperationTime"] = _parse_dt(r.get("OperationTime"))

            out.extend(rows)

    return out


def fetch_gbr_group_statuses(sqlite_url: str) -> dict[str, Any]:
    """Возвращает текущие статусы групп реагирования (ГБР) из SQLite-слепка.

    Источник:
    - GroupResponse: текущий Status_id по каждой группе
    - StatusGroupResponse: справочник статусов (Reason)

    Ожидается база, полученная из дампов через backend/scripts/import_agency_sql.py.
    """

    info = parse_sqlite_url(sqlite_url)
    if not info.path.exists():
        raise FileNotFoundError(f"Agency SQLite DB not found: {info.path}")

    snapshot_at = datetime.utcnow()

    with _connect(info.path) as conn:
        # Fail fast with a clear message if the dump doesn't include required tables.
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('GroupResponse','StatusGroupResponse')"
            ).fetchall()
        }
        if "GroupResponse" not in tables:
            raise RuntimeError("Table GroupResponse not found in agency SQLite DB")
        if "StatusGroupResponse" not in tables:
            raise RuntimeError("Table StatusGroupResponse not found in agency SQLite DB")

        rows = _rows_to_dicts(
            conn.execute(
                """
                SELECT
                  gr.Group_id,
                  gr.Description,
                  gr.Status_id,
                  sgr.Reason AS StatusReason,
                  gr.Event_id,
                  gr.Panel_id,
                  gr.Group_,
                  gr.Engine,
                  gr.Track,
                  gr.Mphone_id,
                  gr.Disabled,
                  gr.Category,
                  gr.callsign,
                  gr.DislocationPointLat,
                  gr.DislocationPointLon,
                  gr.TimeArriveToObject,
                  gr.StartTime,
                  gr.EndTime
                FROM GroupResponse gr
                LEFT JOIN StatusGroupResponse sgr
                  ON sgr.status_id = gr.Status_id
                ORDER BY COALESCE(gr.Description, ''), gr.Group_id
                """
            )
        )

    # Coerce some timestamps when present.
    for r in rows:
        r["StartTime"] = _parse_dt(r.get("StartTime"))
        r["EndTime"] = _parse_dt(r.get("EndTime"))
        r["TimeArriveToObject"] = _parse_dt(r.get("TimeArriveToObject"))

    return {
        "snapshotAt": snapshot_at.isoformat(),
        "rows": rows,
    }


def fetch_gbr_names(sqlite_url: str) -> list[str]:
    """Возвращает список уникальных имён ГБР из агентской SQLite-слепка."""
    info = parse_sqlite_url(sqlite_url)
    if not info.path.exists():
        raise FileNotFoundError(f"Agency SQLite DB not found: {info.path}")

    with _connect(info.path) as conn:
        rows = _rows_to_dicts(
            conn.execute(
                """
                SELECT DISTINCT Description
                FROM GroupResponse
                WHERE Description IS NOT NULL AND trim(Description) != ''
                ORDER BY Description ASC
                """
            )
        )

    return [str(r.get("Description") or "").strip() for r in rows if str(r.get("Description") or "").strip()]


def fetch_gbr_archive_trips(
    sqlite_url: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    group_id: int | None = None,
    panel_id: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """История выездов ГБР из ArchiveGroupResponse.

    Полезно для показа:
    - когда группа выехала/прибыла (StartTime/EndTime)
    - на какой объект (Panel_id)
    - какой статус был выставлен (Status_id -> StatusGroupResponse.Reason)
    """

    info = parse_sqlite_url(sqlite_url)
    if not info.path.exists():
        raise FileNotFoundError(f"Agency SQLite DB not found: {info.path}")

    if limit <= 0:
        limit = 1
    limit = min(int(limit), 50000)

    snapshot_at = datetime.utcnow()

    def _fmt(dt: datetime) -> str:
        # SQLite stores MSSQL datetimes as TEXT; lexicographic compare works for ISO-ish format.
        return dt.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")

    where: list[str] = []
    params: list[Any] = []
    if date_from is not None:
        where.append("agr.StartTime >= ?")
        params.append(_fmt(date_from))
    if date_to is not None:
        where.append("agr.StartTime < ?")
        params.append(_fmt(date_to))
    if group_id is not None:
        where.append("agr.Group_id = ?")
        params.append(int(group_id))
    if panel_id is not None and str(panel_id).strip():
        where.append("agr.Panel_id = ?")
        params.append(str(panel_id).strip())

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with _connect(info.path) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name IN ('ArchiveGroupResponse','StatusGroupResponse','GroupResponse','Panel','Groups','Company')
                """
            ).fetchall()
        }
        if "ArchiveGroupResponse" not in tables:
            raise RuntimeError("Table ArchiveGroupResponse not found in agency SQLite DB")
        if "StatusGroupResponse" not in tables:
            raise RuntimeError("Table StatusGroupResponse not found in agency SQLite DB")

        # Optional object enrichment if Panel/Groups/Company are present.
        join_object_sql = ""
        select_object_sql = ""
        if {"Panel", "Groups", "Company"}.issubset(tables):
            join_object_sql = """
            LEFT JOIN Panel p
              ON p.Panel_id = agr.Panel_id
            LEFT JOIN (
              SELECT Panel_id, MAX(CompanyID) AS CompanyID
              FROM Groups
              GROUP BY Panel_id
            ) g
              ON g.Panel_id = agr.Panel_id
            LEFT JOIN Company c
              ON c.ID = g.CompanyID
            """
            select_object_sql = ",\n                  c.CompanyName AS ObjectName,\n                  c.address AS ObjectAddress"

        rows = _rows_to_dicts(
            conn.execute(
                f"""
                SELECT
                  agr.id,
                  agr.Group_id,
                  gr.Description AS GroupName,
                  agr.StartTime,
                  agr.EndTime,
                  agr.Status_id,
                  sgr.Reason AS StatusReason,
                  agr.Panel_id,
                  agr.Group_ AS GroupNo
                  {select_object_sql}
                FROM ArchiveGroupResponse agr
                LEFT JOIN StatusGroupResponse sgr
                  ON sgr.status_id = agr.Status_id
                LEFT JOIN GroupResponse gr
                  ON gr.Group_id = agr.Group_id
                {join_object_sql}
                {where_sql}
                ORDER BY agr.StartTime DESC, agr.id DESC
                LIMIT {int(limit)}
                """,
                params,
            )
        )

    for r in rows:
        r["StartTime"] = _parse_dt(r.get("StartTime"))
        r["EndTime"] = _parse_dt(r.get("EndTime"))

        # Duration in seconds (if both timestamps are present)
        try:
            st = r.get("StartTime")
            et = r.get("EndTime")
            if isinstance(st, datetime) and isinstance(et, datetime):
                r["DurationSeconds"] = int((et - st).total_seconds())
            else:
                r["DurationSeconds"] = None
        except Exception:
            r["DurationSeconds"] = None

    return {
        "snapshotAt": snapshot_at.isoformat(),
        "rows": rows,
    }


def _suffix_from_date_key(date_key: int) -> str:
    s = str(int(date_key))
    if len(s) != 8:
        return s[:6] + "01"
    return s[:6] + "01"


def fetch_eventservice_actions_for_event_pairs(
    sqlite_url: str,
    *,
    event_pairs: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    """Читает строки из eventserviceYYYYMM01 для набора (Date_Key, Event_id)."""

    if not event_pairs:
        return []

    info = parse_sqlite_url(sqlite_url)
    if not info.path.exists():
        raise FileNotFoundError(f"Agency SQLite DB not found: {info.path}")

    pairs_by_suffix: dict[str, list[tuple[int, int]]] = {}
    for dk, eid in event_pairs:
        suffix = _suffix_from_date_key(dk)
        pairs_by_suffix.setdefault(suffix, []).append((int(dk), int(eid)))

    out: list[dict[str, Any]] = []
    chunk_size = 250

    with _connect(info.path) as conn:
        for suffix, p_list in pairs_by_suffix.items():
            service_table = f"eventservice{suffix}"

            for i in range(0, len(p_list), chunk_size):
                chunk = p_list[i : i + chunk_size]
                values_sql = ", ".join(["(?, ?)"] * len(chunk))
                params: list[Any] = []
                for dk, eid in chunk:
                    params.append(int(dk))
                    params.append(int(eid))

                sql = f"""
                WITH pairs(Date_Key, Event_id) AS (
                    VALUES {values_sql}
                )
                SELECT
                    s.Service_id,
                    s.NameState,
                    s.Event_id,
                    s.Computer,
                    s.OperationTime,
                    s.Date_Key,
                    s.PersonName,
                    s.GrResponseName
                FROM {service_table} s
                INNER JOIN pairs p
                    ON p.Date_Key = s.Date_Key AND p.Event_id = s.Event_id
                ORDER BY s.Date_Key ASC, s.Event_id ASC, s.OperationTime ASC, s.Service_id ASC
                """

                try:
                    rows = _rows_to_dicts(conn.execute(sql, params))
                except Exception:
                    break

                for r in rows:
                    r["OperationTime"] = _parse_dt(r.get("OperationTime"))

                out.extend(rows)

    return out
