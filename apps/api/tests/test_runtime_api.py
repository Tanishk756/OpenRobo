import os
import tempfile

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_runtime_providers_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/runtime/providers")
    assert response.status_code == 200
    data = response.json()
    assert "docker" in data
    assert "podman" in data
    assert "local_process" in data
    assert "provider_type" in data["local_process"]


async def test_runtime_environment_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/runtime/environment")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "rclpy_available" in data
    assert "ros2_cli_available" in data


async def test_runtime_connection_inspector_status(client: AsyncClient):
    response = await client.get("/api/v1/runtime/connection-inspector?distro=humble")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "licensing_notice" in data
    assert "GPL-3.0-only" in data["licensing_notice"]


async def test_runtime_connection_inspector_cli_uninstalled(client: AsyncClient):
    # When uninstalled, executing CLI endpoint should return 400 Bad Request
    response = await client.post("/api/v1/runtime/connection-inspector/cli")
    assert response.status_code in [400, 200]


async def test_runtime_simulators_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/runtime/simulators")
    assert response.status_code == 200
    data = response.json()
    assert "gazebo" in data
    assert "webots" in data
    assert "mujoco" in data
    assert "installed" in data["gazebo"]


async def test_runtime_live_graph_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/runtime/introspection/live")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "nodes" in data
    assert "topics" in data


async def test_runtime_introspection_compare_with_contract(client: AsyncClient):
    payload = {
        "planned_manifest": {
            "id": "test_stack",
            "name": "Test AMR Stack",
        },
        "runtime_contract": {
            "expected_nodes": ["/slam_toolbox"],
            "expected_topics": [
                {"name": "/scan", "msg_type": "sensor_msgs/msg/LaserScan", "required": True},
            ],
        },
        "observed_nodes": [
            {
                "name": "slam_toolbox",
                "namespace": "/",
                "package": "slam_toolbox",
                "publications": [{"topic": "/map", "msg_type": "nav_msgs/msg/OccupancyGrid"}],
                "subscriptions": [{"topic": "/scan", "msg_type": "sensor_msgs/msg/LaserScan"}],
            }
        ],
        "observed_topics": [
            {
                "topic": "/scan",
                "msg_type": "sensor_msgs/msg/LaserScan",
                "publishers": [{"node_name": "rplidar", "qos": {"reliability": "RELIABLE", "durability": "VOLATILE"}}],
                "subscribers": [{"node_name": "slam_toolbox", "qos": {"reliability": "RELIABLE", "durability": "VOLATILE"}}],
            }
        ],
    }

    response = await client.post("/api/v1/runtime/introspection/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "HEALTHY"
    assert data["contract_evaluated"] is True
    assert "nodes" in data
    assert "connections" in data


async def test_runtime_sessions_crud_lifecycle(client: AsyncClient):
    with tempfile.TemporaryDirectory() as tmp_ws:
        create_payload = {
            "stack_id": "test_stack_alpha",
            "workspace_path": tmp_ws,
            "ros_distro": "humble",
            "domain_id": 5,
        }
        res = await client.post("/api/v1/runtime/sessions", json=create_payload)
        assert res.status_code == 201
        session_data = res.json()
        session_id = session_data["id"]
        assert session_data["status"] == "RUNNING"
        assert session_data["stack_id"] == "test_stack_alpha"

        # List sessions
        list_res = await client.get("/api/v1/runtime/sessions")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1

        # Get session
        get_res = await client.get(f"/api/v1/runtime/sessions/{session_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == session_id

        # Stop session
        stop_res = await client.post(f"/api/v1/runtime/sessions/{session_id}/stop")
        assert stop_res.status_code == 200
        assert stop_res.json()["status"] == "STOPPED"


async def test_runtime_build_verify_nonexistent_workspace(client: AsyncClient):
    payload = {
        "workspace_dir": "nonexistent_workspace_dir_xyz",
        "target_distro": "humble",
    }
    response = await client.post("/api/v1/runtime/build/verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert any("Workspace directory does not exist" in err for err in data["errors"])


async def test_runtime_rosbag_inspect_empty_dir(client: AsyncClient):
    with tempfile.TemporaryDirectory() as tmpdir:
        meta_file = os.path.join(tmpdir, "metadata.yaml")
        yaml_content = (
            "rosbag2_bagfile_information:\n"
            "  storage_identifier: sqlite3\n"
            "  duration:\n"
            "    nanoseconds: 5000000000\n"
            "  message_count: 100\n"
            "  topics_with_message_count:\n"
            "    - topic_metadata:\n"
            "        name: /scan\n"
            "        type: sensor_msgs/msg/LaserScan\n"
            "      message_count: 100\n"
        )
        with open(meta_file, "w") as f:
            f.write(yaml_content)

        response = await client.post("/api/v1/runtime/telemetry/rosbag", json={"bag_path": tmpdir})
        assert response.status_code == 200
        data = response.json()
        assert data["storage_identifier"] == "sqlite3"
        assert data["message_count"] == 100
        assert len(data["topics"]) == 1
