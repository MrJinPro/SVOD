from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


@dataclass
class ImportStats:
    executed: int = 0
    skipped: int = 0
    failed: int = 0
    last_error: str | None = None


_SKIP_PREFIXES = (
    "SET ",
    "USE ",
    "LOCK TABLES",
    "UNLOCK TABLES",
    "START TRANSACTION",
    "COMMIT",
    "BEGIN",
    "ROLLBACK",
    "DELIMITER ",
    "ALTER DATABASE ",
    "CREATE DATABASE ",
    "DROP DATABASE ",
)


def _is_mssql_batch_separator_line(line: str) -> bool:
    s = line.strip()
    return s.upper() == "GO"


def _wait_until_file_stable(path: Path, stable_seconds: int, poll_seconds: float, max_wait_seconds: int) -> None:
    start = time.time()
    last_size: int | None = None
    stable_since: float | None = None

    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            size = None

        now = time.time()
        if size is not None and size == last_size:
            if stable_since is None:
                stable_since = now
            if now - stable_since >= stable_seconds:
                return
        else:
            stable_since = None
            last_size = size

        if now - start > max_wait_seconds:
            raise TimeoutError(f"File not stable after {max_wait_seconds}s: {path}")

        time.sleep(poll_seconds)


def _open_text_file_best_effort(path: Path):
    # We keep it simple: most dumps are ASCII-heavy SQL keywords.
    # If the dump is not utf-8, we still want to proceed and skip/execute what we can.
    return path.open("r", encoding="utf-8", errors="replace")


def _open_text_file_with_retry(path: Path, poll_seconds: float = 2.0, max_wait_seconds: int = 600):
    start = time.time()
    while True:
        try:
            return _open_text_file_best_effort(path)
        except OSError as e:
            # Windows: another process can hold an exclusive lock while copying.
            # Retry a bit instead of failing immediately.
            if time.time() - start > max_wait_seconds:
                raise
            time.sleep(poll_seconds)


def iter_sql_statements(path: Path) -> Iterator[str]:
    """Stream SQL statements from a dump file.

    Splits by semicolon only when not inside quotes or comments.
    Handles:
    - line comments: -- ... , # ...
    - block comments: /* ... */
    - MSSQL batch separator: GO (on its own line)
    """

    with _open_text_file_with_retry(path) as f:
        buf: list[str] = []
        in_sq = False
        in_dq = False
        in_line_comment = False
        in_block_comment = False
        prev: str | None = None

        for line in f:
            if _is_mssql_batch_separator_line(line) and not in_sq and not in_dq and not in_block_comment:
                # Flush current buffer as a statement boundary.
                stmt = "".join(buf).strip()
                if stmt:
                    yield stmt
                buf = []
                in_line_comment = False
                prev = None
                continue

            i = 0
            while i < len(line):
                ch = line[i]
                nxt = line[i + 1] if i + 1 < len(line) else ""

                if in_line_comment:
                    # Ignore everything until end of line.
                    i = len(line)
                    continue

                if in_block_comment:
                    if ch == "*" and nxt == "/":
                        in_block_comment = False
                        i += 2
                        prev = None
                        continue
                    i += 1
                    continue

                # Start comments
                if not in_sq and not in_dq:
                    if ch == "-" and nxt == "-":
                        in_line_comment = True
                        i += 2
                        continue
                    if ch == "#":
                        in_line_comment = True
                        i += 1
                        continue
                    if ch == "/" and nxt == "*":
                        in_block_comment = True
                        i += 2
                        continue

                # Quotes
                if ch == "'" and not in_dq:
                    # Handle escaped single quote '' inside string
                    if in_sq and nxt == "'":
                        buf.append("''")
                        i += 2
                        prev = "'"
                        continue
                    in_sq = not in_sq
                    buf.append(ch)
                    i += 1
                    prev = ch
                    continue

                if ch == '"' and not in_sq:
                    in_dq = not in_dq
                    buf.append(ch)
                    i += 1
                    prev = ch
                    continue

                # Statement terminator
                if ch == ";" and not in_sq and not in_dq:
                    buf.append(ch)
                    stmt = "".join(buf).strip()
                    if stmt:
                        yield stmt
                    buf = []
                    i += 1
                    prev = None
                    continue

                # Normal character
                buf.append(ch)
                i += 1
                prev = ch

            # reset line-comment at end of line
            in_line_comment = False

        tail = "".join(buf).strip()
        if tail:
            yield tail


_CREATE_TABLE_TAIL_RE = re.compile(r"\)\s*ENGINE\s*=.*?$", re.IGNORECASE | re.DOTALL)
_MSSQL_CREATE_TABLE_ON_RE = re.compile(r"\)\s*ON\s+\[[^\]]+\]\s*$", re.IGNORECASE | re.DOTALL)
_MSSQL_COLLATE_RE = re.compile(r"\s+COLLATE\s+[A-Za-z0-9_]+", re.IGNORECASE)
_MSSQL_SCHEMA_QUAL_RE = re.compile(r"\[(?P<schema>[^\]]+)\]\.\[(?P<name>[^\]]+)\]")
_MSSQL_DROP_TABLE_RE = re.compile(r"DROP\s+TABLE\s+(?:\[[^\]]+\]\.)?\[(?P<name>[^\]]+)\]", re.IGNORECASE)


