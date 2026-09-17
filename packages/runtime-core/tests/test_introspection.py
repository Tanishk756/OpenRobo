"""Unit tests for ROS Runtime Introspection and Connection Comparator."""

from openrobo_runtime import (
    ConnectionComparator,
    OverallHealthStatus,
    RuntimeGraphInspector,
    TFInspector,
)


def test_runtime_graph_inspector():
    inspector = RuntimeGraphInspector()
    raw_nodes = [
        {"name": "nav2_planner", "namespace": "/", "is_alive": True, "publisher_topics": ["/plan"], "subscriber_topics": ["/goal_pose"]},
        {"name": "slam_toolbox", "namespace": "/", "is_alive": True, "publisher_topics": ["/map"], "subscriber_topics": ["/scan"]},
    ]
    raw_topics = [
        {"name": "/scan", "type": "sensor_msgs/msg/LaserScan", "publishers": ["lidar_node"], "subscribers": ["slam_toolbox"]},
        {"name": "/plan", "type": "nav_msgs/msg/Path", "publishers": ["nav2_planner"], "subscribers": []},
    ]

    nodes, connections = inspector.build_diagnostics_from_graph(raw_nodes, raw_topics)
    assert len(nodes) == 2
    assert len(connections) == 2
    assert connections[0].status == "HEALTHY"
    assert connections[1].status == "ORPHANED_PUBLISHER"


def test_connection_comparator_planned_vs_observed():
    comparator = ConnectionComparator()
    planned_manifest = {
        "id": "diffbot_stack",
        "resources": [
            {"id": "nav2"},
            {"id": "slam_toolbox"},
            {"id": "lidar_driver"},
        ],
    }
    observed_nodes = [
        {"name": "nav2_bringup_node", "is_alive": True},
        {"name": "slam_toolbox_node", "is_alive": True},
    ]
    observed_topics = [
        {"name": "/scan", "type": "sensor_msgs/msg/LaserScan", "publishers": ["lidar_driver_node"], "subscribers": ["slam_toolbox_node"]},
    ]

    res = comparator.compare(planned_manifest, observed_nodes, observed_topics)
    # lidar_driver was not in observed_nodes
    assert "lidar_driver" in res.missing_nodes
    assert res.overall_status == OverallHealthStatus.DEGRADED


def test_tf_inspector():
    raw_tfs = [
        {"frame_id": "laser_frame", "parent_frame_id": "base_link", "is_connected": True, "is_stale": False, "rate_hz": 30.0},
        {"frame_id": "camera_link", "parent_frame_id": "base_link", "is_connected": False, "is_stale": True},
    ]
    tfs = TFInspector.inspect_frames(raw_tfs)
    assert len(tfs) == 2
    assert tfs[0].is_connected is True
    assert tfs[1].is_connected is False
