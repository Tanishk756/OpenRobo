import asyncio
import json
from pathlib import Path

from openrobo_schemas import validate_resource_manifest

from apps.api.database import AsyncSessionLocal, Base, engine
from apps.api.models.resource import ResourceModel, ResourceVersionModel

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_FILE = ROOT / "samples" / "seed_resources.json"


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
                    },
                )
                session.add(res)

                version_entry = ResourceVersionModel(
                    id=item["id"] + "@" + item["version"], resource_id=item["id"], version_string=item["version"], manifest_json=item
                )
                session.add(version_entry)

        await session.commit()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
