# Architecture and operational notes

See [README.md](README.md) for setup, environment variables, API routes, and the architecture diagrams.

## Runtime components

- **n8n** reads Google Sheets and maps form columns to the API's normalized lead payload.
- **FastAPI** validates/authenticates requests, deduplicates by normalized email, stores leads and jobs, and exposes health, metrics, review, and admin operations.
- **Database** uses SQLite for local development and PostgreSQL in Docker Compose. Alembic owns the deployment schema history.
- **Worker** claims persistent jobs and runs the research, email drafting, quality, and delivery agents. Local development can run one worker thread inside the API process; Compose runs a dedicated worker container.
- **Research agent** enriches the submitted lead and retrieves relevant products from the local catalog, with Groq and optional semantic retrieval support.
- **Email agent** creates two grounded variants; **quality agent** rejects unresolved placeholders, weak/missing copy, and ungrounded catalog claims.
- **Mailing agent** sends the approved variant over SMTP as multipart plain text and HTML, then stores delivery state and provider identifiers.
- **Next.js dashboard** calls the API through a same-origin server route. API/admin tokens stay on the server.
- **MCP server** remains an optional tool interface; n8n is the current lead intake path.

## State and duplicate-send protection

Email addresses are normalized for deduplication. A unique database index and transactional job creation protect against repeated sheet trigger delivery. Pipeline jobs store status, stage, progress, attempts, configuration, and errors. Workers claim jobs atomically; PostgreSQL uses `SKIP LOCKED` when available.

Before SMTP, the worker checks the suppression table and existing delivery state. An email attempt enters `SENDING` before network delivery. If the process dies during an ambiguous SMTP operation, the record is not automatically retried as if no send happened; this avoids duplicate outreach at the cost of requiring operator review for uncertain delivery. SMTP is not an exactly-once transport.

Human review is enabled by default. The dashboard shows both variants with a selection control, and stores reviewer feedback with each new draft revision. Revision requests run through durable jobs and pass quality checks before returning to review. The dashboard preview is sandboxed, and the worker rechecks suppression at approval delivery time. Dry-run delivery is audited separately and is not counted as a successful send.

## API security and deployment

`APP_ENV=production` requires `API_AUTH_TOKEN`, hides interactive API documentation, and enables the production guard. The dashboard's catch-all API route injects the bearer token server-side. Admin operations additionally require `ADMIN_API_TOKEN`. n8n must send the bearer token in its HTTP Request node when the API is protected.

The Compose stack runs PostgreSQL, an Alembic migration job, FastAPI, one worker, and the Next.js dashboard. It is intended as a reproducible single-host baseline. Configure TLS at an ingress/reverse proxy and manage backups, credentials, monitoring, retention, and recovery for a real deployment.

## Follow-up milestone boundary

Reply detection and cron-based follow-ups are not implemented. Manual suppression and pre-send suppression checks are present, but they do not infer that a lead replied. A safe follow-up service should consume mailbox/webhook events, classify replies/bounces/unsubscribes, persist a normalized conversation state, and recheck that state immediately before scheduling and sending every follow-up.