def normalize_statement_for_sqlite(stmt: str) -> str | None:
    s = stmt.strip().lstrip("\ufeff").strip()
    if not s:
        return None

    upper = s.upper()

    # Skip common non-SQLite directives and dump metadata.
    for p in _SKIP_PREFIXES:
        if upper.startswith(p):
            return None

    # MSSQL/Navicat dump metadata / maintenance commands
    if upper.startswith("EXEC "):
        return None
    if upper.startswith("DBCC "):
        return None
    if upper.startswith("PRINT "):
        return None
    if upper.startswith("DISABLE TRIGGER"):
        return None
    if upper.startswith("ENABLE TRIGGER"):
        return None
    if upper.startswith("CREATE TRIGGER"):
        return None
    if upper.startswith("CREATE VIEW"):
        return None
    if upper.startswith("CREATE PROCEDURE"):
        return None
    if upper.startswith("CREATE FUNCTION"):
        return None

    # Skip MySQL versioned comments, if they appear as standalone statements.
    if upper.startswith("/*!") and upper.endswith("*/"):
        return None

    # Some dumps include these as standalone.
    if upper in ("GO",):
        return None

    # SQLite doesn't understand MySQL LOCK/KEYS pragmas.
    if upper.startswith("ALTER TABLE") and "DISABLE KEYS" in upper:
        return None
    if upper.startswith("ALTER TABLE") and "ENABLE KEYS" in upper:
        return None

    # For staging import we skip most MSSQL ALTER/INDEX statements.
    if upper.startswith("ALTER TABLE"):
        return None
    if upper.startswith("CREATE ") and " INDEX " in upper:
        return None
    if upper.startswith("CREATE ") and " CLUSTERED " in upper and " INDEX " in upper:
        return None
    if upper.startswith("CREATE ") and " NONCLUSTERED " in upper and " INDEX " in upper:
        return None

    # MSSQL/Navicat pattern: IF EXISTS (...) DROP TABLE [dbo].[X]
    if upper.startswith("IF EXISTS") and "DROP TABLE" in upper:
        m = _MSSQL_DROP_TABLE_RE.search(s)
        if m:
            name = m.group("name")
            return f"DROP TABLE IF EXISTS [{name}]"
        return None

    # Remove MySQL CREATE TABLE tail like ENGINE=InnoDB DEFAULT CHARSET=utf8
    if upper.startswith("CREATE TABLE"):
        # MSSQL: remove replication-specific clause.
        s = re.sub(r"\bNOT\s+FOR\s+REPLICATION\b", "", s, flags=re.IGNORECASE)

        # MSSQL: DEFAULT getdate() is not supported by SQLite.
        s = re.sub(
            r"\bDEFAULT\s*\(?\s*getdate\s*\(\s*\)\s*\)?",
            "DEFAULT CURRENT_TIMESTAMP",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(
            r"\bDEFAULT\s*\(?\s*getutcdate\s*\(\s*\)\s*\)?",
            "DEFAULT CURRENT_TIMESTAMP",
            s,
            flags=re.IGNORECASE,
        )

        # Some dumps contain "DEFAULT NULL NULL".
        s = re.sub(r"\bDEFAULT\s+NULL\s+NULL\b", "DEFAULT NULL", s, flags=re.IGNORECASE)

        # MSSQL: nvarchar(max)/varchar(max) -> TEXT for SQLite.
        s = re.sub(r"\bnvarchar\s*\(\s*max\s*\)", "TEXT", s, flags=re.IGNORECASE)
        s = re.sub(r"\bvarchar\s*\(\s*max\s*\)", "TEXT", s, flags=re.IGNORECASE)

        s = _CREATE_TABLE_TAIL_RE.sub(");", s)
        # MSSQL CREATE TABLE can end with ") ON [PRIMARY]"
        s = _MSSQL_CREATE_TABLE_ON_RE.sub(")", s)

    # Strip MSSQL collations that SQLite doesn't know.
    # Important for performance on huge INSERT-heavy dumps: avoid regex when not needed.
    if "COLLATE" in upper:
        s = _MSSQL_COLLATE_RE.sub("", s)

    # Remove schema qualifiers like [dbo].[Table] -> [Table]
    if "[dbo]." in s or "[DBO]." in s:
        s = s.replace("[dbo].[", "[")
        s = s.replace("[dbo].", "")
        s = s.replace("[DBO].[", "[")
        s = s.replace("[DBO].", "")

    # Also handle other schema qualifiers generically: [schema].[name] -> [name]
    if "].[" in s:
        s = _MSSQL_SCHEMA_QUAL_RE.sub(lambda m: f"[{m.group('name')}]", s)

    # MSSQL Unicode literal prefix: N'...' -> '...'
    if "N'" in s:
        s = re.sub(r"\bN'", "'", s)

    # Remove a few dialect-specific tokens inside statements.
    if "UNSIGNED" in upper:
        s = re.sub(r"\bUNSIGNED\b", "", s, flags=re.IGNORECASE)
    if "AUTO_INCREMENT" in upper:
        s = re.sub(r"\bAUTO_INCREMENT\b", "", s, flags=re.IGNORECASE)
    if "IDENTITY" in upper:
        s = re.sub(r"\bIDENTITY\s*\(\s*\d+\s*,\s*\d+\s*\)", "", s, flags=re.IGNORECASE)

    # MySQL: `name` quoting is fine for SQLite; keep as-is.

    # Safety: SQLite executescript tolerates multiple statements, but we provide single statements already.
    return s.strip()


def _connect_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-200000")  # ~200MB cache in pages (best-effort)
    return conn


def _iter_input_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted([p for p in input_path.glob("*.sql") if p.is_file()])
    raise FileNotFoundError(str(input_path))


def _filter_files(files: list[Path], include_regex: str | None, exclude_regex: str | None) -> list[Path]:
    if not files:
        return []

    inc = re.compile(include_regex, flags=re.IGNORECASE) if include_regex else None
    exc = re.compile(exclude_regex, flags=re.IGNORECASE) if exclude_regex else None

    out: list[Path] = []
    for f in files:
        name = f.name
        if inc and not inc.search(name):
            continue
        if exc and exc.search(name):
            continue
        out.append(f)
    return out


def _normalize_statement_for_sqlite(stmt: str, *, schema_only: bool) -> str | None:
    s = normalize_statement_for_sqlite(stmt)
    if s is None:
        return None
    if schema_only:
        up = s.lstrip().upper()
        if up.startswith("INSERT "):
            return None
        if up.startswith("DELETE "):
            return None
        if up.startswith("UPDATE "):
            return None
    return s


def import_dump(
    sql_file: Path,
    sqlite_db: Path,
    commit_every: int,
    stats: ImportStats,
    *,
    schema_only: bool,
) -> ImportStats:
    conn = _connect_sqlite(sqlite_db)
    cur = conn.cursor()

    pending = 0
    conn.execute("BEGIN")

    last_report = time.time()

    try:
        for raw_stmt in iter_sql_statements(sql_file):
            stmt = _normalize_statement_for_sqlite(raw_stmt, schema_only=schema_only)
            if stmt is None:
                stats.skipped += 1
                continue

            try:
                cur.execute(stmt)
                stats.executed += 1
            except Exception as e:
                stats.failed += 1
                stats.last_error = f"{type(e).__name__}: {e}"
                # Continue best-effort import.

            pending += 1
            if pending >= commit_every:
                conn.commit()
                conn.execute("BEGIN")
                pending = 0

            now = time.time()
            if now - last_report >= 5.0:
                last_report = now
                print(
                    f"[{sql_file.name}] executed={stats.executed} skipped={stats.skipped} failed={stats.failed}"
                    + (f" last_error={stats.last_error}" if stats.last_error else ""),
                    file=sys.stderr,
                )

        conn.commit()
        return stats
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import agency .sql dumps into a SQLite DB (best-effort).")
    parser.add_argument("--input", required=True, help="Path to .sql file or directory with .sql files")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "agency_raw.db"),
        help="SQLite DB path to create/update",
    )
    parser.add_argument("--stable-seconds", type=int, default=10, help="Wait until input file size is stable")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="Polling interval for stability checks")
    parser.add_argument("--max-wait-seconds", type=int, default=1800, help="Max wait time for file stability")
    parser.add_argument("--commit-every", type=int, default=5000, help="Commit every N statements")
    parser.add_argument(
        "--include-regex",
        default=None,
        help="Import only files whose name matches this regex (case-insensitive)",
    )
    parser.add_argument(
        "--exclude-regex",
        default=None,
        help="Skip files whose name matches this regex (case-insensitive)",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Execute only schema statements (DROP/CREATE), skip INSERT/UPDATE/DELETE",
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    files = list(_iter_input_files(input_path))
    files = _filter_files(files, args.include_regex, args.exclude_regex)
    if not files:
        print(f"No .sql files found in {input_path}", file=sys.stderr)
        return 2

    print(f"Output SQLite DB: {output_path}")

    for f in files:
        print(f"\n==> Importing: {f}")
        try:
            _wait_until_file_stable(f, args.stable_seconds, args.poll_seconds, args.max_wait_seconds)
        except TimeoutError as e:
            print(str(e), file=sys.stderr)
            return 3

        stats = ImportStats()
        import_dump(f, output_path, args.commit_every, stats, schema_only=bool(args.schema_only))
        print(
            f"Done: {f.name} executed={stats.executed} skipped={stats.skipped} failed={stats.failed}"
            + (f" last_error={stats.last_error}" if stats.last_error else "")
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
