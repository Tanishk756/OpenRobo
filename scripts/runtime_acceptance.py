#!/usr/bin/env python3
"""OpenRobo Milestone 6.2 - Live Runtime Acceptance & Release Readiness Verification Suite."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Set isolated ROS_DOMAIN_ID immediately before any rclpy initialization
test_domain_id = "42"
os.environ["ROS_DOMAIN_ID"] = test_domain_id

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "packages" / "runtime-core"))
sys.path.insert(0, str(repo_root / "packages" / "schemas"))
sys.path.insert(0, str(repo_root / "packages" / "compat-engine"))
sys.path.insert(0, str(repo_root / "packages" / "workspace-gen"))

from openrobo_runtime.integrations.connection_inspector import ConnectionInspectorAdapter  # noqa: E402
from openrobo_runtime.introspection import ConnectionComparator, QoSEvaluator  # noqa: E402
from openrobo_runtime.models import (  # noqa: E402
    ConnectionInspectorStatus,
    ExpectedTopicContract,
    OverallHealthStatus,
    QoSPolicyCompatibility,
    ReadinessState,
    RuntimeContract,
)
from openrobo_runtime.ros.availability import RosEnvironmentDetector  # noqa: E402
from openrobo_runtime.ros.collector import LiveRosGraphCollector  # noqa: E402


def compute_dir_sha256(directory: Path) -> str:
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(directory):
        dirs.sort()
        for f in sorted(files):
            fp = Path(root) / f
            try:
                hasher.update(fp.read_bytes())
            except Exception:
                pass
    return hasher.hexdigest()


def run_cmd(cmd_list, cwd=None, env=None, timeout=15):
    """Run structured command list without shell=True."""
    p = subprocess.run(
        cmd_list,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        timeout=timeout,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


ALIVE_TALKER = """import rclpy, time
from rclpy.node import Node
from std_msgs.msg import String

rclpy.init()
node = Node('talker')
pub = node.create_publisher(String, '/chatter', 10)

def timer_cb():
    msg = String()
    msg.data = 'Hello World'
    pub.publish(msg)

timer = node.create_timer(0.1, timer_cb)
rclpy.spin(node)
"""

ALIVE_LISTENER = """import rclpy
from rclpy.node import Node
from std_msgs.msg import String

