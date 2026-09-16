from sqlalchemy import String, cast, select
from sqlalchemy.sql import Select

from apps.api.models.resource import ResourceModel
from apps.api.services.search.models import SearchRequest


def build_filtered_query(request: SearchRequest) -> Select:
    stmt = select(ResourceModel)

    if request.type:
        stmt = stmt.where(ResourceModel.type.ilike(request.type))

    if request.license:
        stmt = stmt.where(ResourceModel.spdx_license_id.ilike(request.license))

    if request.domain:
        stmt = stmt.where(cast(ResourceModel.robotics_domains, String).ilike(f"%{request.domain}%"))

    if request.capability:
        stmt = stmt.where(cast(ResourceModel.capabilities, String).ilike(f"%{request.capability}%"))

    if request.ros_version or request.ecosystem:
        target = request.ros_version or request.ecosystem
        stmt = stmt.where(cast(ResourceModel.platforms, String).ilike(f"%{target}%"))

    if request.os:
        stmt = stmt.where(cast(ResourceModel.platforms, String).ilike(f"%{request.os}%"))

    return stmt
