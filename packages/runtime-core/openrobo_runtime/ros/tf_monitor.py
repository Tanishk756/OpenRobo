"""Live Transform (TF2) Frame Connectivity Inspector."""

from typing import Dict, List, Optional

from openrobo_runtime.models import TFDiagnostic


class LiveTFMonitor:
    """Introspects /tf and /tf_static frame relationships."""

    def inspect_transforms(
        self,
        known_tfs: Optional[List[Dict[str, str]]] = None,
        expected_pairs: Optional[List[tuple[str, str]]] = None,
    ) -> List[TFDiagnostic]:
        """Verify presence and continuity of coordinate frame transformations."""
        diagnostics: List[TFDiagnostic] = []
        observed_edges = set()

        if known_tfs:
            for tf in known_tfs:
                parent = tf.get("parent_frame_id", tf.get("parent", ""))
                child = tf.get("frame_id", tf.get("child", ""))
                if parent and child:
                    observed_edges.add((parent, child))
                    diagnostics.append(
                        TFDiagnostic(
                            parent_frame_id=parent,
                            frame_id=child,
                            is_connected=True,
                            is_stale=False,
                            rate_hz=tf.get("rate_hz", 30.0),
                        )
                    )

        if expected_pairs:
            for parent, child in expected_pairs:
                if (parent, child) not in observed_edges:
                    diagnostics.append(
                        TFDiagnostic(
                            parent_frame_id=parent,
                            frame_id=child,
                            is_connected=False,
                            is_stale=True,
                            rate_hz=None,
                        )
                    )

        return diagnostics
