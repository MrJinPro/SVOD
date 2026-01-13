from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time as time_type
from typing import Any
from urllib.parse import parse_qs, urlparse

import pymysql


@dataclass(frozen=True)
class MySQLConnInfo:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str


def parse_mysql_url(url: str) -> MySQLConnInfo:
    # Accept: mysql://user:pass@host:3306/db?charset=cp1251
    # Also accept SQLAlchemy style: mysql+pymysql://...
    u = urlparse(url)
    scheme = (u.scheme or "").lower()
    if not (scheme.startswith("mysql")):
        raise ValueError("agency_database_url must be a MySQL URL")

    qs = parse_qs(u.query)
    charset = (qs.get("charset", [""]) or [""])[0] or "utf8"

    if not u.hostname or not u.path or u.path == "/":
        raise ValueError("agency_database_url must include host and database")

    return MySQLConnInfo(
        host=u.hostname,
        port=u.port or 3306,
        user=u.username or "",
        password=u.password or "",
        database=u.path.lstrip("/"),
        charset=charset,
    )


def _combine_dt(dt: datetime | None, t: time_type | None) -> datetime | None:
    if dt is None:
        return None
    if t is None:
        return dt
    return datetime.combine(dt.date(), t)


def fetch_alarms_since(
    mysql_url: str,
    last_id: int,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Fetch alarms joined with objects after a given ID.

    Returns rows with MySQL-native field names.
    """
    info = parse_mysql_url(mysql_url)
    conn = pymysql.connect(
        host=info.host,
        port=info.port,
        user=info.user,
        password=info.password,
        database=info.database,
        charset=info.charset,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  a.ID_ALARMS,
                  a.ID_OBJECTS,
                  a.NUMBER_CAR,
                  a.FIO_OPERATORS,
                  a.FIO_ENGINEERS,
                  a.NUMBER_SHLEIF,
                  a.OSMOTR,
                  a.DATE_ALARM,
                  a.TIME_ALARM,
                  a.TIME_COMING,
                  a.RESULT_OSMOTR,
                  a.ZAMETKI,
                  a.IS_ZAYAVKA,
                  a.IS_DONE,
                  a.RESULT_ZAYAVKA,
                  a.IS_SHTRAF,
                  a.NUM_SHTRAF,
                  a.IS_PROPAZHA,
                  a.IS_PROP_FIXED,
                  a.IS_DOGOVOR_OTDEL,
                  a.IS_SRABOTKA_FALSE,
                  o.OBJ_NUMBER,
                  o.OBJ_ADRESS,
                  o.OBJ_FIO,
                  o.OBJ_SYSTEM,
                  o.OBJ_STATUS
                FROM alarms a
                LEFT JOIN objects o ON o.ID_OBJECTS = a.ID_OBJECTS
                WHERE a.ID_ALARMS > %s
                ORDER BY a.ID_ALARMS ASC
                LIMIT %s
                """,
                (last_id, limit),
            )
            rows = cur.fetchall()

        # Normalize timestamps where possible
        for r in rows:
            # DATE_ALARM is datetime in schema; TIME_ALARM is time. Keep both but also expose TS
            dt = r.get("DATE_ALARM")
            t = r.get("TIME_ALARM")
            if isinstance(dt, datetime) or dt is None:
                pass
            else:
                # Sometimes drivers return date; handle gracefully
                if isinstance(dt, date_type):
                    dt = datetime.combine(dt, datetime.min.time())
            if isinstance(t, time_type) or t is None:
                pass
            r["_TS"] = _combine_dt(dt, t) or (dt if isinstance(dt, datetime) else None)

        return rows
    finally:
        conn.close()
