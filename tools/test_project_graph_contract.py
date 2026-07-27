#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.project_graph import (
    load_registry,
    build_graph,
)


REQUIRED_GRAPH_KEYS = {
    "graph_version",
    "generated_at",
    "nodes",
    "edges",
    "stats",
}


REQUIRED_NODE_KEYS = {
    "id",
    "type",
    "data",
}


REQUIRED_EDGE_KEYS = {
    "source",
    "target",
    "relation",
}


def main():

    print("=" * 80)
    print("SLH PROJECT GRAPH CONTRACT TEST")
    print("=" * 80)

    registry = load_registry()

    graph = build_graph(
        registry
    )

    missing = (
        REQUIRED_GRAPH_KEYS
        - set(graph.keys())
    )

    assert not missing, (
        f"Missing graph keys: {missing}"
    )

    nodes = graph["nodes"]
    edges = graph["edges"]

    assert isinstance(
        nodes,
        list
    )

    assert isinstance(
        edges,
        list
    )

    node_ids = set()

    for node in nodes:

        missing = (
            REQUIRED_NODE_KEYS
            - set(node.keys())
        )

        assert not missing, (
            f"Node missing keys: {missing}"
        )

        node_id = node["id"]

        assert node_id not in node_ids, (
            f"Duplicate node: {node_id}"
        )

        node_ids.add(
            node_id
        )

        assert isinstance(
            node["type"],
            str
        )

        assert isinstance(
            node["data"],
            dict
        )

    edge_keys = set()

    for edge in edges:

        missing = (
            REQUIRED_EDGE_KEYS
            - set(edge.keys())
        )

        assert not missing, (
            f"Edge missing keys: {missing}"
        )

        source = edge["source"]
        target = edge["target"]
        relation = edge["relation"]

        assert source in node_ids, (
            f"Unknown edge source: {source}"
        )

        assert target in node_ids, (
            f"Unknown edge target: {target}"
        )

        edge_key = (
            source,
            target,
            relation,
        )

        assert edge_key not in edge_keys, (
            f"Duplicate edge: {edge_key}"
        )

        edge_keys.add(
            edge_key
        )

    assert graph["stats"]["nodes"] == len(
        nodes
    )

    assert graph["stats"]["edges"] == len(
        edges
    )

    print()
    print(
        "NODES:",
        len(nodes)
    )

    print(
        "EDGES:",
        len(edges)
    )

    print()

    for node in nodes:

        print(
            "  NODE OK:",
            node["id"]
        )

    for edge in edges:

        print(
            "  EDGE OK:",
            edge["source"],
            "->",
            edge["target"]
        )

    print()
    print("=" * 80)
    print("✅ PROJECT GRAPH CONTRACT PASSED")
    print("✅ ALL NODES VALID")
    print("✅ ALL EDGES VALID")
    print("✅ NO ORPHAN RELATIONSHIPS")
    print("✅ NO DUPLICATE RELATIONSHIPS")
    print("✅ READ-ONLY")
    print("✅ NO RESTART")
    print("=" * 80)


if __name__ == "__main__":
    main()
