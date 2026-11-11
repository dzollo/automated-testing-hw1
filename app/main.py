"""Small in-memory REST API used as a deterministic test target."""

from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Request contract for creating a user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100, examples=["Alice"])
    # Адрес, которого нет в начальных данных, чтобы пример давал 201, а не 409.
    email: EmailStr = Field(examples=["new.user@example.com"])
    age: int = Field(ge=18, le=65, examples=[30])


class UserResponse(BaseModel):
    """Response contract returned by the user endpoints."""

    id: int = Field(gt=0, examples=[1])
    name: str
    email: EmailStr
    age: int = Field(ge=18, le=65)


class MessageResponse(BaseModel):
    """Body of 400 responses produced by FastAPI when the body cannot be decoded."""

    detail: str = Field(examples=["There was an error parsing the body"])


class ErrorDetail(BaseModel):
    """Machine-readable application error."""

    code: str = Field(examples=["USER_NOT_FOUND"])
    message: str = Field(examples=["User with ID 42 was not found"])


class ErrorResponse(BaseModel):
    """Body of errors raised via HTTPException(detail={...})."""

    detail: ErrorDetail


class ValidationErrorItem(BaseModel):
    """One FastAPI/Pydantic validation error."""

    model_config = ConfigDict(extra="allow")

    type: str
    loc: list[str | int]
    msg: str


class ValidationErrorResponse(BaseModel):
    """Body of 422 responses produced by request validation."""

    detail: list[ValidationErrorItem]


NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "User not found"}
}
CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {
        "model": ErrorResponse,
        "description": "A user with this email already exists",
    }
}
INVALID: dict[int | str, dict[str, Any]] = {
    422: {
        "model": ValidationErrorResponse,
        "description": "Request validation failed (including syntactically invalid JSON)",
    }
}
BAD_REQUEST: dict[int | str, dict[str, Any]] = {
    400: {
        "model": MessageResponse,
        "description": "Request body could not be decoded (e.g. invalid UTF-8)",
    }
}


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
        operation_id="list_users",
        response_model=list[UserResponse],
        tags=["users"],
        summary="List users",
    )
    def list_users() -> list[UserResponse]:
        """Return all users sorted by ID."""

        return [users[user_id] for user_id in sorted(users)]

    @app.get(
        "/users/{user_id}",
        operation_id="get_user",
        response_model=UserResponse,
        tags=["users"],
        summary="Get a user by ID",
        responses={**NOT_FOUND, **INVALID},
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
        operation_id="create_user",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["users"],
        summary="Create a user",
        responses={
            201: {
                "description": "User created",
                "links": {
                    "GetCreatedUser": {
                        "operationId": "get_user",
                        "parameters": {"user_id": "$response.body#/id"},
                        "description": "Fetch the user that was just created",
                    }
                },
            },
            **BAD_REQUEST,
            **CONFLICT,
            **INVALID,
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
