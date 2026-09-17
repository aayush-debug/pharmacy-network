"""
Frontend Network Configuration.
Specifies connection parameters to reach the backend TCP server.
Independent of backend code and database files.
"""

import os

TCP_SERVER_HOST: str = os.environ.get("PHARMACY_SERVER_HOST", "127.0.0.1")
TCP_SERVER_PORT: int = int(os.environ.get("PHARMACY_SERVER_PORT", "5000"))
