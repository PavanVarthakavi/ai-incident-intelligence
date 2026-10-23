"""Write the API's OpenAPI schema, the contract the frontend's types are generated from.

python -m app.openapi ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from app.config import Settings
from app.main import create_app


def main() -> None:
    # Fixed settings, so the schema is identical on every machine.
    settings = Settings(_env_file=None, environment="local", ANTHROPIC_API_KEY=None)
    schema = create_app(settings).openapi()
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
