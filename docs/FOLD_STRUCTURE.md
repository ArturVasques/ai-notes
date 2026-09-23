ai-workspace-production/
│
├── app/
│   ├── api/                 # HTTP boundary / FastAPI routers + error handlers (errors.py)
│   ├── agents/               # Agent definitions
│   ├── auth/                 # Authentication, authorization, permission constants (permissions.py)
│   ├── core/                 # Config, logging, middleware, event loop, shared infrastructure (middleware.py, event_loop.py)
│   ├── database/              # Pool, DB lifecycle, dev seed
│   ├── repositories/          # PostgreSQL access
│   ├── schemas/                # Pydantic API/AI contracts
│   ├── services/
│   │   ├── ai/                # Model/Agent execution
│   │   ├── rag/                # Retrieval + chunking
│   │   └── notes/              # Note ingestion orchestration
│   └── tools/                  # Agent tools
│
├── migrations/               # Alembic DB migrations (raw SQL revisions)
├── tests/
│   ├── conftest.py            # Intentionally empty of fixtures: unit tests must not need a database
│   ├── unit/                  # No database, no network
│   │   ├── test_chunking.py           # Chunker bounds, termination, large-overlap regression
│   │   ├── test_config.py             # APP_ENV required, embedding/dimension contract, CORS default
│   │   ├── test_auth_dependencies.py  # Header identity only in development (501 / 401)
│   │   ├── test_api_errors.py         # HTTP error contract, X-Request-ID, masked 500, CORS closed
│   │   ├── test_lifespan.py           # Fail-fast startup, pool closed on shutdown
│   │   ├── test_tools_security.py     # Tools never expose identity, always check a permission
│   │   └── test_event_loop.py         # Windows loop factory never yields ProactorEventLoop
│   └── integration/            # Real PostgreSQL/pgvector
│       ├── conftest.py         # Database pool fixture for the integration suite
│       └── test_note_ownership.py  # Owner-scoped retrieval and FK constraints
├── evals/                     # AI quality evaluation (real OpenAI calls)
├── docs/
│   ├── ARCHITECTURE.md         # Why the system is shaped this way
│   ├── CODESTYLE.md            # Code style and patterns
│   └── FOLD_STRUCTURE.md       # This file
│
├── .github/
│   └── workflows/
│       └── ci.yml              # quality → unit-tests → integration-tests → docker-smoke
│
├── Dockerfile                # Non-root, HEALTHCHECK, pinned deps layer, pip check
├── docker-compose.yml        # LOCAL DEVELOPMENT stack only
├── requirements.txt          # Pinned production dependency lock used by Dockerfile
├── recovery-guidelines.txt   # Sample note content used by the Quick start and evals
├── .dockerignore
├── .gitignore
├── .env.example              # Local development template; production injects config
├── pyproject.toml            # Unpinned dependencies, dev extras, ruff/mypy/pytest config
├── alembic.ini
├── main.py                   # FastAPI app, lifespan, router and middleware registration
├── CHANGELOG.md
├── HELPER.md                 # Command reference
└── README.md                 # Operational guide and "start a new project from this template"
