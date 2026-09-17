from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from openrobo_compat.graph import OpenRoboGraph
from openrobo_compat.models import (
    CompatibilityStatus,
    ConflictDetail,
    EnvironmentTarget,
    EvidenceLevel,
    ResourceCandidate,
    RuleEvaluation,
)
from openrobo_compat.semver import matches_version_constraint


def get_candidate_platforms(cand: ResourceCandidate) -> Dict[str, List[str]]:
    platforms: Dict[str, List[str]] = {}
    if cand.platforms:
        platforms = {k.lower(): [str(x) for x in v] for k, v in cand.platforms.items() if isinstance(v, list)}
    if cand.metadata_json and "platforms" in cand.metadata_json and isinstance(cand.metadata_json["platforms"], dict):
        for k, v in cand.metadata_json["platforms"].items():
            if isinstance(v, list) and k.lower() not in platforms:
                platforms[k.lower()] = [str(x) for x in v]
    return platforms


def get_candidate_ros_distros(cand: ResourceCandidate) -> List[str]:
    platforms = get_candidate_platforms(cand)
    distros = list(platforms.get("ros", []))
    if cand.metadata_json:
        if "ros_distro" in cand.metadata_json:
            rd = cand.metadata_json["ros_distro"]
            if isinstance(rd, list):
                distros.extend(str(x) for x in rd)
            elif isinstance(rd, str):
                distros.append(rd)
        if "ros_version" in cand.metadata_json:
            rv = cand.metadata_json["ros_version"]
            if isinstance(rv, str):
                distros.append(rv)
    seen = set()
    result = []
    for d in distros:
        if d.lower() not in seen:
            seen.add(d.lower())
            result.append(d)
    return result


class BaseRule:
    name: str = "base_rule"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        raise NotImplementedError


class RosDistributionRule(BaseRule):
    name: str = "ros_distribution_compatibility"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []

        target_ros = env.ros_version.strip().lower() if env and env.ros_version else None

        if target_ros:
            for cand in candidates:
                cand_distros = get_candidate_ros_distros(cand)
                if not cand_distros:
                    continue
                cand_distros_lower = {d.lower() for d in cand_distros}
                if "any" not in cand_distros_lower and target_ros not in cand_distros_lower:
                    distro_list = ", ".join(cand_distros)
                    msg = (
                        f"Resource '{cand.name}' supports ROS distributions [{distro_list}], "
                        f"which does not include target '{env.ros_version}'."
                    )
                    remed = (
                        f"Change target ROS environment to one of [{distro_list}] "
                        f"or select a '{env.ros_version}'-compatible release of '{cand.name}'."
                    )
                    conflicts.append(
                        ConflictDetail(
                            source_id=cand.id,
                            conflict_type="ros_distribution_mismatch",
                            message=msg,
                            dependency_path=[cand.id],
                            remediation=remed,
                        )
                    )

        constrained_candidates = [
            (c, get_candidate_ros_distros(c))
            for c in candidates
            if get_candidate_ros_distros(c) and "any" not in {d.lower() for d in get_candidate_ros_distros(c)}
        ]
        if len(constrained_candidates) >= 2:
            common_distros = {d.lower() for d in constrained_candidates[0][1]}
            for _, d_list in constrained_candidates[1:]:
                common_distros &= {d.lower() for d in d_list}
            if not common_distros:
                c1, d1 = constrained_candidates[0]
                c2, d2 = constrained_candidates[1]
                msg = (
                    f"Stack components '{c1.name}' ({', '.join(d1)}) and '{c2.name}' "
                    f"({', '.join(d2)}) share no common ROS distribution."
                )
                conflicts.append(
                    ConflictDetail(
                        source_id=c1.id,
                        target_id=c2.id,
                        conflict_type="incompatible_stack_ros_distributions",
                        message=msg,
                        dependency_path=[c1.id, c2.id],
                        remediation="Ensure all stack components target the same ROS 2 release.",
                    )
                )

        if conflicts:
            has_vendor = any(c.evidence_level == "vendor_tested" for c in candidates)
            evidence = EvidenceLevel.VENDOR_TESTED if has_vendor else EvidenceLevel.INFERRED
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    message=f"ROS distribution mismatch detected for {len(conflicts)} component(s).",
                    evidence_level=evidence,
                    remediation=conflicts[0].remediation,
                ),
                conflicts,
                warnings,
            )

        if target_ros:
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=f"All components compatible with target ROS distribution '{env.ros_version}'.",
                    evidence_level=EvidenceLevel.INFERRED,
                ),
                [],
                warnings,
            )

        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.COMPATIBLE,
                message="No ROS distribution constraints violated.",
                evidence_level=EvidenceLevel.INFERRED,
            ),
            [],
            warnings,
        )


