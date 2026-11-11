"""Multi-step user scenarios against a fresh app instance."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

NEW_USER: dict[str, Any] = {"name": "Bob", "email": "bob.new@example.com", "age": 30}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_create_user_then_get_by_id(client: TestClient) -> None:
    created = client.post("/users", json=NEW_USER)
    assert created.status_code == 201

    body = created.json()
    assert body["email"] == NEW_USER["email"]
    assert created.headers["Location"] == f"/users/{body['id']}"

    fetched = client.get(f"/users/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body

    assert body in client.get("/users").json()


def test_duplicate_email_returns_409(client: TestClient) -> None:
    assert client.post("/users", json=NEW_USER).status_code == 201

    duplicate = client.post("/users", json={**NEW_USER, "name": "Other"})
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": {
            "code": "EMAIL_ALREADY_EXISTS",
            "message": "A user with this email already exists",
        }
    }
    # Дубликат не должен создать лишнюю запись: alice + bob.
    assert len(client.get("/users").json()) == 2


def test_duplicate_email_is_case_insensitive(client: TestClient) -> None:
    assert client.post("/users", json=NEW_USER).status_code == 201

    upper = {**NEW_USER, "email": NEW_USER["email"].upper()}
    assert client.post("/users", json=upper).status_code == 409


def test_seed_user_email_is_taken(client: TestClient) -> None:
    response = client.post("/users", json={**NEW_USER, "email": "alice@example.com"})
    assert response.status_code == 409


def test_ids_are_sequential_and_unique(client: TestClient) -> None:
    first = client.post("/users", json=NEW_USER).json()["id"]
    second = client.post(
        "/users", json={**NEW_USER, "email": "second@example.com"}
    ).json()["id"]
    assert (first, second) == (2, 3)


def test_unknown_user_returns_structured_404(client: TestClient) -> None:
    response = client.get("/users/999")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "USER_NOT_FOUND"


@pytest.mark.parametrize("age", [18, 65])
def test_age_boundaries_are_accepted(client: TestClient, age: int) -> None:
    payload: dict[str, Any] = {**NEW_USER, "email": f"age{age}@example.com", "age": age}
    assert client.post("/users", json=payload).status_code == 201


@pytest.mark.parametrize("age", [17, 66])
def test_age_outside_boundaries_is_rejected(client: TestClient, age: int) -> None:
    response = client.post("/users", json={**NEW_USER, "age": age})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "age"]


def test_invalid_email_is_rejected(client: TestClient) -> None:
    response = client.post("/users", json={**NEW_USER, "email": "not-an-email"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


def test_whitespace_only_name_is_rejected(client: TestClient) -> None:
    response = client.post("/users", json={**NEW_USER, "name": "   "})
    assert response.status_code == 422


def test_malformed_json_returns_422_not_400(client: TestClient) -> None:
    """Фиксирует реальное поведение, с которым согласована спецификация."""

    response = client.post(
        "/users",
        content='{"name": "Bob",',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_non_positive_user_id_is_rejected(client: TestClient) -> None:
    assert client.get("/users/0").status_code == 422
