from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(default="ok", description="Application health status")
    environment: str = Field(description="Active runtime environment")
    version: str = Field(default="0.1.0", description="API version")
    database: str = Field(description="Database connectivity status: healthy or degraded")
