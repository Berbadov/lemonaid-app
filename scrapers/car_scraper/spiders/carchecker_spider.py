from __future__ import annotations

import re

import scrapy

from car_scraper.items import IssueReferenceItem


class CarCheckerSpider(scrapy.Spider):
    name = "carchecker_issues"
    allowed_domains = ["carchecker.pro"]
    start_urls = [
        "https://www.carchecker.pro/sitemap.xml",
        "https://www.carchecker.pro/",
    ]

    custom_settings = {
        "DEPTH_LIMIT": 2,
    }

    def parse(self, response: scrapy.http.Response):
        # Sitemap provides the most complete coverage; homepage anchors are backup discovery.
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", "ignore").lower()
        if response.url.endswith(".xml") or "xml" in content_type:
            yield from self.parse_sitemap(response)
            return

        report_hrefs = response.css("a[href*='/reports/']::attr(href)").getall()
        for href in sorted(set(report_hrefs)):
            absolute = response.urljoin(href)
            if self._is_report_url(absolute):
                yield response.follow(absolute, callback=self.parse_report)

    def parse_sitemap(self, response: scrapy.http.Response):
        locs = re.findall(r"<loc>(.*?)</loc>", response.text, flags=re.IGNORECASE)
        for loc in locs:
            url = loc.strip()
            if not url:
                continue

            if url.endswith(".xml"):
                yield response.follow(url, callback=self.parse_sitemap)
                continue

            if self._is_report_url(url):
                yield response.follow(url, callback=self.parse_report)

    def parse_report(self, response: scrapy.http.Response):
        title = (response.css("h1::text").get() or "").strip()
        if not title:
            return

        breadcrumb = [t.strip() for t in response.css("nav.breadcrumb a::text").getall() if t.strip()]
        make = breadcrumb[1] if len(breadcrumb) > 1 else self._extract_make_from_title(title)
        model = self._extract_model_from_title(title=title, make=make)

        subtitle = self._clean_text(response.css("p.subtitle::text").get() or "")
        summary_line = self._clean_text(response.css("p.summary-line::text").get() or "")
        generation = self._extract_generation(title)
        year_start, year_end = self._extract_year_range(subtitle)

        total_cost = self._clean_text(" ".join(response.css("#total-cost::text").getall()))
        fixed_cost = self._clean_text(response.css("#cost-fixed::text").get() or "")
        risk_buffer = self._clean_text(response.css("#cost-risk::text").get() or "")

        overall_summaries = [
            self._clean_text(t)
            for t in response.css(".summary-box .summary-text::text").getall()
            if self._clean_text(t)
        ]
        overall_summary = overall_summaries[0] if overall_summaries else ""

        checklist_points = self._extract_checklist_points(response)
        recalls, recall_summary = self._extract_recalls(response)

        for risk in response.css(".risk-item"):
            issue_name = self._clean_text(risk.css(".risk-name::text").get() or "")
            if not issue_name:
                continue

            repair_cost = self._clean_text(risk.css(".risk-cost::text").get() or "")
            risk_class = risk.css(".risk-bar-fill::attr(class)").get() or ""
            summary_text = self._clean_text(
                " ".join(
                    t.strip()
                    for t in risk.css("details summary::text").getall()
                    if t.strip()
                )
            )
            summary_text = re.sub(r"\s*·\s*(more|less)\s*", " ", summary_text, flags=re.IGNORECASE)
            summary_text = self._clean_text(summary_text)

            note_text = self._clean_text(
                " ".join(t.strip() for t in risk.css(".risk-note *::text").getall() if t.strip())
            )

            details_parts = [
                f"Vehicle: {title}.",
                f"Issue: {issue_name}.",
            ]
            if repair_cost:
                details_parts.append(f"Repair cost range: {repair_cost}.")
            if summary_text:
                details_parts.append(f"Issue summary: {summary_text}.")
            if note_text:
                details_parts.append(f"Technical notes: {note_text}")
            if total_cost or fixed_cost or risk_buffer:
                details_parts.append(
                    f"Annual maintenance estimate: {total_cost} (fixed: {fixed_cost}, risk buffer: {risk_buffer})."
                )
            if summary_line:
                details_parts.append(f"Model context: {summary_line}")
            if overall_summary:
                details_parts.append(f"Overall reliability summary: {overall_summary}")

            details = self._clean_text(" ".join(part for part in details_parts if part)).strip()[:4500]
            domain = self._infer_domain(issue_name, f"{summary_text} {note_text}")
            severity = self._severity_from_likelihood(risk_class, repair_cost, note_text)

            item = IssueReferenceItem()
            item["source"] = "carchecker.pro"
            item["source_url"] = response.url
            item["make"] = make
            item["model"] = model
            item["generation"] = generation
            item["year_start"] = year_start
            item["year_end"] = year_end
            item["issue_domain"] = domain
            item["severity"] = severity
            item["title"] = issue_name
            item["symptoms"] = self._extract_symptoms(note_text)
            item["details"] = details
            item["recommendation"] = self._recommendation_for_domain(domain, checklist_points)
            yield item

        for recall_label, recall_value in recalls:
            if not recall_label:
                continue

            recall_details_parts = [
                f"Vehicle: {title}.",
                f"Recall/TSB item: {recall_label}.",
            ]
            if recall_value:
                recall_details_parts.append(f"Status/guidance: {recall_value}.")
            if recall_summary:
                recall_details_parts.append(recall_summary)

            recall_blob = f"{recall_label} {recall_value}"
            recall_domain = self._infer_domain(recall_label, recall_blob)
            if recall_domain == "general":
                recall_domain = "manufacturing"

            item = IssueReferenceItem()
            item["source"] = "carchecker.pro"
            item["source_url"] = response.url
            item["make"] = make
            item["model"] = model
            item["generation"] = generation
            item["year_start"] = year_start
            item["year_end"] = year_end
            item["issue_domain"] = recall_domain
            item["severity"] = self._infer_recall_severity(recall_blob)
            item["title"] = f"Recall/TSB: {recall_label}"
            item["symptoms"] = None
            item["details"] = self._clean_text(" ".join(recall_details_parts))[:4500]
            item["recommendation"] = "Verify completion and eligibility by VIN with the manufacturer or dealer."
            yield item

    @staticmethod
    def _is_report_url(url: str) -> bool:
        if not url.startswith("https://"):
            return False
        if "carchecker.pro" not in url:
            return False
        if "/de/reports/" in url:
            return False
        return "/reports/" in url and url.endswith(".html")

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _extract_make_from_title(title: str) -> str | None:
        tokens = title.split()
        if not tokens:
            return None
        return tokens[0]

    @staticmethod
    def _extract_model_from_title(title: str, make: str | None) -> str | None:
        remainder = title
        if make and title.lower().startswith(f"{make.lower()} "):
            remainder = title[len(make) :].strip()

        tokens = remainder.split()
        if not tokens:
            return None

        return tokens[0]

    @staticmethod
    def _extract_generation(title: str) -> str | None:
        tokens = title.split()
        if len(tokens) < 3:
            return None

        for token in tokens[2:6]:
            if re.fullmatch(r"Mk\d+", token, flags=re.IGNORECASE):
                return token
            if re.fullmatch(r"[A-Za-z]{1,4}\d{1,4}[A-Za-z]?", token):
                return token
        return None

    @staticmethod
    def _extract_year_range(subtitle: str) -> tuple[int | None, int | None]:
        match = re.search(r"((?:19|20)\d{2})\s*-\s*((?:19|20)\d{2}|\+)", subtitle)
        if not match:
            return None, None

        year_start = int(match.group(1))
        year_end_raw = match.group(2)
        year_end = None if year_end_raw == "+" else int(year_end_raw)
        return year_start, year_end

    def _extract_checklist_points(self, response: scrapy.http.Response) -> list[str]:
        points = response.xpath(
            "//div[contains(@class,'card')][.//div[contains(@class,'card-title') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pre-purchase inspection checklist')]]//li/strong/text()"
        ).getall()
        normalized = [self._clean_text(point) for point in points if self._clean_text(point)]
        return normalized

    def _extract_recalls(self, response: scrapy.http.Response) -> tuple[list[tuple[str, str]], str]:
        recall_card = response.xpath(
            "//div[contains(@class,'card')][.//div[contains(@class,'card-title') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'recalls')]]"
        )
        labels = [self._clean_text(t) for t in recall_card.css(".compare-label::text").getall() if self._clean_text(t)]
        values = [self._clean_text(t) for t in recall_card.css(".compare-value::text").getall() if self._clean_text(t)]
        rows = list(zip(labels, values))
        summary = self._clean_text(" ".join(recall_card.css(".summary-text::text").getall()))
        return rows, summary

    @staticmethod
    def _infer_domain(title: str, details: str) -> str:
        blob = f"{title} {details}".lower()
        if any(x in blob for x in ["engine", "turbo", "misfire", "timing"]):
            return "engine"
        if any(x in blob for x in ["gearbox", "transmission", "clutch", "cvt"]):
            return "powertrain"
        if any(x in blob for x in ["rust", "paint", "body", "panel", "chassis", "door", "corrosion"]):
            return "body"
        if any(x in blob for x in ["recall", "factory", "manufacturing", "weld", "tsb", "airbag"]):
            return "manufacturing"
        return "general"

    @staticmethod
    def _severity_from_likelihood(risk_class: str, repair_cost: str, note_text: str) -> str:
        classes = risk_class.lower()
        if "risk-high" in classes:
            return "high"
        if "risk-medium" in classes:
            return "medium"

        if "risk-low" in classes:
            return "low"

        max_cost = CarCheckerSpider._extract_max_cost(repair_cost)
        if max_cost is not None and max_cost >= 2000:
            return "high"
        if max_cost is not None and max_cost >= 700:
            return "medium"

        note = note_text.lower()
        if any(x in note for x in ["limp mode", "no-start", "overheating", "fire", "danger"]):
            return "high"
        return "low"

    @staticmethod
    def _extract_max_cost(repair_cost: str) -> int | None:
        values = re.findall(r"\d[\d,]*", repair_cost)
        if not values:
            return None
        numbers = [int(value.replace(",", "")) for value in values]
        return max(numbers) if numbers else None

    @staticmethod
    def _extract_symptoms(note_text: str) -> str | None:
        match = re.search(r"symptoms?\s*include\s*(.+?)(?:\.|;)", note_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()[:700]

        chunks = re.split(r"\.\s+", note_text)
        candidates = [
            chunk.strip()
            for chunk in chunks
            if re.search(r"warning|rattle|noise|vibration|hesitation|loss of power|check engine", chunk, re.IGNORECASE)
        ]
        if not candidates:
            return None
        return " ".join(candidates[:2])[:700]

    @staticmethod
    def _infer_recall_severity(blob: str) -> str:
        text = blob.lower()
        if any(x in text for x in ["airbag", "brake", "fire", "no-start", "safety"]):
            return "high"
        if any(x in text for x in ["recall", "tsb", "software", "warranty"]):
            return "medium"
        return "low"

    @staticmethod
    def _recommendation_for_domain(domain: str, checklist_points: list[str]) -> str:
        if not checklist_points:
            return "Inspect related systems with an independent specialist before purchase."

        keyword_map = {
            "engine": ["cold start", "coolant", "oil", "turbo"],
            "powertrain": ["gearbox", "transmission", "clutch", "dsg"],
            "body": ["body", "paint", "door", "rust"],
            "manufacturing": ["recall", "emissions", "vin", "warranty"],
        }

        selected = []
        for point in checklist_points:
            text = point.lower()
            if any(key in text for key in keyword_map.get(domain, [])):
                selected.append(point)

        if not selected:
            selected = checklist_points[:2]

        return f"Prioritize checks: {', '.join(selected[:3])}."
