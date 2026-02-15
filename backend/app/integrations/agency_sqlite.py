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
              a.Date_Key,
              a.Panel_id,
              a.Group_ AS GroupNo,
              a.Line,
              a.Zone,
              a.Code,
              a.CodeGroup,
              a.TimeEvent,
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
                r["OperationTime"] = _parse_dt(r.get("OperationTime"))

            out.extend(rows)

    return out
