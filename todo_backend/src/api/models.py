from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TodoCreate(BaseModel):
    """Payload for creating a todo."""

    title: str = Field(..., description="Todo title (will be trimmed; must not be empty).")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = (v or "").strip()
        if not trimmed:
            # We intentionally raise ValueError so FastAPI returns 422; handler converts to {message}.
            raise ValueError("Title must not be empty.")
        return trimmed


class TodoUpdate(BaseModel):
    """Payload for updating a todo."""

    title: Optional[str] = Field(None, description="Todo title (trimmed; must not be empty if provided).")
    completed: Optional[bool] = Field(None, description="Whether the todo is completed.")

    @field_validator("title")
    @classmethod
    def validate_title_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Title must not be empty.")
        return trimmed


class TodoResponse(BaseModel):
    """Response model for a todo item."""

    id: int = Field(..., description="Todo ID.")
    title: str = Field(..., description="Todo title.")
    completed: bool = Field(..., description="Whether the todo is completed.")
    created_at: Optional[datetime] = Field(None, description="Created timestamp (ISO-8601).")
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp (ISO-8601).")
