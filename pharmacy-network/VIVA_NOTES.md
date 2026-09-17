# Pharmacy Stock Query System — Viva Voce Preparation Guide

This document is tailored for a **2nd Year Computer Science & Engineering (CSE)** student. It explains every networking concept, design choice, and protocol in plain, beginner-friendly language with technical accuracy to excel in viva examinations.

---

## 1. Fundamental Networking Concepts

### Q1: What is a computer network?
**Answer:** A computer network is a collection of two or more computing devices connected by physical transmission media (cables, optical fiber) or wireless technologies (Wi-Fi) to share resources, transfer files, and exchange data. In our project, the network enables independent computers running pharmacy client interfaces to talk to a central database server.

---

### Q2: What is client-server architecture?
**Answer:** It is a distributed computing model that divides tasks between two distinct roles:
1. **Server**: A centralized host that listens for incoming requests, provides resources or services (like catalog searching or order processing), and manages the database.
2. **Client**: A program (like our desktop application) that initiates requests to the server, receives responses, and displays them to the user.

**Key Rule:** Clients never communicate directly with other clients in this model; all coordination happens through the server.

---

### Q3: What is an IP address?
**Answer:** An **Internet Protocol (IP) Address** is a unique numerical label assigned to every device connected to a computer network (e.g., `192.168.1.15` for IPv4 or `127.0.0.1` for localhost/loopback). It functions like a postal street address: it tells routers and switches *which machine* on the network should receive a packet.

---

### Q4: What is a port?
**Answer:** While an IP address identifies the *computer*, a **Port Number** (a 16-bit integer from 0 to 65535) identifies the *specific program or service* running on that computer.
- Analogy: If the IP address is an apartment building, the port number is the apartment room number.
- In our project:
  - Port 5000 delivers traffic to our TCP Socket Server.
  - Port 5001 delivers traffic to our UDP Discovery Server.
  - Port 8000 delivers traffic to our HTTP REST API Server.
  - Port 2121 delivers traffic to our FTP Server.

---

