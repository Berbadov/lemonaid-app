from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run carchecker scraper")
    parser.add_argument(
        "--brand",
        default=None,
        help="Optional slug prefix filter, e.g. alfa_romeo",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    scrapy_dir = repo_root / "scrapers"

    command = [sys.executable, "-m", "scrapy", "crawl", "carchecker_issues"]
    if args.brand:
        command.extend(["-a", f"brand={args.brand}"])

    subprocess.run(command, cwd=scrapy_dir, check=True)


if __name__ == "__main__":
    main()
