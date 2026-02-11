from __future__ import annotations

import argparse
import re
from pathlib import Path


def _open_text(path: Path):
    return path.open("r", encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a few snippets from a large .sql dump without importing everything."
    )
    parser.add_argument("--file", required=True, help="Path to .sql dump")
    parser.add_argument(
        "--regex",
        required=True,
        help=r"Case-insensitive regex to match lines (e.g. '^INSERT INTO \[dbo\]\.\[archive20260201\]' )",
    )
    parser.add_argument("--max", type=int, default=3, help="Max matches to print")
    parser.add_argument("--context", type=int, default=0, help="Lines of context after each match")
    parser.add_argument("--max-line", type=int, default=2000, help="Max printed line length")
    args = parser.parse_args()

    path = Path(args.file).resolve()
    rx = re.compile(args.regex, flags=re.IGNORECASE)

    printed = 0
    ctx_left = 0

    with _open_text(path) as f:
        for line in f:
            if printed >= args.max and ctx_left <= 0:
                break

            if ctx_left > 0:
                ctx_left -= 1
                s = line.rstrip("\n")
                if len(s) > args.max_line:
                    s = s[: args.max_line] + " ...[trimmed]"
                print(s)
                continue

            if rx.search(line):
                printed += 1
                s = line.rstrip("\n")
                if len(s) > args.max_line:
                    s = s[: args.max_line] + " ...[trimmed]"
                print(s)
                if args.context > 0:
                    ctx_left = args.context

    if printed == 0:
        raise SystemExit("No matches found")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
