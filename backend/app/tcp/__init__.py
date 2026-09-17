"""
TCP Package initialization for Pharmacy Stock Query System backend.
Provides protocol parser, message framer, and multi-threaded TCP server.
"""

from backend.app.tcp.protocol import (
    create_error_response,
    create_success_response,
    decode_line,
    encode_message,
    handle_request,
    process_raw_line,
)
from backend.app.tcp.server import TCPServer

__all__ = [
    "TCPServer",
    "encode_message",
    "decode_line",
    "create_success_response",
    "create_error_response",
    "handle_request",
    "process_raw_line",
]
