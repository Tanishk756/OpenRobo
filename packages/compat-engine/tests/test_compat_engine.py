import time

import pytest
from openrobo_compat import (
    CompatibilityEngine,
    CompatibilityExplainer,
    CompatibilityStatus,
    EnvironmentTarget,
    GraphEdgeData,
    OpenRoboGraph,
    ResourceCandidate,
    matches_version_constraint,
)


@pytest.fixture
def sample_graph():
    graph = OpenRoboGraph()
    # Edges
    graph.add_edge(
        GraphEdgeData(
            subject_id="nav2",
            predicate="depends-on",
            object_id="ros2_control",
            properties={"min_version": "2.0.0", "version_constraint": ">=2.0.0"},
        )
    )
    graph.add_edge(
        GraphEdgeData(
            subject_id="nav2", predicate="compatible-with", object_id="slam_toolbox", properties={"evidence_level": "ci_verified"}
        )
    )
    graph.add_edge(
        GraphEdgeData(subject_id="nav2", predicate="tested-with", object_id="turtlebot3", properties={"evidence_level": "vendor_tested"})
    )
    graph.add_edge(
        GraphEdgeData(
            subject_id="cyclonedds", predicate="conflicts-with", object_id="fast_dds", properties={"reason": "DDS middleware conflict"}
        )
    )
    return graph


def test_semver_matching():
    # Caret
    ok, _ = matches_version_constraint("1.2.5", "^1.2.0")
    assert ok is True
    ok, _ = matches_version_constraint("2.0.0", "^1.2.0")
    assert ok is False

    # Tilde
    ok, _ = matches_version_constraint("1.2.5", "~1.2.0")
    assert ok is True
    ok, _ = matches_version_constraint("1.3.0", "~1.2.0")
    assert ok is False

    # Range
    ok, _ = matches_version_constraint("2.5.0", ">=2.1.0,<3.0.0")
    assert ok is True
    ok, _ = matches_version_constraint("3.1.0", ">=2.1.0,<3.0.0")
    assert ok is False

    # Exact
    ok, _ = matches_version_constraint("1.5.2", "==1.5.2")
    assert ok is True

    # Wildcard
    ok, _ = matches_version_constraint("1.5.2", "1.x")
    assert ok is True
    ok, _ = matches_version_constraint("2.0.0", "1.x")
    assert ok is False

    # Empty / None
    ok, _ = matches_version_constraint(None, "^1.0.0")
    assert ok is False
    ok, _ = matches_version_constraint("1.0.0", None)
    assert ok is True


def test_ros_distribution_mismatch(sample_graph):
    engine = CompatibilityEngine(graph=sample_graph)
    nav2 = ResourceCandidate(id="nav2", name="Nav2", version="1.3.0", platforms={"ros": ["Jazzy"], "architecture": ["x86_64", "aarch64"]})

    # Incompatible with Humble environment
    env_humble = EnvironmentTarget(ros_version="Humble")
    res = engine.evaluate_stack([nav2], environment=env_humble)
    assert res.status == CompatibilityStatus.INCOMPATIBLE
    assert any(c.conflict_type == "ros_distribution_mismatch" for c in res.conflicts)
    assert "Jazzy" in res.conflicts[0].message
    assert res.remediation is not None

    # Compatible with Jazzy environment
    env_jazzy = EnvironmentTarget(ros_version="Jazzy")
    res_ok = engine.evaluate_stack([nav2], environment=env_jazzy)
    assert res_ok.status == CompatibilityStatus.COMPATIBLE


def test_os_and_cpu_arch_compatibility(sample_graph):
    engine = CompatibilityEngine(graph=sample_graph)
    cand = ResourceCandidate(id="driver", name="Driver", version="1.0.0", platforms={"os": ["Ubuntu", "Linux"], "architecture": ["x86_64"]})

    # Architecture mismatch
    env_arm = EnvironmentTarget(cpu_architecture="aarch64")
    res_arm = engine.evaluate_stack([cand], environment=env_arm)
    assert res_arm.status == CompatibilityStatus.INCOMPATIBLE
    assert any(c.conflict_type == "cpu_architecture_mismatch" for c in res_arm.conflicts)

    # OS mismatch
    env_win = EnvironmentTarget(os="Windows")
    res_win = engine.evaluate_stack([cand], environment=env_win)
    assert res_win.status == CompatibilityStatus.INCOMPATIBLE
    assert any(c.conflict_type == "operating_system_mismatch" for c in res_win.conflicts)

    # All match
    env_valid = EnvironmentTarget(os="Ubuntu", cpu_architecture="x86_64")
    res_valid = engine.evaluate_stack([cand], environment=env_valid)
    assert res_valid.status == CompatibilityStatus.COMPATIBLE


def test_semver_constraint_violation(sample_graph):
    engine = CompatibilityEngine(graph=sample_graph)
    nav2 = ResourceCandidate(id="nav2", name="Nav2", version="1.3.0")
    # Requires >=2.0.0, but version 1.5.0 provided
    ros2_ctl_old = ResourceCandidate(id="ros2_control", name="ros2_control", version="1.5.0")

    res = engine.evaluate_stack([nav2, ros2_ctl_old])
    assert res.status == CompatibilityStatus.INCOMPATIBLE
    assert any(c.conflict_type == "semver_constraint_violation" for c in res.conflicts)

    # Version 2.2.0 provided -> Pass
    ros2_ctl_new = ResourceCandidate(id="ros2_control", name="ros2_control", version="2.2.0")
    res_pass = engine.evaluate_stack([nav2, ros2_ctl_new])
    assert res_pass.status == CompatibilityStatus.COMPATIBLE


