from typing import Dict, List, Optional, Set

from openrobo_compat.graph import OpenRoboGraph
from openrobo_compat.models import (
    ConflictDetail,
    EnvironmentTarget,
    ProposedComponentAction,
    ResolutionActionType,
    ResolutionProposal,
    ResourceCandidate,
)
from openrobo_compat.semver import matches_version_constraint


class DependencyResolver:
    """
    Deterministic dependency and version resolver for robotics stacks.
    Inspects graph relationships (DEPENDS_ON, REQUIRES, INCOMPATIBLE_WITH, PROVIDES)
    to identify missing requirements, version clashes, cycles, and generate
    actionable, non-destructive resolution proposals.
    """

    def __init__(
        self,
        graph: OpenRoboGraph,
        available_registry: Optional[Dict[str, ResourceCandidate]] = None,
    ):
        self.graph = graph
        self.registry = available_registry or {}

    def resolve(
        self,
        selected_resources: List[ResourceCandidate],
        environment: Optional[EnvironmentTarget] = None,
        max_depth: int = 10,
    ) -> ResolutionProposal:
        selected_ids: Set[str] = {r.id for r in selected_resources}
        selected_by_id: Dict[str, ResourceCandidate] = {r.id: r for r in selected_resources}

        proposed_actions: List[ProposedComponentAction] = []
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []

        discovered_to_add: Set[str] = set()
        queue: List[tuple[str, str, int]] = []  # (resource_id, parent_id, depth)

        # Initial queue population from selected resources
        for res in selected_resources:
            out_deps = self.graph.get_edges(subject_id=res.id, predicate="DEPENDS_ON")
            out_reqs = self.graph.get_edges(subject_id=res.id, predicate="REQUIRES")
            for edge in out_deps + out_reqs:
                dep_id = edge.object_id
                if dep_id not in selected_ids and dep_id not in discovered_to_add:
                    queue.append((dep_id, res.id, 1))

        # Transitive discovery
        while queue:
            dep_id, parent_id, depth = queue.pop(0)
            if depth > max_depth or dep_id in selected_ids or dep_id in discovered_to_add:
                continue

            discovered_to_add.add(dep_id)
            parent_name = selected_by_id.get(parent_id, ResourceCandidate(id=parent_id, name=parent_id)).name

            if dep_id in self.registry:
                reg_candidate = self.registry[dep_id]
                proposed_actions.append(
                    ProposedComponentAction(
                        action=ResolutionActionType.ADD_COMPONENT,
                        resource_id=dep_id,
                        name=reg_candidate.name,
                        version=reg_candidate.version,
                        category=reg_candidate.type,
                        reason=f"Required by {parent_name}",
                        required_by=parent_id,
                        optional=False,
                    )
                )
                # Expand transitive dependencies of the proposed candidate
                out_deps = self.graph.get_edges(subject_id=dep_id, predicate="DEPENDS_ON")
                out_reqs = self.graph.get_edges(subject_id=dep_id, predicate="REQUIRES")
                out_edges = out_deps + out_reqs
                for e in out_edges:
                    if e.object_id not in selected_ids and e.object_id not in discovered_to_add:
                        queue.append((e.object_id, dep_id, depth + 1))
            else:
                warnings.append(f"Required dependency '{dep_id}' (required by {parent_name}) is not currently indexed in the registry.")

        # Check explicit incompatibility conflicts between selected resources and proposed additions
        all_candidate_ids = selected_ids.union(discovered_to_add)
        for res_id in all_candidate_ids:
            incomp_edges = self.graph.get_edges(subject_id=res_id, predicate="INCOMPATIBLE_WITH")
            for edge in incomp_edges:
                if edge.object_id in all_candidate_ids:
                    src_cand = selected_by_id.get(res_id) or self.registry.get(res_id) or ResourceCandidate(id=res_id, name=res_id)
                    tgt_cand = (
                        selected_by_id.get(edge.object_id)
                        or self.registry.get(edge.object_id)
                        or ResourceCandidate(id=edge.object_id, name=edge.object_id)
                    )
                    res_name = src_cand.name
                    target_name = tgt_cand.name
                    conflicts.append(
                        ConflictDetail(
                            source_id=res_id,
                            target_id=edge.object_id,
                            conflict_type="EXPLICIT_INCOMPATIBILITY",
                            message=f"'{res_name}' is explicitly incompatible with '{target_name}'.",
                            dependency_path=[res_id, edge.object_id],
                            remediation=f"Remove '{res_name}' or replace '{target_name}' with an alternative component.",
                        )
                    )

        # Check for dependency cycles
        cycles = self.graph.find_dependency_cycles()
        for cycle in cycles:
            # Check if cycle involves current stack
            if any(node in all_candidate_ids for node in cycle):
                conflicts.append(
                    ConflictDetail(
                        source_id=cycle[0],
                        target_id=cycle[-1] if len(cycle) > 1 else None,
                        conflict_type="DEPENDENCY_CYCLE",
                        message=f"Circular dependency detected: {' -> '.join(cycle)}",
                        dependency_path=cycle,
                        remediation="Break circular dependency by decoupling package requirements.",
                    )
                )

        # Check version constraints
        for res in selected_resources:
            out_deps = self.graph.get_edges(subject_id=res.id, predicate="DEPENDS_ON")
            for edge in out_deps:
                v_constraint = (edge.properties or {}).get("version_constraint")
                if v_constraint and edge.object_id in selected_by_id:
                    target_res = selected_by_id[edge.object_id]
                    matches, expl = matches_version_constraint(target_res.version, v_constraint)
                    if not matches:
                        conflicts.append(
                            ConflictDetail(
                                source_id=res.id,
                                target_id=edge.object_id,
                                conflict_type="VERSION_MISMATCH",
                                message=(
                                f"'{res.name}' requires '{target_res.name}' constraint "
                                f"'{v_constraint}', but '{target_res.version}' is selected: {expl}"
                            ),
                                dependency_path=[res.id, edge.object_id],
                                remediation=f"Update '{target_res.name}' version to satisfy constraint '{v_constraint}'.",
                            )
                        )

        missing_mandatory_count = len([a for a in proposed_actions if not a.optional])
        missing_optional_count = len([a for a in proposed_actions if a.optional])
        is_fully_resolved = (missing_mandatory_count == 0) and (len(conflicts) == 0)

        summary = (
            "Stack is fully resolved and free of structural conflicts."
            if is_fully_resolved
            else f"Stack has {missing_mandatory_count} missing dependencies and {len(conflicts)} active conflicts."
        )

        return ResolutionProposal(
            is_fully_resolved=is_fully_resolved,
            missing_mandatory_count=missing_mandatory_count,
            missing_optional_count=missing_optional_count,
            proposed_actions=proposed_actions,
            conflicts=conflicts,
            warnings=warnings,
            summary=summary,
        )
