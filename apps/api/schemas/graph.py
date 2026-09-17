from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class GraphEdgeBase(BaseModel):
    subject_id: str = Field(..., json_schema_extra={"example": "ros-navigation/nav2"})
    predicate: str = Field(..., json_schema_extra={"example": "depends-on"})
    object_id: str = Field(..., json_schema_extra={"example": "ros-controls/ros2_control"})
    properties: Optional[Dict[str, Any]] = Field(default=None, validation_alias="properties_json")

    model_config = ConfigDict(populate_by_name=True)


class GraphEdgeCreate(GraphEdgeBase):
    pass


class GraphEdgeRead(GraphEdgeBase):
    id: int
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
