"""Health-check response schema."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = Field(description="Application service name")
    environment: str = Field(description="Current runtime environment")
    version: str = Field(default="0.1.0", description="API version")
