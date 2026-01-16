# iag-runner

Local-first mono-repo with a FastAPI backend, React frontend, Alembic-managed DB, and local Ollama hooks.

## Quick start (local only)
1. Copy env defaults: `cp .env.example .env`
2. Optional DB: `docker compose up -d db`
3. Backend:
   - `cd backend`
   - `python -m venv .venv`
   - `./.venv/Scripts/Activate.ps1` (Windows) or `source .venv/bin/activate` (macOS/Linux)
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload --port 8000`
4. Frontend:
   - `cd frontend`
   - `npm install`
   - `npm run dev`
5. Open `http://localhost:5173` and verify the API at `http://localhost:8000/api/hello`.

## Docker Compose
- Full stack (prod-like): `docker compose up --build`
- DB only: `docker compose up -d db`
- Stop: `docker compose down -v`
Note: Docker Compose uses `DATABASE_URL_DOCKER` for the API container (defaults to `db` hostname).
After first start, run migrations inside the API container:
`docker compose exec api alembic -c /app/db/alembic.ini upgrade head`

## Ollama (host option)
- Run Ollama locally with `ollama serve`.
- Local backend: `OLLAMA_URL=http://localhost:11434`
- Backend in Docker Desktop: `OLLAMA_URL=http://host.docker.internal:11434`
- Linux Docker host: `OLLAMA_URL=http://host.docker.internal:11434` may require `--add-host=host.docker.internal:host-gateway`.

## Tests
- `pip install -r backend/requirements.txt -r tests/requirements.txt`
- `PYTHONPATH=backend pytest tests/backend`

## Make targets
- `make dev` (starts db/api/web via Docker Compose)
- `make test` (runs backend + frontend tests)
