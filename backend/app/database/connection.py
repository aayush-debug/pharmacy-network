"""
Database Connection Manager for Backend.
Provides connections with foreign key enforcement and row factory configuration.
"""

import sqlite3
from pathlib import Path
from backend.app import config


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """
    Creates and returns a SQLite database connection.
    - Enables foreign key constraint checking (PRAGMA foreign_keys = ON).
    - Configures sqlite3.Row row_factory for column-name dictionary-like access.
    """
    target_path = Path(db_path) if db_path else config.DB_PATH

    # Ensure processed directory exists before creating/connecting to the DB
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
