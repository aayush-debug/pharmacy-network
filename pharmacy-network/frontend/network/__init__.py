"""
Pharmacy Network Frontend — Network Package.
Handles network communication (TCP client socket, NDJSON parsing) to the backend.
Frontend NEVER accesses SQLite or backend code directly.
"""

from frontend.network.protocol import ClientProtocolError, ServerError
from frontend.network.tcp_client import PharmacyTCPClient

__all__ = ["PharmacyTCPClient", "ClientProtocolError", "ServerError"]
