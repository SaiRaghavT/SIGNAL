# SIGNAL MVP project context

This note is a working map of the repository for future development sessions. Keep it updated when architecture or setup changes.

## Project shape

- `backend/app/`: FastAPI application, SQLAlchemy persistence, workflow and API services.
- `backend/app/main.py`: FastAPI app entry point; assembles routers for ingestion, canonical data, detection, cases, reporting workflow, submissions, follow-ups, analytics, governance, and agent status. Health check: `GET /health`.
- `backend/app/agents/`: workflow-oriented services and routers for reportability, case assembly, deadlines, attestations, rendering, submissions, acknowledgements, retries, follow-ups, audit, and evidence extraction.
- `backend/app/ingestion/`: FHIR, HL7 v2, and document ingestion.
- `backend/app/canonical/`: normalized patient context, persistence, and query APIs.
- `backend/app/detection/`: structured and document triggers, candidate fusion, and candidate workflow.
- `backend/app/models/`, `backend/alembic/`: database entities and migrations. `backend/app/database.py` creates the PostgreSQL SQLAlchemy engine.
- `database/`: schema and SQL/Python demo seed material.
- `docker/docker-compose.yml`: local PostgreSQL and backend Compose configuration.
- `frontend/src/`: React/Vite app. `App.jsx` defines navigation and screens; `api/` contains HTTP wrappers; `services/` contains workflow helpers; `state/` and `hooks/` hold demo workflow state.
- `candidate-review/`: a separate candidate review implementation/prototype; the primary running API is under `backend/app`.
- `data/`, `documents/`: demo/source materials and data assets.

## Main data flow

FHIR, HL7, or document input is validated and normalized into canonical patient and clinical records. Detection combines structured and document signals, then candidate fusion produces potential candidates. The reportability workflow uses canonical context, jurisdiction resolution, local decision support/rules, and field population to assemble a persisted case. Human review and attestation gate reporting preparation; form rendering and mock ECR submission continue the case workflow. Submission tracking, acknowledgements, retries, follow-ups, deadlines, and audit records are persisted and surfaced in the frontend.

The mock submission transport and acknowledgement/follow-up actions are simulated; this is a demo/MVP, not a live public-health delivery integration. LLM features are optional/configured through settings; deterministic/rule-based paths are available.

## Configuration and startup

Run commands from the `signal-mvp` directory (the one containing `pyproject.toml`).

1. Start PostgreSQL. For the repository Compose stack, run `docker compose -f docker/docker-compose.yml up -d postgres` from this directory.
2. Ensure `.env` has usable `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`. Settings are read in `backend/app/config/settings.py`; `.env` is ignored by Git. Never print or commit its secrets.
3. Backend, using the repository's local virtual environment:

   ```powershell
   .\venv\Scripts\Activate.ps1
   uvicorn backend.app.main:app --reload
   ```

   API docs are at `http://127.0.0.1:8000/docs`; health is `http://127.0.0.1:8000/health`.
4. Frontend, in another terminal:

   ```powershell
   cd frontend
   npm run dev
   ```

   Vite serves the app on `http://localhost:5173` and proxies `/api` and `/health` to port 8000.

Database migrations are in `backend/alembic/versions/`; `alembic.ini` is at project root. Review database setup before running migrations or seed scripts.

## Notes for future changes

- Backend imports use `backend.app.*`; launch Uvicorn from the `signal-mvp` root as `backend.app.main:app`.
- The Compose backend configuration should be checked before relying on it: the Python settings are `DB_*`, while its service currently sets `DATABASE_URL`; the Dockerfile also copies `app` as a top-level package although source imports use `backend.app.*`.
- `README.md` is effectively empty and `frontend/README.md` is the untouched Vite template; this file is the current repository-specific orientation note.
- `.env` was intentionally not read or included in this map.
