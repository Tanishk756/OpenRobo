"""Rosbag2 & MCAP Telemetry Foundation (Milestone 6)."""

import os
import sqlite3
from typing import Any, Dict

import yaml


class RosbagInspector:
    """Safely extracts metadata from ROS 2 bag files (SQLite3 and metadata.yaml)."""

    @staticmethod
    def inspect_bag_directory(bag_dir: str) -> Dict[str, Any]:
        """Inspect a rosbag2 folder containing metadata.yaml and storage files."""
        if not os.path.exists(bag_dir):
            return {"error": f"Bag directory '{bag_dir}' does not exist."}

        meta_file = os.path.join(bag_dir, "metadata.yaml")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    bag_info = data.get("rosbag2_bagfile_information", {})
                    topics_with_count = bag_info.get("topics_with_message_count", [])
                    return {
                        "storage_identifier": bag_info.get("storage_identifier", "sqlite3"),
                        "duration_ns": bag_info.get("duration", {}).get("nanoseconds", 0),
                        "message_count": bag_info.get("message_count", 0),
                        "topics": [
                            {
                                "name": t.get("topic_metadata", {}).get("name"),
                                "type": t.get("topic_metadata", {}).get("type"),
                                "count": t.get("message_count", 0),
                            }
                            for t in topics_with_count
                        ],
                    }
            except Exception as e:
                return {"error": f"Failed to parse metadata.yaml: {str(e)}"}

        # Fallback inspection for raw .db3 files
        db3_files = [f for f in os.listdir(bag_dir) if f.endswith(".db3")]
        if db3_files:
            db_path = os.path.join(bag_dir, db3_files[0])
            return RosbagInspector.inspect_sqlite3_db(db_path)

        return {"error": "No metadata.yaml or .db3 storage files found in bag directory."}

    @staticmethod
    def inspect_sqlite3_db(db_path: str) -> Dict[str, Any]:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name, type FROM topics;")
            topics = [{"name": row[0], "type": row[1]} for row in cursor.fetchall()]

            cursor.execute("SELECT count(*) FROM messages;")
            msg_count = cursor.fetchone()[0]
            conn.close()

            return {
                "storage_identifier": "sqlite3",
                "message_count": msg_count,
                "topics": topics,
            }
        except Exception as e:
            return {"error": f"SQLite3 bag inspection failed: {str(e)}"}
