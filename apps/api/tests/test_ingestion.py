from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from openrobo_schemas import validate_resource_manifest
from sqlalchemy import select

from apps.api.main import app
from apps.api.models.resource import ResourceModel
from apps.api.services.ingestion import (
    GitHubAPIError,
    GitHubClient,
    IngestionAction,
    IngestionSecurityError,
    IngestionService,
    MalformedXmlError,
    PackageXmlMetadata,
    RepoInspectionEvidence,
    build_candidate_manifests,
    parse_package_xml,
    validate_and_parse_github_url,
)

SAMPLE_PACKAGE_XML_F3 = """<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>nav2_bringup</name>
  <version>1.2.5</version>
  <description>Bringup scripts and launch files for Navigation 2</description>
  <maintainer email="michael@openrobotics.org">Michael Jeronimo</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  <depend>rclcpp</depend>
  <depend>nav2_common</depend>
  <exec_depend>nav2_amcl</exec_depend>
  <exec_depend>nav2_controller</exec_depend>
  <test_depend>ament_lint_auto</test_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
"""

SAMPLE_PACKAGE_XML_F1 = """<package format="1">
  <name>sick_scan_xd</name>
  <version>3.2.0</version>
  <description>ROS driver for SICK LiDARs</description>
  <maintainer email="support@sick.de">SICK AG</maintainer>
  <license>Apache 2.0</license>

  <build_depend>roscpp</build_depend>
  <run_depend>roscpp</run_depend>
  <run_depend>sensor_msgs</run_depend>
</package>
"""


def test_validate_and_parse_github_url():
    owner, repo = validate_and_parse_github_url("https://github.com/ros-navigation/navigation2")
    assert owner == "ros-navigation"
    assert repo == "navigation2"

    owner2, repo2 = validate_and_parse_github_url("https://github.com/moveit/moveit2.git/")
    assert owner2 == "moveit"
    assert repo2 == "moveit2"

    # Rejection of invalid protocols and hosts
    with pytest.raises(IngestionSecurityError):
        validate_and_parse_github_url("http://github.com/owner/repo")

    with pytest.raises(IngestionSecurityError):
        validate_and_parse_github_url("file:///etc/passwd")

    with pytest.raises(IngestionSecurityError):
        validate_and_parse_github_url("https://127.0.0.1/owner/repo")

    with pytest.raises(IngestionSecurityError):
        validate_and_parse_github_url("https://169.254.169.254/latest/meta-data")

    with pytest.raises(IngestionSecurityError):
        validate_and_parse_github_url("https://malicious.com/owner/repo")

    with pytest.raises(IngestionSecurityError):
        validate_and_parse_github_url("https://github.com/only-one-part")


def test_parse_package_xml_format3():
    meta = parse_package_xml(SAMPLE_PACKAGE_XML_F3, rel_path="nav2_bringup/package.xml")
    assert meta.name == "nav2_bringup"
    assert meta.version == "1.2.5"
    assert meta.description == "Bringup scripts and launch files for Navigation 2"
    assert meta.license == "Apache-2.0"
    assert "rclcpp" in meta.build_depends
    assert "nav2_amcl" in meta.exec_depends
    assert "ament_cmake" in meta.buildtool_depends
    assert "ament_lint_auto" in meta.test_depends
    assert meta.format_version == 3


def test_parse_package_xml_format1():
    meta = parse_package_xml(SAMPLE_PACKAGE_XML_F1, rel_path="package.xml")
    assert meta.name == "sick_scan_xd"
    assert meta.version == "3.2.0"
    assert meta.license == "Apache 2.0"
    assert "sensor_msgs" in meta.exec_depends


def test_parse_package_xml_security_and_malformed():
    # Empty
    with pytest.raises(MalformedXmlError):
        parse_package_xml("")

    # Malformed syntax
    with pytest.raises(MalformedXmlError):
        parse_package_xml("<package><name>unclosed")

    # XXE entity protection
    with pytest.raises(MalformedXmlError):
        parse_package_xml("<!DOCTYPE package [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><package><name>&xxe;</name></package>")


def test_manifest_builder_monorepo():
    pkg1 = parse_package_xml(SAMPLE_PACKAGE_XML_F3, rel_path="nav2_bringup/package.xml")
    pkg2 = PackageXmlMetadata(
        name="nav2_amcl",
        version="1.2.5",
        description="AMCL Localization node for Nav2",
        license="Apache-2.0",
        build_depends=["rclcpp"],
        exec_depends=["rclcpp"],
        rel_path="nav2_amcl/package.xml"
    )

    evidence = RepoInspectionEvidence(
        owner="ros-navigation",
        repo="navigation2",
        default_branch="main",
        commit_sha="a1b2c3d4e5f6",
        description="ROS 2 Navigation Stack",
        topics=["ros2", "navigation", "robotics"],
        spdx_license_id="Apache-2.0",
        has_package_xml=True,
        packages=[pkg1, pkg2],
        build_systems=["cmake"],
        robotics_markers=["ros_package", "ros_launch"]
    )

    candidates = build_candidate_manifests(evidence)
    assert len(candidates) == 3  # 1 top framework + 2 child packages

    top = candidates[0]
    assert top["id"] == "ros-navigation/navigation2"
    assert top["type"] == "software"
    assert "navigation" in top["robotics_domains"]
    valid, errors = validate_resource_manifest(top)
    assert valid, f"Top manifest invalid: {errors}"

    child1 = candidates[1]
    assert child1["id"] == "ros-navigation/nav2-bringup" or child1["id"] == "ros-navigation/nav2_bringup"
    assert child1["type"] == "ros_package"
    assert child1["version"] == "1.2.5"
    assert child1["license"]["spdx_id"] == "Apache-2.0"
    valid, errors = validate_resource_manifest(child1)
    assert valid, f"Child manifest invalid: {errors}"


