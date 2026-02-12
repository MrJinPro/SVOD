from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


_CREATE_TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE\s+(?:\[(?P<schema1>[^\]]+)\]\.)?\[(?P<table>[^\]]+)\]",
    flags=re.IGNORECASE,
)

# Example:
# ALTER TABLE [dbo].[Groups] ADD CONSTRAINT [fk_Company] FOREIGN KEY ([CompanyID]) REFERENCES [dbo].[Company] ([ID])
_FK_RE = re.compile(
    r"\bALTER\s+TABLE\s+(?:\[(?P<schema_from>[^\]]+)\]\.)?\[(?P<table_from>[^\]]+)\]\s+ADD\s+CONSTRAINT\s+\[(?P<constraint>[^\]]+)\]\s+FOREIGN\s+KEY\s*\((?P<from_cols>[^\)]+)\)\s+REFERENCES\s+(?:\[(?P<schema_to>[^\]]+)\]\.)?\[(?P<table_to>[^\]]+)\]\s*\((?P<to_cols>[^\)]+)\)",
    flags=re.IGNORECASE,
)

_REFERENCES_RE = re.compile(
    r"\bREFERENCES\s+(?:\[(?P<schema>[^\]]+)\]\.)?\[(?P<table>[^\]]+)\]",
    flags=re.IGNORECASE,
)


def _iter_sql_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".sql":
        yield input_path
        return
    if input_path.is_dir():
        for p in sorted(input_path.glob("*.sql")):
            if p.is_file():
                yield p
        return
    raise FileNotFoundError(str(input_path))


def _open_best_effort(path: Path):
    return path.open("r", encoding="utf-8", errors="replace")


def _split_cols(cols_sql: str) -> list[str]:
    # Columns are like: [Panel_id], [Group_] or [idTCode]
    out: list[str] = []
    for part in cols_sql.split(","):
        name = part.strip()
        name = name.strip("[] ")
        if name:
            out.append(name)
    return out


@dataclass(frozen=True)
class ForeignKeyEdge:
    from_table: str
    from_cols: list[str]
    to_table: str
    to_cols: list[str]
    constraint: str | None
    file: str


def scan_links(input_path: Path) -> dict:
    defined_tables: dict[str, str] = {}  # table -> file
    referenced_tables: set[str] = set()
    edges: list[ForeignKeyEdge] = []

    for f in _iter_sql_files(input_path):
        with _open_best_effort(f) as fh:
            for line in fh:
                m = _CREATE_TABLE_RE.search(line)
                if m:
                    table = m.group("table")
                    if table and table not in defined_tables:
                        defined_tables[table] = f.name

                for rm in _REFERENCES_RE.finditer(line):
                    t = rm.group("table")
                    if t:
                        referenced_tables.add(t)

                fm = _FK_RE.search(line)
                if fm:
                    from_table = fm.group("table_from")
                    to_table = fm.group("table_to")
                    constraint = fm.group("constraint")
                    from_cols = _split_cols(fm.group("from_cols") or "")
                    to_cols = _split_cols(fm.group("to_cols") or "")
                    if from_table and to_table:
                        edges.append(
                            ForeignKeyEdge(
                                from_table=from_table,
                                from_cols=from_cols,
                                to_table=to_table,
                                to_cols=to_cols,
                                constraint=constraint,
                                file=f.name,
                            )
                        )

    missing = sorted([t for t in referenced_tables if t not in defined_tables])

    return {
        "input": str(input_path),
        "tables_defined": sorted(defined_tables.keys()),
        "tables_defined_count": len(defined_tables),
        "tables_referenced_count": len(referenced_tables),
        "missing_referenced_tables": missing,
        "edges": [asdict(e) for e in edges],
        "defined_table_to_file": dict(sorted(defined_tables.items(), key=lambda kv: kv[0].lower())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan MSSQL/Navicat .sql dumps to extract CREATE TABLE and FOREIGN KEY REFERENCES, and list missing referenced tables."
    )
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parents[2] / "zeldor_agency"),
        help="Path to .sql file or directory with .sql dumps",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output JSON path (if not set, prints to stdout)",
    )

    args = parser.parse_args()
    report = scan_links(Path(args.input).resolve())

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(str(out_path))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
