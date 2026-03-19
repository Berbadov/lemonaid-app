from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from storage.models import IssueReference


def _to_labeled_count(rows: list[tuple[str | None, int]]) -> list[dict[str, int | str]]:
    result: list[dict[str, int | str]] = []
    for label, count in rows:
        result.append({"label": label or "unknown", "count": int(count)})
    return result


def build_issue_stats(db: Session) -> dict[str, object]:
    total_issues = int(db.scalar(select(func.count()).select_from(IssueReference)) or 0)
    distinct_reports = int(db.scalar(select(func.count(func.distinct(IssueReference.source_url)))) or 0)

    by_domain_rows = db.execute(
        select(IssueReference.issue_domain, func.count())
        .group_by(IssueReference.issue_domain)
        .order_by(desc(func.count()))
    ).all()

    by_severity_rows = db.execute(
        select(IssueReference.severity, func.count())
        .group_by(IssueReference.severity)
        .order_by(desc(func.count()))
    ).all()

    top_makes_rows = db.execute(
        select(IssueReference.make, func.count())
        .group_by(IssueReference.make)
        .order_by(desc(func.count()))
        .limit(10)
    ).all()

    top_models_rows = db.execute(
        select(IssueReference.model, func.count())
        .group_by(IssueReference.model)
        .order_by(desc(func.count()))
        .limit(10)
    ).all()

    missing_make = int(
        db.scalar(
            select(func.count()).where(
                IssueReference.make.is_(None) | (IssueReference.make == "")
            )
        )
        or 0
    )
    missing_model = int(
        db.scalar(
            select(func.count()).where(
                IssueReference.model.is_(None) | (IssueReference.model == "")
            )
        )
        or 0
    )

    return {
        "total_issues": total_issues,
        "distinct_reports": distinct_reports,
        "by_domain": _to_labeled_count(by_domain_rows),
        "by_severity": _to_labeled_count(by_severity_rows),
        "top_makes": _to_labeled_count(top_makes_rows),
        "top_models": _to_labeled_count(top_models_rows),
        "missing_make_count": missing_make,
        "missing_model_count": missing_model,
    }
