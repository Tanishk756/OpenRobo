# ADR-0002: Database, Search, and Knowledge Graph Persistence Architecture

- **Status**: Accepted
- **Date**: 2026-08-31
- **Authors**: OpenRobo Architecture Team

## Context

OpenRobo requires persistent storage for relational metadata across thousands of robotics software packages, hardware specifications, licenses, dependencies, compatibility matrixes, stack manifests, and knowledge graph relations.

Key requirements:
1. Zero-cost infrastructure baseline.
2. Fast multi-faceted filtering (by domain, capability, license, architecture, ROS version).
3. Full-text search and fuzzy trigram matching over project titles, tags, and descriptions.
4. Relational representation of the OpenRobo Knowledge Graph.
5. Strict separation between database access, database migrations, and domain validation.
6. Support for offline/local execution in CLI mode.

## Decision

1. **Database Engine**: PostgreSQL 16+ serving as the unified relational and document store.
   - Initial core capabilities utilized: Relational storage, JSON/JSONB document fields, Full-Text Search (`tsvector` / `tsquery`), and Trigram fuzzy matching (`pg_trgm`).
   - **`pgvector` Excluded from M0**: `pgvector` will NOT be a mandatory dependency for initial milestones (M0–M7). It will be introduced later during Milestone 8 (AI / RAG) when vector embeddings are required.
2. **Database Access & Architecture Separation**:
   - **ORM / Persistence**: SQLAlchemy 2.x using Declarative Mapping and Async Engine support.
   - **Database Migrations**: Alembic for version-controlled, reproducible DDL migrations.
   - **Validation & Serialization**: Pydantic v2 for API request validation, response serialization, and domain boundary checking.
   - *Strict Rule*: ORM models, Alembic scripts, and Pydantic schemas remain decoupled.
3. **OpenRobo Knowledge Graph Storage**:
   - Stored directly in PostgreSQL using normalized node and edge tables (`graph_nodes` and `graph_edges`).
   - Graph queries and traversal algorithms are executed using Python `NetworkX` in memory (or recursive SQL common table expressions `WITH RECURSIVE`).
   - **No External Graph Database**: Neo4j or other specialized graph databases are explicitly avoided unless future scale measurements demonstrate PostgreSQL CTE performance is insufficient.
4. **Deferred External Search Engines**:
   - Elasticsearch and Meilisearch are NOT deployed initially. PostgreSQL `tsvector` with GIN indexing fulfills all early performance and zero-cost operational targets.
5. **Local / Offline Fallback Mode**:
   - For offline CLI execution without a PostgreSQL daemon, the `openrobo` CLI reads local JSON manifest files and builds an in-memory `NetworkX` knowledge graph.

## Database Schema Entities

- `resources`: Primary metadata records.
- `resource_versions`: Immutable version records with specific dependencies.
- `domains` & `capabilities`: Extensible taxonomy lookup tables.
- `graph_edges`: Core Knowledge Graph edge table (`subject_id`, `predicate`, `object_id`, `properties_json`).
- `compatibility_results`: Cached compatibility evaluations with evidence flags.
- `stack_manifests`: Serialized reproducible stack definitions.

## Consequences

### Positive
- Strict separation of concerns (SQLAlchemy 2.x for DB, Alembic for migrations, Pydantic v2 for validation).
- Simplified single-database infrastructure (PostgreSQL handles relational data, JSONB, full-text search, and knowledge graph relations).
- No external vector or graph database dependencies during initial milestones.

### Negative / Trade-offs
- Deep recursive graph traversals beyond 5+ hops must be handled carefully via `WITH RECURSIVE` SQL queries or loaded into Python `NetworkX` graphs to prevent performance bottlenecks.
