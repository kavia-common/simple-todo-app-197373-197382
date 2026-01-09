from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.todos import router as todos_router

openapi_tags = [
    {
        "name": "Todos",
        "description": "CRUD operations for todo items.",
    }
]

app = FastAPI(
    title="Simple Todo API",
    description="FastAPI backend for a simple todo app (SQLite-backed).",
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# CORS: allow the React dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException := Exception)  # type: ignore[misc]
async def _http_exception_passthrough(request: Request, exc: Exception):
    """
    Preserve FastAPI's HTTPException detail if it already matches {message},
    otherwise normalize to {message}.
    """
    # Avoid importing HTTPException directly to keep handler simple and safe:
    # FastAPI's HTTPException has attributes: status_code, detail.
    if exc.__class__.__name__ == "HTTPException":
        status_code = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict) and "message" in detail:
            return JSONResponse(status_code=status_code, content=detail)
        return JSONResponse(status_code=status_code, content={"message": str(detail) if detail else "Request failed."})

    # Fall back for non-HTTP exceptions
    return JSONResponse(status_code=500, content={"message": "Internal server error."})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Normalize validation errors to {message} with 400 status code."""
    # Convert FastAPI's default 422 to 400 as requested.
    return JSONResponse(status_code=400, content={"message": "Invalid input."})


app.include_router(todos_router)


@app.get("/", tags=["Todos"], summary="Health check", description="Simple health check endpoint.")
def health_check():
    """Health check."""
    return {"message": "Healthy"}