class OperatingSystemRule(BaseRule):
    name: str = "operating_system_compatibility"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []

        if not env or not env.os:
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.COMPATIBLE,
                    message="No target operating system constraint specified.",
                    evidence_level=EvidenceLevel.INFERRED,
                ),
                [],
                warnings,
            )

        target_os = env.os.strip().lower()
        for cand in candidates:
            platforms = get_candidate_platforms(cand)
            cand_os = platforms.get("os", [])
            if not cand_os:
                continue
            cand_os_lower = [o.lower() for o in cand_os]
            if "any" not in cand_os_lower and "all" not in cand_os_lower:
                matched = any(target_os in o or o in target_os for o in cand_os_lower)
                if not matched:
                    supported = ", ".join(cand_os)
                    conflicts.append(
                        ConflictDetail(
                            source_id=cand.id,
                            conflict_type="operating_system_mismatch",
                            message=f"Resource '{cand.name}' supports OS [{supported}], which excludes target '{env.os}'.",
                            dependency_path=[cand.id],
                            remediation=f"Deploy on a supported host OS ({supported}) or use a containerized Linux runtime.",
                        )
                    )

        if conflicts:
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    message=f"Operating system mismatch detected for {len(conflicts)} resource(s).",
                    evidence_level=EvidenceLevel.INFERRED,
                    remediation=conflicts[0].remediation,
                ),
                conflicts,
                warnings,
            )

        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.COMPATIBLE,
                message=f"All components compatible with target OS '{env.os}'.",
                evidence_level=EvidenceLevel.INFERRED,
            ),
            [],
            warnings,
        )


class CpuArchitectureRule(BaseRule):
    name: str = "cpu_architecture_compatibility"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []

        if not env or not env.cpu_architecture:
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.COMPATIBLE,
                    message="No CPU architecture constraint specified.",
                    evidence_level=EvidenceLevel.INFERRED,
                ),
                [],
                warnings,
            )

        target_arch = env.cpu_architecture.strip().lower()
        if target_arch in ("arm64", "aarch64"):
            target_arch_set = {"aarch64", "arm64"}
        elif target_arch in ("x86_64", "amd64", "x64"):
            target_arch_set = {"x86_64", "amd64", "x64"}
        else:
            target_arch_set = {target_arch}

        for cand in candidates:
            platforms = get_candidate_platforms(cand)
            cand_archs = platforms.get("architecture", [])
            if not cand_archs:
                continue
            cand_arch_lower = {a.lower() for a in cand_archs}
            if "any" not in cand_arch_lower and "all" not in cand_arch_lower:
                matched = bool(target_arch_set & cand_arch_lower)
                if not matched:
                    supported = ", ".join(cand_archs)
                    msg = (
                        f"Resource '{cand.name}' supports CPU architectures [{supported}], "
                        f"which does not include target '{env.cpu_architecture}'."
                    )
                    remed = (
                        f"Target an architecture supported by '{cand.name}' ({supported}) "
                        f"or cross-compile for '{env.cpu_architecture}'."
                    )
                    conflicts.append(
                        ConflictDetail(
                            source_id=cand.id,
                            conflict_type="cpu_architecture_mismatch",
                            message=msg,
                            dependency_path=[cand.id],
                            remediation=remed,
                        )
                    )

        if conflicts:
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    message=f"CPU architecture mismatch detected for {len(conflicts)} resource(s).",
                    evidence_level=EvidenceLevel.INFERRED,
                    remediation=conflicts[0].remediation,
                ),
                conflicts,
                warnings,
            )

        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.COMPATIBLE,
                message=f"All components compatible with CPU architecture '{env.cpu_architecture}'.",
                evidence_level=EvidenceLevel.INFERRED,
            ),
            [],
            warnings,
        )


