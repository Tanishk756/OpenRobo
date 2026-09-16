import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_graph_edge(client: AsyncClient):
    edge_payload = {"subject_id": "pkg-a/nav", "predicate": "depends-on", "object_id": "pkg-b/core", "properties": {"min_version": "1.0.0"}}
    res = await client.post("/api/v1/graph/edges", json=edge_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["subject_id"] == "pkg-a/nav"
    assert data["predicate"] == "depends-on"
    assert data["object_id"] == "pkg-b/core"

    list_res = await client.get("/api/v1/graph/edges")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


@pytest.mark.asyncio
async def test_create_invalid_predicate_graph_edge_422(client: AsyncClient):
    edge_payload = {"subject_id": "pkg-a/nav", "predicate": "invalid-not-allowed-predicate", "object_id": "pkg-b/core"}
    res = await client.post("/api/v1/graph/edges", json=edge_payload)
    assert res.status_code == 422
