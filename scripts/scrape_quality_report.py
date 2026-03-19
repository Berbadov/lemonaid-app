from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from storage.db import SessionLocal
from storage.stats import build_issue_stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate scrape quality report from SQLite")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for JSON report",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = build_issue_stats(db)
    finally:
        db.close()

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    print(payload)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Saved quality report to: {args.output}")


if __name__ == "__main__":
    main()
