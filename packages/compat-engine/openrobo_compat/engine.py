from typing import Dict, List, Optional, Set

from openrobo_compat.graph import GraphEdgeData, OpenRoboGraph
from openrobo_compat.models import (
    CompatibilityMatrixResponse,
    CompatibilityResult,
    CompatibilityStatus,
    ConflictDetail,
    EnvironmentTarget,
    EvidenceLevel,
    ResourceCandidate,
    ResourceCompatibilityProfile,
    RuleEvaluation,
    utc_now_str,
)
from openrobo_compat.rules import (
    BaseRule,
    CpuArchitectureRule,
    DependencyCycleRule,
    ExplicitConflictRule,
    ExplicitTestedWithRule,
    HardwareAndCapabilityRule,
    OperatingSystemRule,
    RosDistributionRule,
    SemVerConstraintRule,
    get_candidate_ros_distros,
)


class CompatibilityEngine:
    def __init__(self, graph: Optional[OpenRoboGraph] = None):
        self.graph = graph or OpenRoboGraph()
        self.rules: List[BaseRule] = [
            RosDistributionRule(),
            OperatingSystemRule(),
            CpuArchitectureRule(),
            SemVerConstraintRule(),
            ExplicitConflictRule(),
            DependencyCycleRule(),
            HardwareAndCapabilityRule(),
            ExplicitTestedWithRule(),
        ]

    def add_edge(self, edge: GraphEdgeData):
        self.graph.add_edge(edge)

    def add_resource(self, candidate: ResourceCandidate):
        self.graph.add_node(
            candidate.id,
            properties={
                "name": candidate.name,
                "version": candidate.version,
                "type": candidate.type,
                "platforms": candidate.platforms,
                "capabilities": candidate.capabilities,
                "metadata_json": candidate.metadata_json,
                "evidence_level": candidate.evidence_level,
            },
        )

    def evaluate_stack(
        self,
        candidates: List[ResourceCandidate],
        environment: Optional[EnvironmentTarget] = None,
    ) -> CompatibilityResult:
        sorted_candidates = sorted(candidates, key=lambda c: c.id)
        resource_ids = [c.id for c in sorted_candidates]

        all_rule_evaluations: List[RuleEvaluation] = []
        all_conflicts: List[ConflictDetail] = []
        all_warnings: List[str] = []
        highest_evidence = EvidenceLevel.INFERRED

        for c in sorted_candidates:
            if not self.graph.has_node(c.id):
                self.add_resource(c)

        for rule in self.rules:
            eval_result, conflicts, warnings = rule.evaluate(sorted_candidates, self.graph, environment)
            all_rule_evaluations.append(eval_result)
            all_conflicts.extend(conflicts)
            all_warnings.extend(warnings)

            if eval_result.evidence_level == EvidenceLevel.CI_VERIFIED:
                highest_evidence = EvidenceLevel.CI_VERIFIED
            elif eval_result.evidence_level == EvidenceLevel.VENDOR_TESTED and highest_evidence != EvidenceLevel.CI_VERIFIED:
                highest_evidence = EvidenceLevel.VENDOR_TESTED

        status = CompatibilityStatus.COMPATIBLE
        if any(e.status == CompatibilityStatus.INCOMPATIBLE for e in all_rule_evaluations):
            status = CompatibilityStatus.INCOMPATIBLE
        elif any(e.status == CompatibilityStatus.CONDITIONAL for e in all_rule_evaluations):
            status = CompatibilityStatus.CONDITIONAL
        elif all(e.status == CompatibilityStatus.UNKNOWN for e in all_rule_evaluations):
            status = CompatibilityStatus.UNKNOWN

        remediation = None
        if all_conflicts:
            remediation = all_conflicts[0].remediation

        dependency_paths = []
        if len(sorted_candidates) > 1 and all_conflicts:
            for c in sorted_candidates:
                trans_deps = self.graph.get_transitive_dependencies(c.id)
                if trans_deps:
                    dependency_paths.append([c.id] + trans_deps)

        return CompatibilityResult.model_construct(
            status=status,
            resource_ids=resource_ids,
            environment=environment,
            rule_evaluations=all_rule_evaluations,
            conflicts=all_conflicts,
            warnings=sorted(list(set(all_warnings))),
            missing_requirements=[],
            dependency_paths=dependency_paths,
            evidence_level=highest_evidence,
            remediation=remediation,
            evaluated_at=utc_now_str(),
        )

    def evaluate_pair(
        self,
        candidate_a: ResourceCandidate,
        candidate_b: ResourceCandidate,
        environment: Optional[EnvironmentTarget] = None,
    ) -> CompatibilityResult:
        return self.evaluate_stack([candidate_a, candidate_b], environment=environment)

    def evaluate_matrix(
        self,
        candidates: List[ResourceCandidate],
        environment: Optional[EnvironmentTarget] = None,
    ) -> CompatibilityMatrixResponse:
        sorted_candidates = sorted(candidates, key=lambda c: c.id)
        candidate_ids = [c.id for c in sorted_candidates]
        matrix: Dict[str, Dict[str, CompatibilityResult]] = {cid: {} for cid in candidate_ids}
        summary: Dict[str, int] = {
            "compatible": 0,
            "conditional": 0,
            "incompatible": 0,
            "unknown": 0,
        }

        # Pre-seed graph nodes
        for c in sorted_candidates:
            if not self.graph.has_node(c.id):
                self.add_resource(c)

        edge_set = set(self.graph.graph.edges())

        # 1. Precompute self-evaluations
        self_evals: Dict[str, CompatibilityResult] = {}
        cand_distros_map: Dict[str, Set[str]] = {}
        for c in sorted_candidates:
            res = self.evaluate_stack([c], environment=environment)
            self_evals[c.id] = res
            matrix[c.id][c.id] = res
            summary[res.status.value] += 1
            d_list = get_candidate_ros_distros(c)
            cand_distros_map[c.id] = {d.lower() for d in d_list} if d_list else set()

        now_str = utc_now_str()

        # 2. Pairwise evaluations with fast-path edge set checking
        n = len(sorted_candidates)
        for i in range(n):
            c1 = sorted_candidates[i]
            c1_eval = self_evals[c1.id]
            c1_distros = cand_distros_map[c1.id]

            for j in range(i + 1, n):
                c2 = sorted_candidates[j]
                c2_eval = self_evals[c2.id]
                c2_distros = cand_distros_map[c2.id]

                if c1_eval.status == CompatibilityStatus.INCOMPATIBLE or c2_eval.status == CompatibilityStatus.INCOMPATIBLE:
                    merged_conflicts = list(c1_eval.conflicts) + list(c2_eval.conflicts)
                    res = CompatibilityResult.model_construct(
                        status=CompatibilityStatus.INCOMPATIBLE,
                        resource_ids=[c1.id, c2.id],
                        environment=environment,
                        rule_evaluations=c1_eval.rule_evaluations + c2_eval.rule_evaluations,
                        conflicts=merged_conflicts,
                        warnings=[],
                        missing_requirements=[],
                        dependency_paths=[],
                        remediation=merged_conflicts[0].remediation if merged_conflicts else None,
                        evidence_level=c1_eval.evidence_level,
                        evaluated_at=now_str,
                    )
                else:
                    has_edges = (c1.id, c2.id) in edge_set or (c2.id, c1.id) in edge_set
                    ros_mismatch = False
                    if c1_distros and c2_distros and "any" not in c1_distros and "any" not in c2_distros:
                        if not (c1_distros & c2_distros):
                            ros_mismatch = True

                    if not has_edges and not ros_mismatch:
                        res = CompatibilityResult.model_construct(
                            status=CompatibilityStatus.COMPATIBLE,
                            resource_ids=[c1.id, c2.id],
                            environment=environment,
                            rule_evaluations=c1_eval.rule_evaluations,
                            conflicts=[],
                            warnings=[],
                            missing_requirements=[],
                            dependency_paths=[],
                            evidence_level=EvidenceLevel.INFERRED,
                            remediation=None,
                            evaluated_at=now_str,
                        )
                    else:
                        res = self.evaluate_pair(c1, c2, environment=environment)

                matrix[c1.id][c2.id] = res
                matrix[c2.id][c1.id] = res
                summary[res.status.value] += 2

        return CompatibilityMatrixResponse.model_construct(
            candidate_ids=candidate_ids,
            matrix=matrix,
            summary=summary,
            evaluated_at=now_str,
        )

    def get_resource_compatibility_profile(self, candidate: ResourceCandidate) -> ResourceCompatibilityProfile:
        if not self.graph.has_node(candidate.id):
            self.add_resource(candidate)

        deps = self.graph.get_dependencies(candidate.id)
        provides = self.graph.get_neighbors_by_predicate(candidate.id, "provides")
        requires = self.graph.get_neighbors_by_predicate(candidate.id, "requires")
        tested_with = self.graph.get_neighbors_by_predicate(candidate.id, "tested-with", direction="both")
        compat_with = self.graph.get_neighbors_by_predicate(candidate.id, "compatible-with", direction="both")
        conflicts_with = self.graph.get_neighbors_by_predicate(candidate.id, "conflicts-with", direction="both")

        return ResourceCompatibilityProfile(
            resource_id=candidate.id,
            name=candidate.name,
            version=candidate.version,
            type=candidate.type,
            evidence_level=candidate.evidence_level or "inferred",
            direct_dependencies=deps,
            provides=provides,
            requires=requires,
            tested_with=tested_with,
            compatible_with=compat_with,
            conflicts_with=conflicts_with,
            platform_matrix=candidate.platforms or {},
        )
