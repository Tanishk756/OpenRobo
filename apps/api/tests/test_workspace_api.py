import io
import zipfile

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_workspace_preview_direct_manifest(client: AsyncClient):
    manifest = {
        "id": "test_amr_stack",
        "name": "Test AMR Stack",
        "description": "Autonomous mobile robot navigation stack",
        "target": {"ros_distro": "humble", "os": "ubuntu-22.04", "architecture": "x86_64"},
        "resources": [
            {"id": "nav2", "name": "Navigation2", "version": "1.1.0"},
            {"id": "slam_toolbox", "name": "SLAM Toolbox", "version": "2.6.4"},
            {"id": "ros2_control", "name": "ROS 2 Control", "version": "2.20.0"},
            {"id": "custom_sensor", "name": "Custom Sensor", "version": "0.1.0"},
        ],
    }

    response = await client.post("/api/v1/workspace/preview", json={"manifest": manifest})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["stack_name"] == "Test AMR Stack"
    assert data["target_distro"] == "humble"
    assert "nav2" in data["selected_adapters"]
    assert "custom_sensor" in data["unsupported_components"]
    assert data["file_count"] >= 10
    assert "openrobo.manifest.json" in data["files"]
    assert "openrobo.lock.json" in data["files"]
    assert "README.md" in data["files"]
    assert "docker/Dockerfile" in data["files"]
    assert "docker/docker-compose.yml" in data["files"]


async def test_workspace_download_zip_direct_manifest(client: AsyncClient):
    manifest = {
        "id": "test_arm_stack",
        "name": "Test Arm Stack",
        "target": {"ros_distro": "iron", "os": "ubuntu-22.04", "architecture": "x86_64"},
        "resources": [
            {"id": "ros2_control", "name": "ROS 2 Control", "version": "2.20.0"},
        ],
    }

    response = await client.post("/api/v1/workspace/download", json={"manifest": manifest})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment; filename=" in response.headers["content-disposition"]

    # Verify ZIP structure
    zip_bytes = response.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        namelist = zf.namelist()
        assert any(n.endswith("openrobo.manifest.json") for n in namelist)
        assert any(n.endswith("openrobo.lock.json") for n in namelist)
        assert any(n.endswith("package.xml") for n in namelist)
        assert any(n.endswith("CMakeLists.txt") for n in namelist)


async def test_workspace_download_saved_stack(client: AsyncClient):
    # First create a stack
    stack_payload = {
        "name": "saved_robotic_stack",
        "manifest": {
            "id": "saved_robotic_stack",
            "name": "Saved Robotic Stack",
            "target": {"ros_distro": "jazzy", "os": "ubuntu-24.04", "architecture": "x86_64"},
            "resources": [{"id": "nav2", "name": "Navigation2", "version": "1.2.0"}],
        },
    }
    create_res = await client.post("/api/v1/stacks", json=stack_payload)
    assert create_res.status_code == 201
    stack_id = create_res.json()["id"]

    # Download workspace for saved stack
    dl_res = await client.get(f"/api/v1/stacks/{stack_id}/workspace/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(dl_res.content)) as zf:
        namelist = zf.namelist()
        assert len(namelist) >= 10


async def test_workspace_preview_missing_payload(client: AsyncClient):
    response = await client.post("/api/v1/workspace/preview", json={})
    assert response.status_code == 422


async def test_workspace_download_nonexistent_stack(client: AsyncClient):
    response = await client.get("/api/v1/stacks/nonexistent-uuid/workspace/download")
    assert response.status_code == 404
