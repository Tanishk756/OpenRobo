from collections import Counter
from typing import Sequence

from apps.api.models.resource import ResourceModel
from apps.api.services.search.models import SearchFacetDistribution


def compute_facets(resources: Sequence[ResourceModel]) -> SearchFacetDistribution:
    type_counter = Counter()
    domain_counter = Counter()
    capability_counter = Counter()
    license_counter = Counter()
    ros_counter = Counter()

    for res in resources:
        if res.type:
            type_counter[res.type] += 1
        if res.spdx_license_id:
            license_counter[res.spdx_license_id] += 1

        if res.robotics_domains and isinstance(res.robotics_domains, list):
            for d in res.robotics_domains:
                domain_counter[d] += 1

        if res.capabilities and isinstance(res.capabilities, list):
            for c in res.capabilities:
                capability_counter[c] += 1

        if res.platforms and isinstance(res.platforms, dict):
            ros_versions = res.platforms.get("ros_versions", [])
            if isinstance(ros_versions, list):
                for r in ros_versions:
                    ros_counter[r] += 1

    return SearchFacetDistribution(
        types=dict(type_counter.most_common()),
        domains=dict(domain_counter.most_common()),
        capabilities=dict(capability_counter.most_common(20)),
        licenses=dict(license_counter.most_common()),
        ros_versions=dict(ros_counter.most_common()),
    )
