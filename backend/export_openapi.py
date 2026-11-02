import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.main import app  # noqa: E402

openapi_path = backend_dir / "openapi.json"
with open(openapi_path, "w", encoding="utf-8") as f:
    json.dump(app.openapi(), f, indent=2)

print(f"OpenAPI schema exported to {openapi_path}")

