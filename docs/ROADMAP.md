# Personal Finance — Engineering Roadmap

## Purpose

Personal Finance is a small, mobile-first personal finance application used
as a production-oriented engineering laboratory.

The product answers, to the cent: how much came in and from where, how much
was spent and on what, how much was saved and where it went, how much was
invested and in what, transfers between own accounts, reimbursements, and
the month-by-month evolution.

The goal is not to build a large product. The goal is to understand and
implement the engineering required to take a modern, AI-ready application
from localhost to production, on a domain that is useful every day.

The financial domain is described in [`DOMAIN_MODEL.md`](DOMAIN_MODEL.md).

---

## Target Architecture

Angular PWA (iPhone, Add to Home Screen)
  ↓
Microsoft Entra ID / MSAL
  ↓
Bearer access token
  ↓
FastAPI
  ↓
Application services (financial rules)
  ↓
PostgreSQL

Later, on top of the same application services:

- AI Agent + Tools (deterministic financial tools)
- MCP Server

Supporting infrastructure:

- Docker
- Azure Service Bus / Workers
- Azure Blob Storage where justified (receipts, invoices)
- pgvector / RAG only for a real document use case
- Azure Key Vault
- Managed Identity
- Azure Container Registry
- Azure Container Apps
- Application Insights / OpenTelemetry
- GitHub Actions

Principle:

> AI is never the source of truth for financial calculations. Every number
> comes from deterministic application services.

---

# Phase 1 — Personal Finance v1

Status: In progress (design approved, implementation starting)

Already in place from the previous iteration:

- FastAPI backend (`API → Service → Repository`, raw SQL through psycopg)
- Angular 22 frontend
- PostgreSQL and Alembic migrations
- Docker Compose and CI
- structured logging, request IDs, uniform error handling
- trusted `AppContext` authentication boundary (development header only)
- Microsoft Entra app registrations
- MSAL Angular authentication (login/logout, access token acquisition)

Implement (phases F0–F7 in `DOMAIN_MODEL.md`):

- remove the AI Notes domain, AI/RAG code and pgvector
- clean finance baseline migration on plain PostgreSQL
- accounts, categories (with icons), investment assets
- typed transactions: income, expense, transfer, investment, reimbursement
- reports: net savings, savings rate, savings allocation, effective
  spending, cash flow, investments, balances, monthly trend
- mobile-first UI: dashboard, transaction history, Quick Add, insights,
  settings
- PWA manifest and iPhone home-screen configuration

Learning focus:

- modelling a financial domain correctly
- money representation (integer minor units)
- database integrity: CHECK constraints, composite foreign keys, transactions
- per-user data isolation
- mobile-first UI and PWA fundamentals

---

# Phase 2 — Authentication & Authorization

Next milestone. Replace the development `X-User-Id` mechanism with real
Microsoft Entra authentication. Until then the Angular app sends the Bearer
token and the backend does not accept it yet; this is expected.

Flow:

Angular
  → MSAL
  → Microsoft Entra ID
  → Access Token
  → FastAPI
  → JWT validation
  → internal User
  → AppContext

Implement:

- Bearer token authentication
- Entra JWKS signature validation
- issuer, audience and expiration validation
- delegated scope validation
- map Entra `oid` to internal User
- user provisioning strategy (including default categories)
- retain explicit development/test authentication only where justified
- backend authorization through AppContext
- route protection for UX
- revisit MSAL cache location (`SessionStorage` vs `LocalStorage`) once the
  PWA runs over HTTPS on a real iPhone

Learning focus:

- OAuth 2.0 and OpenID Connect
- Authorization Code + PKCE
- access tokens vs ID tokens
- JWT and JWKS
- scopes
- authentication vs authorization
- MSAL token lifecycle
- security boundaries

Principle:

> Microsoft authenticates. The application authorizes.

---

# Phase 3 — Containers

Make the complete application reproducible using containers.

Implement:

- production backend Dockerfile
- frontend Dockerfile (Angular production build served as static files)
- local Docker Compose stack for the whole solution
- container networking
- runtime configuration
- health checks

Learning focus:

- image vs container
- Docker layers and build context
- container networking
- environment variables
- immutable artifacts
- build once, deploy many

---

# Phase 4 — AI Agent + Tools

Add an assistant on top of the existing application services. The agent
never calculates financial figures itself; it calls deterministic tools.

Examples:

- "Gastei 24,80€ num jantar no Sushi Yama com o cartão de refeição"
  → the agent proposes a structured transaction (the same schema as
  `POST /transactions`) → the user confirms → the transaction service
  creates it.
- "Quanto gastei em restaurantes nos últimos 3 meses?"
  → the agent calls `get_spending_by_category`.

Tools (each one maps to an existing service function):

- create_transaction (propose, then confirm)
- list_transactions
- get_spending_by_category
- get_income_summary
- get_savings_summary
- get_investment_summary
- get_financial_overview

Implement:

- Azure AI / Microsoft Foundry integration
- structured outputs
- authenticated tool execution through AppContext
- tool security tests: no tool exposes identity parameters; every tool
  checks a permission
- assisted categorization
- deterministic insights explained in natural language
- AI evals for probabilistic behaviour

Learning focus:

- agents vs deterministic workflows
- tool calling
- trusted application context
- human confirmation for write operations
- AI security boundaries
- structured outputs
- evals

---

# Phase 5 — Asynchronous Processing

Move work that does not belong in the HTTP request lifecycle to workers,
when a real use case appears. Candidates: receipt/invoice processing,
assisted categorization, periodic report snapshots.

Target flow:

API
  → persist
  → Azure Service Bus
  → Worker
  → process
  → persist result

Implement:

