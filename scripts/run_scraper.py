from __future__ import annotations

import os
import subprocess
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scrapy_dir = repo_root / "scrapers"

    command = ["scrapy", "crawl", "carchecker_issues"]
    subprocess.run(command, cwd=scrapy_dir, check=True, env=os.environ.copy())


if __name__ == "__main__":
    main()
