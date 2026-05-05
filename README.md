# Paper Radar

Paper Radar is a compliant academic metadata crawler. The current V0 only fetches
metadata from official/public interfaces, normalizes it into one model, stores it
in SQLite, and exports a JSONL candidate set.

## Current V0

Implemented:

- `PaperItem` Pydantic model
- DOI, arXiv ID, title normalization, and `canonical_id`
- SQLite storage with `papers` and `paper_sources`
- OpenAlex keyword crawl
- arXiv keyword/category crawl through the official API
- Raw response files under `data/raw/`
- JSONL export under `data/exports/`
- Minimal pytest coverage

Not implemented in this first loop:

- Google Scholar scraping
- HTML scraping that violates source terms
- PDF full-text download
- LLM summaries
- recommendation ranking
- Telegram or email push
- Zotero, Obsidian, or Anki integration
- Crossref and Semantic Scholar enrichment
- PubMed, bioRxiv, OpenReview, CORE, IEEE
- GitHub Actions scheduling

## Configure

Edit `config/topics.yaml` to define lanes and keywords/categories.

Edit `config/sources.yaml` for source limits. V0 defaults are intentionally small:

- OpenAlex: 1 keyword per lane, 10 results per query
- arXiv: 1 keyword and 1 category per lane, 10 results per query

Optional environment variables:

- `CONTACT_EMAIL`: polite contact email for OpenAlex
- `OPENALEX_API_KEY`: OpenAlex API key, if available

## Run Locally

```bash
pip install -r requirements.txt
python -m src.main
```

Run tests:

```bash
pytest
```

## Outputs

- `data/raw/<source>/<YYYY-WW>/...`: raw API responses
- `data/papers.sqlite`: SQLite database
- `data/exports/candidates_<YYYY-WW>.jsonl`: normalized candidates
- `logs/crawl_<YYYY-WW>.log`: concise crawl log

## Next Milestones

1. Add `crawl_runs` tracking once the V0 crawl is stable.
2. Add Crossref DOI enrichment.
3. Add Semantic Scholar enrichment.
4. Add weak duplicate detection.
5. Add PubMed, bioRxiv/medRxiv, OpenReview, CORE, and IEEE drivers.
6. Add GitHub Actions after local runs are boring and reliable.
