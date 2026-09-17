"""
Database package for Pharmacy Stock Query System backend.
Provides connection handling, schema initialization, and seeding.
"""

from backend.app.database.connection import get_connection
from backend.app.database.init_db import init_database

__all__ = ["get_connection", "init_database"]

