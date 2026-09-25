# Command Reference

Commands are shown for PowerShell on Windows; on macOS/Linux replace
`.\.venv\Scripts\Activate.ps1` with `source .venv/bin/activate` and
`Copy-Item` with `cp`.

Backend commands run from `backend/`, frontend commands from `frontend/`,
Docker Compose commands from the repository root.


## Local Development

```powershell
cd backend

# Virtual environment and dependencies (application + dev tools)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Configuration: APP_ENV (required), the PostgreSQL password and the Entra
# identifiers (tenant id, API client id). See the comments in the template.
Copy-Item .env.example .env

# Database schema (PostgreSQL configured in .env; create the
# personal_finance database first)
alembic upgrade head

# API. The loop factory is mandatory on Windows (psycopg async mode cannot
# use ProactorEventLoop) and harmless elsewhere.
uvicorn main:app --loop app.core.event_loop:loop_factory
```

```powershell
cd frontend
npm install
npm start          # http://localhost:4200, expects the API on :8000
```

Sign in with Microsoft; the user and its default categories are created on
the first authenticated request. There is no seed script.


## Tests and Code Quality

```powershell
# From backend/

# Unit tests: no database, no network (tokens are signed with a local key)
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
npx prettier --check "src/**/*.{ts,html,scss}"
```


## Docker Compose (local development stack)

```powershell
# From the repository root. Needs ENTRA_TENANT_ID and ENTRA_API_CLIENT_ID in
# the shell or in a root .env (public identifiers, see backend/.env.example).
# Build, run migrations, start the API
docker compose up --build -d

# Readiness (API + database)
curl.exe http://localhost:8000/health/ready

# An authenticated call needs a real Entra access token; without one the API
# answers 401 with WWW-Authenticate: Bearer
curl.exe -i http://localhost:8000/me

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
