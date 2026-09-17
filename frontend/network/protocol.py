"""
Frontend Protocol & Message Framing Module.
Handles client-side NDJSON encoding and response parsing.
Strictly isolated: does NOT import backend code or database modules.
"""

import json


class ClientProtocolError(Exception):
    """Raised when incoming bytes from the server violate NDJSON or JSON format."""
    pass


class ServerError(Exception):
    """Raised when the backend server returns an error response."""
    pass


def encode_request(action: str, **params) -> bytes:
    """
    Serializes a client action and parameters into a Newline-Delimited JSON (NDJSON) byte string.
    Appends a newline '\\n' so the server stream socket can reliably detect message boundaries.
    """
    payload = {"action": action}
    payload.update(params)
    json_str = json.dumps(payload, separators=(",", ":"))
    return (json_str + "\n").encode("utf-8")


def decode_response(line: str) -> dict:
    """
    Parses a single newline-terminated JSON response line received from the server.
    Raises ClientProtocolError if the line is not valid JSON or not an object.
    """
    clean_line = line.strip()
    if not clean_line:
        raise ClientProtocolError("Received empty response line from server.")

    try:
        response_dict = json.loads(clean_line)
    except json.JSONDecodeError as err:
        raise ClientProtocolError(f"Malformed JSON response from server: {err.msg}") from err

    if not isinstance(response_dict, dict):
        raise ClientProtocolError(f"Server response must be a JSON object, got: {type(response_dict).__name__}")

    return response_dict
