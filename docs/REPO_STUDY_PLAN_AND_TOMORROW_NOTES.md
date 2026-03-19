# Lemonaid Tomorrow Notes + Detailed Repo Study Plan

Date: 2026-03-20

This document has two goals:
1. Capture your exact product notes before sleep.
2. Give you a deep study plan with concrete, code-level examples so you can understand and improve this repository end-to-end.

---

## Part 1: Tomorrow Notes (Captured From You)

## 1) Product Direction Decisions

- We do not care about financing options.
- Core value is issue analysis quality, not financing or pricing plans.
- Interface quality is currently secondary (important later, not now).

## 2) Critical Product Problems You Reported

1. Mileage issue:
- Analyzer says mileage is missing even when mileage exists on the page.
- Likely reason: extension currently extracts only a small metadata set.

2. Missing technical specifications extraction:
- Current extraction appears mostly title + description (+ price).
- Must read Sahibinden technical specs (teknik ozellikler), especially:
  - gearbox / transmission
  - horsepower (hp)
  - engine data to infer engine code

3. Weak database grounding:
- Perceived behavior: model seems to make generic conclusions.
- It does not feel strongly grounded in scraped issue DB.

4. Hallucination / over-warning:
- Example: Toyota Corolla 1.8 Hybrid 2022 flagged with broad hidden-mechanical issues too frequently.
- Model appears to over-generalize and output risk-heavy templates.

5. UX quality:
- Popup UI currently feels weak.
- Deferred until core extraction and reasoning quality are fixed.

6. Latency too high:
- Responses feel very slow ("3 business days").
- Need hard latency reduction plan.

## 3) Immediate Priority Order (Tomorrow)

1. Fix metadata extraction quality (Sahibinden technical specs).
2. Improve retrieval grounding (SQL + vector + stricter relevance filters).
3. Reduce hallucination for reliable models with calibration rules.
4. Improve latency with practical optimizations.
5. UI refresh later.

---

## Part 2: What The Code Currently Does (Reality Check)

## A) Extension extraction is currently shallow (confirmed)

In `extension/content.js` the `extractSahibindenMetadata()` function only extracts:
- title
- price_amount
- currency
- description
- url/source

Concrete current behavior:

```js
function extractSahibindenMetadata() {
  const title = textBySelector("h1");
  const priceText = textBySelector(".classified-price-wrapper, .classifiedInfo h3");
  const description = textBySelector("#classifiedDescription") || textBySelector(".classifiedDescription");

  return {
    source: "sahibinden.com",
    url: window.location.href,
    title,
    price_amount: numberFromText(priceText),
    currency: priceText && priceText.includes("TL") ? "TRY" : null,
    description
  };
}
```

Why your mileage complaint is valid:
- There is no extraction for mileage from technical specs.
- No extraction for transmission, fuel_type, hp, engine volume, model year from technical tables.

## B) API supports richer metadata, but extension does not send it

`api/main.py` already supports many fields in transient listing build:
- mileage_km
- fuel_type
- transmission
- engine_volume_cc
- body_type
- year
- make/model

Concrete code path:

```python
listing = AdListing(
    ...
    year=meta.get("year"),
    mileage_km=meta.get("mileage_km"),
    fuel_type=meta.get("fuel_type"),
    transmission=meta.get("transmission"),
    engine_volume_cc=meta.get("engine_volume_cc"),
    body_type=meta.get("body_type"),
    ...
)
```

Meaning:
- Backend schema is ready for richer metadata.
- Extension extractor is the bottleneck.

## C) Retrieval grounding is basic (your observation is accurate)

In `rag/retriever.py`:
- SQL filter is mostly make + model exact-ish matching (`ilike` with raw value).
- If no make/model, it falls back to broad domains (engine/powertrain/body/manufacturing).
- Vector query text is built from `make model description` only.

Concrete code shape:

```python
if listing.make:
    filters.append(IssueReference.make.ilike(listing.make))
if listing.model:
    filters.append(IssueReference.model.ilike(listing.model))
...
query_text_parts = [listing.make or "", listing.model or "", listing.description or ""]
```

Why grounding feels weak:
- No use of year range filtering.
- No use of generation.
- No use of transmission/fuel/engine displacement/hp-derived engine code.
- No relevance scoring feedback to the LLM (just raw contexts).

