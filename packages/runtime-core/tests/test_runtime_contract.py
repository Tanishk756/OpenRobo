from openrobo_runtime.introspection.comparator import ConnectionComparator
from openrobo_runtime.models import (
    ExpectedTopicContract,
    OverallHealthStatus,
    ReadinessState,
    RuntimeContract,
)


def test_comparison_without_contract_does_not_guess_missing_nodes():
    comparator = ConnectionComparator()
    planned_manifest = {
        "id": "my_amr_stack",
        "resources": [
            {"id": "nav2", "name": "Navigation2"},
            {"id": "slam_toolbox", "name": "SLAM Toolbox"},
            {"id": "custom_driver", "name": "Custom Driver"},
        ],
    }
    # Observed active nodes has only 1 node
    observed_nodes = [{"name": "slam_toolbox", "namespace": "/", "is_present": True}]
    observed_topics = [{"topic": "/map", "type": "nav_msgs/msg/OccupancyGrid", "publishers": ["slam_toolbox"]}]

    res = comparator.compare(planned_manifest, observed_nodes, observed_topics)

    assert res.contract_evaluated is False
    assert res.missing_nodes == []  # MUST NOT guess custom_driver or nav2 as missing nodes
    assert res.overall_status == OverallHealthStatus.HEALTHY


def test_comparison_with_explicit_contract_validates_strictly():
    comparator = ConnectionComparator()
    contract = RuntimeContract(
        expected_nodes=["/slam_toolbox", "/nav2_controller"],
        expected_topics=[
            ExpectedTopicContract(name="/scan", msg_type="sensor_msgs/msg/LaserScan", required=True),
            ExpectedTopicContract(name="/map", msg_type="nav_msgs/msg/OccupancyGrid", required=True),
        ],
    )
    planned_manifest = {"id": "my_amr_stack", "runtime_contract": contract.model_dump()}

    # Only slam_toolbox observed, nav2_controller missing
    observed_nodes = [{"name": "slam_toolbox", "namespace": "/", "is_present": True}]
    observed_topics = [
        {"topic": "/scan", "type": "sensor_msgs/msg/LaserScan", "publishers": ["rplidar"]},
        {"topic": "/map", "type": "nav_msgs/msg/OccupancyGrid", "publishers": ["slam_toolbox"]},
    ]

    res = comparator.compare(planned_manifest, observed_nodes, observed_topics)

    assert res.contract_evaluated is True
    assert "/nav2_controller" in res.missing_nodes
    assert res.overall_status == OverallHealthStatus.DEGRADED
    assert res.readiness_state == ReadinessState.RUNTIME_FAILED


def test_comparison_flags_topic_type_mismatch():
    comparator = ConnectionComparator()
    contract = RuntimeContract(
        expected_nodes=["/slam_toolbox"],
        expected_topics=[
            ExpectedTopicContract(name="/scan", msg_type="sensor_msgs/msg/LaserScan", required=True),
        ],
    )
    planned_manifest = {"id": "my_amr_stack", "runtime_contract": contract.model_dump()}

    observed_nodes = [{"name": "slam_toolbox", "namespace": "/"}]
    # Observed topic type is PointCloud2 instead of LaserScan
    observed_topics = [{"topic": "/scan", "type": "sensor_msgs/msg/PointCloud2", "publishers": ["lidar_driver"]}]

    res = comparator.compare(planned_manifest, observed_nodes, observed_topics)

    assert res.overall_status == OverallHealthStatus.DEGRADED
    scan_diag = next(c for c in res.connections if c.topic == "/scan")
    assert scan_diag.status == "TYPE_MISMATCH"
    assert "Expected message type 'sensor_msgs/msg/LaserScan'" in (scan_diag.type_mismatch_detail or "")
