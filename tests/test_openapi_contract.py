"""Schema-driven API contract tests."""

import schemathesis
from hypothesis import settings

from app.main import create_app

schema = schemathesis.openapi.from_asgi("/openapi.json", create_app())


@schema.parametrize()  # type: ignore
def test_api_conforms_to_openapi(case) -> None:  # type: ignore
    """Generate requests and validate API responses against OpenAPI."""

    case.call_and_validate()  # type: ignore


# Stateful: Schemathesis идёт по links из спецификации (POST /users -> GET /users/{id}).
TestUserWorkflow = schema.as_state_machine().TestCase
TestUserWorkflow.settings = settings(
    max_examples=25, stateful_step_count=5, deadline=None
)
