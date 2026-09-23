# AI Notes — Engineering Roadmap

## Purpose

AI Notes is intentionally a small application used as a production-oriented
engineering laboratory.

The product domain must remain simple:

- authenticate a user;
- create and list notes;
- ask an AI questions about those notes.

The goal is not to build a large product. The goal is to understand and
implement the engineering required to take a modern AI application from
localhost to production.

---

## Target Architecture

Angular
  ↓
Microsoft Entra ID / MSAL
  ↓
FastAPI
  ↓
PostgreSQL + pgvector
  ↓
AI / RAG / Tools

Supporting infrastructure:

- Docker
- Azure Service Bus
- Azure Blob Storage where justified
- Azure Key Vault
- Azure Container Registry
- Azure Container Apps
- Application Insights / OpenTelemetry
- GitHub Actions
- MCP Server

---

# Phase 1 — Foundation

Status: In progress

Implemented:

- FastAPI backend
- Angular 22 frontend
- PostgreSQL + pgvector
- Alembic migrations
- Docker Compose
- basic Notes domain
- basic RAG infrastructure
- basic AI agent/tool infrastructure
- Microsoft Entra app registrations
- MSAL Angular authentication
- login/logout
- access token acquisition
- Angular → FastAPI HTTP call
- development CORS configuration

Next:

- implement GET /notes
- connect the authenticated frontend to the Notes API

Learning focus:

- frontend/backend boundaries
- environment configuration
- CORS
- production-oriented repository structure

---

# Phase 2 — Authentication & Authorization

Replace the development X-User-Id authentication mechanism with real
Microsoft Entra authentication.

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
- issuer validation
- audience validation
- token expiration validation
- delegated scope validation
- map Entra `oid` to internal User
- decide and implement user provisioning strategy
- retain explicit development/test authentication only where justified
- backend authorization through AppContext
- Angular HTTP token integration
- route protection for UX

Learning focus:

- OAuth 2.0
- OpenID Connect
- Authorization Code + PKCE
- access tokens vs ID tokens
- JWT
- JWKS
- scopes
- authentication vs authorization
- MSAL token lifecycle
- security boundaries

Principle:

> Microsoft authenticates. AI Notes authorizes.

---

# Phase 3 — Containers

Make the complete application reproducible using containers.

Implement:

- production backend Dockerfile
- frontend Dockerfile
- Angular production build
- local Docker Compose stack
- container networking
- runtime configuration
- health checks

Learning focus:

- image vs container
- Docker layers
- build context
- container networking
- environment variables
- immutable artifacts
- build once, deploy many

---

# Phase 4 — AI Integration

Connect the existing AI architecture to the real application flow.

Implement:

- Azure AI / Microsoft Foundry integration
- AI assistant
- structured outputs where appropriate
- application tools
- authenticated tool execution
- note-aware assistant

Learning focus:

- agents vs deterministic workflows
- tool calling
- trusted application context
- AI security boundaries
- structured outputs

---

# Phase 5 — Production RAG

Evolve note retrieval into a production-oriented RAG pipeline.

Implement:

- note chunking
- embeddings
- pgvector storage
- HNSW indexing
- user-filtered vector retrieval
- retrieval tuning
- optional hybrid retrieval
- context construction
- RAG evaluation

Learning focus:

- embeddings
- vector search
- pgvector
- HNSW
- retrieval quality
- Top-K
- filtering
- prompt injection from retrieved content
- RAG evaluation

---

# Phase 6 — Asynchronous Processing

Move expensive ingestion work outside the HTTP request lifecycle.

Target flow:

POST /notes
  → FastAPI
  → persist note
  → Azure Service Bus
  → Worker
  → chunk
  → embed
  → store vectors

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
- retries
- DLQ
- eventual consistency
- idempotency

---

# Phase 7 — Blob Storage

Introduce Azure Blob Storage only where it provides a useful learning case.

Potential extension:

- note attachments
- document uploads

Implement if justified:

- Blob Storage
- secure upload/download
- SAS where appropriate
- metadata stored in PostgreSQL
- asynchronous document processing

Learning focus:

- object storage
- database vs blob storage
- secure file access
- SAS
- upload security

---

# Phase 8 — Observability

Make application behaviour visible across services.

Implement:

- structured logging
- correlation/request IDs
- OpenTelemetry
- Azure Application Insights
- HTTP tracing
- database tracing
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

Deploy the complete application to Azure.

Target services:

- Azure Container Apps
- Azure Container Registry
- Azure Database for PostgreSQL
- Microsoft Entra ID
- Azure Service Bus
- Azure Blob Storage
- Azure Key Vault
- Application Insights

Implement:

- Managed Identity
- Key Vault integration
- production configuration
- networking
- secrets management
- database connectivity
- production Entra configuration

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

Expose AI Notes capabilities through Model Context Protocol.

Example MCP tools:

- list_notes
- create_note
- search_notes
- ask_notes

Target flow:

Claude / another MCP client
  → MCP
  → AI Notes
  → application services
  → PostgreSQL / AI

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
single milestone:

## Security

- authentication
- authorization
- least privilege
- JWT validation
- secrets management
- input validation
- secure uploads
- prompt injection
- dependency security
- avoid PII in logs

## Testing

- unit tests
- integration tests
- API tests
- authentication tests
- authorization tests
- tenant/user isolation tests where applicable

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

AI Notes must remain small.

The application should not grow into another large SaaS project.

New product features should only be introduced when they are required to
learn or demonstrate an engineering concept.

Target product surface:

- Login
- Notes
- AI Chat

The complexity should live in the engineering and infrastructure, not in
the business domain.

---

# Definition of Done

At the end of the project, an engineer should be able to explain and
demonstrate the complete path:

User
  → Angular
  → Entra/MSAL
  → FastAPI
  → authorization
  → PostgreSQL
  → Service Bus / Worker
  → pgvector / RAG
  → AI Agent / Tools
  → observability
  → Docker
  → CI/CD
  → Azure
  → MCP

The final repository should serve both as:

1. a working production-oriented AI application;
2. a reusable reference architecture / boilerplate for future AI applications.