@pytest.mark.asyncio
async def test_ingestion_service_with_mock_github(db_session):
    mock_client = AsyncMock(spec=GitHubClient)
    mock_client.get_repository_metadata.return_value = {
        "default_branch": "main",
        "description": "2D and 3D SLAM for ROS 2",
        "topics": ["slam", "mapping", "ros2", "lidar"],
        "language": "C++",
        "homepage": "https://slam-toolbox.org",
        "license": {"spdx_id": "LGPL-3.0-only"}
    }
    mock_client.get_head_commit_sha.return_value = "9876543210abcdef"
    mock_client.get_repository_tree.return_value = [
        {"path": "package.xml", "type": "blob"},
        {"path": "CMakeLists.txt", "type": "blob"},
        {"path": "launch/slam.launch.py", "type": "blob"}
    ]
    mock_client.get_raw_file_content.return_value = """<package format="3">
      <name>slam_toolbox</name>
      <version>2.6.4</version>
      <description>Slam Toolbox for ROS 2</description>
      <maintainer email="steve@macenski.com">Steve Macenski</maintainer>
      <license>LGPL-3.0-only</license>
      <depend>rclcpp</depend>
    </package>"""

    service = IngestionService(client=mock_client)

    # First ingestion -> CREATED
    resp = await service.ingest_github_repository(
        db=db_session,
        repository_url="https://github.com/SteveMacenski/slam_toolbox"
    )

    assert resp.repository == "SteveMacenski/slam_toolbox"
    assert resp.revision == "9876543210abcdef"
    assert resp.resources_discovered == 1
    assert resp.resources_created == 1
    assert resp.resources_updated == 0
    assert resp.errors == []
    assert resp.resources[0].action == IngestionAction.CREATED
    assert resp.resources[0].validation_status == "VALID"

    # Verify DB
    stmt = select(ResourceModel).where(ResourceModel.id == "stevemacenski/slam_toolbox")
    res = (await db_session.execute(stmt)).scalar_one()
    assert res.name == "slam_toolbox"
    assert "localization" in res.robotics_domains or "mapping" in res.robotics_domains
    assert res.metadata_json["provenance"]["source_identifier"] == "SteveMacenski/slam_toolbox"

    # Second ingestion -> IDEMPOTENT UPDATED
    resp2 = await service.ingest_github_repository(
        db=db_session,
        repository_url="https://github.com/SteveMacenski/slam_toolbox"
    )
    assert resp2.resources_created == 0
    assert resp2.resources_updated == 1
    assert resp2.resources[0].action == IngestionAction.UPDATED


@pytest.mark.asyncio
async def test_ingestion_api_endpoint(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Invalid SSRF URL -> 400 Bad Request
        ssrf_resp = await client.post(
            "/api/v1/ingestion/github",
            json={"repository_url": "https://127.0.0.1/private/repo"}
        )
        assert ssrf_resp.status_code == 400
        assert "Invalid repository host" in ssrf_resp.json()["detail"] or "prohibited" in ssrf_resp.json()["detail"]

        # 2. Mocked successful ingestion -> 200 OK
        with patch("apps.api.routers.ingestion.IngestionService") as MockServiceClass:
            mock_inst = AsyncMock()
            mock_inst.ingest_github_repository.return_value = {
                "repository": "ros2/ros2_tracing",
                "revision": "feedbeef1234",
                "resources_discovered": 1,
                "resources_created": 1,
                "resources_updated": 0,
                "warnings": [],
                "errors": [],
                "resources": [
                    {
                        "id": "ros2/tracetools",
                        "name": "tracetools",
                        "version": "4.1.0",
                        "type": "ros_package",
                        "action": "created",
                        "validation_status": "VALID",
                        "provenance": {"source_provider": "github"},
                        "errors": []
                    }
                ]
            }
            MockServiceClass.return_value = mock_inst

            resp = await client.post(
                "/api/v1/ingestion/github",
                json={"repository_url": "https://github.com/ros2/ros2_tracing"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["repository"] == "ros2/ros2_tracing"
            assert data["resources_created"] == 1
            assert data["resources"][0]["name"] == "tracetools"


@pytest.mark.asyncio
async def test_ingestion_api_upstream_error_handling(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("apps.api.routers.ingestion.IngestionService") as MockServiceClass:
            mock_inst = AsyncMock()
            mock_inst.ingest_github_repository.side_effect = GitHubAPIError("Repository not found", status_code=404)
            MockServiceClass.return_value = mock_inst

            resp = await client.post(
                "/api/v1/ingestion/github",
                json={"repository_url": "https://github.com/unknown/nonexistent"}
            )
            assert resp.status_code == 404
