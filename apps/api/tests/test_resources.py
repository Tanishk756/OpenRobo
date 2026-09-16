import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_resources_empty(client: AsyncClient):
    response = await client.get('/api/v1/resources')
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_create_and_get_resource(client: AsyncClient):
    payload = {
        'id': 'test-org/test-pkg',
        'name': 'Test Package',
        'version': '1.0.0',
        'type': 'ros_package',
        'source': {'repo_url': 'https://github.com/test-org/test-pkg'},
        'license': {'spdx_id': 'Apache-2.0'},
        'spdx_license_id': 'Apache-2.0',
        'evidence_level': 'ci_verified'
    }
    create_res = await client.post('/api/v1/resources', json=payload)
    assert create_res.status_code == 201
    assert create_res.json()['id'] == 'test-org/test-pkg'
    assert create_res.json()['name'] == 'Test Package'

    get_res = await client.get('/api/v1/resources/test-org/test-pkg')
    assert get_res.status_code == 200
    assert get_res.json()['name'] == 'Test Package'

@pytest.mark.asyncio
async def test_create_duplicate_resource_conflict(client: AsyncClient):
    payload = {
        'id': 'test-org/dup-pkg',
        'name': 'Duplicate Package',
        'version': '1.0.0',
        'type': 'ros_package',
        'source': {'repo_url': 'https://github.com/test-org/dup-pkg'},
        'license': {'spdx_id': 'Apache-2.0'}
    }
    res1 = await client.post('/api/v1/resources', json=payload)
    assert res1.status_code == 201

    res2 = await client.post('/api/v1/resources', json=payload)
    assert res2.status_code == 409

@pytest.mark.asyncio
async def test_get_nonexistent_resource_404(client: AsyncClient):
    res = await client.get('/api/v1/resources/nonexistent/pkg')
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_create_invalid_schema_resource_422(client: AsyncClient):
    invalid_payload = {
        'id': 'invalid-id-without-required-fields'
    }
    res = await client.post('/api/v1/resources', json=invalid_payload)
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_database_isolation_check(client: AsyncClient):
    # This test verifies that each test gets a clean, isolated database
    res = await client.get('/api/v1/resources')
    assert res.status_code == 200
    assert res.json() == []
