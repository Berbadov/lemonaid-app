from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    listing_id: int | None = None
    listing_url: str | None = None
    ad_metadata: dict[str, Any] = Field(default_factory=dict)


class RiskItem(BaseModel):
    title: str
    severity: str
    confidence: float
    rationale: str
    domain: str
    inspection_advice: str


class AnalyzeResponse(BaseModel):
    summary: str
    risks: list[RiskItem]
    listing_id: int | None = None
    source: str | None = None
