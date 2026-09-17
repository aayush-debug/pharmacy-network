"""
UDP Server Discovery Responder.
Listens for discovery datagrams from clients and replies with the active TCP/HTTP connection ports.
Demonstrates connectionless UDP socket programming in Python.
"""

from datetime import datetime, timezone
import json
import socket
import threading
from backend.app import config


class DiscoveryServer:
    """
    UDP Service Discovery responder.
    Listens for 'DISCOVER_PHARMACY_SERVER' broadcasts and sends back server connection metadata.
    """

    def __init__(
        self,
        host: str = config.UDP_HOST,
        port: int = config.UDP_PORT,
        tcp_port: int = config.TCP_PORT,
        http_port: int = config.HTTP_PORT,
    ):
        self.host = host
        self.port = port
        self.tcp_port = tcp_port
        self.http_port = http_port
        self.sock: socket.socket | None = None
        self.is_running = False
        self._thread: threading.Thread | None = None

    def start(self, blocking: bool = True) -> None:
        """Initializes the UDP datagram socket and begins listening for discovery packets."""
        # 1. Create UDP datagram socket (AF_INET = IPv4, SOCK_DGRAM = UDP)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 2. Bind UDP socket to host and port
        self.sock.bind((self.host, self.port))
        self.is_running = True

        print(f"[UDP Discovery] Listening for discovery requests on {self.host}:{self.port} (UDP)")

        if blocking:
            self._listen_loop()
        else:
            self._thread = threading.Thread(target=self._listen_loop, name="UDPDiscoveryLoop", daemon=True)
            self._thread.start()

    def _listen_loop(self) -> None:
        """Loop receiving incoming UDP datagrams and responding to discovery requests."""
        while self.is_running and self.sock:
            try:
                # 3. Receive datagram (blocks until packet arrives)
                data, client_addr = self.sock.recvfrom(2048)
                message = data.decode("utf-8", errors="replace").strip()

                # Check if packet matches discovery query
                is_discovery = "DISCOVER_PHARMACY_SERVER" in message
                if not is_discovery:
                    try:
                        parsed = json.loads(message)
                        if parsed.get("action") == "DISCOVER_PHARMACY_SERVER":
                            is_discovery = True
                    except Exception:
                        pass

                if is_discovery:
                    print(f"[UDP Discovery] Received discovery probe from {client_addr[0]}:{client_addr[1]}")

                    # 4. Construct server discovery info payload
                    response_payload = {
                        "type": "SERVER_INFO",
                        "server_name": "Pharmacy Stock Network Core",
                        "tcp_host": self.host,
                        "tcp_port": self.tcp_port,
                        "http_port": self.http_port,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    response_bytes = json.dumps(response_payload).encode("utf-8")

                    # 5. Send response directly back to client address using sendto()
                    self.sock.sendto(response_bytes, client_addr)

            except OSError:
                # Occurs when socket is closed during stop()
                break

    def stop(self) -> None:
        """Stops the UDP discovery listener and closes socket."""
        self.is_running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        print(f"[UDP Discovery] Stopped on {self.host}:{self.port}")


if __name__ == "__main__":
    import signal
    import sys

    server = DiscoveryServer()

    def handle_sigint(sig, frame):
        print("\n[UDP Discovery] Shutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    print("=== Pharmacy Network UDP Discovery Server ===")
    print("Press Ctrl+C to stop.")
    server.start(blocking=True)
