from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import SETTINGS
from storage.models import AdListing


DEEPSEEK_MODEL = "deepseek-chat"
VALID_SEVERITIES = {"low", "medium", "high"}


def _clip_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _compact_analysis_payload(raw: dict[str, Any]) -> dict[str, Any]:
    summary = _clip_text(raw.get("summary"), 220)

    compact_risks: list[dict[str, Any]] = []
    for risk in raw.get("risks", [])[:8]:
        if not isinstance(risk, dict):
            continue

        severity = str(risk.get("severity", "medium")).lower()
        if severity not in VALID_SEVERITIES:
            severity = "medium"

        confidence = risk.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5

        compact_risks.append(
            {
                "title": _clip_text(risk.get("title") or "Untitled risk", 90),
                "severity": severity,
                "confidence": round(max(0.0, min(float(confidence), 1.0)), 2),
                "rationale": _clip_text(risk.get("rationale") or "No rationale provided.", 190),
                "domain": _clip_text(risk.get("domain") or "general", 40),
                "inspection_advice": _clip_text(
                    risk.get("inspection_advice") or "Verify with an independent mechanic before purchase.",
                    160,
                ),
            }
        )

    return {
        "summary": summary or "Potential issues identified for this listing.",
        "risks": compact_risks,
    }


def _build_prompt(listing: AdListing, contexts: list[dict[str, str]]) -> str:
    context_blob = "\n".join(
        f"- [{ctx['severity']}] {ctx['domain']} | {ctx['title']}: {ctx['details']}"
        for ctx in contexts
    )

    return (
        "You are an automotive risk analyzer for second-hand car buyers. "
        "Focus on possible issues and warning signs. "
        "Keep text concise and practical. "
        "Return JSON with the structure: "
        '{"summary": string, "risks": [{"title": string, "severity": "low|medium|high", '
        '"confidence": number, "rationale": string, "domain": string, "inspection_advice": string}]}. '
        "Constraints: summary <= 220 chars, each title <= 90 chars, rationale <= 190 chars, "
        "inspection_advice <= 160 chars.\n\n"
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
                "rationale": row["details"][:190],
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

    payload = {
        "summary": f"Potential issues inferred for {listing.make or ''} {listing.model or ''}.",
        "risks": risks,
    }
    return _compact_analysis_payload(payload)


def _parse_json_response(content: str) -> dict[str, Any] | None:
    candidates: list[str] = [content.strip()]

    # Typical LLM formatting: fenced code block.
    fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, flags=re.IGNORECASE)
    candidates.extend(fenced)

    # Fallback: first JSON-looking object span.
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(content[start : end + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("risks"), list):
            return parsed
    return None


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
        response_format={"type": "json_object"},
        timeout=90,
    )

    content = response.choices[0].message.content or "{}"
    parsed = _parse_json_response(content)
    if parsed is None:
        return _fallback_analysis(listing, contexts)
    return _compact_analysis_payload(parsed)
