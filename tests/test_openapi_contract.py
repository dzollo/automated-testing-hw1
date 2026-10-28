"""Schema-driven API contract tests."""

import schemathesis

from app.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@schema.parametrize()
def test_api_conforms_to_openapi(case) -> None:
    """Generate requests and validate API responses against OpenAPI."""

    case.call_and_validate()
