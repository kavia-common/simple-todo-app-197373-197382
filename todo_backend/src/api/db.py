import os
import re
import sqlite3
from functools import lru_cache
from typing import Optional


DB_CONNECTION_FILE_DEFAULT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "simple-todo-app-197373-197384",
        "database",
        "db_connection.txt",
    )
)


@lru_cache(maxsize=1)
def _get_db_path_from_connection_file(connection_file_path: str) -> str:
    """
    Parse db_connection.txt and return the canonical SQLite database file path.

    Expected line format (as produced by the DB container tooling):
      # File path: /abs/path/to/myapp.db
    """
    if not os.path.exists(connection_file_path):
        raise FileNotFoundError(
            f"db_connection.txt not found at '{connection_file_path}'. "
            "Ensure the database container has been initialized and the path is available."
        )

    with open(connection_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"^\s*#\s*File path:\s*(.+?)\s*$", content, flags=re.MULTILINE)
    if not match:
        raise ValueError(
            f"Could not find canonical SQLite file path in '{connection_file_path}'. "
            "Expected a line like: '# File path: /abs/path/to/myapp.db'"
        )

    db_path = match.group(1).strip()
    if not db_path:
        raise ValueError("Parsed SQLite DB path was empty.")
    return db_path


def get_db_path() -> str:
    """
    Get the SQLite DB file path from db_connection.txt.

    Allows override via TODO_DB_CONNECTION_FILE env var to support different deployments.
    """
    connection_file_path = os.getenv("TODO_DB_CONNECTION_FILE", DB_CONNECTION_FILE_DEFAULT)
    return _get_db_path_from_connection_file(connection_file_path)


def get_connection() -> sqlite3.Connection:
    """
    Create a sqlite3 connection with safe defaults.

    Returns a connection where rows can be accessed as dict-like objects.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def bool_from_db(value: Optional[int]) -> bool:
    """Convert SQLite integer boolean to Python bool."""
    return bool(int(value or 0))


def bool_to_db(value: bool) -> int:
    """Convert Python bool to SQLite integer boolean."""
    return 1 if value else 0
