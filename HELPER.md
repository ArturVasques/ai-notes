# Command Reference

Every command used to develop, test, lock, build and run this project. The
README explains the flow; this file is the cheat-sheet. Commands are shown for
PowerShell on Windows; on macOS/Linux replace `.\.venv\Scripts\Activate.ps1`
with `source .venv/bin/activate` and `Copy-Item` with `cp`.


## Local Development

```powershell
# Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Dependencies (application + dev tools)
pip install -e ".[dev]"

# Configuration: APP_ENV (required, no default) and a real OPENAI_API_KEY
Copy-Item .env.example .env

# Database schema (needs the PostgreSQL configured in .env; the compose
# stack's db service publishes nothing, so run it via `docker compose up db`
# plus a published port, or point .env at any local PostgreSQL + pgvector)
alembic upgrade head

# Development user (refuses to run unless APP_ENV=development)
python -m app.database.seed

# API with auto-reload
uvicorn main:app --reload

# API without --reload. Mandatory on Windows: uvicorn's default loop there is
# ProactorEventLoop, which psycopg cannot use in async mode. The flag is
# harmless on Linux/macOS and is what the Dockerfile uses.
uvicorn main:app --loop app.core.event_loop:loop_factory

# Swagger UI
http://localhost:8000/docs
```


## Tests

```powershell
# Unit tests: deterministic, no database, no OpenAI calls (~3 s)
pytest tests/unit -v

# Integration tests: real PostgreSQL + pgvector from .env, migrations applied
pytest tests/integration -v

# Coverage report over the whole suite
pytest --cov=app --cov-report=term-missing

# AI evaluations: real OpenAI calls, spends credit, run on demand
python -m evals.run_evals
```

To prove the unit suite really has no database dependency, point it at a
closed port: `$env:POSTGRES_PORT = "1"; pytest tests/unit -q`.


## Code Quality

```powershell
ruff check .            # lint
ruff format --check .   # formatting (CI fails on drift)
ruff format .           # apply formatting
mypy                    # type check (scope configured in pyproject.toml)
```


## Docker (local development stack)

`docker-compose.yml` is a local development stack and nothing else: it
hardcodes `APP_ENV=development`, throwaway `postgres/postgres` credentials
and a plain HTTP port. Production runs the same image with
`APP_ENV=production` and all configuration injected by the platform. See the
README section "Environments".

```powershell
# First start (or after changing dependencies / Dockerfile). Needs
# OPENAI_API_KEY in .env or the shell; compose refuses to start without it.
docker compose up --build -d

# Follow the API logs (structured JSON)
docker compose logs -f api

# Development user, once per database volume
docker compose run --rm --no-deps api python -m app.database.seed

# Create the sample note (JSON title + content)
$headers = @{ "X-User-Id" = "22222222-2222-2222-2222-222222222222" }
$note = @{ title = "Recovery guidelines"; content = (Get-Content -Raw recovery-guidelines.txt) } | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/notes -Headers $headers -ContentType "application/json" -Body $note

# Ask the assistant
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -H "X-User-Id: 22222222-2222-2222-2222-222222222222" `
  -d '{\"message\": \"What should an athlete with a RecoveryScore of 32 do?\"}'

# Rebuild the image after a code change, keeping the database volume
docker compose up --build -d

# Stop / start without losing data
docker compose stop
docker compose start

# Destroy everything, including the database volume
docker compose down -v

# Run the stack side by side with another copy (different project + port)
$env:API_PORT = "8090"; docker compose -p aiws-smoke up --build -d
```

Migrations run automatically: the `migrate` service executes
`alembic upgrade head` before `api` starts and `api` waits for it to finish.
Health: `GET /health/live` (process up), `GET /health/ready` (database
reachable). The image runs as the non-root `appuser` and declares a
`HEALTHCHECK` against `/health/live`.


## Dependencies

Runtime dependencies are declared **unpinned** in `pyproject.toml`
(`[project].dependencies`). `requirements.txt` is the **pinned lock** the
Dockerfile installs. They must not drift, so:

1. Edit `pyproject.toml` (add, remove or constrain a dependency).
2. Regenerate the lock inside the same image the Dockerfile uses, so the
   result is independent of your operating system and local venv:

   ```powershell
   $frozen = docker run --rm -v "${PWD}:/src:ro" python:3.13-slim sh -c "mkdir /build && cp /src/pyproject.toml /build/ && cp -r /src/app /build/app && cd /build && pip install -q --no-cache-dir . 2>/dev/null && pip freeze --exclude ai-workspace-production"
   $header = (Get-Content requirements.txt | Where-Object { $_ -like '#*' })
   ($header + $frozen) | Set-Content -Encoding utf8 requirements.txt
   ```

   On bash: `docker run --rm -v "$PWD:/src:ro" python:3.13-slim sh -c "..."`
   with the same inner command, then prepend the existing comment header.
3. Reinstall your venv: `pip install -e ".[dev]"`.
4. Rebuild: `docker compose up --build -d`. The Dockerfile runs `pip check`
   after installing the application, so a lock that no longer satisfies
   `pyproject.toml` fails the build (and therefore the CI `docker-smoke` job).

Development-only tools (`pytest`, `ruff`, `mypy`, `httpx` for `TestClient`)
live in the `dev` extra and are intentionally absent from the lock and the
image. Upgrading everything to the latest compatible versions is the same
procedure with an unchanged `pyproject.toml`.


## Release

```powershell
# All local gates, in the order CI runs them
ruff check . ; ruff format --check . ; mypy
$env:POSTGRES_PORT = "1"; pytest tests/unit -q; Remove-Item Env:POSTGRES_PORT
pytest tests/integration -q
$env:API_PORT = "8090"; docker compose -p aiws-smoke up --build -d
curl.exe -i http://localhost:8090/health/ready
docker compose -p aiws-smoke down -v
```

Version lives in `pyproject.toml` (`version`) and `main.py` (`FastAPI(version=...)`).
Record changes in `CHANGELOG.md`, then tag: `git tag -a v1.0.0 -m "v1.0.0" ; git push origin v1.0.0`.