class SemVerConstraintRule(BaseRule):
    name: str = "semver_version_constraints"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []
        cand_map = {c.id: c for c in candidates}

        for cand in candidates:
            edges = graph.get_edges(subject_id=cand.id)
            for edge in edges:
                if edge.predicate in ("depends-on", "requires") and edge.object_id in cand_map:
                    target_cand = cand_map[edge.object_id]
                    props = edge.properties or {}
                    constraint = props.get("version_constraint") or props.get("version")
                    if not constraint:
                        min_v = props.get("min_version")
                        max_v = props.get("max_version")
                        if min_v and max_v:
                            constraint = f">={min_v},<={max_v}"
                        elif min_v:
                            constraint = f">={min_v}"
                        elif max_v:
                            constraint = f"<={max_v}"

                    if constraint:
                        matches, explanation = matches_version_constraint(target_cand.version, constraint)
                        if not matches:
                            msg = (
                                f"Resource '{cand.name}' requires '{target_cand.name}' with "
                                f"constraint '{constraint}', but version '{target_cand.version}' was provided. ({explanation})"
                            )
                            conflicts.append(
                                ConflictDetail(
                                    source_id=cand.id,
                                    target_id=target_cand.id,
                                    conflict_type="semver_constraint_violation",
                                    message=msg,
                                    dependency_path=[cand.id, target_cand.id],
                                    remediation=f"Update '{target_cand.name}' to a version satisfying '{constraint}'.",
                                )
                            )

        if conflicts:
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    message=f"SemVer constraint violation detected on {len(conflicts)} dependency edge(s).",
                    evidence_level=EvidenceLevel.INFERRED,
                    remediation=conflicts[0].remediation,
                ),
                conflicts,
                warnings,
            )

        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.COMPATIBLE,
                message="All evaluated dependency version constraints are satisfied.",
                evidence_level=EvidenceLevel.INFERRED,
            ),
            [],
            warnings,
        )


class ExplicitConflictRule(BaseRule):
    name: str = "explicit_graph_conflicts"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []
        cand_map = {c.id: c for c in candidates}
        cand_ids = list(cand_map.keys())

        explicit_conflicts = graph.get_explicit_conflicts(cand_ids)
        for u, v, props in explicit_conflicts:
            source_name = cand_map[u].name if u in cand_map else u
            target_name = cand_map[v].name if v in cand_map else v
            reason = props.get("reason", "Explicit incompatibility declared in graph.")
            conflicts.append(
                ConflictDetail(
                    source_id=u,
                    target_id=v,
                    conflict_type="explicit_conflict",
                    message=f"Components '{source_name}' and '{target_name}' are explicitly incompatible. {reason}",
                    dependency_path=[u, v],
                    remediation=f"Remove '{source_name}' or '{target_name}' from the stack or use an alternative component.",
                )
            )

        if conflicts:
            has_ci = any("ci" in str(props) for _, _, props in explicit_conflicts)
            evidence = EvidenceLevel.CI_VERIFIED if has_ci else EvidenceLevel.VENDOR_TESTED
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    message=f"{len(conflicts)} explicit component conflict(s) detected.",
                    evidence_level=evidence,
                    remediation=conflicts[0].remediation,
                ),
                conflicts,
                warnings,
            )

        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.COMPATIBLE,
                message="No explicit graph conflicts between selected components.",
                evidence_level=EvidenceLevel.INFERRED,
            ),
            [],
            warnings,
        )


