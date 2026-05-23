# Paper Radar

Paper Radar is a compliant cross-disciplinary academic metadata radar for personal use.

The current version is V0.7.3. It collects recent academic metadata from official APIs and public APIs, normalizes records into one `PaperItem` model, stores them in SQLite, exports a JSONL candidate pool, and can generate a lightweight weekly Markdown candidate report with transparent rule-based candidate scoring, lane balance, and an optional reject/downrank log. V0.7.3 calibrates default topic seeds and scoring thresholds after the 2026-W21 real weekly run.

It is not a general-purpose crawler, not a Google Scholar scraper, not a PDF downloader, and not a Zotero replacement.

## V0.7.3 Capabilities

- Unified `PaperItem` model.
- DOI, arXiv ID, title, and PMID-aware canonical ID generation.
- SQLite storage for papers, source references, crawl runs, and possible duplicates.
- OpenAlex discovery by keyword.
- arXiv discovery by keyword and category.
- PubMed discovery through NCBI E-utilities.
- bioRxiv and medRxiv discovery through the official preprint API.
- Crossref enrichment by DOI.
- Semantic Scholar enrichment by DOI or arXiv ID.
- Raw API response saving under `data/raw/<source>/<YYYY-WW>/`.
- JSONL candidate export under `data/exports/`.
- Lightweight weekly candidate-pool Markdown reports under `data/reports/`.
- Diagnostics for local database and export state.
- Central runtime path configuration through `config/app.yaml` and `src.app`.
- Rule-based candidate scoring through `config/scoring.yaml` and `src.ranking`.
- Configurable lane balance for weekly candidate reports.
- Optional reject/downrank log for debugging report filtering decisions.
- Score-audit Markdown report for inspecting scoring calibration.
- Offline source preview for enabled/disabled sources, planned query labels, limits, and estimated max records.
- Empty-export protection in the main pipeline, with an explicit `--allow-empty-export` override.
- Calibrated first keywords in `config/topics.yaml` so default source preview and crawling use narrower lane seeds.
- Calibrated `config/scoring.yaml` to make `S_candidate` harder to reach and missing abstracts more costly.
- Pytest coverage for normalization, storage, enrichment, deduplication, diagnostics, PubMed, bioRxiv/medRxiv, source preview, empty-export protection, and report generation.

## What V0.7.3 Does Not Do

- It does not scrape Google Scholar.
- It does not scrape publisher HTML pages.
- It does not download PDFs.
- It does not run LLM summarization or ranking.
- It does not treat candidate levels as final reading grades.
- It does not automatically select the final weekly 13 items.
- It does not integrate with Zotero, Obsidian, Anki, Telegram, or email.
- It does not use a vector database.

The project philosophy is stable, compliant metadata collection first; recommendation and reading workflow later.

## Configure Topics

Edit:

```bash
config/topics.yaml
```

Each lane can define:

- `keywords`: used by OpenAlex, arXiv keyword search, PubMed, bioRxiv, and medRxiv.
- `arxiv_categories`: used only by arXiv.

## Configure Sources

Edit:

```bash
config/sources.yaml
```

Each source has an `enabled` flag plus conservative limits. New discovery sources are disabled by default.

### Enable PubMed

PubMed uses NCBI E-utilities, not HTML scraping.

```yaml
pubmed:
  enabled: true
  api_key_env: NCBI_API_KEY
  email_env: CONTACT_EMAIL
  days_back: 14
  per_query_limit: 20
  delay_seconds: 0.4
  max_total: 50
  max_queries_per_lane: 1
```

Recommended environment variables:

```powershell
$env:CONTACT_EMAIL="your_email@example.com"
$env:NCBI_API_KEY="your_ncbi_api_key"
```

`NCBI_API_KEY` is optional, but setting `CONTACT_EMAIL` is polite and recommended.

### Enable bioRxiv

bioRxiv uses the official date-range API and filters locally by lane keywords across title, abstract, and category.

```yaml
biorxiv:
  enabled: true
  server: biorxiv
  days_back: 14
  per_query_limit: 50
  delay_seconds: 1
  max_total: 100
  max_queries_per_lane: 1
```

### Enable medRxiv

medRxiv uses the same official API pattern as bioRxiv.

```yaml
medrxiv:
  enabled: true
  server: medrxiv
  days_back: 14
  per_query_limit: 50
  delay_seconds: 1
  max_total: 100
  max_queries_per_lane: 1
```

## Enrichment Boundaries

Crossref and Semantic Scholar are enrichment sources in this project. They are not discovery sources.

- Crossref enriches stored candidates that already have a DOI.
- Semantic Scholar enriches stored candidates that already have a DOI or arXiv ID.
- Crossref does not do keyword discovery by default.
- Semantic Scholar does not do title search by default.
- Semantic Scholar defaults to `require_api_key: true`; if enabled without `S2_API_KEY`, it is skipped with a warning.

## Configure Runtime Paths

Edit:

```bash
config/app.yaml
```

Default local paths remain:

- `data/papers.sqlite`
- `data/raw/`
- `data/exports/`
- `data/reports/`
- `logs/`

Relative paths in `config/app.yaml` resolve under the project root. Absolute paths remain absolute. The `obsidian` section is scaffolding for a possible future packaging mode only; Paper Radar does not currently write to an Obsidian vault or implement an Obsidian plugin.

Supported environment overrides:

