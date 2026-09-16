import pathlib
from typing import List

from apps.api.services.ingestion.github_client import GitHubClient
from apps.api.services.ingestion.models import PackageXmlMetadata, RepoInspectionEvidence
from apps.api.services.ingestion.package_xml_parser import MalformedXmlError, parse_package_xml


class RepositoryInspector:
    def __init__(self, client: GitHubClient):
        self.client = client

    async def inspect_repository(self, owner: str, repo: str) -> RepoInspectionEvidence:
        repo_meta = await self.client.get_repository_metadata(owner, repo)
        default_branch = repo_meta.get("default_branch") or "main"
        description = repo_meta.get("description")
        topics = repo_meta.get("topics", [])
        primary_language = repo_meta.get("language")
        homepage = repo_meta.get("homepage")

        spdx_license_id = None
        license_obj = repo_meta.get("license")
        if license_obj and isinstance(license_obj, dict):
            spdx_license_id = license_obj.get("spdx_id")
            if spdx_license_id in ("NOASSERTION", "other", None):
                spdx_license_id = None

        commit_sha = await self.client.get_head_commit_sha(owner, repo, default_branch)
        tree_items = await self.client.get_repository_tree(owner, repo, default_branch)

        build_systems = set()
        robotics_markers = set()
        package_xml_paths = []
        inspected_files = []

        for item in tree_items:
            path_str = item.get("path", "")
            lower_path = path_str.lower()
            name = pathlib.Path(path_str).name.lower()

            if name == "package.xml":
                if not any(ign in lower_path for ign in ["/test/", "/tests/", "/fixtures/", "/mock/"]):
                    package_xml_paths.append(path_str)
                    inspected_files.append(path_str)

            if name == "cmakelists.txt":
                build_systems.add("cmake")
                inspected_files.append(path_str)
            elif name in ("setup.py", "setup.cfg"):
                build_systems.add("setuptools")
            elif name == "pyproject.toml":
                build_systems.add("pyproject")
            elif name == "cargo.toml":
                build_systems.add("cargo")

            if lower_path.endswith((".urdf", ".xacro")):
                robotics_markers.add("urdf_xacro")
            elif lower_path.endswith((".world", ".sdf")):
                robotics_markers.add("gazebo_world")
            elif lower_path.endswith((".dae", ".stl", ".obj")):
                robotics_markers.add("3d_mesh")
            elif "/launch/" in lower_path or lower_path.endswith((".launch", ".launch.py", ".launch.xml")):
                robotics_markers.add("ros_launch")
            elif name in ("plugin.xml", "nodelet_plugins.xml"):
                robotics_markers.add("plugin_xml")
            elif "ros2_control" in lower_path or "controller" in lower_path:
                robotics_markers.add("control")
            elif lower_path.endswith((".msg", ".srv", ".action")):
                robotics_markers.add("ros_interfaces")

        # Fetch and parse package.xml files
        parsed_packages: List[PackageXmlMetadata] = []
        for p_path in package_xml_paths[:50]:
            try:
                xml_text = await self.client.get_raw_file_content(owner, repo, default_branch, p_path)
                pkg = parse_package_xml(xml_text, rel_path=p_path)
                parsed_packages.append(pkg)
            except (MalformedXmlError, Exception):
                continue

        has_package_xml = len(parsed_packages) > 0
        if has_package_xml:
            robotics_markers.add("ros_package")

        return RepoInspectionEvidence(
            owner=owner,
            repo=repo,
            default_branch=default_branch,
            commit_sha=commit_sha,
            description=description,
            topics=topics,
            spdx_license_id=spdx_license_id,
            primary_language=primary_language,
            homepage=homepage,
            has_package_xml=has_package_xml,
            packages=parsed_packages,
            build_systems=sorted(list(build_systems)),
            robotics_markers=sorted(list(robotics_markers)),
            inspected_files=inspected_files[:100],
        )
