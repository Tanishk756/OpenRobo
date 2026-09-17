"""ROS 2 QoS Profile Compatibility Evaluator."""

from typing import Dict, Tuple

from openrobo_runtime.models import QoSPolicyCompatibility


class QoSEvaluator:
    """Evaluates QoS policy compatibility between ROS 2 publishers and subscribers."""

    @staticmethod
    def evaluate_compatibility(
        pub_qos: Dict[str, str],
        sub_qos: Dict[str, str],
    ) -> Tuple[QoSPolicyCompatibility, str]:
        """
        Evaluate compatibility according to standard ROS 2 QoS matching rules:
        - Reliability: Publisher RELIABLE matches RELIABLE or BEST_EFFORT.
          Publisher BEST_EFFORT with Subscriber RELIABLE is INCOMPATIBLE.
        - Durability: Publisher TRANSIENT_LOCAL matches TRANSIENT_LOCAL or VOLATILE.
          Publisher VOLATILE with Subscriber TRANSIENT_LOCAL is INCOMPATIBLE.
        """
        pub_rel = pub_qos.get("reliability", "RELIABLE").upper()
        sub_rel = sub_qos.get("reliability", "RELIABLE").upper()

        pub_dur = pub_qos.get("durability", "VOLATILE").upper()
        sub_dur = sub_qos.get("durability", "VOLATILE").upper()

        # 1. Reliability Check
        if pub_rel == "BEST_EFFORT" and sub_rel == "RELIABLE":
            return (
                QoSPolicyCompatibility.INCOMPATIBLE,
                "Incompatible Reliability: Publisher offers BEST_EFFORT but Subscriber requests RELIABLE.",
            )

        # 2. Durability Check
        if pub_dur == "VOLATILE" and sub_dur == "TRANSIENT_LOCAL":
            return (
                QoSPolicyCompatibility.INCOMPATIBLE,
                "Incompatible Durability: Publisher offers VOLATILE but Subscriber requests TRANSIENT_LOCAL.",
            )

        return QoSPolicyCompatibility.COMPATIBLE, "QoS profiles are compatible."
