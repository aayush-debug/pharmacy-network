"""
Frontend TCP Client.
Communicates with the backend server exclusively via TCP sockets and NDJSON framing.
Strictly decoupled from SQLite and backend modules.
"""

import socket
import threading
from frontend.network import config
from frontend.network.protocol import (
    ClientProtocolError,
    ServerError,
    decode_response,
    encode_request,
)


class PharmacyTCPClient:
    """
    High-level TCP Socket Client for the Pharmacy Stock Query System.
    Connects to the backend server and provides typed helper methods.
    """

    def __init__(
        self,
        host: str = config.TCP_SERVER_HOST,
        port: int = config.TCP_SERVER_PORT,
        timeout: float = 5.0,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self._buffer: str = ""
        self._lock = threading.Lock()

    def connect(self) -> None:
        """
        Establishes a stream socket connection to the server.
        Performs the TCP 3-way handshake.
        Raises ConnectionRefusedError or TimeoutError on network failure.
        """
        if self.sock is not None:
            return  # Already connected

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self._buffer = ""
        except (ConnectionRefusedError, TimeoutError, OSError) as err:
            if self.sock is not None:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = None
            raise ConnectionError(
                f"Failed to connect to Pharmacy TCP Server at {self.host}:{self.port} - {err}"
            ) from err

    def disconnect(self) -> None:
        """Closes the TCP socket connection cleanly."""
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
            self._buffer = ""

    def is_connected(self) -> bool:
        """Returns True if the client socket is active."""
        return self.sock is not None

    def send_request(self, action: str, **params) -> dict:
        """
        Sends an NDJSON request to the server and blocks until a complete
        newline-terminated JSON response is read from the socket stream.
        Thread-safe across multiple background workers.
        """
        with self._lock:
            if self.sock is None:
                self.connect()

            # 1. Encode request with newline delimiter
            data_bytes = encode_request(action, **params)

            # 2. Transmit bytes across stream socket
            try:
                self.sock.sendall(data_bytes)
            except (BrokenPipeError, ConnectionResetError, OSError) as err:
                self.disconnect()
                raise ConnectionError(f"Lost connection to server while sending: {err}") from err

            # 3. Read bytes until complete '\n' message is assembled
            while "\n" not in self._buffer:
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout as err:
                    raise TimeoutError(f"Server response timed out after {self.timeout}s") from err
                except (ConnectionResetError, OSError) as err:
                    self.disconnect()
                    raise ConnectionError(f"Connection reset by server: {err}") from err

                if not chunk:
                    self.disconnect()
                    raise ConnectionError("Server closed connection unexpectedly (EOF received).")

                self._buffer += chunk.decode("utf-8", errors="replace")

            # 4. Extract single line and decode
            line, self._buffer = self._buffer.split("\n", 1)
            return decode_response(line)

    # =========================================================================
    # High-Level API Methods
    # =========================================================================

    def ping(self) -> dict:
        """Tests connectivity with the backend TCP server."""
        return self.send_request("PING")

    def search_medicines(self, query: str = "") -> list[dict]:
        """
        Searches catalog medicines matching the given brand name, active
        ingredient, or therapeutic category. If query is empty, returns all medicines.
        """
        search_query = query.strip() if query.strip() else "%"
        resp = self.send_request("SEARCH_MEDICINE", query=search_query)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Search failed"))
        return resp.get("results", [])

    def get_low_stock(self, pharmacy_id: int | None = None) -> list[dict]:
        """Queries network for low-stock inventory items."""
        params = {}
        if pharmacy_id is not None:
            params["pharmacy_id"] = pharmacy_id
        resp = self.send_request("GET_LOW_STOCK", **params)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Could not fetch low stock"))
        return resp.get("alerts", [])

    def get_pharmacy_inventory(self, pharmacy_id: int) -> list[dict]:
        """Queries all medicines carried by a specific pharmacy."""
        resp = self.send_request("GET_PHARMACY_INVENTORY", pharmacy_id=pharmacy_id)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Could not fetch inventory"))
        return resp.get("inventory", [])

    def get_medicine(self, medicine_id: int) -> dict | None:
        """Retrieves details of a specific medicine by its unique ID."""
        resp = self.send_request("GET_MEDICINE", medicine_id=medicine_id)
        if resp.get("status") == "error":
            return None
        return resp.get("medicine")

    def check_stock(self, pharmacy_id: int, medicine_id: int) -> dict:
        """Checks the available stock of a specific medicine at a specific pharmacy."""
        resp = self.send_request("CHECK_STOCK", pharmacy_id=pharmacy_id, medicine_id=medicine_id)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Stock check failed"))
        return resp.get("stock", {})

    def find_pharmacies(self, medicine_id: int | None = None) -> list[dict]:
        """
        If medicine_id is provided, returns all pharmacies carrying that medicine
        with stock levels. If medicine_id is None, returns all registered pharmacies.
        """
        if medicine_id is not None:
            resp = self.send_request("CHECK_STOCK", medicine_id=medicine_id)
            if resp.get("status") == "error":
                raise ServerError(resp.get("message", "Pharmacy lookup failed"))
            return resp.get("availability", [])
        else:
            resp = self.send_request("FIND_PHARMACIES")
            if resp.get("status") == "error":
                raise ServerError(resp.get("message", "Pharmacy listing failed"))
            return resp.get("pharmacies", [])

    def place_order(self, pharmacy_id: int, medicine_id: int, quantity: int) -> dict:
        """
        Submits an order for a medicine at a pharmacy.
        Raises ServerError if stock is insufficient or IDs are invalid.
        """
        resp = self.send_request("PLACE_ORDER", pharmacy_id=pharmacy_id, medicine_id=medicine_id, quantity=quantity)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Order placement failed"))
        return resp.get("order", {})

    def get_order(self, order_id: int) -> dict | None:
        """Retrieves details of a placed order by order ID."""
        resp = self.send_request("GET_ORDER", order_id=order_id)
        if resp.get("status") == "error":
            return None
        return resp.get("order")

    def get_pharmacy_orders(self, pharmacy_id: int) -> list[dict]:
        """Retrieves all orders placed at a specific pharmacy branch."""
        resp = self.send_request("GET_PHARMACY_ORDERS", pharmacy_id=pharmacy_id)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Could not fetch orders"))
        return resp.get("orders", [])

    def update_stock(self, pharmacy_id: int, medicine_id: int, quantity: int) -> dict:
        """Updates stock quantity for a medicine at a pharmacy."""
        resp = self.send_request("UPDATE_STOCK", pharmacy_id=pharmacy_id, medicine_id=medicine_id, quantity=quantity)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Stock update failed"))
        return resp.get("stock", {})

    def get_stock_query(
        self,
        pharmacy_id: int | None = None,
        search: str = "",
        category: str = "All",
        status: str = "All",
    ) -> list[dict]:
        """Queries unified medicine stock with 4-tier status calculation."""
        params = {"search": search, "category": category, "status": status}
        if pharmacy_id is not None:
            params["pharmacy_id"] = pharmacy_id
        resp = self.send_request("GET_STOCK_QUERY", **params)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Could not fetch stock query"))
        return resp.get("items", [])

    def add_medicine(
        self,
        brand_name: str,
        manufacturer: str,
        category: str,
        price_inr: float,
        batch_no: str,
        expiry_date: str,
        stock_quantity: int = 50,
        reorder_level: int = 15,
        pharmacy_id: int = 1,
    ) -> dict:
        """Adds a new medicine to catalog and inventory over TCP."""
        resp = self.send_request(
            "ADD_MEDICINE",
            brand_name=brand_name,
            manufacturer=manufacturer,
            category=category,
            price_inr=price_inr,
            batch_no=batch_no,
            expiry_date=expiry_date,
            stock_quantity=stock_quantity,
            reorder_level=reorder_level,
            pharmacy_id=pharmacy_id,
        )
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Failed to add medicine"))
        return resp.get("medicine", {})

    def edit_medicine(
        self,
        medicine_id: int,
        brand_name: str,
        manufacturer: str,
        category: str,
        price_inr: float,
        batch_no: str,
        expiry_date: str,
        stock_quantity: int,
        reorder_level: int,
        pharmacy_id: int = 1,
    ) -> dict:
        """Edits medicine details and stock levels over TCP."""
        resp = self.send_request(
            "EDIT_MEDICINE",
            medicine_id=medicine_id,
            brand_name=brand_name,
            manufacturer=manufacturer,
            category=category,
            price_inr=price_inr,
            batch_no=batch_no,
            expiry_date=expiry_date,
            stock_quantity=stock_quantity,
            reorder_level=reorder_level,
            pharmacy_id=pharmacy_id,
        )
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Failed to update medicine"))
        return resp.get("medicine", {})

    def delete_medicine(self, medicine_id: int) -> dict:
        """Deletes/discontinues a medicine over TCP."""
        resp = self.send_request("DELETE_MEDICINE", medicine_id=medicine_id)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Failed to delete medicine"))
        return resp.get("result", {})

    def process_pos_sale(
        self,
        pharmacy_id: int,
        items: list[dict],
        customer_name: str = "Walk-in Customer",
        payment_method: str = "Cash",
    ) -> dict:
        """Performs atomic POS checkout over TCP with expiry checks and receipt generation."""
        resp = self.send_request(
            "PROCESS_POS_SALE",
            pharmacy_id=pharmacy_id,
            items=items,
            customer_name=customer_name,
            payment_method=payment_method,
        )
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "POS checkout failed"))
        return resp.get("invoice", {})

    def get_expiry_audit(self, pharmacy_id: int | None = None) -> dict:
        """Queries expiry audit metrics and batch shelf life."""
        params = {}
        if pharmacy_id is not None:
            params["pharmacy_id"] = pharmacy_id
        resp = self.send_request("GET_EXPIRY_AUDIT", **params)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Could not load expiry audit"))
        return resp.get("audit", {})

    def get_sales_history(self, pharmacy_id: int | None = None, limit: int = 100) -> list[dict]:
        """Queries sales ledger over TCP."""
        params = {"limit": limit}
        if pharmacy_id is not None:
            params["pharmacy_id"] = pharmacy_id
        resp = self.send_request("GET_SALES_HISTORY", **params)
        if resp.get("status") == "error":
            raise ServerError(resp.get("message", "Could not load sales history"))
        return resp.get("sales", [])

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