### Q5: What is a socket?
**Answer:** A **Socket** is an endpoint for sending or receiving data across a computer network. In software (such as Python's `socket` library), a socket is represented as a file-like descriptor created by combining an **IP Address + Port Number + Transport Protocol (TCP or UDP)**.

```python
# Creating an IPv4 TCP stream socket in Python:
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
```

---

### Q6: What is TCP?
**Answer:** **TCP (Transmission Control Protocol)** is a connection-oriented, reliable transport-layer protocol (OSI Layer 4).
- **Connection-Oriented**: Before any data is transmitted, TCP establishes a virtual connection between client and server using the **3-Way Handshake** (`SYN` → `SYN-ACK` → `ACK`).
- **Reliable**: TCP guarantees delivery. If a packet is dropped by the network, TCP detects the missing sequence number and automatically retransmits it.
- **Ordered**: Packets arriving out of order are reassembled into the exact sequence they were sent.
- **Byte-Stream Oriented**: Data flows as a continuous stream of bytes without built-in message boundaries.

---

### Q7: What is UDP?
**Answer:** **UDP (User Datagram Protocol)** is a connectionless, lightweight transport-layer protocol (OSI Layer 4).
- **Connectionless**: No handshake is performed before transmitting. The sender simply addresses a packet and transmits it ("fire-and-forget").
- **Unreliable**: UDP does not provide acknowledgments, retransmissions, or delivery guarantees. Packets may be lost, duplicated, or arrive out of order.
- **Message-Oriented (Preserves Boundaries)**: Every write operation creates a distinct datagram packet that is read as a single unit on the receiving end.
- **Broadcast/Multicast Capable**: Unlike TCP, UDP can transmit a single packet to all hosts on a local subnet simultaneously.

---

### Q8: TCP vs UDP Comparison

| Feature | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
| :--- | :--- | :--- |
| **Connection** | Connection-oriented (3-way handshake) | Connectionless (No handshake) |
| **Reliability** | Guaranteed delivery (Retransmissions on loss) | Best-effort (No retransmissions) |
| **Ordering** | Guarantees ordered byte arrival | Packets may arrive out of order |
| **Message Boundaries** | None (Continuous byte stream) | Yes (Discrete datagrams) |
| **Speed / Overhead** | Higher overhead (20-byte header, ACKs, timers) | Very low overhead (8-byte header, minimal latency) |
| **Broadcast Support** | Point-to-point only (Unicast) | Supports Unicast, Broadcast, and Multicast |
| **Project Role** | Interactive orders, search, and stock transactions | Server auto-discovery and low-stock alert datagrams |

---

### Q9: What is TCP/IP?
**Answer:** **TCP/IP** refers to the suite of communication protocols that powers the modern internet and private networks. It is organized into a 4-layer model:
1. **Application Layer**: HTTP, FTP, SMTP, DNS (User applications and business data)
2. **Transport Layer**: TCP, UDP (End-to-end communication, port addressing, reliability)
3. **Internet / Network Layer**: IP, ICMP (Logical routing and packet forwarding across networks)
4. **Link / Physical Layer**: Ethernet, Wi-Fi (Physical frames and electrical/radio signals)

---

## 2. Low-Level Socket Mechanics & Message Framing

### Q10: Why does TCP need message framing?
**Answer:** TCP is a **byte-stream protocol**, not a message protocol.
- When a client sends two separate messages:
  - `Message 1: {"action": "PING"}`
  - `Message 2: {"action": "CHECK_STOCK"}`
- TCP guarantees all bytes will arrive in order, but the network or operating system buffers can deliver them in any arbitrary chunk sizes:
  - Case 1 (Packet Aggregation / Nagle's Algorithm): Both messages arrive combined into a single `recv()` call.
  - Case 2 (Packet Fragmentation / MTU Splitting): A single message arrives split across two separate `recv()` calls.
- Without a framing delimiter, the receiver cannot determine where Message 1 ends and Message 2 begins.

---

### Q11: What is NDJSON and why did we choose it?
**Answer:** **NDJSON (Newline-Delimited JSON)** is a message framing format where every complete JSON object is immediately followed by a newline character (`\n`).
- **How it works:**
  1. Sender serializes data to JSON, appends `\n`, and sends bytes.
  2. Receiver accumulates incoming bytes in a buffer string until it sees `\n`.
  3. Receiver splits on `\n`, parses the complete string with `json.loads()`, and leaves any trailing partial bytes in the buffer for the next `recv()` read.
- **Why NDJSON instead of Length-Prefixing?**
  - Human-readable during Wireshark / Netcat debugging.
  - Extremely easy to parse without complex binary byte-packing routines.
  - Works natively with JSON-formatted web and desktop payloads.

---

### Q12: Why use threading on the TCP server and in the GUI?
**Answer:**
1. **On the TCP Server (`TCPServer`)**:
   - The TCP `accept()` and `recv()` socket calls are **blocking operations**.
   - If the server handled clients sequentially on a single thread, a single connected client would block all other pharmacy branches from searching medicines or placing orders.
   - By spawning a separate worker thread (`ClientWorker-<IP>:<Port>`) for each connected client, dozens of pharmacy branches can place orders concurrently without interference.
2. **In the Desktop GUI (`PySide6`)**:
   - The Qt GUI runs an event loop on the Main GUI Thread responsible for rendering controls and handling clicks.
   - If a network call (like waiting for a TCP response) is made on the main thread, the entire GUI freezes and displays "Not Responding".
   - We use non-blocking `QThread` workers to execute network socket I/O in the background and emit signals back to the UI when results arrive.

---

## 3. Application-Layer Protocols

### Q13: What is HTTP and how does it relate to TCP?
**Answer:** **HTTP (Hypertext Transfer Protocol)** is an application-layer (Layer 7) protocol used for transmitting hypermedia and RESTful API data.
- **Relationship to TCP:** HTTP does not define how bytes travel over physical wires; instead, **HTTP runs on top of a TCP stream connection**.
- When you request `GET /api/medicines/1`, an underlying TCP connection to port 80/8000 is established first. The client sends a plaintext HTTP request line and headers over that TCP stream, and the server returns a status code (e.g., `200 OK`) and body over the same TCP connection.

---

### Q14: What is FTP and why is it included?
**Answer:** **FTP (File Transfer Protocol, RFC 959)** is a specialized Layer 7 protocol designed specifically for transferring files between a client and server.
- **Dual-Channel Architecture:**
  - **Control Channel (Port 21 / 2121)**: Remains open throughout the session to transmit commands (`USER`, `PASS`, `LIST`, `RETR`, `QUIT`).
  - **Data Channel (Dynamic Ports)**: A separate, temporary TCP connection spawned specifically to stream the raw bytes of a file.
- **Why included in our project?**
  - In a real pharmacy chain, analytical and audit reports (e.g., daily sales, bulk inventory CSVs of 10,000 medicines) are several megabytes in size.
  - Transferring large files over our interactive TCP socket would clog the transaction queue.
  - FTP demonstrates the appropriate separation between transactional messaging (TCP) and bulk file archiving (FTP).

---

### Q15: What is SMTP and why is it included?
**Answer:** **SMTP (Simple Mail Transfer Protocol, RFC 5321)** is a Layer 7 protocol used for sending electronic mail across IP networks.
- It operates asynchronously: once the sender delivers the email to a mail transfer agent (MTA), the sender does not wait for the recipient to open or read it.
- **Why included in our project?**
  - Demonstrates event-driven notifications: when an order is completed, or when inventory falls below safety reorder levels, the system automatically dispatches an RFC 5321 MIME email to the warehouse administrator without freezing the user's desktop application.

---

## 4. System Architecture & Database Questions

### Q16: Why is SQLite only on the backend? Why not let the frontend directly access the database?
**Answer (Crucial Viva Question):**
Directly connecting client desktops to a remote database is a severe anti-pattern in enterprise software engineering:
1. **Security Vulnerability**: Distributing direct database connections requires placing database passwords and connection strings on client machines, allowing users to alter stock or bypass payment logic.
2. **Business Logic Bypass**: With direct SQL access, a client could run `INSERT INTO orders` without deducting stock or checking `minimum_stock` rules.
3. **Database Concurrency & Lock Contention**: SQLite is an embedded database designed for single-process write access. Multiple clients connecting over network file shares (SMB/NFS) cause database corruption and table locks.
4. **Tight Schema Coupling**: If the database schema changes (e.g., renaming a column), every client application across the country breaks immediately. With an intermediate server, the server adapts the internal query while maintaining a stable API for clients.

---

### Q17: Why is the frontend completely separate?
**Answer:**
- **Separation of Concerns**: The frontend is purely a Presentation Layer responsible for rendering buttons, processing user input, and visualizing alerts.
- **Technology Independence**: Because the backend communicates over standard TCP/IP sockets and NDJSON, the backend does not care what technology the frontend uses. We could write a web dashboard in React, a mobile app in Flutter, or a CLI script, and all of them would work with the existing backend without changing a single line of backend code.

---

### Q18: Why use PySide6 instead of Tkinter or a web framework?
**Answer:**
- **PySide6 (Official Qt for Python)**: Provides a native, professional desktop interface with rich controls (tables, tabs, forms) and built-in cross-platform hardware acceleration.
- **Robust Multi-Threading Model (`QThread`, `Signal`, `Slot`)**: Qt's signal-and-slot mechanism provides thread-safe communication between background socket threads and the UI thread, preventing race conditions and UI lockups.

---

## 5. Dataset & Business Logic

### Q19: How is the Hugging Face dataset used vs. application data?
**Answer (Key Architecture Defense):**
- **External Dataset (`revooda/indian-pharma-data`)**: Used strictly as the **Medicine Master Catalog**. It supplies realistic pharmaceutical metadata: unique product IDs, brand names, active ingredients (e.g., Amoxycillin), dosage forms (Tablet, Syrup), strengths, and manufacturers.
- **Application-Generated Data**: The dataset does **NOT** contain pharmacy branches or inventory. Our application models the actual business operations:
  - Registering pharmacy branches (`City Health Central`, `Metro Care Chemist`, etc.).
  - Distributing stock quantities and assigning minimum reorder thresholds.
  - Recording customer orders, timestamps, fulfillment status, and audit ledgers.

---

## 6. End-to-End Traces (Walkthrough of Core Flows)

### Flow 1: How a Medicine Search travels through the system
1. **User Action**: The user types `"Augmentin"` in the PySide6 search bar and clicks **Search**.
2. **GUI Worker**: `SearchWidget` spawns a background `QThread` and calls `tcp_client.search_medicines("Augmentin")`.
3. **Framing & Transmission**: `PharmacyTCPClient` encodes `{"action":"SEARCH_MEDICINE","query":"Augmentin"}\n` and transmits bytes over the active TCP stream (port 5000).
4. **Server Reception**: The server's dedicated `ClientWorker` thread reads bytes from `recv()`, splits on `\n`, and parses the JSON dictionary.
5. **Protocol Routing**: `protocol.py` validates the action and delegates to `medicine_service.search_medicines("Augmentin")`.
6. **SQL Query**: The service executes a parameterized SQL query:
   ```sql
   SELECT * FROM medicines WHERE brand_name LIKE '%Augmentin%' OR primary_ingredient LIKE '%Augmentin%';
   ```
7. **Response Serialization**: The service returns a list of dictionaries. The protocol layer wraps it in `{"status": "success", "results": [...]}\n` and transmits it back across the socket.
8. **UI Rendering**: The client TCP socket reads the response, deserializes the JSON, and emits a Qt Signal to populate the PySide6 table view.

---

### Flow 2: How an Order Placement travels through the system
1. **User Action**: Pharmacist selects Medicine ID 1 (`Augmentin 625 Duo Tablet`) at Pharmacy ID 1, enters Quantity 15, and clicks **Place Order**.
2. **Client Transmission**: TCP client sends:
   ```json
   {"action": "PLACE_ORDER", "pharmacy_id": 1, "medicine_id": 1, "quantity": 15}\n
   ```
3. **Server Validation**: The server worker routes to `order_service.place_order()`.
4. **Atomic Transaction**:
   - Checks that Pharmacy 1 exists and carries Medicine 1.
   - Verifies available stock (e.g., 28 units $\ge$ 15 units requested).
   - Deducts stock: `UPDATE inventory SET stock_quantity = 13 WHERE pharmacy_id=1 AND medicine_id=1`.
   - Inserts order: `INSERT INTO orders (pharmacy_id, medicine_id, quantity, status) VALUES (1, 1, 15, 'confirmed')`.
   - Logs transaction: `INSERT INTO transactions (pharmacy_id, medicine_id, transaction_type, quantity) VALUES (1, 1, 'SALE', 15)`.
   - Calls `conn.commit()` to persist all changes atomically.
5. **Event Notification Dispatch**:
   - Because new stock (13) is $\le$ safety threshold (17), `is_now_low_stock` is `True`.
   - Fires asynchronous **SMTP Order Confirmation** email.
   - Fires asynchronous **SMTP Urgent Low-Stock Alert** email to administrator.
   - Fires asynchronous **UDP Low-Stock Push Datagram** on port 5002.
6. **Client Confirmation**: Server returns `{"status": "success", "order": {...}}\n`. The GUI displays a success message and updates available stock.

---

### Flow 3: How a Low-Stock Alert works
1. **Trigger Condition**: An order reduces inventory below `minimum_stock` (or an admin adjusts stock).
2. **Datagram Assembly**: `UDPAlertBroadcaster` creates a datagram socket and constructs:
   ```json
   {
     "type": "LOW_STOCK",
     "medicine": "Augmentin 625 Duo Tablet",
     "pharmacy": "City Health Central",
     "stock": 13,
     "minimum": 17,
     "timestamp": "2026-09-17T06:46:36Z"
   }
   ```
3. **Broadcast Transmission**: Sender executes `sendto(data_bytes, ("127.0.0.1", 5002))` without waiting for an acknowledgment.
4. **Client Reception**: The desktop client's background `UDPAlertListener` thread (listening on port 5002) receives the datagram via `recvfrom()`.
5. **Visual Notification**: Listener emits a Qt signal to `AlertsWidget`, highlighting the low-stock item in red and flashing a warning notification.

---

## 7. Comprehensive Protocol Breakdown Table

| Property | 1. TCP Server | 2. UDP Discovery | 3. UDP Alerts | 4. HTTP API | 5. FTP Server | 6. SMTP Mailer |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Purpose** | Core application commands (search, stock, orders) | Auto-detecting active server IP & ports | Instant push alerting for depleted stock | Third-party / admin read-only REST access | Bulk CSV audit report file transfers | Transactional receipts & admin email alerts |
| **Client** | `PharmacyTCPClient` | `discover_pharmacy_server()` | `UDPAlertListener` | Web Browser / cURL | `PharmacyFTPClient` | Python `smtplib` |
| **Server** | `TCPServer` | `DiscoveryServer` | `UDPAlertBroadcaster` | `PharmacyHTTPServer` | `PharmacyFTPServer` | Mail Transfer Agent (MTA) |
| **Port** | **5000** (Configurable) | **5001** (Configurable) | **5002** (Configurable) | **8000** (Configurable) | **2121** (Passive 60000+) | **587** (TLS / Dry-Run) |
| **Transport** | TCP (Stream) | UDP (Datagram) | UDP (Datagram) | TCP (Stream) | Dual TCP (Control + Data) | TCP (Stream) |
| **Data Exchanged** | NDJSON commands & responses | `DISCOVER` probe $\to$ `SERVER_INFO` JSON | Single `LOW_STOCK` JSON datagram | HTTP Request Lines $\to$ JSON payload | FTP RFC 959 Commands $\to$ Raw CSV bytes | RFC 5321 MIME multipart email text |
| **Why Used Here?**| Guaranteed, reliable transaction processing | Eliminates hardcoded IP/port configurations | Ultra-low latency, non-blocking push delivery | Universal web interoperability without custom protocols | Dedicated dual-channel protocol optimized for large files | Standardized asynchronous delivery to external mailboxes |

---

## 8. Viva Cheat Sheet: 5 Core Architectural Rules

1. **"The Frontend NEVER Touches the Database"**: There are zero `sqlite3` imports in `frontend/`. All database queries are executed strictly by backend services.
2. **"TCP Provides Stream Reliability; NDJSON Provides Boundaries"**: TCP ensures no byte is lost; newline characters tell the application where each JSON message ends.
3. **"UDP is for Non-Critical, Low-Latency Messages"**: We use UDP for discovery and alerts because losing an alert packet is preferable to blocking the entire order queue.
4. **"Services Encapsulate Business Logic"**: The HTTP routes, TCP protocol handlers, and report generators all call the *exact same* Python service functions, preventing code duplication.
5. **"Threads Protect Both Server and Client"**: Multi-threading on the server handles multiple clients simultaneously; worker threads in the GUI keep the desktop interface responsive.
