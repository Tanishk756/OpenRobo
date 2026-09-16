# OpenRobo Milestone 2 — Search Engine & Advanced Taxonomy Indexing Implementation Plan

**Milestone:** M2 (Search Engine & Advanced Taxonomy Indexing)  
**Status:** DRAFT / PLANNED  
**Date:** September 16, 2026  
**Author / Maintainer:** Tanishk Singhal  
**Reference Architecture:** [ADR-0002: Database and Search Architecture](adr/0002-database-and-search-architecture.md)

---

## 1. Executive Summary & Goals

Milestone 2 transitions OpenRobo from baseline `ILIKE` pattern filtering into a production-grade, zero-cost, high-performance search engine built entirely within PostgreSQL 16+.

The core objectives of Milestone 2 are:
1. **Full-Text Search Engine (`REQ-M2-01`)**: Weighted full-text search (`tsvector` + `tsquery`) over resource names, slugs, summaries, descriptions, capabilities, and keywords with `ts_rank_cd` ranking.
2. **Fuzzy & Typo-Tolerant Matching (`REQ-M2-01`)**: PostgreSQL `pg_trgm` trigram similarity matching for robust tolerance of typos and partial robotics package names (e.g. `navv2` -> `nav2`, `realsens` -> `realsense`).
3. **Multi-Taxonomy Faceting & Aggregations (`REQ-M2-02`)**: Deterministic faceted counts across Canonical Types, Robotics Domains, Capabilities, SPDX Licenses, Operating Systems, and ROS Versions in a single performant query.
4. **Offline & Test Database Compatibility**: Seamless fallback logic in SQLite in-memory test fixtures ensuring zero-Docker local tests continue passing with 100% test isolation.

---

## 2. Architecture & Design

### A. PostgreSQL Search Subsystem
```
                   Inbound Query ("nav2 slam humble")
                                  │
                                  ▼
                     ┌─────────────────────────┐
                     │   Query Preprocessor    │
                     │  (Tokenize & Sanitize)  │
                     └────────────┬────────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
      ┌─────────────────────┐           ┌─────────────────────┐
      │  tsvector Full-Text │           │   pg_trgm Trigram   │
      │   Exact & Prefix    │           │   Fuzzy Similarity  │
      └──────────┬──────────┘           └──────────┬──────────┘
                 │                                 │
                 └────────────────┬────────────────┘
                                  ▼
                     ┌─────────────────────────┐
                     │   Rank Weighted Score   │
                     │ (0.7 * ts + 0.3 * trgm) │
                     └────────────┬────────────┘
                                  ▼
                     ┌─────────────────────────┐
                     │ Filter Facets & Bounds  │
                     │ (Domain, License, etc.) │
                     └────────────┬────────────┘
                                  ▼
                     ┌─────────────────────────┐
                     │ Paginated JSON Response │
                     │   + Facet Aggregations  │
                     └─────────────────────────┘
```

### B. Weighted Search Dimensions
- **Weight A (1.0)**: `name`, `id` (slug)
- **Weight B (0.4)**: `summary`, `capabilities`, `robotics_domains`
- **Weight C (0.2)**: `description`, `topics`, `keywords`

---

## 3. Database Changes & Migrations

### Alembic Migration: `0003_search_indexes.py`
1. Enable PostgreSQL extension: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
2. Add Generated Column to `resources`:
   ```sql
   ALTER TABLE resources ADD COLUMN search_vector tsvector 
   GENERATED ALWAYS AS (
     setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
     setweight(to_tsvector('english', coalesce(id, '')), 'A') ||
     setweight(to_tsvector('english', coalesce(summary, '')), 'B') ||
     setweight(to_tsvector('english', coalesce(description, '')), 'C')
   ) STORED;
   ```
