"""
UDP Low-Stock Alert Broadcaster.
Sends lightweight UDP datagram push notifications when medicine inventory drops below reorder levels.
Demonstrates connectionless UDP broadcasting.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import socket
from backend.app import config
from backend.app.services import inventory_service


class UDPAlertBroadcaster:
    """
    Transmits real-time UDP alert datagrams to clients.
    Lightweight, fire-and-forget push alerting.
    """

    def __init__(self, broadcast_host: str = "127.0.0.1", broadcast_port: int = config.UDP_ALERT_PORT):
        self.host = broadcast_host
        self.port = broadcast_port

    def send_low_stock_alert(
        self,
        medicine: str,
        pharmacy: str,
        stock: int,
        minimum: int,
        target_host: str | None = None,
        target_port: int | None = None,
    ) -> dict:
        """
        Transmits a single LOW_STOCK UDP datagram packet to the network.
        """
        host = target_host or self.host
        port = target_port or self.port

        payload = {
            "type": "LOW_STOCK",
            "medicine": medicine,
            "pharmacy": pharmacy,
            "stock": stock,
            "minimum": minimum,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        data_bytes = json.dumps(payload).encode("utf-8")

        # Create temporary datagram socket to transmit the packet
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data_bytes, (host, port))
            print(f"[UDP Broadcaster] Sent LOW_STOCK alert for '{medicine}' at '{pharmacy}' to {host}:{port}")
            return payload
        finally:
            sock.close()

    def scan_and_broadcast_all(
        self,
        db_path: Path | str | None = None,
        target_host: str | None = None,
        target_port: int | None = None,
    ) -> list[dict]:
        """
        Queries the service layer for active low-stock conditions
        and broadcasts a UDP alert datagram for each.
        """
        low_items = inventory_service.get_low_stock(db_path=db_path)
        broadcasted = []
        for item in low_items:
            payload = self.send_low_stock_alert(
                medicine=item["brand_name"],
                pharmacy=item["pharmacy_name"],
                stock=item["stock_quantity"],
                minimum=item["minimum_stock"],
                target_host=target_host,
                target_port=target_port,
            )
            broadcasted.append(payload)
        return broadcasted


if __name__ == "__main__":
    broadcaster = UDPAlertBroadcaster()
    print("=== Broadcasting Demo Low-Stock Alert over UDP ===")
    broadcaster.send_low_stock_alert(
        medicine="Mox 500",
        pharmacy="Metro Care Chemist",
        stock=4,
        minimum=10,
    )
