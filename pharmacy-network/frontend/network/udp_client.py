"""
Frontend UDP Client Module.
Implements:
1. UDP Server Discovery: Discovers the active pharmacy TCP/HTTP ports dynamically.
2. UDP Alert Listener: Background datagram listener for real-time low-stock push alerts.
"""

from collections.abc import Callable
import json
import socket
import threading
from frontend.network import config


def discover_pharmacy_server(
    discovery_host: str = "127.0.0.1",
    discovery_port: int = 5001,
    timeout: float = 2.0,
) -> dict | None:
    """
    Broadcasts a 'DISCOVER_PHARMACY_SERVER' datagram and listens for a response.
    Returns the server metadata dict containing 'tcp_port', 'http_port', etc.,
    or None if the discovery probe times out.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        probe_message = b"DISCOVER_PHARMACY_SERVER"
        sock.sendto(probe_message, (discovery_host, discovery_port))

        data, server_addr = sock.recvfrom(2048)
        info = json.loads(data.decode("utf-8"))
        info["discovered_from_ip"] = server_addr[0]
        return info

    except (TimeoutError, socket.timeout):
        return None
    except Exception as err:
        print(f"[UDP Discovery Error]: {err}")
        return None
    finally:
        sock.close()


class UDPAlertListener:
    """
    Asynchronous UDP datagram listener running on a dedicated thread.
    Listens for 'LOW_STOCK' push alert packets from the backend.
    """

    def __init__(
        self,
        listen_host: str = "127.0.0.1",
        listen_port: int = 5002,
        on_alert_received: Callable[[dict], None] | None = None,
    ):
        self.host = listen_host
        self.port = listen_port
        self.on_alert_received = on_alert_received
        self.sock: socket.socket | None = None
        self.is_running = False
        self._thread: threading.Thread | None = None
        self.received_alerts: list[dict] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        """Starts the UDP datagram listener thread."""
        if self.is_running:
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.is_running = True

        self._thread = threading.Thread(target=self._listen_loop, name="UDPAlertListenerThread", daemon=True)
        self._thread.start()
        print(f"[UDP Alert Listener] Listening on {self.host}:{self.port}")

    def _listen_loop(self) -> None:
        while self.is_running and self.sock:
            try:
                data, sender = self.sock.recvfrom(4096)
                text = data.decode("utf-8", errors="replace")
                alert_dict = json.loads(text)

                with self._lock:
                    self.received_alerts.append(alert_dict)

                if self.on_alert_received:
                    self.on_alert_received(alert_dict)

            except OSError:
                break
            except Exception as err:
                print(f"[UDP Alert Listener Error]: {err}")

    def stop(self) -> None:
        """Shuts down the listener socket cleanly."""
        self.is_running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