## D) Hallucination pressure source

In `rag/analyzer.py`:
- Model always asked to produce risks.
- There is no explicit "safe outcome" calibration threshold.
- There is no strict confidence floor and no suppression for weak context matches.

Current behavior was improved for text length, but not yet deeply calibrated for conservative reliability conclusions.

## E) Latency source likely includes:

- Remote LLM call to DeepSeek (`chat.completions.create`).
- Prompt + context size can be large.
- No response cache for repeated/similar listings.
- End-to-end includes extension -> background -> API -> retrieval -> model -> response.

---

## Part 3: 10-Page Study Plan (Concrete + Repo-Specific)

This is intentionally long and practical. Think of each "Page" as one focused learning block.

---

## Page 1: System Map + Request Lifecycle

Goal:
- Understand exactly what happens from "Analyze Current Page" click to risk cards in popup.

Study files:
- `extension/popup.js`
- `extension/content.js`
- `extension/background.js`
- `api/main.py`
- `rag/retriever.py`
- `rag/analyzer.py`

Trace exercise:
1. In popup click handler, identify where metadata is requested.
2. Follow `chrome.tabs.sendMessage` into content script.
3. Follow `chrome.runtime.sendMessage` into background.
4. Follow fetch to `/analyze`.
5. Follow API analyze endpoint.
6. Follow retrieval + LLM call.
7. Follow returned risks into popup cards.

Concrete snippet to inspect:

```js
const metadata = await getAdMetadata(tab.id);
const result = await requestAnalysis(metadata);
for (const risk of risks) {
  resultNode.appendChild(createRiskCard(risk));
}
```

Output you should produce for yourself:
- One sequence diagram showing every hop and payload shape.

---

## Page 2: Data Model Mastery (SQLite / SQLAlchemy)

Goal:
- Understand how listing and issue data is structured and where fields are missing.

Study files:
- `storage/models.py`
- `storage/db.py`
- `api/schemas.py`

Key entities:
- `AdListing`
- `IssueReference`
- `ListingIssueAnalysis`

Concrete learning task:
- List every field in `AdListing` and mark:
  - currently sent from extension
  - currently always null
  - should be extracted from teknik ozellikler

SQL exercise (manual check):

```sql
SELECT make, model, year, mileage_km, transmission, fuel_type, engine_volume_cc
FROM ad_listings
ORDER BY id DESC
LIMIT 20;
```

Expected insight:
- Most rows from extension path are likely sparse.

---

## Page 3: Scraper and Issue Reference Pipeline

Goal:
- Understand what your knowledge base contains and how it is populated.

Study files:
- `scrapers/car_scraper/spiders/carchecker_spider.py`
- `scrapers/car_scraper/pipelines.py`
- `storage/models.py`

Key logic checkpoints:
- URL discovery from sitemap/homepage.
- Parsing risks and recalls.
- Domain and severity inference rules.
- Upsert strategy in pipeline (`source_url + title`).

Concrete snippet to reason about:

```python
domain = self._infer_domain(issue_name, f"{summary_text} {note_text}")
severity = self._severity_from_likelihood(risk_class, repair_cost, note_text)
```

Exercise:
- For 5 known issues, manually verify domain/severity mapping quality.
- Write down false positives where `general` should be specific domain.

---

## Page 4: Retrieval Quality Engineering (Most Important)

Goal:
- Make the analyzer rely more on DB and less on generic LLM priors.

Study files:
- `rag/retriever.py`
- `rag/vector_store.py`
- `scripts/index_issue_references.py`

Current weakness summary:
- Retrieval query lacks year/transmission/fuel/engine-hp dimensions.

Improvement design (implement later):
1. Add structured filters:
- make/model exact normalized match
- year within `year_start/year_end` bounds
- optional generation match

2. Build enriched query text:
- include transmission
- include fuel_type
- include engine_volume_cc
- include parsed HP
- include inferred engine code token

3. Re-rank contexts:
- score each context by structured match quality before sending to LLM.

Concrete pseudocode target:

```python
score = 0
if row.make == listing.make: score += 3
if row.model == listing.model: score += 3
if year_match: score += 2
if transmission_hint_match: score += 1
if fuel_hint_match: score += 1
```

Expected effect:
- Less generic output.
- More database-grounded statements.

