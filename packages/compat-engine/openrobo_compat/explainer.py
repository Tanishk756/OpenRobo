from openrobo_compat.models import CompatibilityResult


class CompatibilityExplainer:
    @staticmethod
    def explain_result(result: CompatibilityResult) -> str:
        lines = []
        lines.append(f"Compatibility Status: {result.status.value.upper()}")
        lines.append(f"Evidence Level: {result.evidence_level.value}")
        lines.append(f"Evaluated Resources: {', '.join(result.resource_ids)}")

        if result.environment:
            env_parts = []
            if result.environment.ros_version:
                env_parts.append(f"ROS: {result.environment.ros_version}")
            if result.environment.os:
                env_parts.append(f"OS: {result.environment.os}")
            if result.environment.cpu_architecture:
                env_parts.append(f"Arch: {result.environment.cpu_architecture}")
            if env_parts:
                lines.append(f"Target Environment: [{', '.join(env_parts)}]")

        if result.conflicts:
            lines.append("\nConflicts Detected:")
            for i, conflict in enumerate(result.conflicts, 1):
                lines.append(f"  {i}. [{conflict.conflict_type}] {conflict.message}")
                if conflict.dependency_path:
                    path_str = " -> ".join(conflict.dependency_path)
                    lines.append(f"     Dependency Path: {path_str}")
                if conflict.remediation:
                    lines.append(f"     Remediation: {conflict.remediation}")

        if result.warnings:
            lines.append("\nWarnings:")
            for warn in result.warnings:
                lines.append(f"  - {warn}")

        if result.remediation:
            lines.append(f"\nOverall Recommendation: {result.remediation}")

        return "\n".join(lines)