- Azure Service Bus
- worker process
- message contracts
- retries
- idempotency
- dead-letter queue
- processing state

Learning focus:

- queues
- asynchronous architecture
- backpressure
- retries and DLQ
- eventual consistency
- idempotency

---

# Phase 6 — Blob Storage

Introduce Azure Blob Storage for files that belong outside the database.

Likely use case:

- receipt and invoice uploads attached to transactions

Implement:

- Blob Storage
- secure upload/download
- SAS where appropriate
- metadata stored in PostgreSQL
- asynchronous document processing (Phase 5)

Learning focus:

- object storage
- database vs blob storage
- secure file access
- SAS
- upload security

---

# Phase 7 — RAG (when a real use case exists)

Structured financial data is answered by SQL and deterministic tools, not by
vector search. RAG returns only for unstructured content, most likely
receipts and invoices from Phase 6.

Implement if justified:

- document text extraction
- chunking
- embeddings
- pgvector storage and HNSW indexing
- user-filtered vector retrieval
- context construction
- RAG evaluation

Learning focus:

- when RAG is (and is not) the right tool
- embeddings and vector search
- pgvector and HNSW
- retrieval quality, Top-K, filtering
- prompt injection from retrieved content
- RAG evaluation

---

# Phase 8 — Observability

Make application behaviour visible across services.

Implement:

- structured logging
- correlation/request IDs
- OpenTelemetry
- Azure Application Insights
- HTTP and database tracing
- AI operation tracing
- worker tracing
- useful metrics
- error visibility

Learning focus:

- logs vs metrics vs traces
- distributed tracing
- correlation IDs
- diagnosing production failures
- AI observability

---

# Phase 9 — CI/CD

Create a professional delivery pipeline.

GitHub
  → GitHub Actions
  → tests / quality gates
  → Docker build
  → Azure Container Registry
  → Azure Container Apps

Implement:

- backend CI
- frontend CI
- automated tests
- Docker image build
- ACR push
- deployment
- immutable image tags
- environment promotion
- rollback strategy
- database migration strategy
- GitHub → Azure OIDC authentication

Learning focus:

- CI vs CD
- artifacts
- build once, deploy many
- image registries
- deployment strategies
- rollback
- migrations during deployment
- secretless CI authentication

---

# Phase 10 — Azure Production Infrastructure

Deploy the complete application to Azure. This is also the first HTTPS
environment for testing the installed PWA on an iPhone.

Target services:

- Azure Container Apps
- Azure Container Registry
- Azure Database for PostgreSQL
- Microsoft Entra ID
- Azure Service Bus (if Phase 5 is implemented)
- Azure Blob Storage (if Phase 6 is implemented)
- Azure Key Vault
- Application Insights

Implement:

- Managed Identity
- Key Vault integration
- production configuration
- networking
- secrets management
- database connectivity
- production Entra configuration (HTTPS redirect URIs)

Learning focus:

- Azure identity
- Managed Identity
- secrets
- cloud networking
- production configuration
- least privilege

Principle:

> Applications should authenticate to Azure services using identities rather
> than long-lived credentials whenever possible.

---

# Phase 11 — MCP Server

Expose financial capabilities through Model Context Protocol.

Example MCP tools:

- list_transactions
- create_transaction
- get_spending_by_category
- get_financial_overview

Target flow:

Claude / another MCP client
  → MCP
  → Personal Finance
  → application services
  → PostgreSQL

Learning focus:

- MCP architecture
- MCP server
- tools and resources
- MCP vs REST API
- MCP tools vs internal agent tools
- authentication and authorization for MCP clients

This milestone should make the distinction between these three concepts clear:

1. REST API — interface for software clients.
2. Agent tools — capabilities exposed internally to an AI agent.
3. MCP — standardized interface for external AI clients to discover and use capabilities.

---

# Cross-Cutting Engineering

These concerns apply throughout the roadmap rather than belonging to a
single milestone.

## Security

- authentication
- authorization
- per-user data isolation (every financial query scoped to the caller)
- owner never taken from the request body
- least privilege
- JWT validation
- secrets management
- input validation
- secure uploads
- prompt injection
- dependency security
- avoid PII and financial data in logs

## Financial correctness

- money as integer minor units end to end
- one row per movement; transfers are atomic by construction
- metrics computed only in backend services
- tests that reproduce known scenarios to the cent

## Testing

- unit tests
- integration tests
- API tests
- authentication and authorization tests
- user isolation tests

## AI Evals

Use evals for probabilistic AI behaviour rather than treating them as
ordinary deterministic tests.

## Database

- migrations
- indexes
- transactions
- constraints
- connection pooling
- production migration strategy

---

# Scope Guardrail

The application must remain small.

It should not grow into a large SaaS product. New product features are only
introduced when they are useful day to day or are needed to learn an
engineering concept.

Not in scope for v1: bank integrations, Splitwise, broker APIs, live prices,
automatic import, OCR, AI, complex budgeting, notifications, multi-currency,
shared household accounts, subscription detection, financial advice.

Target product surface:

- Login
- Home (dashboard)
- Transactions and Quick Add
- Insights
- Settings (accounts, categories, investment assets)
- AI assistant (later)

The complexity should live in the engineering and infrastructure, not in
the business domain.

---

# Definition of Done

At the end of the project, an engineer should be able to explain and
demonstrate the complete path:

User (iPhone PWA)
  → Angular
  → Entra/MSAL
  → FastAPI
  → authorization
  → application services
  → PostgreSQL
  → Service Bus / Worker
  → AI Agent / Tools
  → observability
  → Docker
  → CI/CD
  → Azure
  → MCP

The final repository should serve both as:

1. a working, production-oriented personal finance application;
2. a reusable reference architecture / boilerplate for future AI-ready
   applications.