---

## Page 5: Prompt + Hallucination Control

Goal:
- Reduce weird high-risk claims for reliable cars unless strong evidence exists.

Study file:
- `rag/analyzer.py`

Current good changes:
- output compacting and clipping
- shorter rationale/advice

Next upgrades to learn and add:
1. Add "evidence-first" output contract:
- each risk must cite one supporting context title/source.

2. Add abstention rule:
- if retrieved evidence confidence is weak, output fewer risks and include "low evidence" marker.

3. Add reliability guardrails:
- for known reliable model+year combinations, require stronger evidence to assign high severity.

Example stronger system instruction (future):

```text
Do not output high-severity risks unless supported by at least one explicit retrieved context.
If evidence is weak, output "monitoring recommendations" not mechanical failure claims.
```

Exercise:
- Compare 10 Corolla/Auris/Prius analyses before/after guardrails.

---

## Page 6: Sahibinden Teknik Ozellikler Extraction Plan

Goal:
- Fix the metadata bottleneck in extension.

Study file:
- `extension/content.js`

What to add:
- parser for table/list based technical specs blocks.
- normalize Turkish labels to canonical keys.

Target extracted keys:
- year
- mileage_km
- transmission
- fuel_type
- engine_volume_cc
- horsepower_hp
- body_type
- drivetrain (if present)

Example mapping idea:

```js
const LABEL_MAP = {
  "kilometre": "mileage_km",
  "vites": "transmission",
  "yakit": "fuel_type",
  "motor hacmi": "engine_volume_cc",
  "motor gucu": "horsepower_hp",
  "model yili": "year"
};
```

Normalization helpers to study/write:
- Turkish character normalization for robust matching.
- number parsing with separators.
- convert "1.5" liters to cc (1500) if needed.

Exercise:
- Collect 20 live ad HTML snapshots and run parser tests offline.

---

## Page 7: Engine Code Inference Logic

Goal:
- Improve model-specific issue matching by deriving approximate engine family.

Inputs to use:
- make, model, year
- fuel_type
- engine_volume_cc
- horsepower_hp
- transmission

Approach:
1. Rule table for common Turkish-market models (start small).
2. Return "engine_profile" token(s), not hard certainty.

Example:

```python
if make == "Toyota" and model == "Corolla" and fuel == "Hybrid" and engine_cc in [1798, 1800]:
    return ["2ZR-FXE", "toyota_hybrid_gen4"]
```

Use in retrieval:
- append these tokens to vector query text.
- optionally add lightweight metadata filter in vector candidates.

Important discipline:
- treat as probabilistic hints; never claim exact engine code without explicit evidence.

---

## Page 8: Latency Reduction Playbook

Goal:
- Bring analysis time from painful to acceptable.

Measure first (baseline):
- extension click to first response
- API `/analyze` internal steps timing
- DeepSeek call duration

Low-risk optimizations:
1. Retrieval limit tuning:
- reduce unnecessary context count when metadata confidence is high.

2. Prompt size trimming:
- pass compressed context summaries, not long raw text.

3. Response caching:
- key by normalized `make+model+year+mileage+fuel+transmission+engine_cc`.
- cache recent results in SQLite or in-memory LRU.

4. Parallel prep:
- pre-format query text and context scoring before API call where possible.

5. Timeout / fallback strategy:
- strict timeout and deterministic fallback with explicit message.

Concrete instrumentation example:

```python
started = time.perf_counter()
contexts = retrieve_issue_context(...)
retrieval_ms = (time.perf_counter() - started) * 1000
```

Success target:
- P50 under 6s
- P90 under 12s

---

## Page 9: Testing Strategy You Should Learn Here

Goal:
- Move from smoke tests to confidence tests.

Current tests are minimal:
- `tests/test_health.py`
- `tests/test_schema.py`

Add these test classes:
1. Content parser tests (`extension/content.js` via fixture HTML snapshots).
2. Retrieval relevance tests (`rag/retriever.py`) with seeded SQLite.
3. Hallucination regression tests with known-safe sample set.
4. Latency budget tests for key paths.
5. API contract tests for required response fields.

Evaluation harness already exists:
- `scripts/eval_sahibinden_level5.py`

Use it for regression gates:
- expected-domain hit rate threshold
- high-risk overprediction threshold for known reliable models
- average latency threshold

