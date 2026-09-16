import pytest
from openrobo_compat import GraphEdgeData, OpenRoboGraph


def test_graph_add_edge_and_query():
    graph = OpenRoboGraph()
    graph.add_node("robot-pkg/nav2")
    graph.add_node("robot-pkg/ros2_control")

    edge = GraphEdgeData(
        subject_id="robot-pkg/nav2", predicate="depends-on", object_id="robot-pkg/ros2_control", properties={"min_version": "2.0.0"}
    )
    graph.add_edge(edge)

    deps = graph.get_dependencies("robot-pkg/nav2")
    assert "robot-pkg/ros2_control" in deps


def test_invalid_predicate_raises_error():
    graph = OpenRoboGraph()
    with pytest.raises(ValueError, match="Invalid predicate"):
        graph.add_edge(GraphEdgeData(subject_id="a", predicate="invalid-predicate", object_id="b"))
