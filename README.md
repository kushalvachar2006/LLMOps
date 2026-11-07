# LLMOps Platform

Build, manage, deploy and monitor LLM applications. Stack: Streamlit, FastAPI, MongoDB (PyMongo), Google Gemini (`google-genai`), Docker, GitHub Actions, Pytest.

**Status: Phase 1 (Foundation) complete.** Phases 2-5 (prompt versioning, datasets, experiments, evaluation, monitoring, deployments) are planned; those sidebar pages are labelled "Planned" and show no fake data.

## What works now
Project CRUD with pagination, Gemini generation through the backend only, Prompt Playground (system instruction, model, temperature, top-p, max tokens), request IDs, latency, token usage, persisted telemetry, health checks, and an Overview page computed from stored records.

## Quick start
See [docs/setup.md](docs/setup.md). Architecture and schema: [docs/architecture.md](docs/architecture.md).

## Security notes
The API key lives only in backend environment variables and is never returned by the API or shown in the UI. `.env` is git-ignored and excluded from Docker images. CORS is limited to `CORS_ORIGINS`. Prompt text is not stored by default.

## Known limitations (Phase 1)
No authentication or per-project access control yet (Phase 4). No retries or fallback (Phase 5). Overview statistics cover the latest 100 requests; full aggregation arrives with Monitoring (Phase 3). Live Gemini, live MongoDB and Docker have not been exercised.
