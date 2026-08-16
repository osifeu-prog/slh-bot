#!/usr/bin/env python3

"""
SLH Project Graph v1

Builds a read-only graph from the canonical Project Registry.

Graph:
    PROJECT
       ↓
    REPOSITORY
       ↓
   DEPLOYMENT
       ↓
    DEVICE
       ↓
 INSTALLATION

Only confirmed relationships are emitted.
Unknown relationships remain absent.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent

REGISTRY_FILE = (
    ROOT
    / "state"
    / "takeover"
    / "project_registry.json"
)

GRAPH_FILE = (
    ROOT
    / "state"
    / "takeover"
    / "project_graph.json"
)


def now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


def load_registry() -> dict[str, Any]:

    if not REGISTRY_FILE.exists():

        return {}

    try:

        data = json.loads(
            REGISTRY_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):

            return data

    except Exception:

        pass

    return {}


def add_node(
    nodes: dict[str, dict[str, Any]],
    node_id: str,
    node_type: str,
    data: dict[str, Any] | None = None
):

    if node_id not in nodes:

        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "data": data or {},
        }


def add_edge(
    edges: list[dict[str, Any]],
    source: str,
    target: str,
    relation: str
):

    edges.append(
        {
            "source": source,
            "target": target,
            "relation": relation,
        }
    )


def build_graph(
    registry: dict[str, Any]
) -> dict[str, Any]:

    nodes = {}
    edges = []

    projects = registry.get(
        "projects",
        {}
    )

    if not isinstance(
        projects,
        dict
    ):

        projects = {}

    for project_id, project in projects.items():

        project_node = (
            f"project:{project_id}"
        )

        add_node(
            nodes,
            project_node,
            "project",
            {
                "project_id": project_id,
                "name": project.get(
                    "name"
                ),
                "type": project.get(
                    "type"
                ),
                "path": project.get(
                    "path"
                ),
                "status": project.get(
                    "status"
                ),
                "health": project.get(
                    "health"
                ),
            }
        )

        git = project.get(
            "git",
            {}
        )

        if (
            isinstance(git, dict)
            and git.get(
                "is_repository"
            )
            and git.get(
                "remote"
            )
        ):

            remote = git["remote"]

            repository_node = (
                f"repository:{remote}"
            )

            add_node(
                nodes,
                repository_node,
                "repository",
                {
                    "remote": remote,
                }
            )

            add_edge(
                edges,
                project_node,
                repository_node,
                "HAS_REPOSITORY"
            )

        repository = project.get(
            "repository"
        )

        if (
            isinstance(
                repository,
                dict
            )
        ):

            repository_id = (
                repository.get(
                    "id"
                )
                or repository.get(
                    "url"
                )
                or repository.get(
                    "name"
                )
            )

            if repository_id:

                repository_node = (
                    f"repository:{repository_id}"
                )

                add_node(
                    nodes,
                    repository_node,
                    "repository",
                    repository
                )

                add_edge(
                    edges,
                    project_node,
                    repository_node,
                    "HAS_REPOSITORY"
                )

        deployment = project.get(
            "deployment"
        )

        if (
            isinstance(
                deployment,
                dict
            )
        ):

            deployment_id = (
                deployment.get(
                    "id"
                )
                or deployment.get(
                    "name"
                )
            )

            if deployment_id:

                deployment_node = (
                    f"deployment:{deployment_id}"
                )

                add_node(
                    nodes,
                    deployment_node,
                    "deployment",
                    deployment
                )

                add_edge(
                    edges,
                    project_node,
                    deployment_node,
                    "HAS_DEPLOYMENT"
                )

        devices = project.get(
            "devices",
            []
        )

        if isinstance(
            devices,
            list
        ):

            for device in devices:

                if not isinstance(
                    device,
                    dict
                ):

                    continue

                device_id = (
                    device.get(
                        "id"
                    )
                    or device.get(
                        "device_id"
                    )
                    or device.get(
                        "name"
                    )
                )

                if not device_id:

                    continue

                device_node = (
                    f"device:{device_id}"
                )

                add_node(
                    nodes,
                    device_node,
                    "device",
                    device
                )

                add_edge(
                    edges,
                    project_node,
                    device_node,
                    "HAS_DEVICE"
                )

        installations = project.get(
            "installations",
            []
        )

        if isinstance(
            installations,
            list
        ):

            for installation in installations:

                if not isinstance(
                    installation,
                    dict
                ):

                    continue

                installation_id = (
                    installation.get(
                        "id"
                    )
                    or installation.get(
                        "installation_id"
                    )
                    or installation.get(
                        "name"
                    )
                )

                if not installation_id:

                    continue

                installation_node = (
                    f"installation:{installation_id}"
                )

                add_node(
                    nodes,
                    installation_node,
                    "installation",
                    installation
                )

                add_edge(
                    edges,
                    project_node,
                    installation_node,
                    "HAS_INSTALLATION"
                )

    return {
        "graph_version": "1.0",
        "generated_at": now(),
        "nodes": list(
            nodes.values()
        ),
        "edges": edges,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
        },
    }


def write_graph():

    registry = load_registry()

    graph = build_graph(
        registry
    )

    GRAPH_FILE.write_text(
        json.dumps(
            graph,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    return graph


if __name__ == "__main__":

    graph = write_graph()

    print("=" * 80)
    print("SLH PROJECT GRAPH v1")
    print("=" * 80)

    print()
    print(
        "NODES:",
        graph["stats"]["nodes"]
    )

    print(
        "EDGES:",
        graph["stats"]["edges"]
    )

    print()

    for node in graph["nodes"]:

        print(
            "NODE:",
            node["id"],
            "|",
            node["type"]
        )

    print()

    for edge in graph["edges"]:

        print(
            "EDGE:",
            edge["source"],
            "->",
            edge["target"],
            "|",
            edge["relation"]
        )

    print()
    print(
        "OUTPUT:",
        GRAPH_FILE
    )

    print()
    print("=" * 80)
    print("GRAPH GENERATED")
    print("READ-ONLY REGISTRY ACCESS")
    print("NO BOT RESTART")
    print("=" * 80)
