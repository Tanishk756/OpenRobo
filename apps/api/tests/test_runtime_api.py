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


async def test_runtime_connection_inspector_status(client: AsyncClient):
    response = await client.get("/api/v1/runtime/connection-inspector?distro=humble")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "licensing_notice" in data
    assert "GPL-3.0-only" in data["licensing_notice"]


async def test_runtime_simulators_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/runtime/simulators")
    assert response.status_code == 200
    data = response.json()
    assert "gazebo" in data
    assert "webots" in data
    assert "mujoco" in data
    assert "installed" in data["gazebo"]


async def test_runtime_introspection_compare(client: AsyncClient):
    payload = {
        "planned_manifest": {
            "id": "test_stack",
            "name": "Test AMR Stack",
            "resources": [
                {"id": "nav2", "name": "Navigation2"},
                {"id": "slam_toolbox", "name": "SLAM Toolbox"},
            ],
            "runtime_graph": {
                "nodes": [
                    {
                        "name": "slam_toolbox",
                        "package": "slam_toolbox",
                        "publications": [{"topic": "/map", "msg_type": "nav_msgs/msg/OccupancyGrid"}],
                        "subscriptions": [{"topic": "/scan", "msg_type": "sensor_msgs/msg/LaserScan"}],
                    }
                ]
            },
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
                "topic": "/map",
                "msg_type": "nav_msgs/msg/OccupancyGrid",
                "publishers": [{"node_name": "slam_toolbox", "qos": {"reliability": "RELIABLE", "durability": "TRANSIENT_LOCAL"}}],
                "subscribers": [],
            }
        ],
    }

    response = await client.post("/api/v1/runtime/introspection/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] in ["HEALTHY", "DEGRADED"]
    assert "nodes" in data
    assert "connections" in data


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
