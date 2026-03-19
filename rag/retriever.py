from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from rag.vector_store import ChromaIssueStore
from storage.models import AdListing, IssueReference


def retrieve_issue_context(db: Session, listing: AdListing, limit: int = 10) -> list[dict[str, str]]:
    contexts: list[dict[str, str]] = []

    filters = []
    if listing.make:
        filters.append(IssueReference.make.ilike(listing.make))
    if listing.model:
        filters.append(IssueReference.model.ilike(listing.model))

    if filters:
        stmt = select(IssueReference).where(and_(*filters)).limit(limit)
    else:
        stmt = select(IssueReference).where(
            or_(
                IssueReference.issue_domain.ilike("%engine%"),
                IssueReference.issue_domain.ilike("%powertrain%"),
                IssueReference.issue_domain.ilike("%body%"),
                IssueReference.issue_domain.ilike("%manufacturing%"),
            )
        ).limit(limit)

    for row in db.execute(stmt).scalars().all():
        contexts.append(
            {
                "title": row.title,
                "severity": row.severity,
                "domain": row.issue_domain,
                "details": row.details,
                "source_url": row.source_url,
            }
        )

    query_text_parts = [listing.make or "", listing.model or "", listing.description or ""]
    query_text = " ".join(part for part in query_text_parts if part).strip()

    if query_text:
        vector_rows = ChromaIssueStore().query(query_text, limit=min(5, limit))
        for entry in vector_rows:
            contexts.append(
                {
                    "title": str(entry.get("metadata", {}).get("title", "VectorContext")),
                    "severity": str(entry.get("metadata", {}).get("severity", "unknown")),
                    "domain": str(entry.get("metadata", {}).get("issue_domain", "unknown")),
                    "details": str(entry.get("document", "")),
                    "source_url": str(entry.get("metadata", {}).get("source_url", "")),
                }
            )

    seen = set()
    unique_contexts = []
    for item in contexts:
        key = (item["title"], item["details"])
        if key in seen:
            continue
        seen.add(key)
        unique_contexts.append(item)

    return unique_contexts[:limit]
