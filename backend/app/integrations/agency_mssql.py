from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse


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
    # - mssql+pyodbc://user:pass@host:1433/Pult4DB?driver=ODBC+Driver+17+for+SQL+Server
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
    driver = unquote((qs.get("driver", [""]) or [""])[0]) or "ODBC Driver 17 for SQL Server"

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
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
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

    with pyodbc.connect(conn_str, timeout=10) as conn:
        conn.setdecoding(pyodbc.SQL_CHAR, encoding="cp1251")
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
        conn.setencoding(encoding="utf-8")

        for m in months:
            if len(out) >= limit:
                break

            suffix = _month_table_suffix(m)
            archive_table = f"{archives_db_name}.dbo.archive{suffix}"
            service_table = f"{archives_db_name}.dbo.eventservice{suffix}"

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
              a.Result_Text,
              a.StateEvent,
              es.NameState,
              es.PersonName,
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
            except Exception:
                # Если конкретной месячной таблицы нет — просто пропускаем
                continue

    return out
