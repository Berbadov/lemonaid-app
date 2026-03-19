from __future__ import annotations

from sqlalchemy import select

from rag.vector_store import ChromaIssueStore
from storage.db import SessionLocal
from storage.models import IssueReference


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(select(IssueReference)).scalars().all()
        if not rows:
            print("No issue references found. Run scraper first.")
            return

        store = ChromaIssueStore()
        ids = []
        docs = []
        metas = []

        for row in rows:
            ids.append(f"issue-{row.id}")
            docs.append(f"{row.title}. {row.details}")
            metas.append(
                {
                    "title": row.title,
                    "severity": row.severity,
                    "issue_domain": row.issue_domain,
                    "make": row.make or "",
                    "model": row.model or "",
                    "source_url": row.source_url,
                }
            )

        store.upsert_documents(ids=ids, documents=docs, metadatas=metas)
        print(f"Indexed {len(rows)} issue references to Chroma.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