- `PAPER_RADAR_CONFIG_DIR`
- `PAPER_RADAR_DATA_DIR`
- `PAPER_RADAR_REPORTS_DIR`
- `PAPER_RADAR_EXPORTS_DIR`
- `PAPER_RADAR_LOGS_DIR`
- `PAPER_RADAR_DATABASE_PATH`

## Configure Scoring

Edit:

```bash
config/scoring.yaml
```

V0.7 scoring is rule-based and explainable. It uses metadata completeness, freshness, source quality, lane keyword matches, simple cross-domain keyword overlap, review/survey signals, and simple noise penalties. Weights, thresholds, lane balance, reject behavior, and report detail settings are configurable.

Candidate levels such as `S_candidate`, `A_candidate`, `B_candidate`, and `C_candidate` are report-stage candidate levels only. They are not final weekly reading grades.

## Run Locally

For the authoritative validation and run-command reference, see `docs/testing.md`.

Install dependencies:

```bash
uv sync --extra dev
```

Run the metadata pipeline:

```bash
uv run python -m src.main
```

Preview configured sources and planned queries without network access:

```bash
uv run python -m src.main --source-preview
```

`--dry-run` is an alias for the same source preview. If a normal pipeline run collects no records, it logs a warning and skips writing the current candidate export by default. Use `--allow-empty-export` only when an empty JSONL export is intentional.

Or with an explicit config directory:

```bash
uv run python -m src.main --config-dir config
```

Run diagnostics:

```bash
uv run python -m src.diagnostics
```

```bash
uv run python -m src.diagnostics --config-dir config
```

Generate the weekly candidate-pool report:

```bash
uv run python -m src.report.weekly_candidates
```

```bash
uv run python -m src.report.weekly_candidates --config-dir config
```

Generate a reject/downrank log alongside the report:

```bash
uv run python -m src.report.weekly_candidates --write-reject-log
```

Use the compatibility metadata ranking path:

```bash
uv run python -m src.report.weekly_candidates --no-scoring
```

Generate a score-audit calibration report:

```bash
uv run python -m src.report.score_audit
```

Useful score-audit options:

```bash
uv run python -m src.report.score_audit --config-dir config
uv run python -m src.report.score_audit --export-file data/exports/candidates_2026-W21.jsonl
uv run python -m src.report.score_audit --output-dir data/reports
uv run python -m src.report.score_audit --per-lane 20
uv run python -m src.report.score_audit --compare-no-scoring
```

Run tests:

```bash
uv run --extra dev pytest -q
```

## Weekly Candidate Report

The report command reads `data/exports/candidates_<YYYY-WW>.jsonl` for the current week. If the current week export does not exist, it uses the latest available export. The default export directory and report output directory come from `config/app.yaml`.

It writes:

```bash
data/reports/weekly_candidates_<YYYY-WW>.md
```

The report is a candidate pool for later screening. It is not a reading list. It groups items by lane when `source_query` is available and includes compact metadata plus score details for later screening:

- candidate level
- radar score
- score reasons
- penalties
- title
- shortened authors
- date
- source
- venue
- DOI, arXiv ID, or PMID
- URL
- abstract preview
- fields and keywords
- source query

You can adjust the number of items per lane:

```bash
uv run python -m src.report.weekly_candidates --per-lane 20
```

Or with:

```powershell
$env:PAPER_RADAR_REPORT_PER_LANE="20"
```

When requested with `--write-reject-log`, V0.7 also writes:

```bash
data/reports/rejected_candidates_<YYYY-WW>.md
```

The score audit reads the same candidate export and writes:

```bash
data/reports/score_audit_<YYYY-WW>.md
```

It includes candidate level counts, lane/source stats, score component totals, penalty counts, near-threshold candidates, top/bottom selected candidates, rejected/downranked summaries, and deterministic calibration notes.

## Output Files

Pipeline runs can generate:

- `data/raw/<source>/<YYYY-WW>/...`: raw API responses.
- `data/papers.sqlite`: local SQLite database.
- `data/exports/candidates_<YYYY-WW>.jsonl`: normalized candidate export.
- `data/reports/weekly_candidates_<YYYY-WW>.md`: lightweight weekly candidate report.
- `data/reports/rejected_candidates_<YYYY-WW>.md`: optional reject/downrank debug log.
- `data/reports/score_audit_<YYYY-WW>.md`: score calibration audit report.
- `logs/crawl_<YYYY-WW>.log`: crawl logs.

These are the default local paths. V0.6.5 allows them to be redirected through `config/app.yaml` or the supported runtime environment variables.

Runtime artifacts are ignored by git except for placeholder files.

## Maintained Docs

- `AGENTS.md`: repository working rules, recovery protocol, and documentation sync rules.
- `docs/architecture.md`: current architecture and module boundaries.
- `docs/changes.md`: dated decisions, accepted tradeoffs, and verification notes.
- `docs/testing.md`: authoritative run and validation commands.
- `data/AGENTS.md`: rules for runtime data, raw responses, exports, reports, and local databases.

## Data Model Notes

Core tables:

- `papers`: one row per canonical paper.
- `paper_sources`: source/query/raw-response references for each paper.
- `crawl_runs`: per source/query or enrichment-item run status.
- `possible_duplicates`: possible duplicate pairs, never auto-merged.

## Suggested Roadmap

Good next candidates:

1. Run a real weekly trial and manually calibrate `config/topics.yaml` and `config/scoring.yaml`.
2. Improve source-specific field coverage and diagnostics.
3. Later, consider selected-item local organization or safe OA PDF download as a separate V0.8 task.

Keep the boundary clear: collect clean metadata first, then build recommendation and reading workflows on top.
