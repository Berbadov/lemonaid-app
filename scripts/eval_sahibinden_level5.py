from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from fastapi.testclient import TestClient

from api.main import app
from config import SETTINGS


VALID_SEVERITIES = {"low", "medium", "high"}
REQUIRED_RISK_FIELDS = {
    "title",
    "severity",
    "confidence",
    "rationale",
    "domain",
    "inspection_advice",
}
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SAMPLES_PATH = (ROOT / "data" / "sahibinden_eval_samples.json").resolve()
DEFAULT_OUTPUT_PATH = (ROOT / "reports" / "sahibinden_level5_eval.json").resolve()


def _resolve_existing_path(path: Path) -> Path:
    if path.is_absolute() and path.exists():
        return path

    candidates = [
        path,
        Path.cwd() / path,
        SCRIPT_DIR / path,
        ROOT / path,
    ]
    for candidate in candidates:
        normalized = candidate.resolve()
        if normalized.exists():
            return normalized

    attempted = "\n".join(f"- {candidate.resolve()}" for candidate in candidates)
    raise FileNotFoundError(
        f"Could not find samples file: {path}\nChecked these locations:\n{attempted}"
    )


def _resolve_output_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def _clip(text: Any, limit: int = 220) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _format_console_report(report: dict[str, Any], max_risks_per_sample: int) -> str:
    lines: list[str] = []
    lines.append("=== Sahibinden Level-5 Evaluation ===")
    lines.append(
        f"Mode: {report['mode']} | Samples: {report['sample_count']} | Success: {report['success_count']} ({report['success_rate'] * 100:.1f}%)"
    )
    lines.append(
        f"Avg latency: {report['avg_latency_ms']} ms | Avg risks/success: {report['avg_risks_per_success']}"
    )
    lines.append(
        "Quality checks: "
        f"invalid severity={report['invalid_severity_count']}, "
        f"missing risk fields={report['missing_field_risk_count']}, "
        f"expected-domain hit rate={report['expected_domain_hit_rate'] * 100:.1f}%"
    )

    lines.append("")
    lines.append("Severity distribution:")
    for severity, count in sorted(
        report.get("severity_distribution", {}).items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"- {severity}: {count}")

    lines.append("")
    lines.append("Top domains:")
    for idx, (domain, count) in enumerate(
        sorted(report.get("domain_distribution", {}).items(), key=lambda item: (-item[1], item[0])), start=1
    ):
        if idx > 10:
            break
        lines.append(f"- {domain}: {count}")

    lines.append("")
    lines.append("Per-sample detail:")
    for index, sample in enumerate(report.get("sample_reports", []), start=1):
        lines.append("")
        lines.append(
            f"{index}. {sample.get('title', 'Unknown listing')} | {sample.get('make', '?')} {sample.get('model', '?')} | status={sample.get('status_code')} | latency={sample.get('latency_ms')} ms"
        )

        if sample.get("status_code") != 200:
            lines.append(f"   API error: {_clip(sample.get('error', ''), 300)}")
            continue

        lines.append(
            f"   Risks: {sample.get('risk_count', 0)} (high={sample.get('high_risk_count', 0)}, medium={sample.get('medium_risk_count', 0)}, low={sample.get('low_risk_count', 0)})"
        )

        expected_domains = sample.get("expected_domains", [])
        missing_expected_domains = sample.get("missing_expected_domains", [])
        if expected_domains:
            lines.append(
                f"   Expected domains: {', '.join(expected_domains)} | Missing: {', '.join(missing_expected_domains) if missing_expected_domains else 'none'}"
            )

        lines.append(f"   Summary: {_clip(sample.get('summary', ''), 340)}")
        risk_items = sample.get("risks", [])
        if not risk_items:
            lines.append("   Risk detail: none")
            continue

        lines.append("   Risk detail:")
        for risk in risk_items[:max_risks_per_sample]:
            confidence_value = risk.get("confidence")
            if isinstance(confidence_value, (float, int)):
                confidence_text = f"{confidence_value:.2f}"
            else:
                confidence_text = str(confidence_value)

            lines.append(
                "   - "
                f"[{risk.get('severity', '?')}] {risk.get('title', 'Untitled risk')} "
                f"(domain={risk.get('domain', 'general')}, confidence={confidence_text})"
            )
            lines.append(f"     Why: {_clip(risk.get('rationale', ''), 240)}")
            lines.append(f"     Check: {_clip(risk.get('inspection_advice', ''), 240)}")

        if len(risk_items) > max_risks_per_sample:
            hidden = len(risk_items) - max_risks_per_sample
            lines.append(f"   ... {hidden} more risks omitted for readability")

    return "\n".join(lines)


