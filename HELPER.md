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

# Configuration: APP_ENV (required) and the PostgreSQL password
Copy-Item .env.example .env

# Database schema (PostgreSQL configured in .env; create the
# personal_finance database first)
alembic upgrade head

# Development user + default categories (refuses to run unless APP_ENV=development)
python -m app.database.seed

# API. The loop factory is mandatory on Windows (psycopg async mode cannot
# use ProactorEventLoop) and harmless elsewhere.
uvicorn main:app --loop app.core.event_loop:loop_factory
```


## Tests and Code Quality

```powershell
# From backend/

# Unit tests: no database, no network
pytest tests/unit -v

# Integration tests: real PostgreSQL from .env, migrations applied
pytest tests/integration -v

# Lint, formatting, types
ruff check .
ruff format --check .
mypy
```

```powershell
# From frontend/
npm test -- --watch=false
npm run build
```


## Docker Compose (local development stack)

```powershell
# From the repository root.
# Build, run migrations, start the API
docker compose up --build -d

# Development user and its default categories (idempotent)
docker compose run --rm --no-deps api python -m app.database.seed

# Create an account as the development user
$headers = @{ "X-User-Id" = "22222222-2222-2222-2222-222222222222" }
$account = @{ name = "Current Account"; type = "CHECKING" } | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/accounts -Headers $headers -ContentType "application/json" -Body $account

# Readiness (API + database)
curl.exe http://localhost:8000/health/ready

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
$frozen = docker run --rm -v "${PWD}:/src:ro" python:3.13-slim sh -c "mkdir /build && cp /src/pyproject.toml /build/ && cp -r /src/app /build/app && cd /build && pip install -q --no-cache-dir . 2>/dev/null && pip freeze --exclude personal-finance"
$header = (Get-Content requirements.txt | Where-Object { $_ -like '#*' })
($header + $frozen) | Set-Content -Encoding utf8 requirements.txt
```

Then `pip install -e ".[dev]"` and `docker compose up --build -d`. The
Dockerfile runs `pip check`, so a lock that drifted from `pyproject.toml`
fails the build.
