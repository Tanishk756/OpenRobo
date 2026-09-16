import re
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.resource import ResourceModel
from apps.api.services.search.facets import compute_facets
from apps.api.services.search.models import (
    SearchFacetDistribution,
    SearchRequest,
    SearchResponse,
    SearchResultHit,
)
from apps.api.services.search.query_builder import build_filtered_query
from apps.api.services.search.ranking import calculate_relevance_score


class SearchService:
    @staticmethod
    def _tokenize(query_str: Optional[str]) -> List[str]:
        if not query_str:
            return []
        return [t.lower() for t in re.findall(r"[a-zA-Z0-9_.-]+", query_str) if len(t) >= 2]

    async def search(self, db: AsyncSession, request: SearchRequest) -> SearchResponse:
        stmt = build_filtered_query(request)
        result = await db.execute(stmt)
        all_matched_resources = list(result.scalars().all())

        raw_q = (request.q or "").strip()
        tokens = self._tokenize(raw_q)

        scored_items: List[Tuple[ResourceModel, float, Optional[str]]] = []

        if raw_q:
            for res in all_matched_resources:
                score, highlight = calculate_relevance_score(res=res, query_tokens=tokens, raw_query=raw_q, enable_fuzzy=request.fuzzy)
                if score > 0.0:
                    scored_items.append((res, score, highlight))

            # Rank by Score DESC, then Name ASC
            scored_items.sort(key=lambda item: (-item[1], item[0].name.lower()))
        else:
            # If no query string, preserve all filtered candidates with default score 1.0
            scored_items = [(res, 1.0, None) for res in all_matched_resources]
            scored_items.sort(key=lambda item: item[0].name.lower())

        total = len(scored_items)

        # Compute facet distribution over all matched resources
        matching_resources_for_facets = [item[0] for item in scored_items]
        facets = compute_facets(matching_resources_for_facets)

        # Pagination slice
        paginated_slice = scored_items[request.offset : request.offset + request.limit]

        hits: List[SearchResultHit] = []
        for res, score, highlight in paginated_slice:
            hits.append(
                SearchResultHit(
                    id=res.id,
                    name=res.name,
                    type=res.type,
                    summary=res.summary,
                    description=res.description,
                    spdx_license_id=res.spdx_license_id,
                    repo_url=res.repo_url,
                    robotics_domains=res.robotics_domains or [],
                    capabilities=res.capabilities or [],
                    platforms=res.platforms or {},
                    evidence_level=res.evidence_level or "unknown",
                    score=score,
                    highlight=highlight,
                )
            )

        return SearchResponse(query=request.q, total=total, limit=request.limit, offset=request.offset, items=hits, facets=facets)

    async def get_facets(self, db: AsyncSession, q: Optional[str] = None) -> SearchFacetDistribution:
        req = SearchRequest(q=q, limit=1000, offset=0)
        res = await self.search(db, req)
        return res.facets
