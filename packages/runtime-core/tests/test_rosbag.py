"""Unit tests for Rosbag telemetry inspection."""

from openrobo_runtime import RosbagInspector


def test_inspect_missing_bag_dir(tmp_path):
    res = RosbagInspector.inspect_bag_directory(str(tmp_path / "missing_bag"))
    assert "error" in res


def test_inspect_bag_yaml(tmp_path):
    bag_dir = tmp_path / "sample_bag"
    bag_dir.mkdir()
    meta_content = """rosbag2_bagfile_information:
  storage_identifier: sqlite3
  duration:
    nanoseconds: 5000000000
  message_count: 150
  topics_with_message_count:
    - topic_metadata:
        name: /scan
        type: sensor_msgs/msg/LaserScan
      message_count: 150
"""
    (bag_dir / "metadata.yaml").write_text(meta_content)

    res = RosbagInspector.inspect_bag_directory(str(bag_dir))
    assert res["storage_identifier"] == "sqlite3"
    assert res["message_count"] == 150
    assert len(res["topics"]) == 1
    assert res["topics"][0]["name"] == "/scan"
