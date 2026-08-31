# OpenRobo Agent Instructions

## Project

OpenRobo is a free, open-source, vendor-neutral robotics ecosystem platform.

Core workflow:

DISCOVER → UNDERSTAND → BUILD → SIMULATE → DEPLOY → CONTRIBUTE

## Source of Truth

Before making architectural or production changes, read:

1. MASTER_AGENT_INSTRUCTIONS.md
2. docs/00_MASTER_SPECIFICATION.md
3. all relevant files under docs/
4. schemas/
5. existing implementation
6. implementation ledger
7. architecture decision records

Do not invent requirements that contradict these documents.

## Engineering Standard

Build production-quality software.

Do not create:
- fake functionality
- fake data presented as real
- placeholder implementations presented as complete
- hard-coded demos instead of real functionality
- undocumented architectural shortcuts

Every meaningful feature must include appropriate tests.

## Architecture

Respect the approved architecture:

- Next.js
- React
- TypeScript
- FastAPI
- Python
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- JSON Schema
- Vitest
- React Testing Library
- Playwright
- Pytest

Do not replace these technologies without documenting and justifying the decision.

## Robotics

OpenRobo must support all robotics domains through an extensible taxonomy.

Do not hard-code the platform around one robotics ecosystem.

Support relationships between:
- software
- hardware
- robots
- simulation
- datasets
- AI
- documentation
- projects
- other resources

## Knowledge Graph

The OpenRobo Knowledge Graph is foundational.

Use PostgreSQL initially.

Do not introduce Neo4j or another graph database unless measured requirements justify it.

## Open Source

OpenRobo's own code is intended to use Apache-2.0.

Upstream projects retain their own licenses.

Never remove upstream attribution or licensing information.

Never make blanket legal compatibility claims.

## Local First

OpenRobo must remain usable locally wherever practical.

Do not introduce mandatory paid cloud services.

Do not introduce mandatory AI APIs.

## Security

Treat all external repositories, URLs, submitted metadata, and code as untrusted.

Never execute arbitrary external repository code inside the main application.

Never commit secrets.

## Verification

Never claim a feature is complete without actually testing it.

When appropriate, run:

- lint
- type checking
- unit tests
- integration tests
- schema validation
- browser tests
- builds
- database migrations

Record failures honestly.

## Git

Make focused commits.

Use conventional commit messages where practical.

Never force-push or rewrite shared history without explicit approval.

Do not commit generated secrets, local credentials, or unnecessary build artifacts.

## Human Approval

Ask for approval before:
- destructive operations
- permanent architectural changes
- introducing mandatory paid services
- changing the project license
- exposing production credentials
- irreversible data migrations
- major public releases

For routine reversible engineering decisions, proceed autonomously and document the decision.

## Current Rule

Always check the implementation ledger before starting a milestone.

Never skip milestones.

Never claim completion without evidence.
