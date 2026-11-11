"""OpenAPI specification regression test."""

import json
from pathlib import Path

from app.main import app

SPEC_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def test_openapi_specification_is_up_to_date() -> None:
    """Ensure the committed specification matches the application."""

    expected = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert app.openapi() == expected
