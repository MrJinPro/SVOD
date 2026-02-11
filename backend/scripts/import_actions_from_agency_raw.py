from __future__ import annotations

import argparse
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Stats:
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


def _list_eventservice_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'eventservice%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def import_actions(agency_db: Path, svod_db: Path, table_regex: str | None = None) -> None:
    src = _connect(agency_db)
    dst = _connect(svod_db)

    try:
        tables = _list_eventservice_tables(src)
        if table_regex:
            import re

            rx = re.compile(table_regex, flags=re.IGNORECASE)
            tables = [t for t in tables if rx.search(t)]

        if not tables:
            raise SystemExit("No eventservice* tables found in agency_raw.db")

        dst.execute(
            """
            CREATE TABLE IF NOT EXISTS event_actions (
              id TEXT PRIMARY KEY,
              event_id TEXT NOT NULL,
              action_name TEXT NOT NULL,
              action_time TEXT NOT NULL,
              operator_name TEXT,
              computer TEXT,
              gbr_name TEXT,
              date_key INTEGER NOT NULL,
              raw_event_id INTEGER NOT NULL,
              source_table TEXT NOT NULL,
              source_pk INTEGER NOT NULL,
              UNIQUE(source_table, source_pk)
            )
            """
        )
        dst.commit()

        ins = dst.cursor()
        for t in tables:
            print(f"Importing {t} ...")
            stats = Stats()

            cur = src.execute(
                f"SELECT Service_id, NameState, Event_id, Computer, OperationTime, Date_Key, PersonName, GrResponseName FROM '{t}' ORDER BY Service_id"
            )

            batch: list[tuple] = []
            for row in cur:
                stats.read += 1
                source_pk = int(row["Service_id"])
                date_key = int(row["Date_Key"])
                raw_event_id = int(row["Event_id"])

                event_id = f"mssql:{date_key}:{raw_event_id}"

                # Stable deterministic uuid by (table, pk)
                uid = uuid.uuid5(uuid.NAMESPACE_URL, f"{t}:{source_pk}")
                action_id = str(uid)

                batch.append(
                    (
                        action_id,
                        event_id,
                        row["NameState"],
                        row["OperationTime"],
                        row["PersonName"],
                        row["Computer"],
                        row["GrResponseName"],
                        date_key,
                        raw_event_id,
                        t,
                        source_pk,
                    )
                )

                if len(batch) >= 5000:
                    ins.executemany(
                        """
                        INSERT OR IGNORE INTO event_actions (
                          id, event_id, action_name, action_time,
                          operator_name, computer, gbr_name,
                          date_key, raw_event_id,
                          source_table, source_pk
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        batch,
                    )
                    stats.inserted += ins.rowcount if ins.rowcount and ins.rowcount > 0 else 0
                    dst.commit()
                    batch.clear()

            if batch:
                ins.executemany(
                    """
                    INSERT OR IGNORE INTO event_actions (
                      id, event_id, action_name, action_time,
                      operator_name, computer, gbr_name,
                      date_key, raw_event_id,
                      source_table, source_pk
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    batch,
                )
                stats.inserted += ins.rowcount if ins.rowcount and ins.rowcount > 0 else 0
                dst.commit()
                batch.clear()

            print(f"{t}: read={stats.read} inserted~={stats.inserted}")

        print("Done.")
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
    parser = argparse.ArgumentParser(description="Import operator actions from agency_raw.db into backend/svod.db")
    parser.add_argument("--agency", default=str(Path(__file__).resolve().parents[1] / "agency_raw.db"))
    parser.add_argument("--svod", default=str(Path(__file__).resolve().parents[1] / "svod.db"))
    parser.add_argument("--table-regex", default=None, help="Optional regex to filter eventservice tables")
    args = parser.parse_args()

    import_actions(Path(args.agency).resolve(), Path(args.svod).resolve(), args.table_regex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