rclpy.init()
node = Node('listener')
sub = node.create_subscription(String, '/chatter', lambda m: None, 10)
rclpy.spin(node)
"""


def main():
    print("=" * 70)
    print("OPENROBO M6.2 LIVE RUNTIME ACCEPTANCE & VERIFICATION SUITE")
    print("=" * 70)

    evidence = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "os": sys.platform,
        "python_version": sys.version.split()[0],
        "phases": {},
        "verdict": "FAILED",
    }

    env = os.environ.copy()

    # PHASE 1
    print("\n[PHASE 1] Discovering Live ROS Environment...")
    detector = RosEnvironmentDetector()
    ros_info = detector.detect()
    print(f"  Status:             {ros_info.status}")
    print(f"  Distro:             {ros_info.distro}")
    print(f"  ROS Version:        {ros_info.ros_version}")
    print(f"  RMW Implementation: {ros_info.rmw_implementation}")
    print(f"  rclpy Available:    {ros_info.rclpy_available}")
    print(f"  ros2 CLI Available: {ros_info.ros2_cli_available}")
    print(f"  ROS Domain ID:      {ros_info.domain_id}")

    if not ros_info.rclpy_available and not ros_info.ros2_cli_available:
        print("[-] FATAL: Neither rclpy nor ros2 CLI is available in this environment.")
        sys.exit(1)

    evidence["phases"]["phase_1_env"] = {
        "status": str(ros_info.status),
        "distro": ros_info.distro,
        "rmw": ros_info.rmw_implementation,
        "rclpy": ros_info.rclpy_available,
        "ros2_cli": ros_info.ros2_cli_available,
        "domain_id": ros_info.domain_id,
    }

    # PHASE 2
    print("\n[PHASE 2] Starting Minimal Live ROS Graph Fixture (talker & listener)...")
    active_procs = []

    try:
        talker_proc = subprocess.Popen(
            [sys.executable, "-c", ALIVE_TALKER],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        active_procs.append(talker_proc)

        listener_proc = subprocess.Popen(
            [sys.executable, "-c", ALIVE_LISTENER],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        active_procs.append(listener_proc)

        time.sleep(3.0)

        code, out_nodes, _ = run_cmd(["ros2", "node", "list"], env=env)
        code, out_topics, _ = run_cmd(["ros2", "topic", "list"], env=env)
        print(f"  Native ros2 node list:\n{out_nodes}")
        print(f"  Native ros2 topic list:\n{out_topics}")

        evidence["phases"]["phase_2_graph_spawn"] = {
            "native_nodes": out_nodes.splitlines(),
            "native_topics": out_topics.splitlines(),
        }

        # PHASE 3
        print("\n[PHASE 3] Executing OpenRobo LiveRosGraphCollector...")
        collector = LiveRosGraphCollector()
        graph_dict = collector.collect()
        collected_nodes = graph_dict.get("nodes", [])
        collected_topics = graph_dict.get("topics", [])
        print(f"  Collector Status: {graph_dict.get('status')}")
        node_names = [n.get("name") for n in collected_nodes]
        topic_names = [t.get("name") for t in collected_topics]
        print(f"  Collected {len(collected_nodes)} nodes: {node_names}")
        print(f"  Collected {len(collected_topics)} topics: {topic_names}")

        assert "talker" in node_names or "/talker" in node_names, "Talker node not observed by collector"
        assert "listener" in node_names or "/listener" in node_names, "Listener node not observed by collector"

        evidence["phases"]["phase_3_live_collector"] = {
            "status": graph_dict.get("status"),
            "nodes": node_names,
            "topics": topic_names,
        }

        # PHASE 4
        print("\n[PHASE 4] Evaluating Valid Runtime Contract against Live Graph...")
        valid_contract = RuntimeContract(
            expected_nodes=["talker", "listener"],
            expected_topics=[
                ExpectedTopicContract(name="/chatter", msg_type="std_msgs/msg/String", required=True)
            ],
            expected_transforms=[],
            expected_services=[],
        )
        comparator = ConnectionComparator()
        eval_result = comparator.compare(
            planned_manifest={"name": "live-acceptance-stack", "version": "1.0.0"},
            observed_nodes=collected_nodes,
            observed_topics=collected_topics,
            runtime_contract=valid_contract,
        )
        print(f"  Overall Status:   {eval_result.overall_status}")
        print(f"  Readiness State:  {eval_result.readiness_state}")
        print(f"  Missing Nodes:    {eval_result.missing_nodes}")
        print(f"  Summary:          {eval_result.summary}")

        assert eval_result.overall_status == OverallHealthStatus.HEALTHY, f"Expected HEALTHY, got {eval_result.overall_status}"
        assert eval_result.readiness_state == ReadinessState.RUNTIME_VERIFIED
        assert len(eval_result.missing_nodes) == 0

        evidence["phases"]["phase_4_contract_healthy"] = {
            "overall_status": str(eval_result.overall_status),
            "readiness_state": str(eval_result.readiness_state),
            "missing_nodes": eval_result.missing_nodes,
            "summary": eval_result.summary,
        }

        # PHASE 5
        print("\n[PHASE 5] Evaluating Intentional Failure Contracts...")
        missing_node_contract = RuntimeContract(
            expected_nodes=["talker", "listener", "nonexistent_robot_node"],
            expected_topics=[],
        )
        fail_result_1 = comparator.compare(
            planned_manifest={},
            observed_nodes=collected_nodes,
            observed_topics=collected_topics,
            runtime_contract=missing_node_contract,
        )
        print(f"  5a (Missing Node) Status: {fail_result_1.overall_status}, Missing: {fail_result_1.missing_nodes}")
        assert "nonexistent_robot_node" in fail_result_1.missing_nodes
        assert fail_result_1.overall_status in [OverallHealthStatus.DEGRADED, OverallHealthStatus.FAILED]

        mismatch_contract = RuntimeContract(
            expected_nodes=["talker"],
            expected_topics=[
                ExpectedTopicContract(name="/chatter", msg_type="sensor_msgs/msg/LaserScan", required=True)
            ],
        )
        fail_result_2 = comparator.compare(
            planned_manifest={},
            observed_nodes=collected_nodes,
            observed_topics=collected_topics,
            runtime_contract=mismatch_contract,
        )
        mismatch_diags = [c for c in fail_result_2.connections if c.status == "TYPE_MISMATCH"]
        print(f"  5b (Type Mismatch) Status: {fail_result_2.overall_status}, Mismatches: {[c.topic for c in mismatch_diags]}")
        assert len(mismatch_diags) > 0

        evidence["phases"]["phase_5_intentional_failures"] = {
            "missing_node_detected": "nonexistent_robot_node" in fail_result_1.missing_nodes,
            "type_mismatch_detected": len(mismatch_diags) > 0,
        }

    finally:
        print("\n[CLEANUP] Stopping Phase 2-5 test graph processes...")
        for p in active_procs:
            p.terminate()
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()
        time.sleep(1.0)

    # PHASE 6
    print("\n[PHASE 6] Creating Real Live QoS Mismatch Endpoints...")
    qos_procs = []
    try:
        best_effort_pub_code = """import rclpy, time
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
rclpy.init()
node = Node('qos_be_pub')
qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
pub = node.create_publisher(String, '/qos_test_topic', qos)
def cb():
    msg = String(); msg.data = 'be_test'
    pub.publish(msg)
