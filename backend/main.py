"""
Unified Backend Server Launcher.
Starts all 4 backend network server daemons concurrently:
1. TCP Socket Server (Port 5000)
2. UDP Discovery Server (Port 5001)
3. HTTP REST API Server (Port 8000)
4. FTP File Transfer Server (Port 2121)

Press Ctrl+C to cleanly stop all servers.
"""

from pathlib import Path
import signal
import sys
import time

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app import config
from backend.app.ftp.reports import generate_all_reports
from backend.app.ftp.server import PharmacyFTPServer
from backend.app.http.server import PharmacyHTTPServer
from backend.app.tcp.server import TCPServer
from backend.app.udp.discovery_server import DiscoveryServer


def main():
    print("=" * 65)
    print("      PHARMACY NETWORK — UNIFIED BACKEND SERVER STACK        ")
    print("=" * 65)
    print(f"Database Path: {config.DB_PATH}")

    # Ensure fresh reports exist for FTP service
    try:
        generate_all_reports()
    except Exception as e:
        print(f"[Warning] Initial report generation note: {e}")

    # 1. TCP Server
    tcp_server = TCPServer(host=config.TCP_HOST, port=config.TCP_PORT)
    tcp_server.start(blocking=False)

    # 2. UDP Discovery Server
    udp_discovery = DiscoveryServer(
        host=config.UDP_HOST,
        port=config.UDP_PORT,
        tcp_port=config.TCP_PORT,
        http_port=config.HTTP_PORT,
    )
    udp_discovery.start(blocking=False)

    # 3. HTTP REST API Server
    http_server = PharmacyHTTPServer(host=config.HTTP_HOST, port=config.HTTP_PORT)
    http_server.start(blocking=False)

    # 4. FTP File Transfer Server
    ftp_server = PharmacyFTPServer(
        host=config.FTP_HOST,
        port=config.FTP_PORT,
        user=config.FTP_USER,
        password=config.FTP_PASS,
    )
    ftp_server.start(blocking=False)

    print("-" * 65)
    print("All backend network services are running:")
    print(f"  • TCP Socket Server:   {config.TCP_HOST}:{config.TCP_PORT}")
    print(f"  • UDP Discovery:       {config.UDP_HOST}:{config.UDP_PORT}")
    print(f"  • UDP Alert Listener:  {config.UDP_HOST}:{config.UDP_ALERT_PORT}")
    print(f"  • HTTP REST API:       http://{config.HTTP_HOST}:{config.HTTP_PORT}/api")
    print(f"  • FTP Reports Server:  ftp://{config.FTP_HOST}:{config.FTP_PORT} (User: {config.FTP_USER})")
    print("-" * 65)
    print("Ready for PySide6 client connections. Press Ctrl+C to stop.")

    def shutdown(sig, frame):
        print("\n[System] Initiating graceful shutdown of all servers...")
        try:
            tcp_server.stop()
        except Exception:
            pass
        try:
            udp_discovery.stop()
        except Exception:
            pass
        try:
            http_server.stop()
        except Exception:
            pass
        try:
            ftp_server.stop()
        except Exception:
            pass
        print("[System] All servers stopped cleanly. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep main thread alive
    while True:
        try:
            time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            shutdown(None, None)


if __name__ == "__main__":
    main()
