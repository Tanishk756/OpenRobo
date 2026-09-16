import pytest

from apps.api.models.resource import ResourceModel, ResourceVersionModel
from apps.api.services.search import (
    SearchRequest,
    SearchService,
    calculate_relevance_score,
    compute_trigram_similarity,
)


@pytest.fixture
async def sample_search_resources(db_session):
    resources = [
        ResourceModel(
            id="ros-navigation/navigation2",
            name="Navigation 2",
            type="software",
            summary="ROS 2 Navigation Stack including path planning and recovery",
            description="The complete ROS 2 navigation framework for autonomous mobile robots.",
            spdx_license_id="Apache-2.0",
            robotics_domains=["navigation", "control"],
            capabilities=["path_planning", "obstacle_avoidance"],
            platforms={"operating_systems": ["Linux", "Ubuntu 24.04"], "ros_versions": ["ROS 2 Humble", "ROS 2 Jazzy"]},
            evidence_level="ci_verified",
        ),
        ResourceModel(
            id="stevemacenski/slam_toolbox",
            name="SLAM Toolbox",
            type="ros_package",
            summary="2D and 3D SLAM package for mobile robotics",
            description="Lifelong mapping and localization using LiDAR and odometry.",
            spdx_license_id="LGPL-3.0-only",
            robotics_domains=["localization", "mapping"],
            capabilities=["slam", "sensor_streaming"],
            platforms={"operating_systems": ["Linux", "Ubuntu 24.04"], "ros_versions": ["ROS 2 Humble"]},
            evidence_level="upstream_declared",
        ),
        ResourceModel(
            id="facontidavide/plotjuggler",
            name="PlotJuggler",
            type="tool",
            summary="Timeseries visualization tool for robotics telemetry",
            description="Plot and analyze real-time and recorded ROS topic data.",
            spdx_license_id="MPL-2.0",
            robotics_domains=["visualization"],
            capabilities=["timeseries_plotting", "ros_bag_analysis"],
            platforms={"operating_systems": ["Linux", "Ubuntu 22.04", "Windows"], "ros_versions": ["ROS 2 Humble", "ROS 2 Jazzy"]},
            evidence_level="ci_verified",
        ),
        ResourceModel(
            id="intel/realsense_ros",
            name="Intel RealSense ROS 2 Driver",
            type="driver",
            summary="Driver for Intel RealSense D435 and T265 cameras",
            description="Streams RGB-D pointclouds and IMU telemetry.",
            spdx_license_id="Apache-2.0",
            robotics_domains=["perception"],
            capabilities=["sensor_streaming", "pointcloud_processing"],
            platforms={"operating_systems": ["Linux", "Ubuntu 22.04"], "ros_versions": ["ROS 2 Humble"]},
            evidence_level="upstream_declared",
        ),
    ]

    for r in resources:
        db_session.add(r)
        ver = ResourceVersionModel(
            id=f"{r.id}@1.0.0", resource_id=r.id, version_string="1.0.0", manifest_json={"id": r.id, "name": r.name, "version": "1.0.0"}
        )
        db_session.add(ver)

    await db_session.commit()
    return resources


def test_trigram_similarity_computation():
    assert compute_trigram_similarity("plotjuggler", "plotjuggler") == 1.0
    sim = compute_trigram_similarity("plotjugler", "plotjuggler")
    assert sim > 0.60
    assert compute_trigram_similarity("slam", "navigation") == 0.0


def test_relevance_ranking_calculation():
    res = ResourceModel(
        id="ros-navigation/navigation2",
        name="Navigation 2",
        type="software",
        summary="ROS 2 Navigation Stack",
        description="Autonomous navigation for robots",
        robotics_domains=["navigation"],
        capabilities=["path_planning"],
    )

    score_exact, highlight_exact = calculate_relevance_score(res, ["navigation"], "navigation 2")
    assert score_exact >= 1.5
    assert highlight_exact is not None

    score_typo, _ = calculate_relevance_score(res, ["navigatn"], "navigatn", enable_fuzzy=True)
    assert score_typo > 0.0


@pytest.mark.asyncio
async def test_search_service_queries(db_session, sample_search_resources):
    service = SearchService()

    # 1. Query 'slam'
    req1 = SearchRequest(q="slam")
    resp1 = await service.search(db_session, req1)
    assert resp1.total == 1
    assert resp1.items[0].id == "stevemacenski/slam_toolbox"
    assert "localization" in resp1.facets.domains

    # 2. Query typo 'plotjugler' (Fuzzy)
    req2 = SearchRequest(q="plotjugler", fuzzy=True)
    resp2 = await service.search(db_session, req2)
    assert resp2.total >= 1
    assert resp2.items[0].id == "facontidavide/plotjuggler"

    # 3. Filter by domain 'perception'
    req3 = SearchRequest(domain="perception")
    resp3 = await service.search(db_session, req3)
    assert resp3.total == 1
    assert resp3.items[0].id == "intel/realsense_ros"

    # 4. Combined query + filter
    req4 = SearchRequest(q="ROS", type="tool")
    resp4 = await service.search(db_session, req4)
    assert resp4.total == 1
    assert resp4.items[0].id == "facontidavide/plotjuggler"

    # 5. Facet distributions
    facets = await service.get_facets(db_session)
    assert "Apache-2.0" in facets.licenses
    assert "navigation" in facets.domains
    assert "ROS 2 Humble" in facets.ros_versions


@pytest.mark.asyncio
async def test_search_api_endpoints(client, sample_search_resources):
    # 1. Search endpoint
    resp = await client.get("/api/v1/search?q=navigation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Navigation 2"
    assert "facets" in data
    assert "types" in data["facets"]

    # 2. Facets endpoint
    facet_resp = await client.get("/api/v1/search/facets")
    assert facet_resp.status_code == 200
    facet_data = facet_resp.json()
    assert "domains" in facet_data
    assert "types" in facet_data
    assert "licenses" in facet_data
