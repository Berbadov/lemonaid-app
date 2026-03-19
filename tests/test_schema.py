from storage.models import AdListing, IssueReference


def test_model_instantiation() -> None:
    listing = AdListing(source="sample", url="https://example.com/a")
    issue = IssueReference(
        source="sample",
        source_url="https://example.com/b",
        issue_domain="engine",
        severity="medium",
        title="Sample issue",
        details="Sample details",
    )

    assert listing.source == "sample"
    assert issue.issue_domain == "engine"
