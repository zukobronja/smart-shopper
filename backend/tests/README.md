# SmartShopper Backend Tests

This directory contains the pytest-based automated tests and supporting assets for the SmartShopper backend. The suite currently exercises the Tavily integration stack, LangGraph scaffolding, extraction pipeline, and multi-phase verification checks defined in the project roadmap.

## Directory Layout

```
backend/tests/
├── README.md                    # You are here
├── __init__.py                  # Enables `backend.tests` package imports
├── insomnia_collection.json     # REST client collection for manual API checks
├── test_batch_simple.py         # Batch extraction smoke tests
├── test_credibility_scorer.py   # Credibility scoring unit tests
├── test_extractors.py           # Hybrid extractor + schema validation tests
├── test_fixes_verification.py   # Regression checks for targeted bug fixes
├── test_graph_foundation.py     # LangGraph state/config sanity tests
├── test_integration.py          # High-level extraction integration tests
├── test_optimized_tavily.py     # OptimizedTavilyClient behaviour tests
├── test_phase2_verification.py  # Phase 2 authentication/API regression suite
├── test_phase3_verification.py  # Phase 3 extraction system regression suite
├── test_phase4_verification.py  # Phase 4 LangGraph groundwork validation
├── test_phase5_batch_processing.py # Batch processing + performance guardrails
└── test_tavily_retriever_agent.py  # LangGraph Tavily agent contract tests
```

## Test Script Summaries

- `test_batch_simple.py`: Exercises basic batch-extraction flows to ensure fixtures and schemas stay aligned during refactors.
- `test_credibility_scorer.py`: Verifies the four-component credibility scoring model (domain reputation, recency, extractability, consensus) including penalty paths.
- `test_extractors.py`: Covers Tavily/LLM hybrid extraction, schema coverage thresholds, and fallback behaviour for `ecom_v1`/`review_v1` contracts.
- `test_fixes_verification.py`: Regression harness for specific defects documented in `BUG_TRACKER.md`; prevents reintroducing previously fixed issues.
- `test_graph_foundation.py`: Confirms the LangGraph state machine, configuration profiles, and placeholder nodes compile and execute with the mocked state.
- `test_integration.py`: Runs cross-cutting integration checks against the extraction pipeline ensuring orchestration between clients, scorers, and validators.
- `test_optimized_tavily.py`: Validates query optimisation, two-step search->extract flow, fallback handling, and cost guards in `OptimizedTavilyClient`.
- `test_phase2_verification.py`: Protects Phase 2 deliverables (auth core, API scaffolding) from regressions.
- `test_phase3_verification.py`: Ensures the end-to-end extraction system and golden URL coverage targets remain intact.
- `test_phase4_verification.py`: Validates Phase 4 groundwork, including LangGraph agent wiring, state transitions, and cost/time limits.
- `test_phase5_batch_processing.py`: Early guardrails for upcoming Phase 5 work—tests batch embedding/extraction flows and performance thresholds.
- `test_tavily_retriever_agent.py`: Checks the LangGraph Tavily Retriever agent’s state interactions, error handling, and metric reporting.

## Running the Suite

From the repository root:

```bash
# Run entire backend test suite
cd backend
PYTHONPATH=. pytest tests -v

# Run a specific test module
PYTHONPATH=. pytest tests/test_optimized_tavily.py -v

# Run the slow integration tests only
PYTHONPATH=. pytest tests/test_integration.py -m integration
```

Add `--maxfail=1` or `-k <pattern>` as needed during development. Coverage can be collected via `pytest --cov=app --cov-report=html`.

## Environment & Dependencies

- Ensure `uv pip install -e ".[dev]"` has been executed from the repo root.
- Populate `.env` (or export variables) with valid `TAVILY_API_KEY` and `OPENAI_API_KEY` to enable live API calls; tests auto-skip when keys are absent.
- The suite uses `pytest-asyncio`; keep async fixtures awaited properly. See `pyproject.toml` for plugin versions.

## Writing New Tests

1. Name the file `test_<feature>.py` and place it here so pytest discovers it.
2. Prefer fixture reuse; define shared fixtures in `conftest.py` (to be added) instead of duplicating setup logic.
3. Mock expensive external calls for unit tests; rely on live endpoints only within explicitly marked integration tests.
4. Document non-obvious behaviours inside the test file with concise comments and link to related docs/tasks when relevant.

## Helpful Commands

```bash
# List slowest tests to spot performance issues
PYTHONPATH=. pytest tests --durations=10

# Drop into pdb when a test fails
PYTHONPATH=. pytest tests -x --pdb

# Rerun failures without rerunning the whole suite
PYTHONPATH=. pytest tests --lf
```

Keep this README updated as new test modules arrive or behaviours change so the suite remains transparent for future contributors.
