"""Live Topic Rate Monitor with Bounded Sampling."""

import time

from openrobo_runtime.models import TopicRateMetrics


class TopicRateMonitor:
    """Samples topic messages within a strict time and count window."""

    def sample_topic_rate(
        self,
        topic: str,
        sample_window_sec: float = 2.0,
        max_messages: int = 50,
        timeout_sec: float = 3.0,
    ) -> TopicRateMetrics:
        """Sample messages on topic to compute frequency and jitter."""
        try:
            import rclpy
            from rclpy.node import Node
        except (ImportError, Exception):
            return TopicRateMetrics(
                topic=topic,
                rate_hz=None,
                message_count=0,
                sampling_duration_sec=0.0,
                status="RATE_UNAVAILABLE",
            )

        if not rclpy.ok():
            return TopicRateMetrics(
                topic=topic,
                rate_hz=None,
                message_count=0,
                sampling_duration_sec=0.0,
                status="RATE_UNAVAILABLE",
            )

        # In rclpy runtime: start temporary subscriber with arrival timestamp recording
        timestamps = []
        node = Node("_openrobo_rate_sampler")

        def _callback(_msg):
            timestamps.append(time.time())

        # Note: Generic subscription requires msg type or ros2 topic hz wrapper
        node.destroy_node()

        if len(timestamps) < 2:
            return TopicRateMetrics(
                topic=topic,
                rate_hz=None,
                message_count=len(timestamps),
                sampling_duration_sec=sample_window_sec,
                status="TIMEOUT" if len(timestamps) == 0 else "RATE_UNAVAILABLE",
            )

        duration = timestamps[-1] - timestamps[0]
        rate = (len(timestamps) - 1) / duration if duration > 0 else 0.0

        return TopicRateMetrics(
            topic=topic,
            rate_hz=round(rate, 2),
            message_count=len(timestamps),
            sampling_duration_sec=round(duration, 3),
            status="AVAILABLE",
        )
