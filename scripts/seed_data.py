import asyncio
import json
from pathlib import Path

from openrobo_schemas import validate_graph_edge, validate_resource_manifest

from apps.api.database import AsyncSessionLocal, Base, engine
from apps.api.models.graph import GraphEdgeModel, GraphNodeModel
from apps.api.models.resource import ResourceModel, ResourceVersionModel

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_FILE = ROOT / "samples" / "seed_resources.json"
EDGES_FILE = ROOT / "samples" / "seed_edges.json"


async def seed_database():
    print("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if not SAMPLES_FILE.exists():
        print(f"Error: Sample file {SAMPLES_FILE} not found.")
        return

    with open(SAMPLES_FILE, "r", encoding="utf-8") as f:
        resources_data = json.load(f)

    print(f"Seeding {len(resources_data)} canonical robotics resources...")
    async with AsyncSessionLocal() as session:
        for item in resources_data:
            valid, errors = validate_resource_manifest(item)
            if not valid:
                print(f"  [SKIP] Manifest invalid: {item.get('id')} - {errors}")
                continue

            existing = await session.get(ResourceModel, item["id"])
            if existing:
                print(f"  [EXISTING] {item['id']} already in database. Updating...")
                existing.name = item["name"]
                existing.type = item["type"]
                existing.summary = item.get("summary")
                existing.description = item.get("description")
                existing.spdx_license_id = item["license"]["spdx_id"]
                existing.repo_url = item["source"]["repo_url"]
                existing.evidence_level = item.get("evidence", {}).get("level", "unknown")
                existing.robotics_domains = item.get("robotics_domains", [])
                existing.capabilities = item.get("capabilities", [])
                existing.platforms = item.get("platforms", {})
                existing.metadata_json = {
                    "source": item.get("source", {}),
                    "license": item.get("license", {}),
                    "evidence": item.get("evidence", {}),
                    "platforms": item.get("platforms", {}),
                }
            else:
                print(f"  [INSERT] {item['id']}")
                res = ResourceModel(
                    id=item["id"],
                    name=item["name"],
                    type=item["type"],
                    summary=item.get("summary"),
                    description=item.get("description"),
                    spdx_license_id=item["license"]["spdx_id"],
                    repo_url=item["source"]["repo_url"],
                    evidence_level=item.get("evidence", {}).get("level", "unknown"),
                    robotics_domains=item.get("robotics_domains", []),
                    capabilities=item.get("capabilities", []),
                    platforms=item.get("platforms", {}),
                    metadata_json={
                        "source": item.get("source", {}),
                        "license": item.get("license", {}),
                        "evidence": item.get("evidence", {}),
                        "platforms": item.get("platforms", {}),
                    },
                )
                session.add(res)

                version_entry = ResourceVersionModel(
                    id=item["id"] + "@" + item["version"],
                    resource_id=item["id"],
                    version_string=item["version"],
                    manifest_json=item,
                )
                session.add(version_entry)

            # Ensure node in graph_nodes
            gnode = await session.get(GraphNodeModel, item["id"])
            if not gnode:
                session.add(GraphNodeModel(id=item["id"], node_type=item["type"]))

        await session.commit()

        # Seed graph edges if present
        if EDGES_FILE.exists():
            with open(EDGES_FILE, "r", encoding="utf-8") as f:
                edges_data = json.load(f)
            print(f"Seeding {len(edges_data)} canonical knowledge graph edges...")
            for edge in edges_data:
                valid, errors = validate_graph_edge(edge)
                if not valid:
                    print(f"  [SKIP] Invalid edge: {edge} - {errors}")
                    continue

                sub_node = await session.get(GraphNodeModel, edge["subject_id"])
                if not sub_node:
                    session.add(GraphNodeModel(id=edge["subject_id"], node_type="resource"))
                obj_node = await session.get(GraphNodeModel, edge["object_id"])
                if not obj_node:
                    session.add(GraphNodeModel(id=edge["object_id"], node_type="resource"))
                await session.flush()

                # Check if edge already exists
                edge_entry = GraphEdgeModel(
                    subject_id=edge["subject_id"],
                    predicate=edge["predicate"],
                    object_id=edge["object_id"],
                    properties_json=edge.get("properties"),
                )
                session.add(edge_entry)

            await session.commit()

    print("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
