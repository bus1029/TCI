# TCI Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-23

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
- 006-gitlab-onprem-connection: Added Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, cryptography
- 001-git-repo-connection: Added Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.x, redis-py, structlog, Jinja2, HTMX


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
