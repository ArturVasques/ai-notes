# Personal Finance — Domain Model

Status: approved design. F0 (baseline cleanup) and F1 (backend domain) done; reports start at F2.

This document is the reference for the financial domain: what each concept
means, how it is stored, and how every metric is calculated. Financial rules
live in the backend application services; the frontend and any future AI
layer only call those services.

---

## 1. Decisions

| # | Decision |
|---|---|
| D1 | One typed row per financial movement (`transactions.kind`). No double-entry ledger. |
| D2 | Money is an integer number of minor units (cents): `BIGINT` in PostgreSQL, `int` in Python, integer `number` in TypeScript. Never floating point. |
| D3 | A reimbursement is linked to its original expense for **effective spending**, and always keeps its own real date for **cash flow**. They are different metrics. |
| D4 | New clean baseline migration for the finance domain. Plain PostgreSQL; pgvector removed until a real RAG use case (documents/invoices) exists. |
| D5 | Current AI/RAG code is deleted (preserved in Git history). No `OPENAI_API_KEY` and no AI dependencies in this phase. |
| D6 | The frontend sends only the MSAL Bearer token. No `X-User-Id` bridge in Angular. Frontend/backend integration stays incomplete until Entra JWT validation is implemented in FastAPI (next milestone). |
| D7 | MSAL cache stays in `SessionStorage`. Re-evaluate once the PWA runs over HTTPS on a real iPhone. |
| D8 | Out of v1: shared receivables, credit cards, investment sales, investment quantities. The model must not block them later. |
| S1 | "How much did I save" is **Net Savings = Income − Effective Expenses**, not the change in savings accounts. Where that money went is a separate breakdown (**Savings Allocation**). |
| S2 | `TRANSFER` and `INVESTMENT` are never expenses. Current → Broker is a `TRANSFER`; Broker → S&P 500 is an `INVESTMENT`. |

---

## 2. Concepts

**Account**: a place where money exists (current account, savings account,
meal card, Coverflex, cash, broker cash). Names are user-defined. The type is
one of a small fixed set:

| Type | Meaning |
|---|---|
| `CHECKING` | Everyday current account |
| `SAVINGS` | Savings / interest-bearing account. Drives the "Savings accounts" allocation line. |
| `CASH` | Physical cash |
| `BENEFITS` | Meal card, Coverflex and similar employer benefit balances |
| `BROKERAGE` | Uninvested cash held at a broker |

**Category**: user-managed classification for `EXPENSE` or `INCOME`, with a
stable icon key. Archived categories stay attached to historical data.

**Investment asset**: the destination of an investment (e.g. "S&P 500", ETF;
"Nike", `NKE`, STOCK). The symbol is optional. Type is one of `ETF`, `STOCK`,
`FUND`, `BOND`, `CRYPTO`, `OTHER`. No prices, valuation or quantities in v1.

**Transaction**: one financial movement, typed by `kind`. The amount is always
positive; its direction comes from `from_account_id` / `to_account_id`.

