import pytest
from openrobo_compat.graph import GraphEdgeData, OpenRoboGraph
from openrobo_compat.models import ResolutionActionType, ResourceCandidate
from openrobo_compat.resolver import DependencyResolver


@pytest.fixture
def sample_graph():
    graph = OpenRoboGraph()
    graph.add_node("nav2", {"type": "navigation"})
    graph.add_node("slam_toolbox", {"type": "mapping"})
    graph.add_node("laser_geometry", {"type": "perception"})
    graph.add_node("fastdds", {"type": "middleware"})
    graph.add_node("cyclonedds", {"type": "middleware"})
    graph.add_node("cycle_a", {"type": "control"})
    graph.add_node("cycle_b", {"type": "control"})

    # Dependencies
    graph.add_edge(GraphEdgeData(subject_id="nav2", predicate="DEPENDS_ON", object_id="slam_toolbox"))
    graph.add_edge(GraphEdgeData(subject_id="slam_toolbox", predicate="DEPENDS_ON", object_id="laser_geometry"))

    # Version constraint: nav2 requires slam_toolbox >=2.0.0,<3.0.0
    graph.add_edge(
        GraphEdgeData(
            subject_id="nav2",
            predicate="DEPENDS_ON",
            object_id="slam_toolbox",
            properties={"version_constraint": ">=2.0.0,<3.0.0"},
        )
    )

    # Incompatibilities
    graph.add_edge(GraphEdgeData(subject_id="fastdds", predicate="INCOMPATIBLE_WITH", object_id="cyclonedds"))

    # Cycles
    graph.add_edge(GraphEdgeData(subject_id="cycle_a", predicate="DEPENDS_ON", object_id="cycle_b"))
    graph.add_edge(GraphEdgeData(subject_id="cycle_b", predicate="DEPENDS_ON", object_id="cycle_a"))

    return graph


@pytest.fixture
def sample_registry():
    return {
        "nav2": ResourceCandidate(id="nav2", name="Nav2", version="1.3.0"),
        "slam_toolbox": ResourceCandidate(id="slam_toolbox", name="SLAM Toolbox", version="2.7.4"),
        "laser_geometry": ResourceCandidate(id="laser_geometry", name="Laser Geometry", version="2.5.0"),
        "fastdds": ResourceCandidate(id="fastdds", name="FastDDS", version="2.14.0"),
        "cyclonedds": ResourceCandidate(id="cyclonedds", name="CycloneDDS", version="0.10.4"),
        "cycle_a": ResourceCandidate(id="cycle_a", name="Cycle Node A", version="1.0.0"),
        "cycle_b": ResourceCandidate(id="cycle_b", name="Cycle Node B", version="1.0.0"),
    }


def test_direct_and_transitive_resolution(sample_graph, sample_registry):
    resolver = DependencyResolver(sample_graph, sample_registry)
    proposal = resolver.resolve([sample_registry["nav2"]])

    assert not proposal.is_fully_resolved
    assert proposal.missing_mandatory_count == 2
    actions = {a.resource_id: a for a in proposal.proposed_actions}
    assert "slam_toolbox" in actions
    assert "laser_geometry" in actions
    assert actions["slam_toolbox"].action == ResolutionActionType.ADD_COMPONENT
    assert "Required by Nav2" in actions["slam_toolbox"].reason


def test_fully_resolved_stack(sample_graph, sample_registry):
    resolver = DependencyResolver(sample_graph, sample_registry)
    stack = [
        sample_registry["nav2"],
        sample_registry["slam_toolbox"],
        sample_registry["laser_geometry"],
    ]
    proposal = resolver.resolve(stack)

    assert proposal.is_fully_resolved
    assert proposal.missing_mandatory_count == 0
    assert len(proposal.conflicts) == 0


def test_incompatibility_conflict_detection(sample_graph, sample_registry):
    resolver = DependencyResolver(sample_graph, sample_registry)
    proposal = resolver.resolve([sample_registry["fastdds"], sample_registry["cyclonedds"]])

    assert not proposal.is_fully_resolved
    assert len(proposal.conflicts) >= 1
    conflict_types = [c.conflict_type for c in proposal.conflicts]
    assert "EXPLICIT_INCOMPATIBILITY" in conflict_types


def test_dependency_cycle_detection(sample_graph, sample_registry):
    resolver = DependencyResolver(sample_graph, sample_registry)
    proposal = resolver.resolve([sample_registry["cycle_a"]])

    assert not proposal.is_fully_resolved
    conflict_types = [c.conflict_type for c in proposal.conflicts]
    assert "DEPENDENCY_CYCLE" in conflict_types


def test_version_mismatch_detection(sample_graph, sample_registry):
    # Set invalid slam_toolbox version 1.5.0
    bad_slam = ResourceCandidate(id="slam_toolbox", name="SLAM Toolbox", version="1.5.0")
    custom_reg = dict(sample_registry)
    custom_reg["slam_toolbox"] = bad_slam

    resolver = DependencyResolver(sample_graph, custom_reg)
    proposal = resolver.resolve([sample_registry["nav2"], bad_slam])

    conflict_types = [c.conflict_type for c in proposal.conflicts]
    assert "VERSION_MISMATCH" in conflict_types


def test_unavailable_dependency_warning(sample_graph):
    # Registry missing slam_toolbox and laser_geometry
    sparse_registry = {"nav2": ResourceCandidate(id="nav2", name="Nav2", version="1.3.0")}
    resolver = DependencyResolver(sample_graph, sparse_registry)
    proposal = resolver.resolve([sparse_registry["nav2"]])

    assert len(proposal.warnings) > 0
    assert any("not currently indexed" in w for w in proposal.warnings)
