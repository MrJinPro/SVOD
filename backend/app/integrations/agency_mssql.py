from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse


def _months_between(start_date: date, end_date: date) -> list[date]:
    months: list[date] = []
    d = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while d <= end_month:
        months.append(d)
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)
    return months


@dataclass(frozen=True)
class MSSQLConnInfo:
    host: str
    port: int
    database: str
    username: str | None
    password: str | None
    driver: str
    trust_server_certificate: bool
    encrypt: bool


def _date_key(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


def _month_table_suffix(d: date) -> str:
    # В агентской БД таблицы архивов называются как archiveYYYYMM01 / eventserviceYYYYMM01
    return d.strftime("%Y%m01")


def parse_mssql_url(url: str) -> MSSQLConnInfo:
    # Accept SQLAlchemy-like URLs:
    # - mssql+pyodbc://user:pass@host:1433/Pult4DB?driver=ODBC+Driver+18+for+SQL+Server
    # - mssql://user:pass@host:1433/Pult4DB?driver=...
    u = urlparse(url)
    scheme = (u.scheme or "").lower()
    if not scheme.startswith("mssql"):
        raise ValueError("agency_database_url must be an MSSQL URL")

    host = u.hostname
    if not host:
        raise ValueError("agency_database_url must include host")

    database = (u.path or "").lstrip("/")
    if not database:
        raise ValueError("agency_database_url must include database name in path")

    port = int(u.port or 1433)

    qs = parse_qs(u.query or "")
    # На Linux чаще установлен msodbcsql18, поэтому дефолтим на 18.
    # Если в окружении стоит только 17 — укажите driver=ODBC+Driver+17+for+SQL+Server в URL.
    driver = unquote((qs.get("driver", [""]) or [""])[0]) or "ODBC Driver 18 for SQL Server"

    trust = (qs.get("TrustServerCertificate", [""]) or [""])[0].lower()
    trust_server_certificate = trust in ("1", "true", "yes")

    encrypt = (qs.get("Encrypt", [""]) or [""])[0].lower()
    encrypt_bool = encrypt in ("1", "true", "yes")

    username = u.username
    password = u.password

    return MSSQLConnInfo(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        driver=driver,
        trust_server_certificate=trust_server_certificate,
        encrypt=encrypt_bool,
    )


def _build_odbc_conn_str(info: MSSQLConnInfo) -> str:
    server = f"{info.host},{info.port}" if info.port else info.host
    parts = [
        f"DRIVER={{{info.driver}}}",
        f"SERVER={server}",
        f"DATABASE={info.database}",
    ]

    if info.username:
        parts.append(f"UID={info.username}")
    if info.password:
        parts.append(f"PWD={info.password}")

    # Настройки TLS
    parts.append(f"Encrypt={'yes' if info.encrypt else 'no'}")
    parts.append(f"TrustServerCertificate={'yes' if info.trust_server_certificate else 'no'}")

    return ";".join(parts)


def _require_pyodbc():
    try:
        import pyodbc  # type: ignore

        return pyodbc
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pyodbc не установлен/не доступен. Установите зависимости backend и ODBC драйвер SQL Server (например, ODBC Driver 17/18)."
        ) from e


def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
    cols = [c[0] for c in cursor.description]
    out: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        d = {cols[i]: row[i] for i in range(len(cols))}
        out.append(d)
    return out


def fetch_gbr_group_statuses(mssql_url: str) -> dict[str, Any]:
    """Возвращает текущие статусы групп реагирования (ГБР) напрямую из MSSQL.

    Источник:
    - dbo.GroupResponse: текущий Status_id по каждой группе
    - dbo.StatusGroupResponse: справочник статусов (Reason)
    """

    pyodbc = _require_pyodbc()
    info = parse_mssql_url(mssql_url)
    conn_str = _build_odbc_conn_str(info)

    snapshot_at = datetime.utcnow()

    sql = """
    SELECT
        gr.Group_id,
        gr.Description,
        gr.Status_id,
        sgr.reason AS StatusReason,
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
    FROM dbo.GroupResponse gr
    LEFT JOIN dbo.StatusGroupResponse sgr
        ON sgr.status_id = gr.Status_id
    ORDER BY ISNULL(gr.Description, ''), gr.Group_id
    """

    with pyodbc.connect(conn_str, timeout=10) as conn:
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        with conn.cursor() as cur:
            cur.execute(sql)
            rows = _rows_to_dicts(cur)

    return {
        "snapshotAt": snapshot_at.isoformat(),
        "rows": rows,
    }


