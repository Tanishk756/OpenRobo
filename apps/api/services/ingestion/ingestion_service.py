from typing import Optional

from openrobo_schemas import validate_resource_manifest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.resource import ResourceModel, ResourceVersionModel, utc_now
from apps.api.services.ingestion.github_client import GitHubClient, validate_and_parse_github_url
from apps.api.services.ingestion.manifest_builder import build_candidate_manifests
from apps.api.services.ingestion.models import GithubIngestionResponse, IngestionAction, IngestionResourceSummary
from apps.api.services.ingestion.repository_inspector import RepositoryInspector


class IngestionService:
    def __init__(self, github_token: Optional[str] = None, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient(token=github_token)
        self.inspector = RepositoryInspector(self.client)

    async def ingest_github_repository(
        self,
        db: AsyncSession,
        repository_url: str,
        force_refresh: bool = False
    ) -> GithubIngestionResponse:
        owner, repo = validate_and_parse_github_url(repository_url)

        # Inspect repository
        evidence = await self.inspector.inspect_repository(owner, repo)

        # Build resource manifest candidates
        candidates = build_candidate_manifests(evidence)

        summaries = []
        created_count = 0
        updated_count = 0
        warnings = []
        errors = []

        for candidate in candidates:
            res_id = candidate["id"]
            res_name = candidate["name"]
            res_ver = candidate["version"]
            res_type = candidate["type"]
            provenance = candidate.get("provenance", {})

            # Validate against canonical JSON schema
            valid, schema_errors = validate_resource_manifest(candidate)
            if not valid:
                errors.append(f"Resource '{res_id}' failed schema validation: {'; '.join(schema_errors)}")
                summaries.append(
                    IngestionResourceSummary(
                        id=res_id,
                        name=res_name,
                        version=res_ver,
                        type=res_type,
                        action=IngestionAction.FAILED,
                        validation_status="INVALID",
                        provenance=provenance,
                        errors=schema_errors
                    )
                )
                continue

            # Idempotency / Safe Upsert in Database
            stmt = select(ResourceModel).where(ResourceModel.id == res_id)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            action = IngestionAction.CREATED
            if existing:
                action = IngestionAction.UPDATED
                existing.name = res_name
                existing.type = res_type
                existing.summary = candidate.get("summary")
                existing.description = candidate.get("description")
                existing.spdx_license_id = candidate.get("license", {}).get("spdx_id", "NOASSERTION")
                existing.repo_url = candidate.get("source", {}).get("repo_url")
                existing.robotics_domains = candidate.get("robotics_domains", [])
                existing.capabilities = candidate.get("capabilities", [])
                existing.platforms = candidate.get("platforms", {})
                existing.evidence_level = candidate.get("evidence", {}).get("level", "automatically_detected")
                existing.metadata_json = {
                    "provenance": provenance,
                    "dependencies": candidate.get("dependencies", {}),
                    "sub_packages": candidate.get("sub_packages", [])
                }
                existing.updated_at = utc_now()
                updated_count += 1

                # Check if version exists
                ver_stmt = select(ResourceVersionModel).where(
                    ResourceVersionModel.resource_id == res_id,
                    ResourceVersionModel.version_string == res_ver
                )
                ver_res = await db.execute(ver_stmt)
                existing_ver = ver_res.scalar_one_or_none()
                if existing_ver:
                    existing_ver.manifest_json = candidate
                else:
                    new_ver = ResourceVersionModel(
                        id=f"{res_id}@{res_ver}",
                        resource_id=res_id,
                        version_string=res_ver,
                        manifest_json=candidate
                    )
                    db.add(new_ver)

            else:
                new_resource = ResourceModel(
                    id=res_id,
                    name=res_name,
                    type=res_type,
                    summary=candidate.get("summary"),
                    description=candidate.get("description"),
                    spdx_license_id=candidate.get("license", {}).get("spdx_id", "NOASSERTION"),
                    repo_url=candidate.get("source", {}).get("repo_url"),
                    robotics_domains=candidate.get("robotics_domains", []),
                    capabilities=candidate.get("capabilities", []),
                    platforms=candidate.get("platforms", {}),
                    evidence_level=candidate.get("evidence", {}).get("level", "automatically_detected"),
                    metadata_json={
                        "provenance": provenance,
                        "dependencies": candidate.get("dependencies", {}),
                        "sub_packages": candidate.get("sub_packages", [])
                    }
                )
                db.add(new_resource)
                new_ver = ResourceVersionModel(
                    id=f"{res_id}@{res_ver}",
                    resource_id=res_id,
                    version_string=res_ver,
                    manifest_json=candidate
                )
                db.add(new_ver)
                created_count += 1

            summaries.append(
                IngestionResourceSummary(
                    id=res_id,
                    name=res_name,
                    version=res_ver,
                    type=res_type,
                    action=action,
                    validation_status="VALID",
                    provenance=provenance,
                    errors=[]
                )
            )

        await db.commit()

        return GithubIngestionResponse(
            repository=f"{owner}/{repo}",
            revision=evidence.commit_sha,
            resources_discovered=len(candidates),
            resources_created=created_count,
            resources_updated=updated_count,
            warnings=warnings,
            errors=errors,
            resources=summaries
        )
