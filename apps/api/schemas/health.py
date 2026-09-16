from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "healthy"})
    version: str = Field(..., json_schema_extra={"example": "0.1.0"})
    environment: str = Field(..., json_schema_extra={"example": "development"})
    database: str = Field(..., json_schema_extra={"example": "connected"})
