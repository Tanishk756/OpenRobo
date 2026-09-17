import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_evaluate_compatibility_success(client: AsyncClient):
    payload = {
        "resource_ids": ["ros-navigation/nav2", "ros-controls/ros2_control"],
        "environment": {"ros_version": "Jazzy", "os": "Ubuntu", "cpu_architecture": "x86_64"},
    }
    resp = await client.post("/api/v1/compatibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("compatible", "conditional", "incompatible", "unknown")
    assert "rule_evaluations" in data
    assert len(data["rule_evaluations"]) > 0


@pytest.mark.asyncio
async def test_evaluate_compatibility_validation_error(client: AsyncClient):
    payload = {"resource_ids": []}
    resp = await client.post("/api/v1/compatibility/evaluate", json=payload)
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_get_compatibility_matrix(client: AsyncClient):
    resp = await client.get(
        "/api/v1/compatibility/matrix?ids=ros-navigation/nav2,ros-controls/ros2_control,robotis/turtlebot3&ros_version=Jazzy"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "candidate_ids" in data
    assert len(data["candidate_ids"]) == 3
    assert "matrix" in data
    assert "summary" in data
    assert "ros-navigation/nav2" in data["matrix"]


@pytest.mark.asyncio
async def test_post_compatibility_matrix(client: AsyncClient):
    payload = {"resource_ids": ["ros-navigation/nav2", "stevemacenski/slam_toolbox"], "environment": {"ros_version": "Humble"}}
    resp = await client.post("/api/v1/compatibility/matrix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidate_ids"]) == 2
    assert "summary" in data


@pytest.mark.asyncio
async def test_get_resource_compatibility_profile(client: AsyncClient):
    resp = await client.get("/api/v1/compatibility/resource/ros-navigation/nav2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource_id"] == "ros-navigation/nav2"
    assert "direct_dependencies" in data
    assert "platform_matrix" in data


@pytest.mark.asyncio
async def test_graph_edges_filtering(client: AsyncClient):
    # Add an edge
    edge_payload = {
        "subject_id": "test-node-a",
        "predicate": "depends-on",
        "object_id": "test-node-b",
        "properties": {"min_version": "1.0.0"},
    }
    create_resp = await client.post("/api/v1/graph/edges", json=edge_payload)
    assert create_resp.status_code == 201

    # Filter by subject_id
    filter_resp = await client.get("/api/v1/graph/edges?subject_id=test-node-a")
    assert filter_resp.status_code == 200
    edges = filter_resp.json()
    assert len(edges) >= 1
    assert any(e["subject_id"] == "test-node-a" for e in edges)

    # Filter by predicate
    pred_resp = await client.get("/api/v1/graph/edges?predicate=depends-on")
    assert pred_resp.status_code == 200
    pred_edges = pred_resp.json()
    assert all(e["predicate"] == "depends-on" for e in pred_edges)