| Kind | from_account | to_account | category | investment_asset | reimburses | Meaning |
|---|---|---|---|---|---|---|
| `EXPENSE` | required | — | required (EXPENSE) | — | — | Money spent |
| `INCOME` | — | required | required (INCOME) | — | — | Money earned |
| `TRANSFER` | required | required, ≠ from | — | — | — | Money moved between own accounts; wealth-neutral |
| `INVESTMENT` | required | — | — | required | — | Money put into an investment asset |
| `REIMBURSEMENT` | — | required | — (inherits the expense's) | — | required, an `EXPENSE` | Money paid back for an expense (shared bill, refund) |

There is no `SAVING` kind. Saving money into a savings account is a
`TRANSFER` whose destination is a `SAVINGS` account; Quick Add offers it as a
preset.

Invariants (enforced by the service; the shape rules are also database CHECKs):

- The sum of reimbursements linked to an expense never exceeds that expense.
  Checked with `SELECT … FOR UPDATE` on the expense inside the same SQL
  transaction.
- A category's kind must match the transaction kind.
- Archived accounts, categories and assets cannot be used in new transactions
  but remain on historical ones.
- A transfer is only allowed between accounts with the same currency.
- `kind` cannot change after creation (delete and recreate instead).
- An expense with reimbursements cannot be deleted.
- `user_id` always comes from the authenticated `AppContext`, never from the
  request body.

---

## 3. Metrics

All metrics are computed in backend services for a period `[from, to]` of
`occurred_on` dates. The AI layer will never compute them.

### Spending

- **Gross expenses** = Σ `EXPENSE` with `occurred_on` in the period.
- **Reimbursements attributed** = Σ `REIMBURSEMENT` linked to those expenses,
  whatever date the reimbursement arrived.
- **Effective expenses** = Gross expenses − Reimbursements attributed.
- **Spending by category** uses effective amounts (a reimbursement reduces
  its expense's category).

Consequence: a past month's effective expenses decrease when a reimbursement
for one of its expenses arrives later. This is intended.

### Income and savings

- **Income** = Σ `INCOME` in the period. Reimbursements are never income.
- **Net savings** = Income − Effective expenses.
- **Savings rate** = Net savings / Income (not defined when Income is 0).

### Savings allocation

Where the period's money went, by real dates:

- **Savings accounts** = net change of all `SAVINGS` account balances in the
  period (transfers in − transfers out, plus income such as interest paid into
  them, minus anything spent or invested from them).
- **Investments** = Σ `INVESTMENT` in the period.
- **Retained cash** = Net savings − Savings accounts − Investments.

Retained cash is the residual, so the three lines always add up to Net
savings. It can be negative (reserves were drawn down) and it also absorbs
timing differences, such as a reimbursement still to arrive or broker cash
not yet invested.

> **Conceptual note.** Retained cash is an analytical, residual metric that
> decomposes the savings generated in the period. It does not necessarily
> represent where all accumulated wealth is held in accounting terms.
> Movements funded by savings accumulated in earlier periods (for example,
> moving old savings into investments) can make this decomposition unsuitable
> for explaining changes in net worth. A net-worth view may be added later.

### Cash flow

By real dates only:

- **Net cash flow** = Income + Reimbursements received in the period − Gross
  expenses in the period.
- **Transfers** are reported separately and never affect income, expenses or
  cash flow.
- **Account balance** = opening balance + Σ inflows (`INCOME`,
  `REIMBURSEMENT`, incoming `TRANSFER`) − Σ outflows (`EXPENSE`,
  `INVESTMENT`, outgoing `TRANSFER`).

### Worked example (one month)

| Movement | Kind |
|---|---|
| Salary 3000.00 → Current | INCOME (Salary) |
| Expenses paid from Current, 2100.00 in total, including a 100.00 restaurant bill | EXPENSE |
| 100.00 → Current, half of a shared bill (50.00) plus a 50.00 refund, received the same month | REIMBURSEMENT → those expenses |
| Current → Savings 500.00 | TRANSFER |
| Current → Broker 300.00 | TRANSFER |
| Broker → S&P 500 300.00 | INVESTMENT |

| Metric | Value |
|---|---|
| Income | 3000.00 |
| Gross / effective expenses | 2100.00 / 2000.00 |
| **Net savings** | **1000.00** |
| Savings rate | 33.33 % |
| Allocation: savings accounts | 500.00 |
| Allocation: investments | 300.00 |
| Allocation: retained cash | 200.00 |
| Net cash flow | 1000.00 |
| Transfers | 800.00 |

If the 100.00 of reimbursements arrived the following month instead, this
month would still show effective expenses of 2000.00 and net savings of
1000.00, but net cash flow 900.00 and retained cash 200.00. Next month's cash
flow would include the +100.00; its expenses and income would not change.

---

## 4. Database

Single baseline migration. Plain PostgreSQL, raw SQL through psycopg (as
today). Every monetary column is `BIGINT` in minor units.

```sql
users (                                    -- unchanged
  id UUID PK, external_identity_id TEXT UNIQUE, name, email UNIQUE, created_at
)

accounts (
  id UUID PK, user_id UUID NOT NULL REFERENCES users ON DELETE CASCADE,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('CHECKING','SAVINGS','CASH','BENEFITS','BROKERAGE')),
  description TEXT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'EUR',
  opening_balance_minor BIGINT NOT NULL DEFAULT 0,
  archived_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, id)
)

categories (
  id UUID PK, user_id UUID NOT NULL REFERENCES users ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('EXPENSE','INCOME')),
  icon TEXT NOT NULL CHECK (icon ~ '^[a-z0-9-]{1,40}$'),
  archived_at, created_at,
  UNIQUE (user_id, id)
)
-- unique active name per user and kind:
CREATE UNIQUE INDEX ... ON categories (user_id, kind, lower(name)) WHERE archived_at IS NULL

investment_assets (
  id UUID PK, user_id UUID NOT NULL REFERENCES users ON DELETE CASCADE,
  name TEXT NOT NULL, symbol TEXT NULL,
  type TEXT NOT NULL CHECK (type IN ('ETF','STOCK','FUND','BOND','CRYPTO','OTHER')),
  archived_at, created_at,
  UNIQUE (user_id, id)
)

transactions (
  id UUID PK, user_id UUID NOT NULL REFERENCES users ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('INCOME','EXPENSE','TRANSFER','INVESTMENT','REIMBURSEMENT')),
  amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
  occurred_on DATE NOT NULL,
  description TEXT NULL,
  from_account_id UUID NULL, to_account_id UUID NULL,
  category_id UUID NULL, investment_asset_id UUID NULL,
  reimburses_transaction_id UUID NULL,
  created_at, updated_at,
  UNIQUE (user_id, id),
  FOREIGN KEY (user_id, from_account_id)           REFERENCES accounts (user_id, id),
  FOREIGN KEY (user_id, to_account_id)             REFERENCES accounts (user_id, id),
  FOREIGN KEY (user_id, category_id)               REFERENCES categories (user_id, id),
  FOREIGN KEY (user_id, investment_asset_id)       REFERENCES investment_assets (user_id, id),
  FOREIGN KEY (user_id, reimburses_transaction_id) REFERENCES transactions (user_id, id),
  CHECK (shape per kind, as in the table in section 2)
)
-- indexes: (user_id, occurred_on DESC, created_at DESC), (user_id, category_id),
--          (reimburses_transaction_id)
```

- The composite `(user_id, …)` foreign keys make it impossible, at database
  level, to reference another user's account, category, asset or expense.
- Referencing foreign keys use the default `NO ACTION` (restrict): accounts,
  categories and assets are archived, never deleted while referenced.
- `occurred_on` is a `DATE` (the day the user chose), avoiding time-zone
  bugs. Ordering within a day uses `created_at`.
- Currency lives on the account; transaction currency is the account's.
  Multi-currency is prepared for but not implemented (v1 is EUR).
- Default categories are **not** inserted by the migration. The service
  `provision_default_categories(user_id)` creates them; today the development
  seed calls it, later user provisioning (JWT milestone) will.

Default categories (user-editable):

- Expense: Groceries, Restaurants, Housing, Transport, Car, Health, Shopping,
  Entertainment, Travel, Subscriptions.
- Income: Salary, Meal Allowance, Benefits, Interest, Dividends, Other Income.

### Room for D8 without implementing it

- Credit cards: a new account type whose balance may go negative; paying the
  card is a `TRANSFER`.
- Investment sales: a new kind (e.g. `DIVESTMENT`) from an asset into an
  account.
- Quantities: a nullable `units NUMERIC` on investment transactions.
- Shared receivables: a nullable "expected reimbursement" on an expense.

---

## 5. Backend

Layers stay as today: `api → services → repositories → PostgreSQL`, with
`AppContext` as the trusted identity.

```
app/
├── api/            accounts.py, categories.py, investment_assets.py,
│                   transactions.py, reports.py, health.py, errors.py
├── auth/           context.py, dependencies.py, permissions.py (finance:read, finance:write)
├── core/           config.py, logging.py, middleware.py, event_loop.py
├── database/       connection.py, seed.py
├── repositories/   one per table + user_repository.py
├── schemas/        Pydantic contracts per resource
└── services/finance/
    accounts_service.py, categories_service.py, investment_assets_service.py,
    transactions_service.py, reports_service.py
```

### HTTP API

| Endpoint | Purpose |
|---|---|
| `GET/POST /accounts`, `PATCH /accounts/{id}` | Manage accounts; archive through `PATCH` |
| `GET /accounts/balances` | Current balance per account (F2) |
| `GET/POST /categories?kind=`, `PATCH /categories/{id}` | Manage categories and icons |
| `GET/POST /investment-assets`, `PATCH /investment-assets/{id}` | Manage investment assets |
| `GET /transactions?from&to&kind&category_id&account_id&investment_asset_id&limit&cursor` | History with filters, keyset pagination |
| `POST /transactions` | Create; body is a discriminated union on `kind` |
| `GET/PATCH/DELETE /transactions/{id}` | Read, edit, delete |
| `GET /reports/overview?from&to` | Income, expenses, net savings, rate, allocation, cash flow, transfers |
| `GET /reports/spending-by-category` | Effective expenses per category |
| `GET /reports/savings`, `GET /reports/investments` | Allocation detail; invested by asset/account |
| `GET /reports/monthly-trend` | Month-by-month income, expenses and net savings |

`POST /transactions` accepts `ExpenseCreate | IncomeCreate | TransferCreate |
InvestmentCreate | ReimbursementCreate`, discriminated by `kind`. The same
schema will later be the structured output of "AI proposes a transaction";
the user confirms before it is created.

### AI-ready services (no AI now)

Each future tool maps to one public service function taking `AppContext`:

| Future tool | Service function |
|---|---|
| `create_transaction` | `transactions_service.create_transaction` |
| `list_transactions` | `transactions_service.list_transactions` |
| `get_spending_by_category` | `reports_service.get_spending_by_category` |
| `get_income_summary` | `reports_service.get_income_summary` |
| `get_savings_summary` | `reports_service.get_savings_summary` |
| `get_investment_summary` | `reports_service.get_investment_summary` |
| `get_financial_overview` | `reports_service.get_financial_overview` |

The HTTP API calls them now; agent tools and MCP will call the same functions
later, so financial rules are never duplicated.

### Implementation notes (F1)

Decisions taken while implementing F1, beyond or refining the design above:

- **Permissions** are checked inside the services (`finance:read` for reads,
  `finance:write` for writes), so future tools get the same checks as HTTP.
- **Error mapping**: a business rule violation or a body reference to a
  missing/foreign row → 400 `VALIDATION_ERROR`; a path id that is missing or
  belongs to another user → 404 `NOT_FOUND` (indistinguishable); duplicate
  active name or deleting an expense with reimbursements → 409 `CONFLICT`;
  missing permission → 403 `FORBIDDEN`; malformed body → 422.
- **Unique active names** apply to accounts and investment assets too (per
  user, case-insensitive, archived rows excluded), not only to categories.
- **Immutable after creation**: account currency, category kind, transaction
  kind. Account type and asset type can be edited.
- **Amounts** are strict JSON integers (floats, numeric strings and booleans
  are rejected), with an upper bound of 999 999 999 999 minor units.
  Opening balances may be negative.
- **Extra reimbursement date rules**: a reimbursement cannot be dated before
  its expense, and an expense cannot be moved after its earliest
  reimbursement. An expense cannot shrink below what was already reimbursed.
  A reimbursement may arrive in any account of the same currency.
- **Concurrency**: every operation that changes how much of an expense is
  reimbursed locks the expense row (`SELECT … FOR UPDATE`), so concurrent
  reimbursements cannot exceed it.
- **Transaction responses** include `reimbursed_amount_minor` (sum of linked
  reimbursements; 0 for other kinds).
- **History filters**: `account_id` matches either side of a movement;
  `category_id` also matches reimbursements of expenses in that category.
  Pagination is keyset-based with an opaque cursor, 50 rows by default and
  200 at most.
- **Deleting** a transaction is a hard delete; accounts, categories and
  assets have no delete endpoint (archive only).
- **Default categories** are created by
  `categories_service.provision_default_categories`, called today by the
  development seed. There is no endpoint for it.
- **Known limitation until user provisioning**: a development `X-User-Id`
  that has no row in `users` fails on the first write (foreign key) with a
  masked 500. Run the seed first; the JWT milestone will provision users.

---

## 6. Frontend

Mobile-first Angular PWA, designed for iPhone Safari → Add to Home Screen.

Navigation: a bottom bar with Home · Transactions · **+** · Insights ·
Settings, respecting the iPhone safe area.

| Page | Content |
|---|---|
| Home | Month switcher; cards for Income, Expenses, Net savings (with rate), Invested; allocation bar (savings accounts / investments / retained); effective spending by category as CSS bars; last 5 transactions |
| Transactions | Day-grouped list (Today / Yesterday / date); filter sheet for period, type, category and account; tap to edit |
| **+** Quick Add | Global bottom sheet. Type selector (default Expense; Income, Transfer, Save, Invest, Reimbursement). Amount first with `inputmode="decimal"`; category icon grid (recent first); account chips (last used preselected); optional description; date defaults to today. Save button within thumb reach. Fields adapt to the type. |
| Insights | Monthly trend, net savings and rate over time, allocation history, invested by asset, cash flow vs net savings |
| Settings | Accounts, categories (name, icon, archive), investment assets, sign out |

Structure (folders only when they contain code):

```
src/app/
├── core/       auth/ (unchanged MSAL), api/ (environment base URL, Bearer interceptor), layout/ (shell, bottom nav)
├── shared/     money formatting/parsing, category icon component
└── features/   dashboard/, transactions/ (incl. quick add), accounts/, categories/,
                investments/, insights/, settings/
```

- **Money input**: `"24,80"` → `2480` by string parsing, never
  `parseFloat × 100`. Display with `Intl.NumberFormat('pt-PT', { style:
  'currency', currency })`.
- **Icons**: Lucide (open source, tree-shakeable per icon, consistent stroke
  style). Only a curated allowlist of about 40 icons is bundled. The database
  stores only the key (`utensils`, `car`, `house`, `shopping-cart`, `plane`,
  …); the frontend resolves it through the allowlist with a fallback icon.
  The backend validates the key format; it never stores SVG or HTML.
  Material Symbols was rejected: it is an icon font (large download, no
  tree-shaking).
- **UI**: no component library. Custom SCSS design tokens, native `<dialog>`
  as bottom sheet (focus trap and Escape handling built in), Signal Forms,
  lazy-loaded feature routes, charts as plain CSS bars.
- **PWA**: `manifest.webmanifest` (name, `display: standalone`, theme and
  background colours, 192/512/maskable placeholder icons),
  `apple-touch-icon`, `apple-mobile-web-app-*` meta tags,
  `viewport-fit=cover`. No service worker in v1: it adds stale-cache risk
  around the MSAL redirect and is not required for Add to Home Screen.
- **Auth**: MSAL unchanged (redirect, `SessionStorage`). The interceptor
  attaches only the Bearer access token. Until FastAPI validates it, API
  calls from the browser are expected to fail with 401.

---

## 7. What is removed and what is kept

| Removed | Kept |
|---|---|
| `api/notes.py`, `api/chat.py` | `api/health.py`, `api/errors.py` (without `AssistantContractError`) |
| `agents/`, `tools/`, `services/ai/`, `services/rag/`, `services/notes/`, `core/openai.py` | `auth/*` with finance permissions |
| `schemas/{note,rag,chat,assistant}.py`, `repositories/note_repository.py` | `core/*`; config loses `AISettings`, embedding contract and `RAG_*` |
| `evals/`, `tests/unit/test_chunking.py`, `tests/unit/test_tools_security.py`, `tests/integration/test_note_ownership.py` | `database/*` without pgvector registration; `user_repository`; `schemas/user.py` |
| Dependencies `openai`, `openai-agents`, `pgvector`; `OPENAI_*` and `RAG_*` in compose, CI and `.env.example` | Remaining unit tests, updated |
| `alembic/versions/aa7cc31ac6dd_create_initial_schema.py` (replaced by a finance baseline) | Alembic setup |
| `pgvector/pgvector:pg18` image in compose and CI (replaced by `postgres:18`) | Docker Compose stack, Dockerfile, CI jobs |
| `frontend/src/app/features/notes/` | `frontend/src/app/core/auth/*` |

The tool-security testing pattern (tools never expose `user_id`; every tool
checks a permission) returns with the Agent + Tools milestone.

Local databases must be recreated after F0 (`docker compose down -v`, or
drop the local database), because the baseline migration is replaced.

---

## 8. Implementation phases

Each phase ends with `ruff`, `mypy`, backend unit and integration tests, and
frontend Vitest green.

| Phase | Scope |
|---|---|
| F0 Cleanup | Remove notes/AI/RAG code, dependencies and configuration; plain PostgreSQL; update compose, CI, README, HELPER, CHANGELOG |
| F1 Backend domain | Finance baseline migration; repositories, services and API for accounts, categories, investment assets and transactions; invariants; integration tests for per-user isolation, CHECK shapes, transfer atomicity and reimbursement caps |
| F2 Reports | Overview, spending by category, savings allocation, investments, balances, monthly trend; tests that reproduce the worked example to the cent, including the late-reimbursement case |
| F3 Frontend foundation | Environments, Bearer interceptor, shell and bottom nav, lazy routes, design tokens, Lucide allowlist, PWA manifest and meta tags, sign-in screen |
| F4 Quick Add + Transactions | Bottom sheet, day-grouped list, filters, edit and delete |
| F5 Dashboard + Insights | |
| F6 Settings | Account, category (icon picker) and investment asset management with archiving |
| F7 Docs | README, ADR for money representation and the transaction model, roadmap status |

---

## 9. Open items

- Technical identifiers were renamed in F0 (`personal-finance` package and
  Compose project, "Personal Finance API", database `personal_finance`). The
  repository and local folder are still `ai-notes`.
- The baseline migration `0001` contains the complete finance schema (F1
  extended it instead of adding a second migration, as there is no
  production database). Future schema changes use new migrations.
- Testing on an iPhone needs an HTTPS origin registered as an Entra redirect
  URI (dev tunnel or Azure deployment); the MSAL redirect in iOS standalone
  mode must be verified on a real device.
