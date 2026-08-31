# System Architecture

Initial logical architecture:

Web UI
→ API
→ Registry / Search / Compatibility / Stack Builder / Ingestion services
→ PostgreSQL + object storage only where necessary
→ external/upstream open-source repositories and registries

The platform should avoid mirroring large upstream assets unless redistribution is explicitly permitted and operationally justified.

Recommended initial implementation direction:
- Frontend: Next.js + React + TypeScript
- Backend: Python + FastAPI
- Database: PostgreSQL
- API schema: OpenAPI
- Resource schemas: JSON Schema + YAML/JSON
- Containers: OCI/Docker-compatible
- CI: GitHub Actions
- Search: PostgreSQL initially; dedicated search engine only when justified

Technology choices remain subject to the detailed architecture review.