timer = node.create_timer(0.1, cb)
rclpy.spin(node)
"""
        p_pub = subprocess.Popen(
            [sys.executable, "-c", best_effort_pub_code],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        qos_procs.append(p_pub)

        reliable_sub_code = """import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
rclpy.init()
node = Node('qos_rel_sub')
qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
sub = node.create_subscription(String, '/qos_test_topic', lambda m: None, qos)
rclpy.spin(node)
"""
        p_sub = subprocess.Popen(
            [sys.executable, "-c", reliable_sub_code],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        qos_procs.append(p_sub)

        time.sleep(3.0)

        # Collect live ROS graph and extract actual observed endpoint QoS metadata
        collector = LiveRosGraphCollector()
        qos_graph = collector.collect()
        topics = qos_graph.get("topics", [])
        qos_topic = next((t for t in topics if t.get("name") == "/qos_test_topic"), None)
        print(f"  Observed live /qos_test_topic metadata from collector: {qos_topic}")
        assert qos_topic is not None, "Failed to observe /qos_test_topic in live graph"

        # Pass the extracted live observed QoS dictionaries directly into QoSEvaluator
        pub_qos = qos_topic.get("publisher_qos", {})
        sub_qos = qos_topic.get("subscriber_qos", {})
        print(f"  Extracted live publisher QoS:  {pub_qos}")
        print(f"  Extracted live subscriber QoS: {sub_qos}")

        evaluator = QoSEvaluator()
        compat, reason = evaluator.evaluate_compatibility(pub_qos, sub_qos)
        print(f"  QoS Evaluation: {compat} ({reason})")
        assert compat == QoSPolicyCompatibility.INCOMPATIBLE, f"Expected INCOMPATIBLE, got {compat}"

        evidence["phases"]["phase_6_qos_test"] = {
            "topic_detected": True,
            "publisher_qos": pub_qos,
            "subscriber_qos": sub_qos,
            "evaluation": str(compat),
            "reason": reason,
        }
    finally:
        print("\n[CLEANUP] Stopping Phase 6 QoS test processes...")
        for p in qos_procs:
            p.terminate()
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()
        time.sleep(1.0)

    # PHASE 7
    print("\n[PHASE 7] Probing Connection Inspector Adapter...")
    ci_adapter = ConnectionInspectorAdapter()
    ci_info = ci_adapter.detect()
    print(f"  Status:              {ci_info.status}")
    print(f"  Installed:           {ci_info.status == ConnectionInspectorStatus.INSTALLED}")
    print(f"  Version:             {ci_info.version}")
    print(f"  Distro Supported:    {ci_info.distro_support}")
    print(f"  Discovered Binaries: {ci_info.executables}")

    cli_result = {}
    is_installed = ci_info.status == ConnectionInspectorStatus.INSTALLED
    if is_installed and "inspect_cli" in ci_info.executables:
        print("  Running connection_inspector CLI inspect_cli...")
        cli_result = ci_adapter.run_cli_inspection(timeout_sec=5)
        print(f"  CLI Exit Code: {cli_result.get('exit_code')}")
        print(f"  CLI Stdout:    {cli_result.get('stdout', '')[:200]}")

    evidence["phases"]["phase_7_connection_inspector"] = {
        "status": str(ci_info.status),
        "installed": is_installed,
        "version": ci_info.version,
        "distro_supported": str(ci_info.distro_support),
        "executables": ci_info.executables,
        "cli_executed": cli_result.get("executed", False),
        "cli_exit_code": cli_result.get("exit_code"),
    }

    # PHASE 8
    print("\n[PHASE 8] Probing Gazebo Simulator...")
    gz_binary = shutil.which("gz") or shutil.which("ign")
    gz_ver_out = ""
    if gz_binary:
        code, gz_ver_out, _ = run_cmd([gz_binary, "sim", "--version"])
    print(f"  Gazebo Binary:  {gz_binary}")
    print(f"  Gazebo Version: {gz_ver_out}")

    evidence["phases"]["phase_8_gazebo"] = {
        "binary": gz_binary,
        "version": gz_ver_out,
        "detected": bool(gz_binary),
    }

    # PHASE 9
    print("\n[PHASE 9] Executing Real Colcon Build on Generated Workspace...")
    fixture_dir = Path("/tmp/openrobo_m6_acceptance_ws")
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)

    src_dir = fixture_dir / "src" / "openrobo_bringup"
    src_dir.mkdir(parents=True, exist_ok=True)

    # Note: openrobo-test@example.com is an RFC 2606 reserved test address used solely for fixture validation
    (src_dir / "package.xml").write_text("""<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>openrobo_bringup</name>
  <version>1.0.0</version>
  <description>OpenRobo Acceptance Fixture Package (Test Only)</description>
  <!-- Explicit test fixture maintainer per RFC 2606 -->
  <maintainer email="openrobo-test@example.com">OpenRobo Test Maintainer</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

  <depend>rclpy</depend>
  <depend>std_msgs</depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
