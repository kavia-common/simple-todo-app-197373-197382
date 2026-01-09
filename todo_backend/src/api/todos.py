from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from src.api.db import bool_from_db, bool_to_db, get_connection
from src.api.models import TodoCreate, TodoResponse, TodoUpdate

router = APIRouter(prefix="/api/todos", tags=["Todos"])


class ErrorMessage(BaseModel):
    """Consistent error response payload."""

    message: str = Field(..., description="Human-readable error message.")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        # SQLite stores TEXT; assume ISO-8601 or None
        return datetime.fromisoformat(value)
    except Exception:
        # If DB contains unexpected format, avoid failing the API; return None
        return None


def _row_to_todo(row) -> TodoResponse:
    return TodoResponse(
        id=int(row["id"]),
        title=str(row["title"]),
        completed=bool_from_db(row["completed"]),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )


def _not_found(todo_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": f"Todo {todo_id} not found."},
    )


@router.get(
    "",
    response_model=List[TodoResponse],
    summary="List todos",
    description="Return all todos ordered by created_at descending.",
    responses={400: {"model": ErrorMessage}},
    operation_id="listTodos",
)
def list_todos() -> List[TodoResponse]:
    """List all todos (newest first)."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT id, title, completed, created_at, updated_at
            FROM todos
            ORDER BY
              CASE WHEN created_at IS NULL THEN 1 ELSE 0 END,
              created_at DESC,
              id DESC
            """
        )
        rows = cur.fetchall()
        return [_row_to_todo(r) for r in rows]


@router.post(
    "",
    response_model=TodoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create todo",
    description="Create a new todo. Title is trimmed and must not be empty.",
    responses={400: {"model": ErrorMessage}},
    operation_id="createTodo",
)
def create_todo(payload: TodoCreate) -> TodoResponse:
    """Create a new todo."""
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Title must not be empty."})

    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO todos (title, completed, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (title, 0, now, now),
        )
        todo_id = cur.lastrowid
        row = conn.execute(
            """
            SELECT id, title, completed, created_at, updated_at
            FROM todos
            WHERE id = ?
            """,
            (todo_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Failed to create todo."})
    return _row_to_todo(row)


@router.get(
    "/{todo_id}",
    response_model=TodoResponse,
    summary="Get todo",
    description="Get a todo by ID.",
    responses={404: {"model": ErrorMessage}},
    operation_id="getTodo",
)
def get_todo(todo_id: int) -> TodoResponse:
    """Get a single todo by id."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, completed, created_at, updated_at
            FROM todos
            WHERE id = ?
            """,
            (todo_id,),
        ).fetchone()

    if not row:
        raise _not_found(todo_id)
    return _row_to_todo(row)


@router.put(
    "/{todo_id}",
    response_model=TodoResponse,
    summary="Update todo",
    description="Full update of a todo's title and completed fields.",
    responses={400: {"model": ErrorMessage}, 404: {"model": ErrorMessage}},
    operation_id="updateTodo",
)
def update_todo(todo_id: int, payload: TodoUpdate) -> TodoResponse:
    """Full update for a todo."""
    # For PUT, require both fields (title + completed) to be present.
    if payload.title is None or payload.completed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Both 'title' and 'completed' are required for PUT."},
        )

    title = payload.title.strip() if payload.title is not None else ""
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Title must not be empty."})

    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if not existing:
            raise _not_found(todo_id)

        conn.execute(
            """
            UPDATE todos
            SET title = ?, completed = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, bool_to_db(bool(payload.completed)), now, todo_id),
        )
        row = conn.execute(
            """
            SELECT id, title, completed, created_at, updated_at
            FROM todos
            WHERE id = ?
            """,
            (todo_id,),
        ).fetchone()

    if not row:
        raise _not_found(todo_id)
    return _row_to_todo(row)


@router.patch(
    "/{todo_id}/toggle",
    response_model=TodoResponse,
    summary="Toggle completed",
    description="Flip the completed state for a todo.",
    responses={404: {"model": ErrorMessage}},
    operation_id="toggleTodo",
)
def toggle_todo(todo_id: int) -> TodoResponse:
    """Toggle a todo's completed state."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, completed FROM todos WHERE id = ?",
            (todo_id,),
        ).fetchone()
        if not row:
            raise _not_found(todo_id)

        new_completed = 0 if bool_from_db(row["completed"]) else 1
        conn.execute(
            """
            UPDATE todos
            SET completed = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_completed, now, todo_id),
        )
        updated = conn.execute(
            """
            SELECT id, title, completed, created_at, updated_at
            FROM todos
            WHERE id = ?
            """,
            (todo_id,),
        ).fetchone()

    if not updated:
        raise _not_found(todo_id)
    return _row_to_todo(updated)


@router.delete(
    "/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete todo",
    description="Delete a todo by ID.",
    responses={404: {"model": ErrorMessage}},
    operation_id="deleteTodo",
)
def delete_todo(todo_id: int) -> Response:
    """Delete a todo."""
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if not existing:
            raise _not_found(todo_id)

        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