def fetch_gbr_names(mssql_url: str) -> list[str]:
    """Возвращает список уникальных имён ГБР из агентской MSSQL базы."""
    pyodbc = _require_pyodbc()
    info = parse_mssql_url(mssql_url)
    conn_str = _build_odbc_conn_str(info)

    sql = """
    SELECT DISTINCT Description
    FROM dbo.GroupResponse
    WHERE Description IS NOT NULL AND LTRIM(RTRIM(Description)) != ''
    ORDER BY Description ASC
    """

    with pyodbc.connect(conn_str, timeout=10) as conn:
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        with conn.cursor() as cur:
            cur.execute(sql)
            rows = _rows_to_dicts(cur)

    return [str(r.get("Description") or "").strip() for r in rows if str(r.get("Description") or "").strip()]


def fetch_objects_snapshot(mssql_url: str) -> dict[str, Any]:
    """Снимает снапшот объектов/групп/ответственных из Pult4DB.

    Возвращает структуру:
    {
      "objects": [ {panel_id,...} ],
      "groups": [ {panel_id, group_no,...} ],
      "responsibles": [ {panel_id, group_no, order_no, name, address, list_id} ],
      "phones": [ {list_id, phone, type_id} ],
    }
    """

    pyodbc = _require_pyodbc()
    info = parse_mssql_url(mssql_url)
    conn_str = _build_odbc_conn_str(info)

    with pyodbc.connect(conn_str, timeout=10) as conn:
        # SQL Server returns NVARCHAR/NCHAR via SQL_WCHAR as UTF-16LE.
        # Decoding it as UTF-8 can crash on Cyrillic data.
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        with conn.cursor() as cur:
            cur.execute(
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
                  c.[address] AS CompanyAddress,
                  c.Memo AS CompanyMemo
                FROM dbo.Panel p
                LEFT JOIN (
                  SELECT Panel_id, MAX(CompanyID) AS CompanyID
                  FROM dbo.Groups
                  GROUP BY Panel_id
                ) g ON g.Panel_id = p.Panel_id
                LEFT JOIN dbo.Company c ON c.ID = g.CompanyID
                """
            )
            objects = _rows_to_dicts(cur)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  Panel_id,
                  Group_ AS GroupNo,
                  Message AS GroupName,
                  IsOpen,
                  TimeEvent
                FROM dbo.Groups
                """
            )
            groups = _rows_to_dicts(cur)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  r.panel_id AS Panel_id,
                  r.Group_ AS GroupNo,
                  r.Responsible_Number AS OrderNo,
                  rl.ResponsiblesList_id AS ListId,
                  rl.Responsible_Name AS ResponsibleName,
                  rl.Responsible_Address AS ResponsibleAddress
                FROM dbo.Responsibles r
                INNER JOIN dbo.ResponsiblesList rl
                  ON rl.ResponsiblesList_id = r.ResponsiblesList_id
                """
            )
            responsibles = _rows_to_dicts(cur)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  ResponsiblesList_id AS ListId,
                  PhoneNo,
                  TypeTel_id AS TypeId
                FROM dbo.ResponsibleTel
                """
            )
            phones = _rows_to_dicts(cur)

    return {
        "objects": objects,
        "groups": groups,
        "responsibles": responsibles,
        "phones": phones,
    }


