from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class Unauthorized(AppError):
    def __init__(self, message: str = "Требуется вход") -> None:
        super().__init__("unauthorized", message, 401)


class Forbidden(AppError):
    def __init__(self, message: str = "Действие недоступно") -> None:
        super().__init__("forbidden", message, 403)


class NotFound(AppError):
    def __init__(self, message: str = "Не найдено") -> None:
        super().__init__("not_found", message, 404)


class Conflict(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, 409, details)


class Gone(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 410)


class Unprocessable(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, 422, details)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Неверные данные запроса",
                    "details": {"fields": jsonable_encoder(exc.errors())},
                }
            },
        )
