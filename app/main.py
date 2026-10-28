"""Small in-memory REST API used as a deterministic test target."""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Request contract for creating a user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100, examples=["Alice"])
    email: EmailStr = Field(examples=["alice@example.com"])
    age: int = Field(ge=18, le=65, examples=[30])


class UserResponse(BaseModel):
    """Response contract returned by the user endpoints."""

    id: int = Field(gt=0, examples=[1])
    name: str
    email: EmailStr
    age: int = Field(ge=18, le=65)


def create_app() -> FastAPI:
    """Create an isolated app instance with fresh in-memory test data."""

    app = FastAPI(
        title="Users Mock API",
        description=(
            "A sample REST API for automated testing. "
            "Data is stored in memory and reset whenever the app is created."
        ),
        version="1.0.0",
    )

    users: dict[int, UserResponse] = {
        1: UserResponse(
            id=1,
            name="Alice Example",
            email="alice@example.com",
            age=30,
        )
    }
    next_user_id = 2

    @app.options("/users", include_in_schema=False)
    def options_users() -> Response:
        """Advertise the HTTP methods supported by the users resource."""

        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={"Allow": "GET, POST"},
        )

    @app.get(
        "/users",
        response_model=list[UserResponse],
        tags=["users"],
        summary="List users",
    )
    def list_users() -> list[UserResponse]:
        """Return all users sorted by ID."""

        return [users[user_id] for user_id in sorted(users)]

    @app.get(
        "/users/{user_id}",
        response_model=UserResponse,
        tags=["users"],
        summary="Get a user by ID",
        responses={404: {"description": "User not found"}},
    )
    def get_user(
        user_id: Annotated[
            int,
            Path(gt=0, description="The positive ID of the user"),
        ],
    ) -> UserResponse:
        """Return a user or a structured 404 error."""

        user = users.get(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "USER_NOT_FOUND",
                    "message": f"User with ID {user_id} was not found",
                },
            )

        return user

    @app.post(
        "/users",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["users"],
        summary="Create a user",
        responses={
            400: {"description": "Malformed JSON request body"},
            409: {"description": "A user with this email already exists"},
            422: {"description": "Request validation failed"},
        },
    )
    def create_user(payload: UserCreate, response: Response) -> UserResponse:
        """Create a user after validating uniqueness and field constraints."""

        nonlocal next_user_id

        email = str(payload.email).lower()
        if any(str(user.email).lower() == email for user in users.values()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "EMAIL_ALREADY_EXISTS",
                    "message": "A user with this email already exists",
                },
            )

        user = UserResponse(
            id=next_user_id,
            name=payload.name,
            email=payload.email,
            age=payload.age,
        )
        users[next_user_id] = user
        next_user_id += 1

        response.headers["Location"] = f"/users/{user.id}"
        return user

    return app


app = create_app()
