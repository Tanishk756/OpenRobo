import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_templates(client: AsyncClient):
    resp = await client.get("/api/v1/stacks/templates")
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 4
    template_ids = [t["id"] for t in templates]
    assert "mobile_robot_navigation" in template_ids
    assert "rgbd_perception_slam" in template_ids


@pytest.mark.asyncio
async def test_validate_adhoc_stack(client: AsyncClient):
    payload = {
        "components": [
            {"resource_id": "ros-navigation/nav2", "version": "1.3.0", "category": "navigation"},
            {"resource_id": "stevemacenski/slam_toolbox", "version": "2.7.4", "category": "mapping"},
        ],
        "target_os": "ubuntu_24_04",
        "target_arch": "x86_64",
        "target_ros_distro": "jazzy",
    }
    resp = await client.post("/api/v1/stacks/validate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["total_components"] == 2
    assert "compatibility_result" in data
    assert "resolution_proposal" in data


@pytest.mark.asyncio
async def test_resolve_adhoc_stack(client: AsyncClient):
    payload = {
        "components": [{"resource_id": "ros-navigation/nav2", "version": "1.3.0", "category": "navigation"}],
        "target_os": "ubuntu_24_04",
        "target_arch": "x86_64",
        "target_ros_distro": "jazzy",
    }
    resp = await client.post("/api/v1/stacks/resolve", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "is_fully_resolved" in data
    assert "proposed_actions" in data


@pytest.mark.asyncio
async def test_stack_crud_workflow(client: AsyncClient):
    # 1. Create stack
    create_payload = {
        "name": "my_test_robot_stack",
        "version": "1.0.0",
        "description": "Test stack created during automated test run",
        "robot_domain": "mobile_robotics",
        "robot_type": "differential_drive",
        "target_os": "ubuntu_24_04",
        "target_arch": "x86_64",
        "target_ros_distro": "jazzy",
        "components": [{"resource_id": "ros-navigation/nav2", "version": "1.3.0", "category": "navigation", "optional": False}],
        "metadata": {"author": "Tester"},
    }
    resp = await client.post("/api/v1/stacks", json=create_payload)
    assert resp.status_code == 201
    created_stack = resp.json()
    stack_id = created_stack["id"]
    assert stack_id.startswith("stack_")
    assert created_stack["name"] == "my_test_robot_stack"

    # 2. Get stack by ID
    get_resp = await client.get(f"/api/v1/stacks/{stack_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == stack_id

    # 3. List stacks
    list_resp = await client.get("/api/v1/stacks?q=my_test_robot_stack")
    assert list_resp.status_code == 200
    stacks = list_resp.json()
    assert any(s["id"] == stack_id for s in stacks)

    # 4. Update stack
    update_payload = {
        "description": "Updated description for test stack",
        "components": [
            {"resource_id": "ros-navigation/nav2", "version": "1.3.0", "category": "navigation", "optional": False},
            {"resource_id": "stevemacenski/slam_toolbox", "version": "2.7.4", "category": "mapping", "optional": False},
        ],
    }
    patch_resp = await client.patch(f"/api/v1/stacks/{stack_id}", json=update_payload)
    assert patch_resp.status_code == 200
    updated_stack = patch_resp.json()
    assert updated_stack["description"] == "Updated description for test stack"
    assert len(updated_stack["components"]) == 2

    # 5. Validate saved stack
    val_resp = await client.post(f"/api/v1/stacks/{stack_id}/validate")
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["stack_id"] == stack_id
    assert val_data["total_components"] == 2

    # 6. Resolve saved stack
    res_resp = await client.post(f"/api/v1/stacks/{stack_id}/resolve")
    assert res_resp.status_code == 200
    assert "proposed_actions" in res_resp.json()

    # 7. Export manifest
    manifest_resp = await client.get(f"/api/v1/stacks/{stack_id}/manifest")
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["name"] == "my_test_robot_stack"
    assert len(manifest["components"]) == 2

    # 8. Delete stack
    del_resp = await client.delete(f"/api/v1/stacks/{stack_id}")
    assert del_resp.status_code == 204

    # Verify deleted
    not_found_resp = await client.get(f"/api/v1/stacks/{stack_id}")
    assert not_found_resp.status_code == 404


@pytest.mark.asyncio
async def test_import_stack_manifest(client: AsyncClient):
    valid_manifest = {
        "name": "imported_test_stack",
        "version": "1.0.0",
        "robot": {"domain": "mobile_robotics", "type": "amr"},
        "target_platform": {"os": "ubuntu_24_04", "arch": "x86_64", "ros_distribution": "jazzy"},
        "components": [{"resource_id": "ros-navigation/nav2", "version": "1.3.0", "category": "navigation"}],
    }
    resp = await client.post("/api/v1/stacks/import", json={"manifest": valid_manifest})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert "validation" in data

    # Malformed manifest (missing robot)
    invalid_manifest = {
        "name": "invalid_stack",
        "version": "1.0.0",
        "components": [],
    }
    inv_resp = await client.post("/api/v1/stacks/import", json={"manifest": invalid_manifest})
    assert inv_resp.status_code == 422
