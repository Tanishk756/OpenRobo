from typing import Any, Dict, List, Optional

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
    "derived-from"
}

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
        if edge.predicate not in VALID_PREDICATES:
            raise ValueError(f"Invalid predicate '{edge.predicate}'. Must be one of {VALID_PREDICATES}")
        self.graph.add_edge(
            edge.subject_id,
            edge.object_id,
            predicate=edge.predicate,
            **(edge.properties or {})
        )

    def get_dependencies(self, node_id: str) -> List[str]:
        if node_id not in self.graph:
            return []
        dependencies = []
        for _, target, data in self.graph.out_edges(node_id, data=True):
            if data.get("predicate") in ("depends-on", "requires"):
                dependencies.append(target)
        return dependencies

    def get_neighbors_by_predicate(self, node_id: str, predicate: str) -> List[str]:
        if node_id not in self.graph:
            return []
        results = []
        for _, target, data in self.graph.out_edges(node_id, data=True):
            if data.get("predicate") == predicate:
                results.append(target)
        return results
