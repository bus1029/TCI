# TCI Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-06

## Active Technologies
- TypeScript 5.6 on Node.js 22 LTS + Fastify 5, Zod 3.24, Prisma 6, BullMQ 5, ioredis, pino, React 19, Next.js 15 App Router (004-git-repo-connection)
- PostgreSQL 16 for connection metadata/audit/preview summaries, Redis 7 for job queue, local disk mirror cache under `.runtime/git-mirrors` (004-git-repo-connection)
- PostgreSQL 16 for workspace-scoped connection metadata, encrypted OAuth grant material, sync runs, ticket snapshots, and comment snapshots; Redis 7 for scheduled batch jobs, retry backoff, and sync coordination (005-ticket-system-integration)
- PostgreSQL 16 for connection metadata, scope settings, sync runs, and ticket snapshots; Redis 7 for sync job orchestration (001-ticket-system-integration)
- PostgreSQL 16 for connection/event/snapshot metadata, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `.runtime/git-mirrors`, local snapshot archive under `.runtime/code-snapshots` (006-git-repo-connection)
- PostgreSQL 16 for connection/event/snapshot metadata and trace references, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `.runtime/git-mirrors`, local snapshot archive under `.runtime/code-snapshots` (001-git-repo-connection)
- Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, HTMX (001-git-repo-connection)
- Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography (006-gitlab-onprem-connection)
- PostgreSQL 16 for connection/event/snapshot metadata, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `pilot-git-repo-connection/.runtime/git-mirrors`, local snapshot archive under `pilot-git-repo-connection/.runtime/code-snapshots` (006-gitlab-onprem-connection)
- PostgreSQL 16 for connection/event/snapshot metadata and legacy planning references, Redis 7 for webhook and snapshot jobs, local disk mirror cache under `pilot-git-repo-connection/.runtime/git-mirrors`, local snapshot archive under `pilot-git-repo-connection/.runtime/code-snapshots` (003-repository-first-connections)
- Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography, Python standard `zipfile`/`pathlib` for archive inspection and extraction (004-zip-upload-workspace-delete)
- PostgreSQL 16 for workspace deletion metadata, local upload metadata, repository connection metadata, events, sync runs, and snapshot metadata; Redis 7 for async snapshot jobs; local disk mirror cache under `pilot-git-repo-connection/.runtime/git-mirrors`; local snapshot archive under `pilot-git-repo-connection/.runtime/code-snapshots` (004-zip-upload-workspace-delete)

- Markdown, Spec Kit 0.5.1, repository shell workflow + Spec Kit templates, Git branch workflow, GitHub repository/webhook contract artifacts (001-repo-source-traceability)

## Project Structure

```text
src/
tests/
```

## Commands

# Add commands for Markdown, Spec Kit 0.5.1, repository shell workflow

## Code Style

Markdown, Spec Kit 0.5.1, repository shell workflow: Follow standard conventions

## Recent Changes
- 004-zip-upload-workspace-delete: Added Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography, Python standard `zipfile`/`pathlib` for archive inspection and extraction
- 003-repository-first-connections: Added Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography
- 003-repository-first-connections: Added Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read
`specs/004-zip-upload-workspace-delete/plan.md`
<!-- SPECKIT END -->
