from __future__ import annotations

import json

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import AnalyzeRequest, AnalyzeResponse
from rag.analyzer import analyze_listing
from rag.retriever import retrieve_issue_context
from storage.db import create_all_tables, get_db_session
from storage.models import AdListing, ListingIssueAnalysis

app = FastAPI(title="Lemonaid Analyzer API", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    create_all_tables()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _build_transient_listing(payload: AnalyzeRequest) -> AdListing:
    meta = payload.ad_metadata or {}
    return AdListing(
        source=meta.get("source", "ad_page"),
        source_listing_id=str(meta.get("source_listing_id", "")) or None,
        url=payload.listing_url or meta.get("url", "unknown://transient"),
        title=meta.get("title"),
        make=meta.get("make"),
        model=meta.get("model"),
        trim=meta.get("trim"),
        year=meta.get("year"),
        mileage_km=meta.get("mileage_km"),
        fuel_type=meta.get("fuel_type"),
        transmission=meta.get("transmission"),
        engine_volume_cc=meta.get("engine_volume_cc"),
        body_type=meta.get("body_type"),
        location=meta.get("location"),
        currency=meta.get("currency"),
        price_amount=meta.get("price_amount"),
        body_condition_notes=meta.get("body_condition_notes"),
        manufacturing_notes=meta.get("manufacturing_notes"),
        description=meta.get("description"),
        raw_metadata_json=json.dumps(meta, ensure_ascii=False),
        retrieval_text=meta.get("retrieval_text"),
    )


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest, db: Session = Depends(get_db_session)) -> AnalyzeResponse:
    listing = None

    if payload.listing_id is not None:
        listing = db.get(AdListing, payload.listing_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="listing_id not found")
    elif payload.listing_url:
        stmt = select(AdListing).where(AdListing.url == payload.listing_url).limit(1)
        listing = db.execute(stmt).scalar_one_or_none()

    if listing is None:
        if not payload.ad_metadata and not payload.listing_url:
            raise HTTPException(
                status_code=400,
                detail="Provide listing_id, listing_url, or ad_metadata",
            )
        listing = _build_transient_listing(payload)

    contexts = retrieve_issue_context(db, listing)
    analysis = analyze_listing(listing, contexts)

    persisted_listing_id = listing.id if listing.id else None
    if persisted_listing_id is not None:
        db.add(
            ListingIssueAnalysis(
                listing_id=persisted_listing_id,
                model_used="deepseek-chat" if analysis else "fallback",
                status="success",
                response_json=json.dumps(analysis, ensure_ascii=False),
            )
        )
        db.commit()

    return AnalyzeResponse(
        summary=analysis.get("summary", "No summary available"),
        risks=analysis.get("risks", []),
        listing_id=persisted_listing_id,
        source=listing.source,
    )
