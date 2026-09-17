"""
Multi-Threaded TCP Socket Server.
Listens for incoming client connections, assigns a dedicated worker thread
to each client, and processes requests using Newline-Delimited JSON (NDJSON).
Uses only Python standard library socket and threading modules.
"""

import socket
import threading
from pathlib import Path
from backend.app import config
from backend.app.tcp import protocol


class TCPServer:
    """
    Multi-threaded TCP Socket Server for the Pharmacy Network.
    Demonstrates Layer 4 TCP/IP socket programming in Python.
    """

    def __init__(
        self,
        host: str = config.TCP_HOST,
        port: int = config.TCP_PORT,
        db_path: Path | str | None = None,
        backlog: int = 5,
    ):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.backlog = backlog
        self.server_socket: socket.socket | None = None
        self.is_running = False
        self._active_threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    def start(self, blocking: bool = True) -> None:
        """
        Creates, binds, listens, and starts accepting client connections.
        If blocking is True, blocks the calling thread in the accept loop.
        If blocking is False, runs the accept loop in a background thread.
        """
        # 1. Create TCP/IP socket (AF_INET = IPv4, SOCK_STREAM = TCP)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 2. Allow immediate address reuse upon restart
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 3. Bind socket to host and port
        self.server_socket.bind((self.host, self.port))
        self.port = self.server_socket.getsockname()[1]

        # 4. Listen for incoming client connections
        self.server_socket.listen(self.backlog)
        self.is_running = True

        print(f"[TCP Server] Listening on {self.host}:{self.port} (backlog={self.backlog})")

        if blocking:
            self._accept_loop()
        else:
            accept_thread = threading.Thread(target=self._accept_loop, name="TCPAcceptLoop", daemon=True)
            accept_thread.start()

    def _accept_loop(self) -> None:
        """Continuously accepts incoming client connections and spawns worker threads."""
        while self.is_running and self.server_socket:
            try:
                # 5. Accept client connection (blocks until a client connects)
                client_sock, client_addr = self.server_socket.accept()
                print(f"[TCP Server] Accepted connection from {client_addr[0]}:{client_addr[1]}")

                # 6. Spawn a dedicated worker thread for the client
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    name=f"ClientWorker-{client_addr[0]}:{client_addr[1]}",
                    daemon=True,
                )
                with self._lock:
                    self._active_threads.append(client_thread)
                client_thread.start()

            except OSError:
                # Occurs when the server socket is closed during stop()
                break

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple) -> None:
        """
        Worker function running on a dedicated thread for a single connected client.
        Accumulates byte stream chunks and extracts newline-delimited JSON messages.
        """
        buffer = ""
        client_ip, client_port = client_addr[0], client_addr[1]

        try:
            while self.is_running:
                # 7. Receive raw bytes from TCP stream (up to 4096 bytes at a time)
                chunk = client_sock.recv(4096)
                if not chunk:
                    # An empty bytes object indicates the client has cleanly disconnected
                    print(f"[TCP Server] Client {client_ip}:{client_port} disconnected cleanly.")
                    break

                # Decode chunk to text and append to stream buffer
                buffer += chunk.decode("utf-8", errors="replace")

                # 8. Process every complete message terminated by '\n' (NDJSON framing)
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    # 9. Route message through protocol and service layer
                    response_dict = protocol.process_raw_line(line, db_path=self.db_path)

                    # 10. Frame and serialize response to NDJSON bytes
                    response_bytes = protocol.encode_message(response_dict)

                    # 11. Send complete byte buffer back to client
                    client_sock.sendall(response_bytes)

        except (ConnectionResetError, BrokenPipeError):
            print(f"[TCP Server] Connection reset by client {client_ip}:{client_port}")
        except Exception as err:
            print(f"[TCP Server] Error handling client {client_ip}:{client_port}: {err}")
        finally:
            # 12. Close client socket cleanly
            try:
                client_sock.close()
            except Exception:
                pass

    def stop(self) -> None:
        """Shuts down the server socket and stops the accept loop."""
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
        print(f"[TCP Server] Stopped on {self.host}:{self.port}")


if __name__ == "__main__":
    import signal
    import sys

    server = TCPServer()

    def handle_sigint(sig, frame):
        print("\n[TCP Server] Shutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    print("=== Pharmacy Network TCP Socket Server ===")
    print("Press Ctrl+C to stop.")
    server.start(blocking=True)
