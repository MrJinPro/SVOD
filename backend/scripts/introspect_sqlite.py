from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="List tables/columns in a SQLite DB")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    conn = sqlite3.connect(str(db_path))
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        print(f"DB: {db_path}")
        print(f"Tables: {len(tables)}")

        for (tname,) in tables:
            cols = conn.execute(f"PRAGMA table_info('{tname}')").fetchall()
            col_desc = ", ".join([f"{c[1]}:{c[2]}" for c in cols])
            print(f"- {tname}: {col_desc}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
