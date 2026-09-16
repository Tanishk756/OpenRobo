import pytest
from httpx import AsyncClient

SAMPLE_RESOURCE = {
    "id": "test-org/nav-core",
    "name": "Nav Core Package",
    "version": "1.0.0",
    "type": "ros_package",
    "summary": "Core navigation and path-planning algorithms for mobile robots",
    "description": "Long form description of the Nav Core Package.",
    "source": {"repo_url": "https://github.com/test-org/nav-core"},
    "license": {"spdx_id": "Apache-2.0"},
    "robotics_domains": ["navigation", "amr", "ground"],
    "capabilities": ["path-planning", "slam", "obstacle-avoidance"],
    "platforms": {"operating_systems": ["Ubuntu 24.04"], "ros_versions": ["Jazzy", "Humble"], "cpu_architectures": ["x86_64", "arm64"]},
    "evidence": {"level": "ci_verified"},
}

SAMPLE_ARM_RESOURCE = {
    "id": "test-org/arm-ctrl",
    "name": "Arm Controller",
    "version": "2.0.0",
    "type": "driver",
    "summary": "Hardware driver and servo controller for robotic arms",
    "source": {"repo_url": "https://github.com/test-org/arm-ctrl"},
    "license": {"spdx_id": "BSD-3-Clause"},
    "robotics_domains": ["manipulation", "arms"],
    "capabilities": ["real-time-control", "servo-control"],
    "platforms": {"operating_systems": ["Ubuntu 24.04"], "ros_versions": ["Jazzy"]},
    "evidence": {"level": "upstream_declared"},
}


@pytest.mark.asyncio
async def test_list_resources_empty(client: AsyncClient):
    response = await client.get("/api/v1/resources")
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers.get("X-Total-Count") == "0"


@pytest.mark.asyncio
async def test_create_and_get_resource(client: AsyncClient):
    create_res = await client.post("/api/v1/resources", json=SAMPLE_RESOURCE)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["id"] == "test-org/nav-core"
    assert created_data["name"] == "Nav Core Package"
    assert created_data["robotics_domains"] == ["navigation", "amr", "ground"]
    assert created_data["capabilities"] == ["path-planning", "slam", "obstacle-avoidance"]

    get_res = await client.get("/api/v1/resources/test-org/nav-core")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == "test-org/nav-core"
    assert get_data["name"] == "Nav Core Package"
    assert get_data["platforms"]["ros_versions"] == ["Jazzy", "Humble"]


@pytest.mark.asyncio
async def test_create_duplicate_conflict(client: AsyncClient):
    res1 = await client.post("/api/v1/resources", json=SAMPLE_RESOURCE)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/resources", json=SAMPLE_RESOURCE)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_get_nonexistent_resource_404(client: AsyncClient):
    res = await client.get("/api/v1/resources/nonexistent/package-id")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_invalid_manifest_422(client: AsyncClient):
    invalid_manifest = {"id": "invalid_no_slash_namespace", "name": "Invalid"}
    res = await client.post("/api/v1/resources", json=invalid_manifest)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_search_and_filtering(client: AsyncClient):
    await client.post("/api/v1/resources", json=SAMPLE_RESOURCE)
    await client.post("/api/v1/resources", json=SAMPLE_ARM_RESOURCE)

    # 1. Search keyword q
    q_res = await client.get("/api/v1/resources?q=nav")
    assert q_res.status_code == 200
    assert len(q_res.json()) == 1
    assert q_res.json()[0]["id"] == "test-org/nav-core"

    # 2. Filter by type
    type_res = await client.get("/api/v1/resources?type=driver")
    assert type_res.status_code == 200
    assert len(type_res.json()) == 1
    assert type_res.json()[0]["id"] == "test-org/arm-ctrl"

    # 3. Filter by domain
    dom_res = await client.get("/api/v1/resources?domain=manipulation")
    assert dom_res.status_code == 200
    assert len(dom_res.json()) == 1
    assert dom_res.json()[0]["id"] == "test-org/arm-ctrl"

    # 4. Filter by capability
    cap_res = await client.get("/api/v1/resources?capability=slam")
    assert cap_res.status_code == 200
    assert len(cap_res.json()) == 1
    assert cap_res.json()[0]["id"] == "test-org/nav-core"

    # 5. Filter by ecosystem (Humble)
    eco_res = await client.get("/api/v1/resources?ecosystem=Humble")
    assert eco_res.status_code == 200
    assert len(eco_res.json()) == 1
    assert eco_res.json()[0]["id"] == "test-org/nav-core"

    # 6. Pagination
    all_res = await client.get("/api/v1/resources?limit=1&offset=0")
    assert all_res.status_code == 200
    assert len(all_res.json()) == 1
    assert all_res.headers.get("X-Total-Count") == "2"

    offset_res = await client.get("/api/v1/resources?limit=1&offset=1")
    assert offset_res.status_code == 200
    assert len(offset_res.json()) == 1


@pytest.mark.asyncio
async def test_database_isolation(client: AsyncClient):
    # Verifies that previous tests have not left any resources in the database
    res = await client.get("/api/v1/resources")
    assert res.status_code == 200
    assert res.json() == []