def fetch_archive_events_since(
    mssql_url: str,
    *,
    archives_db_name: str,
    cursor_date_key: int,
    cursor_event_id: int,
    limit: int,
    until_date_key: int | None = None,
) -> list[dict[str, Any]]:
    """Читает события из pult4db_archives.archiveYYYYMM01 начиная с курсора.

    Возвращает события в порядке возрастания (Date_Key, Event_id).
    """

    if limit <= 0:
        return []

    pyodbc = _require_pyodbc()
    info = parse_mssql_url(mssql_url)
    conn_str = _build_odbc_conn_str(info)

    if until_date_key is None:
        until_date_key = _date_key(date.today())

    # Генерируем список месячных таблиц от cursor_date_key до until_date_key
    start_date = datetime.strptime(str(cursor_date_key), "%Y%m%d").date()
    end_date = datetime.strptime(str(until_date_key), "%Y%m%d").date()

    months = _months_between(start_date, end_date)

    out: list[dict[str, Any]] = []

    with pyodbc.connect(conn_str, timeout=10) as conn:
        # SQL Server returns NVARCHAR/NCHAR via SQL_WCHAR as UTF-16LE.
        # Decoding it as UTF-8 can crash on Cyrillic data.
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        for m in months:
            if len(out) >= limit:
                break

            suffix = _month_table_suffix(m)
            archive_table = f"{archives_db_name}.dbo.archive{suffix}"
            service_table = f"{archives_db_name}.dbo.eventservice{suffix}"

            # Reference dictionary tables from the main DB (the one in the URL).
            # We keep them fully-qualified to support cross-database joins.
            code_table = f"{info.database}.dbo.Code_T"
            states_table = f"{info.database}.dbo.States"

            remaining = limit - len(out)

            sql = f"""
            SELECT TOP ({int(remaining)})
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
                es.NameState,
                es.PersonName,
                st.StateName AS StateName,
                st.isOverProcess AS StateIsOverProcess,
                COALESCE(ct.CodeMes_RU, ct.Message) AS CodeText,
                es.GrResponseName,
                es.OperationTime
            FROM {archive_table} a
            OUTER APPLY (
                SELECT TOP (1)
                    s.NameState,
                    s.PersonName,
                    s.GrResponseName,
                    s.OperationTime
                FROM {service_table} s
                WHERE s.Event_id = a.Event_id AND s.Date_Key = a.Date_Key
                ORDER BY s.OperationTime DESC
            ) es
            LEFT JOIN {states_table} st
                ON st.State_id = a.StateEvent
            LEFT JOIN {code_table} ct
                ON ct.Code = a.Code AND ct.CodeGroup = a.CodeGroup
            WHERE a.Date_Key BETWEEN ? AND ?
                AND (
                    a.Date_Key > ?
                    OR (a.Date_Key = ? AND a.Event_id > ?)
                )
            ORDER BY a.Date_Key ASC, a.Event_id ASC
            """

            params = [cursor_date_key, until_date_key, cursor_date_key, cursor_date_key, cursor_event_id]

            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows = _rows_to_dicts(cur)
                    out.extend(rows)
            except Exception as e:
                # If a specific monthly table is missing, skip it.
                # Otherwise, surface the error (so API can report it).
                msg = str(e)
                if "Invalid object name" in msg or "42S02" in msg:
                    continue
                raise

    return out