class DependencyCycleRule(BaseRule):
    name: str = "dependency_cycle_detection"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []
        cand_map = {c.id: c for c in candidates}

        if len(candidates) == 2:
            c1_id, c2_id = candidates[0].id, candidates[1].id
            c1_deps = graph.get_dependencies(c1_id)
            c2_deps = graph.get_dependencies(c2_id)
            if c2_id in c1_deps and c1_id in c2_deps:
                cycle = [c1_id, c2_id]
                names = [cand_map[c1_id].name, cand_map[c2_id].name]
                cycle_str = " -> ".join(names + [names[0]])
                warnings.append(f"Circular dependency cycle detected: {cycle_str}")
                conflicts.append(
                    ConflictDetail(
                        source_id=c1_id,
                        target_id=c2_id,
                        conflict_type="circular_dependency",
                        message=f"Circular dependency detected: {cycle_str}",
                        dependency_path=cycle,
                        remediation="Decouple circular dependencies using interfaces or separate abstraction packages.",
                    )
                )
        elif len(candidates) > 2:
            cand_set = set(cand_map.keys())
            sub_dep = nx.DiGraph()
            for u in cand_set:
                for v in graph.get_dependencies(u):
                    if v in cand_set:
                        sub_dep.add_edge(u, v)
            try:
                candidate_cycles = [sorted(cycle) for cycle in nx.simple_cycles(sub_dep)]
            except Exception:
                candidate_cycles = []

            for cycle in candidate_cycles:
                names = [cand_map[n].name if n in cand_map else n for n in cycle]
                cycle_str = " -> ".join(names + [names[0]])
                warnings.append(f"Circular dependency cycle detected: {cycle_str}")
                conflicts.append(
                    ConflictDetail(
                        source_id=cycle[0],
                        target_id=cycle[-1],
                        conflict_type="circular_dependency",
                        message=f"Circular dependency detected: {cycle_str}",
                        dependency_path=cycle,
                        remediation="Decouple circular dependencies using interfaces or separate abstraction packages.",
                    )
                )

        if conflicts:
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.CONDITIONAL,
                    message=f"Detected {len(conflicts)} dependency cycle(s). Stack may fail to build or initialize.",
                    evidence_level=EvidenceLevel.INFERRED,
                    remediation=conflicts[0].remediation,
                ),
                conflicts,
                warnings,
            )

        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.COMPATIBLE,
                message="No circular dependency cycles detected.",
                evidence_level=EvidenceLevel.INFERRED,
            ),
            [],
            warnings,
        )


class HardwareAndCapabilityRule(BaseRule):
    name: str = "hardware_and_capabilities"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        conflicts: List[ConflictDetail] = []
        warnings: List[str] = []

        provided_capabilities: Set[str] = set()
        provided_hardware: Set[str] = set()

        if env:
            provided_capabilities.update(c.lower() for c in env.capabilities)
            provided_hardware.update(h.lower() for h in env.hardware)

        for cand in candidates:
            provided_capabilities.update(c.lower() for c in cand.capabilities)
            prov_nodes = graph.get_neighbors_by_predicate(cand.id, "provides", direction="out")
            provided_capabilities.update(p.lower() for p in prov_nodes)

        for cand in candidates:
            req_nodes = graph.get_neighbors_by_predicate(cand.id, "requires", direction="out")
            for req in req_nodes:
                norm_req = req.lower()
                if req in {c.id for c in candidates}:
                    continue
                if norm_req not in provided_capabilities and norm_req not in provided_hardware:
                    msg = (
                        f"Resource '{cand.name}' requires interface or capability '{req}', "
                        "which is not currently present in stack or environment."
                    )
                    warnings.append(msg)

        msg = (
            "All required capabilities satisfied."
            if not warnings
            else f"{len(warnings)} optional or external capability requirement(s) unfulfilled."
        )
        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.COMPATIBLE if not warnings else CompatibilityStatus.CONDITIONAL,
                message=msg,
                evidence_level=EvidenceLevel.INFERRED,
            ),
            conflicts,
            warnings,
        )


class ExplicitTestedWithRule(BaseRule):
    name: str = "explicit_tested_with_verification"

    def evaluate(
        self,
        candidates: List[ResourceCandidate],
        graph: OpenRoboGraph,
        env: Optional[EnvironmentTarget] = None,
    ) -> Tuple[RuleEvaluation, List[ConflictDetail], List[str]]:
        cand_map = {c.id: c for c in candidates}
        cand_ids = list(cand_map.keys())
        tested_pairs = []

        for u in cand_ids:
            for v in cand_ids:
                if u != v:
                    tested = graph.get_neighbors_by_predicate(u, "tested-with", direction="both")
                    if v in tested:
                        tested_pairs.append((u, v))

        if tested_pairs:
            pair_strs = [f"{cand_map[u].name} <-> {cand_map[v].name}" for u, v in tested_pairs[:3]]
            return (
                RuleEvaluation(
                    rule_name=self.name,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=f"Verified hardware/software testing evidence between: {', '.join(pair_strs)}",
                    evidence_level=EvidenceLevel.VENDOR_TESTED,
                ),
                [],
                [],
            )

        return (
            RuleEvaluation(
                rule_name=self.name,
                status=CompatibilityStatus.UNKNOWN,
                message="No explicit vendor or CI integration test evidence found between candidate resources.",
                evidence_level=EvidenceLevel.UNKNOWN,
            ),
            [],
            [],
        )
