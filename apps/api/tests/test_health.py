import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get('/api/v1/health')
    assert response.status_code == 200
    data = response.json()
    assert 'status' in data
    assert data['version'] == '0.1.0'

@pytest.mark.asyncio
async def test_readiness_endpoint(client: AsyncClient):
    response = await client.get('/api/v1/health/readiness')
    assert response.status_code == 200
    assert response.json() == {'ready': True}

@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get('/')
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'OpenRobo API Service'
