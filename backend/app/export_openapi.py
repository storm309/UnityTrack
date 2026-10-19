"""Export the OpenAPI JSON schema for TypeScript type generation."""

import json
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import create_app  # noqa: E402


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