def _load_samples(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Sample file must contain a list of objects")
    return payload


def _evaluate_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    client = TestClient(app)

    successes = 0
    total_latency_ms = 0.0
    total_risks = 0
    severity_counter: Counter[str] = Counter()
    domain_counter: Counter[str] = Counter()

    invalid_severity_count = 0
    missing_field_risk_count = 0
    expected_domain_hits = 0
    expected_domain_total = 0

    sample_reports: list[dict[str, Any]] = []

    for sample in samples:
        payload = {
            "listing_url": sample.get("url"),
            "ad_metadata": sample,
        }

        started = time.perf_counter()
        response = client.post("/analyze", json=payload)
        latency_ms = (time.perf_counter() - started) * 1000.0
        total_latency_ms += latency_ms

        entry = {
            "title": sample.get("title"),
            "make": sample.get("make"),
            "model": sample.get("model"),
            "latency_ms": round(latency_ms, 2),
            "status_code": response.status_code,
        }

        if response.status_code != 200:
            entry["error"] = response.text[:300]
            sample_reports.append(entry)
            continue

        data = response.json()
        risks = data.get("risks", []) if isinstance(data, dict) else []

        successes += 1
        total_risks += len(risks)
        sample_high_count = 0
        sample_medium_count = 0
        sample_low_count = 0

        returned_domains = set()
        risk_details: list[dict[str, Any]] = []
        for risk in risks:
            missing_fields = sorted(REQUIRED_RISK_FIELDS - set(risk.keys()))
            if missing_fields:
                missing_field_risk_count += 1

            severity = str(risk.get("severity", "")).lower()
            severity_counter[severity] += 1
            if severity not in VALID_SEVERITIES:
                invalid_severity_count += 1
            elif severity == "high":
                sample_high_count += 1
            elif severity == "medium":
                sample_medium_count += 1
            elif severity == "low":
                sample_low_count += 1

            domain = str(risk.get("domain", "general")).lower()
            domain_counter[domain] += 1
            returned_domains.add(domain)

            risk_details.append(
                {
                    "title": risk.get("title"),
                    "severity": severity,
                    "confidence": risk.get("confidence"),
                    "domain": domain,
                    "rationale": risk.get("rationale"),
                    "inspection_advice": risk.get("inspection_advice"),
                    "missing_fields": missing_fields,
                }
            )

        expected_domains = [str(x).lower() for x in sample.get("expect_domains", [])]
        for expected in expected_domains:
            expected_domain_total += 1
            if expected in returned_domains:
                expected_domain_hits += 1

        entry["risk_count"] = len(risks)
        summary_text = str(data.get("summary", ""))
        entry["summary"] = summary_text
        entry["summary_excerpt"] = _clip(summary_text, 180)
        entry["domains"] = sorted(returned_domains)
        entry["expected_domains"] = expected_domains
        entry["missing_expected_domains"] = sorted(set(expected_domains) - returned_domains)
        entry["high_risk_count"] = sample_high_count
        entry["medium_risk_count"] = sample_medium_count
        entry["low_risk_count"] = sample_low_count
        entry["risks"] = risk_details
        sample_reports.append(entry)

    sample_count = len(samples)
    avg_latency = total_latency_ms / sample_count if sample_count else 0.0
    avg_risks = total_risks / successes if successes else 0.0

    return {
        "mode": "deepseek" if SETTINGS.deepseek_api_key else "fallback",
        "sample_count": sample_count,
        "success_count": successes,
        "success_rate": round(successes / sample_count, 4) if sample_count else 0.0,
        "avg_latency_ms": round(avg_latency, 2),
        "avg_risks_per_success": round(avg_risks, 2),
        "invalid_severity_count": invalid_severity_count,
        "missing_field_risk_count": missing_field_risk_count,
        "expected_domain_hit_rate": (
            round(expected_domain_hits / expected_domain_total, 4) if expected_domain_total else 0.0
        ),
        "severity_distribution": dict(severity_counter),
        "domain_distribution": dict(domain_counter),
        "sample_reports": sample_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Level-5 Sahibinden evaluation")
    parser.add_argument(
        "--samples",
        type=Path,
        default=DEFAULT_SAMPLES_PATH,
        help="Path to sample metadata JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write evaluation report JSON",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Optional limit for number of samples to evaluate (0 means all)",
    )
    parser.add_argument(
        "--max-risks-per-sample",
        type=int,
        default=5,
        help="How many risks to show per sample in console detail output",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Also print full JSON report to stdout",
    )
    args = parser.parse_args()

    samples_path = _resolve_existing_path(args.samples)
    output_path = _resolve_output_path(args.output)

    samples = _load_samples(samples_path)
    if args.max_samples and args.max_samples > 0:
        samples = samples[: args.max_samples]

    report = _evaluate_samples(samples)

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    print(_format_console_report(report, max_risks_per_sample=max(1, args.max_risks_per_sample)))

    if args.print_json:
        print("\n=== Full JSON Report ===")
        print(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    print(f"Loaded samples from: {samples_path}")
    print(f"Saved evaluation report to: {output_path}")


if __name__ == "__main__":
    main()
