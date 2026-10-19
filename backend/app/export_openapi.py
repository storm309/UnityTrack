"""Export the OpenAPI JSON schema for TypeScript type generation."""

import json
from pathlib import Path

from app.main import create_app


def export_openapi() -> None:
    """Generate openapi.json file from FastAPI application."""
    app = create_app()
    openapi_schema = app.openapi()
    output_path = Path(__file__).resolve().parent.parent / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"OpenAPI schema successfully written to {output_path}")


if __name__ == "__main__":
    export_openapi()
