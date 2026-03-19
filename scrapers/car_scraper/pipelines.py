from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from storage.db import SessionLocal, create_all_tables
from storage.models import IssueReference


class SQLiteIssuePipeline:
    def open_spider(self, spider):
        create_all_tables()
        self.db = SessionLocal()

    def close_spider(self, spider):
        self.db.close()

    def process_item(self, item, spider):
        stmt = select(IssueReference).where(
            IssueReference.source_url == item.get("source_url"),
            IssueReference.title == item.get("title"),
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.make = item.get("make")
            existing.model = item.get("model")
            existing.generation = item.get("generation")
            existing.year_start = item.get("year_start")
            existing.year_end = item.get("year_end")
            existing.issue_domain = item.get("issue_domain") or "general"
            existing.severity = item.get("severity") or "medium"
            existing.symptoms = item.get("symptoms")
            existing.details = item.get("details") or ""
            existing.recommendation = item.get("recommendation")
        else:
            row = IssueReference(
                source=item.get("source") or "carchecker.pro",
                source_url=item.get("source_url") or "",
                make=item.get("make"),
                model=item.get("model"),
                generation=item.get("generation"),
                year_start=item.get("year_start"),
                year_end=item.get("year_end"),
                issue_domain=item.get("issue_domain") or "general",
                severity=item.get("severity") or "medium",
                title=item.get("title") or "Untitled issue",
                symptoms=item.get("symptoms"),
                details=item.get("details") or "",
                recommendation=item.get("recommendation"),
            )
            self.db.add(row)

        self.db.commit()
        return item
