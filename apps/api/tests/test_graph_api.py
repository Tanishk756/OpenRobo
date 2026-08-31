import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.main import app

@pytest.mark.asyncio
async def test_create_and_list_graph_edge():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        edge_payload = {
            "subject_id": "pkg-a/nav",
            "predicate": "depends-on",
            "object_id": "pkg-b/core",
            "properties": {"min_version": "1.0.0"}
        }
        res = await ac.post("/api/v1/graph/edges", json=edge_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["subject_id"] == "pkg-a/nav"
        assert data["predicate"] == "depends-on"

        list_res = await ac.get("/api/v1/graph/edges")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1