3. Add GIN Indexes:
   - `CREATE INDEX idx_resources_search_vector ON resources USING GIN (search_vector);`
   - `CREATE INDEX idx_resources_name_trgm ON resources USING GIN (name gin_trgm_ops);`
   - `CREATE INDEX idx_resources_id_trgm ON resources USING GIN (id gin_trgm_ops);`

---

## 4. API Design & Endpoints

### 1. `GET /api/v1/search`
Query Parameters:
- `q`: Search query text (e.g. `slam lidar`)
- `type`: Resource kind filter
- `domain`: Robotics domain filter
- `capability`: Capability filter
- `license`: SPDX license filter
- `ros_version`: ROS version filter (e.g. `ROS 2 Humble`)
- `os`: Operating system filter
- `fuzzy`: Boolean (default `true`)
- `limit`: Integer (default 20, max 100)
- `offset`: Integer (default 0)

Response:
```json
{
  "query": "slam",
  "total": 4,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "id": "stevemacenski/slam_toolbox",
      "name": "SLAM Toolbox",
      "score": 0.94,
      "highlight": "2D and 3D <b>SLAM</b> for ROS 2",
      "..." : "..."
    }
  ],
  "facets": {
    "types": { "ros_package": 3, "driver": 1 },
    "domains": { "localization": 4, "mapping": 4 },
    "licenses": { "LGPL-3.0-only": 1, "Apache-2.0": 3 },
    "ros_versions": { "ROS 2 Humble": 4, "ROS 2 Jazzy": 3 }
  }
}
```

### 2. `GET /api/v1/search/facets`
Returns global facet distribution counts across the registry for rendering dynamic filter counts in the frontend.

---

## 5. Frontend Integration Plan

1. **Dynamic Facet Counts**: Display item counts next to filter chips in `SearchAndFilters.tsx` (e.g., `Navigation (12)`, `Perception (8)`).
2. **Search Autocomplete / Instant Suggestions**: Popover under search bar suggesting top matching resources as the engineer types.
3. **Keyword Highlighting**: Bold matching tokens in search result descriptions.

---

## 6. Testing Strategy

1. **Pytest Search Tests (`apps/api/tests/test_search.py`)**:
   - Exact keyword match
   - Prefix match
   - Trigram typo tolerance (`navv2` matching `nav2`)
   - Combined multi-facet filtering (Domain + ROS Version + SPDX License)
   - Facet aggregation accuracy
   - SQLite compatibility fallback validation
2. **Vitest Frontend Tests (`apps/web/tests/unit/search.test.tsx`)**:
   - Autocomplete dropdown rendering
   - Facet chip count display
   - Search query debounce and highlighting

---

## 7. Performance Targets

- Query latency: `< 15ms` for full-text + trigram match on 10,000 resources.
- Facet aggregation latency: `< 25ms`.
- Zero additional external operational cost.

---

## 8. Implementation Task Breakdown

| Task ID | Task Description | Dependencies | Estimated Complexity |
|---|---|---|---|
| **TASK-M2-01** | Create Alembic migration `0003_search_indexes.py` with `pg_trgm` and GIN indexes | DB / Alembic | Low |
| **TASK-M2-02** | Implement SQL Search Query Builder with hybrid `tsvector` + `pg_trgm` ranking | SQLAlchemy | Medium |
| **TASK-M2-03** | Implement Multi-Taxonomy Facet Aggregator | SQLAlchemy | Medium |
| **TASK-M2-04** | Expose `GET /api/v1/search` and `GET /api/v1/search/facets` | FastAPI | Low |
| **TASK-M2-05** | Add search unit and integration tests with SQLite fallback | Pytest | Medium |
| **TASK-M2-06** | Update `openrobo search` CLI command to use search endpoint | Typer CLI | Low |
| **TASK-M2-07** | Integrate dynamic facet counts and search highlights in Next.js web app | Next.js / React | Medium |
| **TASK-M2-08** | Monorepo verification and M2 verification report | CI / pnpm check | Low |