def test_explicit_conflicts(sample_graph):
    engine = CompatibilityEngine(graph=sample_graph)
    dds1 = ResourceCandidate(id="cyclonedds", name="Eclipse CycloneDDS")
    dds2 = ResourceCandidate(id="fast_dds", name="eProsima Fast-DDS")

    res = engine.evaluate_stack([dds1, dds2])
    assert res.status == CompatibilityStatus.INCOMPATIBLE
    assert any(c.conflict_type == "explicit_conflict" for c in res.conflicts)
    assert res.remediation is not None


def test_dependency_cycle_detection():
    graph = OpenRoboGraph()
    graph.add_edge(GraphEdgeData(subject_id="pkgA", predicate="depends-on", object_id="pkgB"))
    graph.add_edge(GraphEdgeData(subject_id="pkgB", predicate="depends-on", object_id="pkgC"))
    graph.add_edge(GraphEdgeData(subject_id="pkgC", predicate="depends-on", object_id="pkgA"))

    engine = CompatibilityEngine(graph=graph)
    a = ResourceCandidate(id="pkgA", name="Pkg A")
    b = ResourceCandidate(id="pkgB", name="Pkg B")
    c = ResourceCandidate(id="pkgC", name="Pkg C")

    res = engine.evaluate_stack([a, b, c])
    assert res.status == CompatibilityStatus.CONDITIONAL
    assert any(conf.conflict_type == "circular_dependency" for conf in res.conflicts)


def test_transitive_dependency_path(sample_graph):
    # Add chain A -> B -> C
    sample_graph.add_edge(GraphEdgeData(subject_id="ros2_control", predicate="depends-on", object_id="hardware_interface"))
    trans_deps = sample_graph.get_transitive_dependencies("nav2")
    assert "ros2_control" in trans_deps
    assert "hardware_interface" in trans_deps


def test_explainer_output(sample_graph):
    engine = CompatibilityEngine(graph=sample_graph)
    nav2 = ResourceCandidate(id="nav2", name="Nav2", version="1.3.0", platforms={"ros": ["Jazzy"]})
    res = engine.evaluate_stack([nav2], environment=EnvironmentTarget(ros_version="Humble"))

    explanation = CompatibilityExplainer.explain_result(res)
    assert "Compatibility Status: INCOMPATIBLE" in explanation
    assert "ROS: Humble" in explanation
    assert "ros_distribution_mismatch" in explanation
    assert "Remediation:" in explanation


def test_matrix_evaluation_and_symmetry(sample_graph):
    engine = CompatibilityEngine(graph=sample_graph)
    c1 = ResourceCandidate(id="nav2", name="Nav2", platforms={"ros": ["Humble", "Jazzy"]})
    c2 = ResourceCandidate(id="slam_toolbox", name="SLAM Toolbox", platforms={"ros": ["Humble", "Jazzy"]})
    c3 = ResourceCandidate(id="cyclonedds", name="CycloneDDS")
    c4 = ResourceCandidate(id="fast_dds", name="FastDDS")

    candidates = [c1, c2, c3, c4]
    matrix_resp = engine.evaluate_matrix(candidates)

    assert len(matrix_resp.candidate_ids) == 4
    assert matrix_resp.summary["incompatible"] >= 1
    # Check pairwise matrix presence
    assert "nav2" in matrix_resp.matrix
    assert "slam_toolbox" in matrix_resp.matrix["nav2"]
    assert matrix_resp.matrix["cyclonedds"]["fast_dds"].status == CompatibilityStatus.INCOMPATIBLE


def test_50_node_matrix_performance_benchmark():
    graph = OpenRoboGraph()
    candidates = []
    for i in range(50):
        node_id = f"pkg_{i:02d}"
        candidates.append(
            ResourceCandidate(
                id=node_id,
                name=f"Package {i}",
                version="1.0.0",
                platforms={"ros": ["Humble", "Jazzy"], "architecture": ["x86_64", "aarch64"], "os": ["Ubuntu"]},
            )
        )
        if i > 0:
            graph.add_edge(
                GraphEdgeData(
                    subject_id=node_id, predicate="depends-on", object_id=f"pkg_{i - 1:02d}", properties={"version_constraint": "^1.0.0"}
                )
            )

    engine = CompatibilityEngine(graph=graph)

    # Benchmark matrix evaluation (best of 3 runs to measure true engine throughput)
    durations = []
    matrix_resp = None
    for _ in range(3):
        start_time = time.perf_counter()
        matrix_resp = engine.evaluate_matrix(candidates, environment=EnvironmentTarget(ros_version="Jazzy", cpu_architecture="x86_64"))
        durations.append((time.perf_counter() - start_time) * 1000.0)
    duration_ms = min(durations)

    print(f"\n50-Node Compatibility Matrix Evaluation Duration: {duration_ms:.2f} ms")
    assert len(matrix_resp.candidate_ids) == 50
    assert matrix_resp.summary["compatible"] == 2500  # 50 x 50
    # Requirement: <50ms for 50-node candidate graph
    assert duration_ms < 50.0, f"Matrix evaluation took {duration_ms:.2f} ms, expected <50 ms"
