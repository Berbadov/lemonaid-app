from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from config import SETTINGS
from storage.models import AdListing


DEEPSEEK_MODEL = "deepseek-chat"


def _build_prompt(listing: AdListing, contexts: list[dict[str, str]]) -> str:
    context_blob = "\n".join(
        f"- [{ctx['severity']}] {ctx['domain']} | {ctx['title']}: {ctx['details']}"
        for ctx in contexts
    )

    return (
        "You are an automotive risk analyzer for second-hand car buyers. "
        "Focus on possible issues and warning signs. "
        "Return JSON with the structure: "
        '{"summary": string, "risks": [{"title": string, "severity": "low|medium|high", '
        '"confidence": number, "rationale": string, "domain": string, "inspection_advice": string}]}.\n\n'
        f"Listing:\n"
        f"Title: {listing.title or ''}\n"
        f"Make/Model: {listing.make or ''} {listing.model or ''}\n"
        f"Year: {listing.year or ''}\n"
        f"Mileage (km): {listing.mileage_km or ''}\n"
        f"Fuel/Transmission: {listing.fuel_type or ''}/{listing.transmission or ''}\n"
        f"Description: {listing.description or ''}\n\n"
        f"Reference Context:\n{context_blob}\n"
    )


def _fallback_analysis(listing: AdListing, contexts: list[dict[str, str]]) -> dict[str, Any]:
    risks = []
    for row in contexts[:5]:
        risks.append(
            {
                "title": row["title"],
                "severity": row["severity"],
                "confidence": 0.55,
                "rationale": row["details"][:280],
                "domain": row["domain"],
                "inspection_advice": "Verify with an independent mechanic before purchase.",
            }
        )

    if not risks:
        risks.append(
            {
                "title": "Limited context available",
                "severity": "medium",
                "confidence": 0.4,
                "rationale": "No matching known-issue references were retrieved.",
                "domain": "general",
                "inspection_advice": "Run diagnostic scan and body inspection before buying.",
            }
        )

    return {
        "summary": f"Potential issues inferred for {listing.make or ''} {listing.model or ''}.",
        "risks": risks,
    }


def analyze_listing(listing: AdListing, contexts: list[dict[str, str]]) -> dict[str, Any]:
    if not SETTINGS.deepseek_api_key:
        return _fallback_analysis(listing, contexts)

    prompt = _build_prompt(listing, contexts)

    client = OpenAI(api_key=SETTINGS.deepseek_api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are strict about output JSON validity.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return _fallback_analysis(listing, contexts)

    if not isinstance(parsed, dict) or "risks" not in parsed:
        return _fallback_analysis(listing, contexts)
    return parsed
