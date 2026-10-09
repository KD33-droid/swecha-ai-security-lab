# Swecha AI Security Lab

Reusable browser-based AI/agent cybersecurity lab.

## V1 stack
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy + Alembic
- Data: PostgreSQL
- Cache/live coordination: Redis
- Runtime: Docker Compose

## Development order
1. Platform bootstrap
2. C1 end-to-end vertical slice
3. C2-C4 using the same challenge contracts
4. TA/scoring/load-test hardening

## Core rule
The LLM is an untrusted decision-maker. The application is the authority.

## C1 backend foundation

The first vertical slice now includes the reusable domain schema, Alembic migration, workshop/team/session join flow, challenge-run provisioning, and development bootstrap endpoint.

After the stack is running:

```bash
docker compose exec backend alembic upgrade head
curl -X POST http://localhost:8000/api/v1/dev/bootstrap
```

The development bootstrap returns a workshop code and team code. Join with:

```bash
curl -X POST http://localhost:8000/api/v1/workshops/join \
  -H 'Content-Type: application/json' \
  -d '{"workshop_code":"DEV-LAB","team_code":"ALPHA","display_name":"KD"}'
```

Use the returned `session_token` to start C1:

```bash
curl -X POST http://localhost:8000/api/v1/workshops/challenges/start \
  -H 'Content-Type: application/json' \
  -d '{"session_token":"<SESSION_TOKEN>","challenge_slug":"ignore-the-rules"}'
```

## C1 RETEST API

After reaching SECURE with a correct root cause and at least one protective control:

1. `POST /api/v1/c1/retest/start`
2. `POST /api/v1/c1/retest/attack` with an equivalent prompt-injection attempt.
3. `POST /api/v1/c1/retest/functionality` with a password-reset support request.

The backend evaluates the retest. A blocked equivalent attack awards 25 points; preserved password-reset functionality awards 10 points. Passing both completes C1 at 90 points. A failed retest returns the run to SECURE.


## C1 status and discovery

The authoritative C1 runtime status is available at:

```bash
curl "http://localhost:8000/api/v1/c1/status?session_token=<SESSION_TOKEN>&run_id=<RUN_ID>"
```

The response exposes the current server-side score, phase/state, discovery progress, configured controls, and retest state. This works across BREAK, SECURE, RETEST, and COMPLETED; `/api/v1/c1/secure` remains the SECURE-phase control view.

Discovery is awarded automatically from actual `knowledge_read` tool activity. Two distinct normal customer-facing documents (`KB-001` through `KB-003`) are required. Re-reading the same document does not add points, and internal `KB-004` is excluded.

C1 awards the 10 discovery points when the learner explores at least two distinct normal, customer-facing knowledge documents during BREAK. Internal-only KB-004 is never counted as discovery evidence. Discovery is evaluated from server-side tool events rather than a self-reported checkbox.

A challenge run can be reset without deleting its audit history:

```bash
curl -X POST http://localhost:8000/api/v1/workshops/challenges/<RUN_ID>/reset \
  -H 'Content-Type: application/json' \
  -d '{"session_token":"<SESSION_TOKEN>"}'
```

A reset generates a fresh synthetic secret, clears runtime state and score, increments `reset_count`, and records `CHALLENGE_RESET`.

With discovery completed, the full C1 score is 100: discovery 10 + exploitation 20 + root cause 15 + mitigation 20 + retest 25 + functionality 10. Without discovery, the completed run is 90.

## C2-C4 challenge vertical slices

All four challenges use the same server-authoritative lifecycle:

`BREAK -> SECURE -> RETEST -> COMPLETED`

A failed retest returns the run to `SECURE`. Reset returns any run to `BREAK` and preserves the audit history.

### C2 — The Helpful Document
- Vulnerability: indirect prompt injection / RAG poisoning.
- Break: a normal password-reset query retrieves a poisoned synthetic document whose embedded instruction is incorrectly treated as authority.
- Objective: demonstrate retrieval of the poisoned document and protected synthetic secret disclosure.
- Controls: retrieval isolation, content trust boundary, instruction/data separation, output validation.
- Retest: repeat the equivalent poisoned-document path; normal password-reset functionality must remain available.

API:
- `POST /api/v1/c2/message`
- `PATCH /api/v1/c2/secure`
- `POST /api/v1/c2/retest/start`
- `POST /api/v1/c2/retest/attack`
- `POST /api/v1/c2/retest/functionality`
- `GET /api/v1/c2/status`

### C3 — Too Much Power
- Vulnerability: excessive tool authorization.
- Break: a synthetic order/refund request can reach the high-impact `issue_refund` tool without an authorization boundary.
- Objective: demonstrate unauthorized high-impact tool execution.
- Controls: least privilege, tool authorization, approval gate, parameter validation.
- Retest: equivalent refund request must be blocked while order lookup remains functional.

API:
- `POST /api/v1/c3/message`
- `PATCH /api/v1/c3/secure`
- `POST /api/v1/c3/retest/start`
- `POST /api/v1/c3/retest/attack`
- `POST /api/v1/c3/retest/functionality`
- `GET /api/v1/c3/status`

### C4 — Whose Data?
- Vulnerability: broken object-level authorization / sensitive data disclosure.
- Break: the agent retrieves another synthetic customer's record using a user-controlled customer ID.
- Objective: demonstrate cross-customer data disclosure.
- Controls: object-level authorization, tenant isolation, data minimization, output filtering.
- Retest: equivalent cross-customer lookup must be blocked while the participant's own customer record remains available.

API:
- `POST /api/v1/c4/message`
- `PATCH /api/v1/c4/secure`
- `POST /api/v1/c4/retest/start`
- `POST /api/v1/c4/retest/attack`
- `POST /api/v1/c4/retest/functionality`
- `GET /api/v1/c4/status`

## Local containerized validation

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
curl -X POST http://localhost:8000/api/v1/dev/bootstrap
curl http://localhost:8000/api/v1/challenges
```

The development bootstrap registers C1-C4 and enables all four for the `DEV-LAB` workshop. PostgreSQL is exposed on host port `5433` to avoid collisions with an existing local PostgreSQL service.

Each challenge uses bounded synthetic state only. There is no shell execution, arbitrary code execution, external network access, browser automation, real credential handling, or real customer data.
