import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.main import app

@pytest.mark.asyncio
async def test_list_resources():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/resources")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_create_and_get_resource():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "id": "test-org/test-pkg",
            "name": "Test Package",
            "version": "1.0.0",
            "type": "ros_package",
            "source": {"repo_url": "https://github.com/test-org/test-pkg"},
            "license": {"spdx_id": "Apache-2.0"},
            "spdx_license_id": "Apache-2.0",
            "evidence_level": "ci_verified"
        }
        create_res = await ac.post("/api/v1/resources", json=payload)
        assert create_res.status_code in (201, 409)

        get_res = await ac.get("/api/v1/resources/test-org/test-pkg")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Test Package"