""")

    (src_dir / "CMakeLists.txt").write_text("""cmake_minimum_required(VERSION 3.8)
project(openrobo_bringup)

find_package(ament_cmake REQUIRED)

ament_package()
""")

    ws_digest = compute_dir_sha256(fixture_dir / "src")
    print(f"  Fixture Workspace Digest (src/): {ws_digest}")

    build_start = time.time()
    colcon_code, colcon_out, colcon_err = run_cmd(
        ["colcon", "build"],
        cwd=fixture_dir,
        env=env,
        timeout=120,
    )
    build_duration = time.time() - build_start
    print(f"  Colcon Exit Code: {colcon_code} (in {build_duration:.2f}s)")
    print(f"  Colcon Output:    {colcon_out[:300]}")

    assert colcon_code == 0, f"Colcon build failed with exit code {colcon_code}: {colcon_err}"

    evidence["phases"]["phase_9_colcon_build"] = {
        "status": "BUILD_VERIFIED" if colcon_code == 0 else "BUILD_FAILED",
        "exit_code": colcon_code,
        "duration_sec": round(build_duration, 2),
        "workspace_digest": ws_digest,
        "distro": ros_info.distro,
    }

    # PHASE 10
    print("\n[PHASE 10] Checking Docker Availability...")
    docker_bin = shutil.which("docker")
    docker_avail = False
    if docker_bin:
        code, out, _ = run_cmd([docker_bin, "version", "--format", "{{.Server.Version}}"])
        docker_avail = (code == 0 and bool(out.strip()))
    print(f"  Docker Daemon Available: {docker_avail}")

    evidence["phases"]["phase_10_docker"] = {
        "daemon_available": docker_avail,
        "status": "DOCKER_AVAILABLE" if docker_avail else "NOT_EXECUTED",
    }

    # PHASE 11
    evidence["verdict"] = "RUNTIME_VERIFIED"
    print("\n" + "=" * 70)
    print("ALL M6.2 ACCEPTANCE CRITERIA SATISFIED: RUNTIME_VERIFIED")
    print("=" * 70)

    evidence_path = repo_root / "docs" / "acceptance_evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2))
    print(f"Saved live acceptance evidence to: {evidence_path}")


if __name__ == "__main__":
    main()
