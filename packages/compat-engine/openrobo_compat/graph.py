from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel

VALID_PREDICATES = {
    "depends-on",
    "optional-dependency",
    "conflicts-with",
    "compatible-with",
    "tested-with",
    "provides",
    "implements",
    "driver-for",
    "hardware-for",
    "simulation-model-for",
    "simulated-by",
    "runs-on",
    "requires",
    "used-by",
    "part-of",
    "alternative-to",
    "derived-from",
}

PREDICATE_NORMALIZATION = {
    "depends_on": "depends-on",
    "optional_dependency": "optional-dependency",
    "conflicts_with": "conflicts-with",
    "incompatible_with": "conflicts-with",
    "incompatible-with": "conflicts-with",
    "compatible_with": "compatible-with",
    "tested_with": "tested-with",
    "driver_for": "driver-for",
    "hardware_for": "hardware-for",
    "simulation_model_for": "simulation-model-for",
    "simulated_by": "simulated-by",
    "runs_on": "runs-on",
    "used_by": "used-by",
    "part_of": "part-of",
    "alternative_to": "alternative-to",
    "derived_from": "derived-from",
}


def normalize_predicate(predicate: str) -> str:
    p = predicate.strip().lower()
    return PREDICATE_NORMALIZATION.get(p, p)


class GraphEdgeData(BaseModel):
    subject_id: str
    predicate: str
    object_id: str
    properties: Optional[Dict[str, Any]] = None


class OpenRoboGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_node(self, node_id: str, properties: Optional[Dict[str, Any]] = None):
        self.graph.add_node(node_id, **(properties or {}))

    def add_edge(self, edge: GraphEdgeData):
        norm_predicate = normalize_predicate(edge.predicate)
        if norm_predicate not in VALID_PREDICATES:
            raise ValueError(f"Invalid predicate '{edge.predicate}'. Must be one of {VALID_PREDICATES}")
        self.graph.add_edge(edge.subject_id, edge.object_id, predicate=norm_predicate, **(edge.properties or {}))

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if node_id in self.graph:
            return dict(self.graph.nodes[node_id])
        return None

    def has_node(self, node_id: str) -> bool:
        return node_id in self.graph

    def get_dependencies(self, node_id: str) -> List[str]:
        if node_id not in self.graph:
            return []
        dependencies = []
        for _, target, data in self.graph.out_edges(node_id, data=True):
            if data.get("predicate") in ("depends-on", "requires"):
                dependencies.append(target)
        return dependencies

    def get_dependents(self, node_id: str) -> List[str]:
        if node_id not in self.graph:
            return []
        dependents = []
        for source, _, data in self.graph.in_edges(node_id, data=True):
            if data.get("predicate") in ("depends-on", "requires"):
                dependents.append(source)
        return dependents

    def get_neighbors_by_predicate(self, node_id: str, predicate: str, direction: str = "out") -> List[str]:
        if node_id not in self.graph:
            return []
        norm_pred = normalize_predicate(predicate)
        results = []
        if direction in ("out", "both"):
            for _, target, data in self.graph.out_edges(node_id, data=True):
                if data.get("predicate") == norm_pred:
                    results.append(target)
        if direction in ("in", "both"):
            for source, _, data in self.graph.in_edges(node_id, data=True):
                if data.get("predicate") == norm_pred:
                    if source not in results:
                        results.append(source)
        return results

    def get_edges(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
    ) -> List[GraphEdgeData]:
        edges = []
        norm_pred = normalize_predicate(predicate) if predicate else None

        # O(degree) fast path when subject_id is specified
        if subject_id:
            if subject_id not in self.graph:
                return []
            for _, v, data in self.graph.out_edges(subject_id, data=True):
                if object_id and v != object_id:
                    continue
                edge_pred = data.get("predicate")
                if norm_pred and edge_pred != norm_pred:
                    continue
                props = {k: val for k, val in data.items() if k != "predicate"}
                edges.append(
                    GraphEdgeData(
                        subject_id=subject_id,
                        predicate=edge_pred,
                        object_id=v,
                        properties=props or None,
                    )
                )
            return edges

        # General traversal
        for u, v, data in self.graph.edges(data=True):
            if object_id and v != object_id:
                continue
            edge_pred = data.get("predicate")
            if norm_pred and edge_pred != norm_pred:
                continue
            props = {k: val for k, val in data.items() if k != "predicate"}
            edges.append(
                GraphEdgeData(
                    subject_id=u,
                    predicate=edge_pred,
                    object_id=v,
                    properties=props or None,
                )
            )
        return sorted(edges, key=lambda e: (e.subject_id, e.predicate, e.object_id))

    def find_dependency_cycles(self) -> List[List[str]]:
        dep_graph = nx.DiGraph()
        for u, v, data in self.graph.edges(data=True):
            if data.get("predicate") in ("depends-on", "requires"):
                dep_graph.add_edge(u, v)
        try:
            return [sorted(cycle) for cycle in nx.simple_cycles(dep_graph)]
        except Exception:
            return []

    def get_transitive_dependencies(self, node_id: str) -> List[str]:
        if node_id not in self.graph:
            return []
        visited: List[str] = []
        visited_set: Set[str] = set()

        def dfs(curr: str):
            for dep in self.get_dependencies(curr):
                if dep not in visited_set:
                    visited_set.add(dep)
                    dfs(dep)
                    visited.append(dep)

        dfs(node_id)
        return visited

    def find_path(self, source_id: str, target_id: str, predicates: Optional[Set[str]] = None) -> Optional[List[str]]:
        if source_id not in self.graph or target_id not in self.graph:
            return None
        if source_id == target_id:
            return [source_id]

        sub_g = nx.DiGraph()
        for u, v, data in self.graph.edges(data=True):
            p = data.get("predicate")
            if predicates is None or p in predicates:
                sub_g.add_edge(u, v)

        try:
            return nx.shortest_path(sub_g, source=source_id, target=target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_explicit_conflicts(self, node_ids: List[str]) -> List[Tuple[str, str, Dict[str, Any]]]:
        conflicts = []
        node_set = set(node_ids)
        for u in node_ids:
            if u not in self.graph:
                continue
            for _, v, data in self.graph.out_edges(u, data=True):
                if data.get("predicate") in ("conflicts-with", "incompatible-with"):
                    if v in node_set:
                        conflicts.append((u, v, data))
        return sorted(conflicts, key=lambda c: (c[0], c[1]))
