# Personal Finance

Personal Finance is a small, mobile-first personal finance application and a
production-oriented engineering laboratory. It is designed to be used daily
on an iPhone (Safari → Add to Home Screen) and works on desktop too.

- **Backend:** FastAPI (`API → Service → Repository`), raw SQL through psycopg.
- **Data:** PostgreSQL 18. Migrations with Alembic. Money is stored as
  integer minor units (cents) end to end.
- **Frontend:** Angular 22 (standalone, signals, `httpResource`), no UI
  library, Lucide icons. Swipeable tab pager, glass navigation and sheets,
  day/night themes, PWA manifest.
- **Authentication:** Microsoft Entra ID. Angular signs in with MSAL and
  sends a Bearer access token; the API validates it and provisions the user
  on first login.
- **Domain:** accounts, categories, investment assets and five transaction
  kinds (income, expense, transfer, investment, reimbursement). Savings are
  transfers into savings accounts. See [`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md).
- **Roadmap:** [`docs/ROADMAP.md`](docs/ROADMAP.md).

Current state: **Personal Finance v1** — the complete local application.
There is no AI in this phase.

Commands for every step below are in [`HELPER.md`](HELPER.md).


## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (`app/`), Alembic (`alembic/`), tests, `Dockerfile`, `pyproject.toml` |
| `frontend/` | Angular app (`src/app/core`: auth, layout, stores; `src/app/features`: pages and services; `src/app/shared`: money, dates, icons, sheet) |
| `docs/` | Domain model and engineering roadmap |
| `docker-compose.yml` | Local development stack (PostgreSQL + API) |
| `.github/workflows/` | CI |

Backend commands (`pytest`, `ruff`, `mypy`, `alembic`, `uvicorn`) run from
`backend/`; frontend commands (`npm start`, `npm test`, `npm run build`)
from `frontend/`.


## API

All endpoints except `/health/*` require `Authorization: Bearer <Entra
access token>`. Swagger UI is at `http://localhost:8000/docs`.

| Endpoint | Purpose |
|---|---|
| `GET /me` | The caller's profile (provisioned from the token). |
| `GET/POST /accounts`, `GET/PATCH /accounts/{id}` | Accounts; archive/restore with `PATCH {"archived": true/false}`. |
| `GET /accounts/balances?as_of&include_archived` | Balance per account: opening balance + movements. |
| `GET/POST /categories`, `GET/PATCH /categories/{id}` | Income and expense categories with icon keys. |
| `GET/POST /investment-assets`, `GET/PATCH /investment-assets/{id}` | Investment destinations. |
| `GET/POST /transactions`, `GET/PATCH/DELETE /transactions/{id}` | The five kinds; filters and keyset pagination. |
| `GET /reports/overview?from&to` | Income, gross/effective expenses, net savings, savings rate, allocation, cash flow. |
| `GET /reports/categories?kind&from&to` | Effective amount per category. |
| `GET /reports/savings?from&to` | Net savings, allocation and savings accounts detail. |
| `GET /reports/investments?from&to` | Invested by asset and by source account (all time without a period). |
| `GET /reports/monthly-trend?months&until` | Month-by-month flow metrics. |
| `GET /health/live`, `GET /health/ready` | Process and database health. |

Metric definitions and error codes are in
[`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md).


## Authentication

```
Angular → MSAL → Microsoft Entra ID → access token (v2)
  → Authorization: Bearer → FastAPI → JWT validation (RS256 via JWKS,
  iss, aud, exp/nbf, tid, ver, scp) → oid → internal user → AppContext
```

- `backend/app/auth/jwt_validator.py` validates the token; nothing trusts a
  claim before the signature is verified, and tokens are never logged.
- `backend/app/services/users_service.py` maps the Entra `oid`
  (`users.external_identity_id`) to an internal user, creating it with the
  default categories on the first login. Email is informational only.
- `backend/app/auth/dependencies.py` turns the result into a trusted
  `AppContext`; every service reads identity only from it.
- Invalid or missing tokens answer `401` with a generic message; an
  unreachable identity provider answers `503`.
- The frontend attaches the token in one place,
  `frontend/src/app/core/auth/auth.interceptor.ts`, for API requests only.

Required configuration (public identifiers, not secrets): `ENTRA_TENANT_ID`,
`ENTRA_API_CLIENT_ID` and `ENTRA_REQUIRED_SCOPE` for the API (see
`backend/.env.example`); client id, authority and scope for the frontend in
`frontend/src/environments/`.


## Environments

| APP_ENV | Where | Configuration |
|---|---|---|
| `development` | Laptop (`uvicorn` + `backend/.env`, or `docker compose`) | `backend/.env` / root `.env` for Compose |
| `test` | CI | Workflow variables; tests replace the authentication dependency |
| `production` | Container platform, same image | Injected by the platform |

`APP_ENV` is required. `.env` files are never committed; `backend/.env.example`
documents every variable.


## Tests

- Backend: `pytest tests/unit` (no database, no network; the JWT validator
  is tested with a locally generated RSA key), `pytest tests/integration`
  (real PostgreSQL; reports reproduce the domain model's worked example to
  the cent), `ruff check .`, `ruff format --check .`, `mypy`.
- Frontend: `npm test -- --watch=false` (Vitest) and `npm run build`.

CI (`.github/workflows/ci.yml`) runs the backend quality gates, unit tests,
integration tests against a PostgreSQL service and a Docker Compose smoke
test.


## Docker

`docker compose up --build -d` starts PostgreSQL 18, runs the migrations and
starts the API. The compose file is a local development stack only; the
image runs as a non-root user with a healthcheck.


## Not included yet

Azure deployment (also the first HTTPS origin for testing the installed PWA
on an iPhone), asynchronous processing, observability beyond structured
logs, AI agent + tools, and MCP. See the roadmap.
