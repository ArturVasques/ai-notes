# Command Reference

Commands are shown for PowerShell on Windows; on macOS/Linux replace
`.\.venv\Scripts\Activate.ps1` with `source .venv/bin/activate` and
`Copy-Item` with `cp`.

Backend commands run from `backend/`; Docker Compose commands run from the
repository root.


## Local Development

```powershell
cd backend

# Virtual environment and dependencies (application + dev tools)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Configuration: APP_ENV (required) and a real OPENAI_API_KEY
Copy-Item .env.example .env

# Database schema (PostgreSQL + pgvector configured in .env)
alembic upgrade head

# Development user (refuses to run unless APP_ENV=development)
python -m app.database.seed

# API. The loop factory is mandatory on Windows (psycopg async mode cannot
# use ProactorEventLoop) and harmless elsewhere.
uvicorn main:app --loop app.core.event_loop:loop_factory
```


## Tests and Code Quality

```powershell
# From backend/

# Unit tests: no database, no OpenAI calls
pytest tests/unit -v

# Integration tests: real PostgreSQL + pgvector from .env, migrations applied
pytest tests/integration -v

# Lint, formatting, types
ruff check .
ruff format --check .
mypy

# AI evaluations: real OpenAI calls, spends credit. Needs the sample note below.
python -m evals.run_evals
```


## Docker Compose (local development stack)

```powershell
# From the repository root.
# Build, run migrations, start the API (needs OPENAI_API_KEY in the shell or
# in a root .env read by Compose)
docker compose up --build -d

# Development user, once per database volume
docker compose run --rm --no-deps api python -m app.database.seed

# Create the sample note
$headers = @{ "X-User-Id" = "22222222-2222-2222-2222-222222222222" }
$note = @{ title = "Project kickoff"; content = "The AI Notes project kickoff meeting is on Monday at 10:00." } | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/notes -Headers $headers -ContentType "application/json" -Body $note

# Ask the assistant
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -H "X-User-Id: 22222222-2222-2222-2222-222222222222" `
  -d '{\"message\": \"When is the project kickoff meeting?\"}'

# Logs, stop/start (keeps data), destroy (including the database volume)
docker compose logs -f api
docker compose stop
docker compose start
docker compose down -v
```


## Dependencies

Direct dependencies are declared unpinned in `pyproject.toml`.
`requirements.txt` is the pinned lock the Dockerfile installs; never edit it
by hand. After changing `pyproject.toml`, regenerate it inside the same image
the Dockerfile uses (from `backend/`):

```powershell
$frozen = docker run --rm -v "${PWD}:/src:ro" python:3.13-slim sh -c "mkdir /build && cp /src/pyproject.toml /build/ && cp -r /src/app /build/app && cd /build && pip install -q --no-cache-dir . 2>/dev/null && pip freeze --exclude ai-notes"
$header = (Get-Content requirements.txt | Where-Object { $_ -like '#*' })
($header + $frozen) | Set-Content -Encoding utf8 requirements.txt
```

Then `pip install -e ".[dev]"` and `docker compose up --build -d`. The
Dockerfile runs `pip check`, so a lock that drifted from `pyproject.toml`
fails the build.