def fetch_archive_events_recent(
    mssql_url: str,
    *,
    archives_db_name: str,
    date_from_key: int,
    date_to_key: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Читает самые свежие события из архивов MSSQL за диапазон дат.

    Возвращает события в порядке убывания (Date_Key, Event_id).
    """

    if limit <= 0:
        return []

    pyodbc = _require_pyodbc()
    info = parse_mssql_url(mssql_url)
    conn_str = _build_odbc_conn_str(info)

    start_date = datetime.strptime(str(int(date_from_key)), "%Y%m%d").date()
    end_date = datetime.strptime(str(int(date_to_key)), "%Y%m%d").date()

    months = _months_between(start_date, end_date)

    out: list[dict[str, Any]] = []

    with pyodbc.connect(conn_str, timeout=10) as conn:
        # SQL Server returns NVARCHAR/NCHAR via SQL_WCHAR as UTF-16LE.
        # Decoding it as UTF-8 can crash on Cyrillic data.
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        # Most recent first: iterate months in reverse.
        for m in reversed(months):
            if len(out) >= limit:
                break

            suffix = _month_table_suffix(m)
            archive_table = f"{archives_db_name}.dbo.archive{suffix}"
            service_table = f"{archives_db_name}.dbo.eventservice{suffix}"

            # Reference dictionary tables from the main DB (the one in the URL).
            code_table = f"{info.database}.dbo.Code_T"
            states_table = f"{info.database}.dbo.States"

            remaining = limit - len(out)

            sql = f"""
            SELECT TOP ({int(remaining)})
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
                es.NameState,
                es.PersonName,
                st.StateName AS StateName,
                st.isOverProcess AS StateIsOverProcess,
                COALESCE(ct.CodeMes_RU, ct.Message) AS CodeText,
                es.GrResponseName,
                es.OperationTime
            FROM {archive_table} a
            OUTER APPLY (
                SELECT TOP (1)
                    s.NameState,
                    s.PersonName,
                    s.GrResponseName,
                    s.OperationTime
                FROM {service_table} s
                WHERE s.Event_id = a.Event_id AND s.Date_Key = a.Date_Key
                ORDER BY s.OperationTime DESC
            ) es
            LEFT JOIN {states_table} st
                ON st.State_id = a.StateEvent
            LEFT JOIN {code_table} ct
                ON ct.Code = a.Code AND ct.CodeGroup = a.CodeGroup
            WHERE a.Date_Key BETWEEN ? AND ?
            ORDER BY a.Date_Key DESC, a.Event_id DESC
            """

            params = [int(date_from_key), int(date_to_key)]

            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows = _rows_to_dicts(cur)
                    out.extend(rows)
            except Exception as e:
                msg = str(e)
                if "Invalid object name" in msg or "42S02" in msg:
                    continue
                raise

    return out


def fetch_alarm_stands_analysis(
    mssql_url: str,
    *,
    archives_db_name: str,
    date_from: datetime,
    date_to: datetime,
    q: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Анализ объектов из dbo.Stands по архиву событий.

    - Источник стендов: основная БД (dbo.Stands)
    - Архив событий: {archives_db_name}.dbo.archiveYYYYMM01

    Возвращает строки:
      Panel_id, CompanyName/Address (если есть), EventsCount, LastEventAt, TimeBegin/TimeEnd
    """

    pyodbc = _require_pyodbc()
    info = parse_mssql_url(mssql_url)
    conn_str = _build_odbc_conn_str(info)

    snapshot_at = datetime.utcnow()

    # Normalize range.
    if date_to < date_from:
        date_from, date_to = date_to, date_from

    date_from_key = _date_key(date_from.date())
    date_to_key = _date_key(date_to.date())

    # Cap for safety: a huge Stands table would make archive aggregation too slow.
    hard_cap = max(int(limit) * 10, 1000)

    stands_rows: list[dict[str, Any]] = []
    with pyodbc.connect(conn_str, timeout=10) as conn:
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        # Active stands: only stand objects (standorkey=0).
        # Join basic object meta (CompanyName/Address) via Groups -> Company.
        sql_stands = f"""
        ;WITH g AS (
          SELECT Panel_id, MAX(CompanyID) AS CompanyID
          FROM {info.database}.dbo.Groups
          GROUP BY Panel_id
        )
        SELECT TOP ({int(hard_cap)})
          s.Panel_id AS Panel_id,
          s.Group_ AS GroupNo,
          s.Zone AS Zone,
          s.TimeBegin AS TimeBegin,
          s.TimeEnd AS TimeEnd,
          s.Type_Stand AS TypeStand,
          s.standorkey AS StandOrKey,
          c.CompanyName AS CompanyName,
          c.[address] AS CompanyAddress
        FROM {info.database}.dbo.Stands s
        LEFT JOIN g ON g.Panel_id = s.Panel_id
        LEFT JOIN {info.database}.dbo.Company c ON c.ID = g.CompanyID
        WHERE (s.TimeEnd IS NULL OR s.TimeEnd >= GETDATE())
          AND s.standorkey = 0
        ORDER BY s.TimeBegin DESC, s.id DESC
        """

        with conn.cursor() as cur:
            cur.execute(sql_stands)
            stands_rows = _rows_to_dicts(cur)

        query = (q or "").strip().lower()
        if query:
            def _match(row: dict[str, Any]) -> bool:
                panel_id = str(row.get("Panel_id") or "").strip().lower()
                company = str(row.get("CompanyName") or "").strip().lower()
                address = str(row.get("CompanyAddress") or "").strip().lower()
                # Also allow searching by zone/group as a convenient fallback.
                group_no = str(row.get("GroupNo") or row.get("Group_") or "").strip().lower()
                zone = str(row.get("Zone") or "").strip().lower()
                hay = " ".join([panel_id, company, address, group_no, zone])
                return query in hay

            stands_rows = [r for r in stands_rows if _match(r)]

        panel_ids = [str(r.get("Panel_id") or "").strip() for r in stands_rows]
        panel_ids = [p for p in panel_ids if p]
        panel_ids = list(dict.fromkeys(panel_ids))

        # Aggregate events per stand object from archive tables.
        start_date = datetime.strptime(str(int(date_from_key)), "%Y%m%d").date()
        end_date = datetime.strptime(str(int(date_to_key)), "%Y%m%d").date()
        months = _months_between(start_date, end_date)

        counts: dict[str, int] = {}
        last_at: dict[str, datetime] = {}
        code_counts: dict[str, dict[tuple[str, int | None], int]] = {}
        code_last_at: dict[str, dict[tuple[str, int | None], datetime]] = {}

        if panel_ids:
            chunk_size = 200
            for m in months:
                suffix = _month_table_suffix(m)
                archive_table = f"{archives_db_name}.dbo.archive{suffix}"

                month_missing = False

                for i in range(0, len(panel_ids), chunk_size):
                    chunk = panel_ids[i : i + chunk_size]
                    placeholders = ", ".join(["?"] * len(chunk))
                    sql = f"""
                    SELECT
                      a.Panel_id AS Panel_id,
                      COUNT(1) AS EventsCount,
                      MAX(a.TimeEvent) AS LastEventAt
                    FROM {archive_table} a
                    WHERE a.Date_Key BETWEEN ? AND ?
                      AND a.Panel_id IN ({placeholders})
                    GROUP BY a.Panel_id
                    """
                    params: list[Any] = [int(date_from_key), int(date_to_key), *chunk]
                    try:
                        with conn.cursor() as cur:
                            cur.execute(sql, params)
                            rows = _rows_to_dicts(cur)
                    except Exception as e:
                        msg = str(e)
                        if "Invalid object name" in msg or "42S02" in msg:
                            month_missing = True
                            break
                        raise

                    for r in rows:
                        pid = str(r.get("Panel_id") or "").strip()
                        if not pid:
                            continue
                        c = int(r.get("EventsCount") or 0)
                        counts[pid] = counts.get(pid, 0) + c
                        la = r.get("LastEventAt")
                        if isinstance(la, datetime):
                            prev = last_at.get(pid)
                            if prev is None or la > prev:
                                last_at[pid] = la

                if month_missing:
                    continue

                # Per-code aggregation to find top noisy code per Panel_id.
                month_missing = False
                for i in range(0, len(panel_ids), chunk_size):
                    chunk = panel_ids[i : i + chunk_size]
                    placeholders = ", ".join(["?"] * len(chunk))
                    sql = f"""
                    SELECT
                      a.Panel_id AS Panel_id,
                      a.Code AS Code,
                      a.CodeGroup AS CodeGroup,
                      COUNT(1) AS CodeCount,
                      MAX(a.TimeEvent) AS LastEventAt
                    FROM {archive_table} a
                    WHERE a.Date_Key BETWEEN ? AND ?
                      AND a.Panel_id IN ({placeholders})
                    GROUP BY a.Panel_id, a.Code, a.CodeGroup
                    """
                    params = [int(date_from_key), int(date_to_key), *chunk]
                    try:
                        with conn.cursor() as cur:
                            cur.execute(sql, params)
                            rows = _rows_to_dicts(cur)
                    except Exception as e:
                        msg = str(e)
                        if "Invalid object name" in msg or "42S02" in msg:
                            month_missing = True
                            break
                        raise

                    for r in rows:
                        pid = str(r.get("Panel_id") or "").strip()
                        code = str(r.get("Code") or "").strip()
                        if not pid or not code:
                            continue
                        code_group = r.get("CodeGroup")
                        try:
                            code_group_int = int(code_group) if code_group is not None else None
                        except Exception:
                            code_group_int = None

                        key = (code, code_group_int)
                        per_panel = code_counts.setdefault(pid, {})
                        per_panel[key] = per_panel.get(key, 0) + int(r.get("CodeCount") or 0)

                        la = r.get("LastEventAt")
                        if isinstance(la, datetime):
                            per_panel_last = code_last_at.setdefault(pid, {})
                            prev = per_panel_last.get(key)
                            if prev is None or la > prev:
                                per_panel_last[key] = la

                if month_missing:
                    continue

        # Resolve top code per panel.
        top_code: dict[str, tuple[str, int | None] | None] = {}
        top_code_count: dict[str, int] = {}
        for pid, per_panel in code_counts.items():
            best_key: tuple[str, int | None] | None = None
            best_count = -1
            for key, c in per_panel.items():
                if c > best_count:
                    best_key = key
                    best_count = c
                elif c == best_count and best_key is not None:
                    # Tie-breaker: prefer the code with more recent event.
                    prev_last = (code_last_at.get(pid) or {}).get(best_key)
                    curr_last = (code_last_at.get(pid) or {}).get(key)
                    if isinstance(curr_last, datetime) and isinstance(prev_last, datetime) and curr_last > prev_last:
                        best_key = key
                        best_count = c
            if best_key is not None and best_count >= 0:
                top_code[pid] = best_key
                top_code_count[pid] = best_count

        # Fetch code texts for top codes.
        code_text_by_key: dict[tuple[str, int | None], str] = {}
        top_keys = [k for k in top_code.values() if k is not None]
        top_keys = list(dict.fromkeys(top_keys))
        if top_keys:
            code_table = f"{info.database}.dbo.Code_T"
            # Build OR conditions, because (Code, CodeGroup) IN (...) is clunky in pyodbc.
            conditions: list[str] = []
            params: list[Any] = []
            for (code, code_group) in top_keys:
                if code_group is None:
                    conditions.append("(Code = ?)")
                    params.append(code)
                else:
                    conditions.append("(Code = ? AND CodeGroup = ?)")
                    params.extend([code, int(code_group)])

            where = " OR ".join(conditions)
            sql = f"""
            SELECT Code, CodeGroup, COALESCE(CodeMes_RU, Message) AS CodeText
            FROM {code_table}
            WHERE {where}
            """
            try:
                with pyodbc.connect(conn_str, timeout=10) as conn:
                    conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
                    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
                    conn.setencoding(encoding="utf-8")
                    with conn.cursor() as cur:
                        cur.execute(sql, params)
                        rows = _rows_to_dicts(cur)
                        for r in rows:
                            c = str(r.get("Code") or "").strip()
                            if not c:
                                continue
                            cg = r.get("CodeGroup")
                            try:
                                cg_int = int(cg) if cg is not None else None
                            except Exception:
                                cg_int = None
                            text = r.get("CodeText")
                            if isinstance(text, str) and text.strip():
                                code_text_by_key[(c, cg_int)] = text.strip()
            except Exception:
                # Code texts are optional for this endpoint.
                code_text_by_key = code_text_by_key

    # Build final rows and sort by volume.
    out_rows: list[dict[str, Any]] = []
    for r in stands_rows:
        pid = str(r.get("Panel_id") or "").strip()
        la = last_at.get(pid)
        best_key = top_code.get(pid)
        best_code = best_key[0] if best_key else None
        best_group = best_key[1] if best_key else None
        best_text = code_text_by_key.get(best_key) if best_key else None
        out_rows.append(
            {
                "panelId": pid,
                "objectName": r.get("CompanyName"),
                "address": r.get("CompanyAddress"),
                "eventsCount": int(counts.get(pid, 0)),
                "lastEventAt": la.isoformat() if isinstance(la, datetime) else None,
                "topCode": best_code,
                "topCodeGroup": best_group,
                "topCodeText": best_text,
                "topCodeCount": int(top_code_count.get(pid, 0)),
                "timeBegin": r.get("TimeBegin").isoformat() if isinstance(r.get("TimeBegin"), datetime) else r.get("TimeBegin"),
                "timeEnd": r.get("TimeEnd").isoformat() if isinstance(r.get("TimeEnd"), datetime) else r.get("TimeEnd"),
            }
        )

    out_rows.sort(key=lambda x: (int(x.get("eventsCount") or 0), x.get("lastEventAt") or ""), reverse=True)
    out_rows = out_rows[: int(limit)]

    return {"snapshotAt": snapshot_at.isoformat(), "rows": out_rows}

    out: list[dict[str, Any]] = []

    with pyodbc.connect(conn_str, timeout=10) as conn:
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        for m in reversed(months):
            if len(out) >= limit:
                break

            suffix = _month_table_suffix(m)
            archive_table = f"{archives_db_name}.dbo.archive{suffix}"
            service_table = f"{archives_db_name}.dbo.eventservice{suffix}"

            code_table = f"{info.database}.dbo.Code_T"
            states_table = f"{info.database}.dbo.States"

            remaining = limit - len(out)

            sql = f"""
            SELECT TOP ({int(remaining)})
                a.Event_id,
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
                es.NameState,
                es.PersonName,
                st.StateName AS StateName,
                st.isOverProcess AS StateIsOverProcess,
                COALESCE(ct.CodeMes_RU, ct.Message) AS CodeText,
                es.GrResponseName,
                es.OperationTime
            FROM {archive_table} a
            OUTER APPLY (
                SELECT TOP (1)
                    s.NameState,
                    s.PersonName,
                    s.GrResponseName,
                    s.OperationTime
                FROM {service_table} s
                WHERE s.Event_id = a.Event_id AND s.Date_Key = a.Date_Key
                ORDER BY s.OperationTime DESC
            ) es
            LEFT JOIN {states_table} st
                ON st.State_id = a.StateEvent
            LEFT JOIN {code_table} ct
                ON ct.Code = a.Code AND ct.CodeGroup = a.CodeGroup
            WHERE a.Date_Key BETWEEN ? AND ?
            ORDER BY a.Date_Key DESC, a.Event_id DESC
            """

            params = [int(date_from_key), int(date_to_key)]

            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    out.extend(_rows_to_dicts(cur))
            except Exception as e:
                msg = str(e)
                if "Invalid object name" in msg or "42S02" in msg:
                    continue
                raise

    return out


def _suffix_from_date_key(date_key: int) -> str:
    s = str(int(date_key))
    if len(s) != 8:
        # Fallback: best-effort
        return s[:6] + "01"
    return s[:6] + "01"


def fetch_eventservice_actions_for_event_pairs(
    mssql_url: str,
    *,
    archives_db_name: str,
    event_pairs: Iterable[tuple[int, int]],
) -> list[dict[str, Any]]:
    """Читает строки из eventserviceYYYYMM01 для набора (Date_Key, Event_id).

    Возвращает все matching действия, отсортированные по (Date_Key, Event_id, OperationTime, Service_id).
    """

    pairs = list(event_pairs)
    if not pairs:
        return []

    pyodbc = _require_pyodbc()
    info = parse_mssql_url(mssql_url)
    conn_str = _build_odbc_conn_str(info)

    pairs_by_suffix: dict[str, list[tuple[int, int]]] = {}
    for dk, eid in pairs:
        suffix = _suffix_from_date_key(dk)
        pairs_by_suffix.setdefault(suffix, []).append((int(dk), int(eid)))

    out: list[dict[str, Any]] = []
    chunk_size = 200

    def _chunks(items: list[int], size: int) -> Iterable[list[int]]:
        for j in range(0, len(items), size):
            yield items[j : j + size]

    with pyodbc.connect(conn_str, timeout=10) as conn:
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        conn.setencoding(encoding="utf-8")

        for suffix, p_list in pairs_by_suffix.items():
            service_table = f"{archives_db_name}.dbo.eventservice{suffix}"

            # Most compatible approach across SQL Server versions: query by (Date_Key, Event_id IN (...)).
            by_date_key: dict[int, list[int]] = {}
            for dk, eid in p_list:
                by_date_key.setdefault(int(dk), []).append(int(eid))

            for dk, event_ids in by_date_key.items():
                # Deduplicate to avoid bloating parameter lists.
                uniq_event_ids = sorted(set(event_ids))
                for ids_chunk in _chunks(uniq_event_ids, chunk_size):
                    placeholders = ", ".join(["?"] * len(ids_chunk))
                    sql = f"""
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
                    WHERE s.Date_Key = ?
                      AND s.Event_id IN ({placeholders})
                    ORDER BY s.Date_Key ASC, s.Event_id ASC, s.OperationTime ASC, s.Service_id ASC
                    """

                    params: list[Any] = [int(dk)] + [int(x) for x in ids_chunk]

                    try:
                        with conn.cursor() as cur:
                            cur.execute(sql, params)
                            out.extend(_rows_to_dicts(cur))
                    except Exception as e:
                        msg = str(e)
                        if "Invalid object name" in msg or "42S02" in msg:
                            # Missing monthly table.
                            break
                        raise

    return out


def fetch_gbr_archive_trips(
        mssql_url: str,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        group_id: int | None = None,
        panel_id: str | None = None,
        limit: int = 500,
) -> dict[str, Any]:
        """История выездов ГБР из dbo.ArchiveGroupResponse.

        Возвращает строки с:
        - временем выезда/прибытия (StartTime/EndTime)
        - объектом (Panel_id + CompanyName/address при наличии связей)
        - статусом (Status_id + StatusGroupResponse.reason)
        """

        pyodbc = _require_pyodbc()
        info = parse_mssql_url(mssql_url)
        conn_str = _build_odbc_conn_str(info)

        if limit <= 0:
                limit = 1
        limit = min(int(limit), 50000)

        snapshot_at = datetime.utcnow()

        where: list[str] = []
        params: list[Any] = []
        if date_from is not None:
                where.append("agr.StartTime >= ?")
                params.append(date_from)
        if date_to is not None:
                where.append("agr.StartTime < ?")
                params.append(date_to)
        if group_id is not None:
                where.append("agr.Group_id = ?")
                params.append(int(group_id))
        if panel_id is not None and str(panel_id).strip():
                where.append("agr.Panel_id = ?")
                params.append(str(panel_id).strip())

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
        SELECT TOP ({int(limit)})
            agr.id,
            agr.Group_id,
            gr.Description AS GroupName,
            agr.StartTime,
            agr.EndTime,
            agr.Status_id,
            sgr.reason AS StatusReason,
            agr.Panel_id,
            agr.Group_ AS GroupNo,
            c.CompanyName AS ObjectName,
            c.[address] AS ObjectAddress
        FROM dbo.ArchiveGroupResponse agr
        LEFT JOIN dbo.StatusGroupResponse sgr
            ON sgr.status_id = agr.Status_id
        LEFT JOIN dbo.GroupResponse gr
            ON gr.Group_id = agr.Group_id
        LEFT JOIN (
            SELECT Panel_id, MAX(CompanyID) AS CompanyID
            FROM dbo.Groups
            GROUP BY Panel_id
        ) g
            ON g.Panel_id = agr.Panel_id
        LEFT JOIN dbo.Company c
            ON c.ID = g.CompanyID
        {where_sql}
        ORDER BY agr.StartTime DESC, agr.id DESC
        """

        with pyodbc.connect(conn_str, timeout=10) as conn:
                conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
                conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
                conn.setencoding(encoding="utf-8")

                with conn.cursor() as cur:
                        cur.execute(sql, params)
                        rows = _rows_to_dicts(cur)

        for r in rows:
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
