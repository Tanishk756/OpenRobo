"""TF2 Transform Tree Inspector."""

from typing import Any, Dict, List

from openrobo_runtime.models import TFDiagnostic


class TFInspector:
    """Inspects TF2 coordinate frame transformations."""

    @staticmethod
    def inspect_frames(frames_data: List[Dict[str, Any]]) -> List[TFDiagnostic]:
        diagnostics = []
        for f in frames_data:
            fid = f.get("frame_id", "unknown")
            pid = f.get("parent_frame_id", "unknown")
            is_conn = f.get("is_connected", True)
            is_stale = f.get("is_stale", False)
            rate = f.get("rate_hz")

            diagnostics.append(
                TFDiagnostic(
                    frame_id=fid,
                    parent_frame_id=pid,
                    is_connected=is_conn,
                    is_stale=is_stale,
                    rate_hz=rate,
                )
            )
        return diagnostics