---

## Page 10: UX Iteration (Later, But Structured)

Goal:
- Improve readability and trust in extension popup after data/logic fixes.

Current UI files:
- `extension/popup.html`
- `extension/popup.css`
- `extension/popup.js`

UX principles for this product:
1. Evidence transparency:
- every risk card should show "Why this risk" and "Evidence source".

2. Confidence language:
- show low/medium/high confidence badges with tooltips.

3. Actionable outputs:
- short mechanic checklist, not paragraphs.

4. User trust:
- add "What we could not verify" section.

5. Speed UX:
- progressive loading states and partial rendering.

---

## Part 4: Concrete 14-Day Learning + Execution Program

This is your practical schedule.

## Day 1
- Read request lifecycle files.
- Draw flow diagram.
- Run extension once end-to-end with logs open.

## Day 2
- Deep dive data models.
- Inspect SQLite content quality.
- Build a missing-fields checklist.

## Day 3
- Inspect scraper outputs and issue stats.
- Identify top 10 noisy issue references.

## Day 4
- Implement Sahibinden technical spec extraction prototype.
- Parse mileage, transmission, fuel, year from real pages.

## Day 5
- Add hp and engine displacement parsing.
- Normalize values and validate against 20 pages.

## Day 6
- Upgrade retriever with structured filters.
- Add year-aware and metadata-aware ranking.

## Day 7
- Add engine profile hint logic.
- Include hints in retrieval query text.

## Day 8
- Add hallucination guardrails in prompt + post-processing.
- Create "safe evidence" behavior for reliable models.

## Day 9
- Add response caching and context size trimming.
- Benchmark latency improvements.

## Day 10
- Expand eval harness metrics:
  - over-warning rate
  - evidence coverage
  - latency percentiles

## Day 11
- Build parser fixture tests for Sahibinden HTML snapshots.

## Day 12
- Add retriever unit tests with seeded DB fixtures.

## Day 13
- Refine popup risk cards for concise + trustworthy output.

## Day 14
- Full regression run and release checklist.

---

## Part 5: Suggested Immediate TODO For Next Session

Tomorrow opening steps (90-minute block):

1. Implement technical specs extractor in `extension/content.js`.
2. Log raw metadata payload sent from popup to API.
3. Verify API receives non-null:
- mileage_km
- fuel_type
- transmission
- year
- engine_volume_cc

4. Add temporary debug response field in `/analyze` locally (or logs) to show retrieval contexts selected.
5. Run `scripts/eval_sahibinden_level5.py` with 10 samples and compare domain hit + latency.

Acceptance checklist for tomorrow:
- At least 80 percent of sampled Sahibinden pages produce non-null mileage_km.
- At least 70 percent produce non-null transmission and fuel_type.
- Domain hit rate improves vs baseline.
- No "mileage missing" wording when mileage exists in metadata.

---

## Part 6: Concrete Code Reading Exercises (Do Not Skip)

Exercise A: Why DB grounding feels weak
- Read `rag/retriever.py`.
- Write down exactly how many metadata fields are used today.
- Add a short note on each omitted field and expected impact.

Exercise B: Understand analyzer behavior
- Read `rag/analyzer.py`.
- Identify where prompt is built.
- Identify where JSON output is parsed.
- Identify where text is compacted.

Exercise C: Understand extension metadata gap
- Read `extension/content.js`.
- Create a map from Sahibinden label text -> normalized backend keys.

Exercise D: Understand persistence and indexing
- Read `scripts/index_issue_references.py`.
- Explain how metadata from issue references is sent to vector store.

---

## Part 7: Known Risks and Guardrails

Known risks:
- HTML selectors for Sahibinden can change.
- Overfitting to one page structure causes silent extraction failures.
- Vector backend availability may vary by machine.
- LLM response style drift can increase hallucinations.

Guardrails:
- Strong parser test fixtures.
- Fallback selectors and defensive null handling.
- Output schema validation before response.
- Conservative risk mode when evidence is weak.

---

## Part 8: Final Encouragement Note

You provided the right product instincts:
- prioritize factual extraction
- reduce hallucination
- force evidence grounding
- optimize latency

Those are exactly the hard parts that make this product real.

Sleep well. Tomorrow you already have a clear map.
