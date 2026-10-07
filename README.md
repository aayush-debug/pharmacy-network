# Pharmacy Stock Query System — Multi-Protocol Client-Server Architecture

A comprehensive Computer Networking implementation demonstrating distributed systems, socket programming, application protocols, and database isolation using Python and PySide6.

> **Academic Disclaimer:** This project is an independent educational demonstration inspired by retail pharmacy distribution networks. It is **not** affiliated with Apollo Pharmacy or any commercial pharmaceutical entity.

---

## 1. Problem Statement

Retail pharmacy chains operate across multiple geographical branches, each managing dynamic stock levels for thousands of medicines. Critical operational problems include:
1. **Inventory Opacity**: Customers visiting one branch often find life-saving drugs out of stock without knowing if an adjacent branch carries them.
2. **Delayed Stock Alerts**: Reordering typically relies on manual audits, leading to stockouts of essential formulations.
3. **Monolithic Vulnerability**: Directly connecting client desktops to an operational database creates security risks, database lock contention, and network protocol inefficiencies.
4. **Protocol Mismatch**: Monolithic HTTP or database connections fail to demonstrate the specific transport needs of different tasks—such as high-frequency stream transactions, low-overhead discovery broadcasts, asynchronous push notifications, or bulk file transfers.

---

## 2. Objectives

- **Low-Level Socket Programming**: Implement raw stream (`SOCK_STREAM`) and datagram (`SOCK_DGRAM`) socket communication without high-level networking frameworks.
- **Protocol Specialization**: Demonstrate the coexistence of six networking protocols (TCP, UDP, HTTP, FTP, SMTP, NDJSON), each assigned to its optimal task.
- **Strict Architectural Separation**: Decouple the frontend client completely from the backend database (zero SQL or database driver imports on the client).
- **Concurrent Multi-Threading**: Manage multiple simultaneous client sessions using thread pools and non-blocking desktop worker threads (`QThread`).
- **Real-World Pharmaceutical Dataset**: Integrate 10,000 active Indian medicines from Hugging Face (`revooda/indian-pharma-data`) into an indexed relational catalog.

---

## 3. System Architecture

```
                       PySide6 DESKTOP CLIENT
                                 │
                   TCP/IP (NDJSON Socket Framing)
                                 │
                         PYTHON TCP SERVER
                                 │
                           SERVICE LAYER
                   (Pure Python Business Logic)
                                 │
                            SQLite DB
                   (Isolated Relational Store)
                                 │
 ┌───────────────┬───────────────┼───────────────┬───────────────┐
 │               │               │               │               │
UDP             UDP            HTTP/1.1         FTP            SMTP
Discovery     Low-Stock       REST API         Reports        MIME Alerts
(Port 5001)   Alerts (5002)   (Port 8000)     (Port 2121)     (Port 587/Dry)
```

---

## 4. Technology Stack

| Component | Technology | Role & Justification |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Native support for standard networking libraries (`socket`, `http`, `ftplib`, `smtplib`, `sqlite3`). |
| **Desktop GUI** | PySide6 (Qt 6) | Professional desktop client with asynchronous `QThread` workers, preventing UI freeze during network I/O. |
| **Transport Layer** | `socket` (TCP/UDP) | Low-level Layer 4 networking demonstrating stream bytes and datagram packets. |
| **Message Framing** | NDJSON | Newline-Delimited JSON solves TCP byte-stream boundary aggregation without byte stuffing. |
| **Database** | SQLite 3 | Embedded ACID-compliant relational store encapsulated strictly on the backend. |
| **HTTP Server** | `http.server` | Multi-threaded standard-library REST API for external/administrative inspection. |
| **FTP Server** | `pyftpdlib` | RFC 959 dual-channel file transfer server for bulk CSV report retrieval. |
| **SMTP Delivery** | `smtplib` + `email` | MIME-compliant transactional email generation for order confirmation & low-stock alerts. |
| **Dataset Source** | Hugging Face `datasets` | Programmatic extraction of `revooda/indian-pharma-data` master catalog. |

---

## 5. Folder Structure

```
pharmacy-network/
├── backend/
│   ├── app/
│   │   ├── config.py              # Centralized environment configurations
│   │   ├── database/
│   │   │   ├── connection.py      # Thread-safe SQLite connection factory
│   │   │   ├── init_db.py         # Schema executor & PRAGMA foreign key config
│   │   │   ├── schema.sql         # 5 normalized relational tables + indexes
│   │   │   └── seed.py            # Initial branch seed data
│   │   ├── services/              # Pure domain business logic (Zero network/UI code)
│   │   │   ├── medicine_service.py
│   │   │   ├── inventory_service.py
│   │   │   ├── pharmacy_service.py
│   │   │   ├── order_service.py
│   │   │   └── notification_service.py
│   │   ├── tcp/                   # Layer 4 TCP Multi-Threaded Server & Framing
│   │   │   ├── server.py
│   │   │   └── protocol.py
│   │   ├── udp/                   # Layer 4 UDP Broadcast & Datagram Push
│   │   │   ├── discovery_server.py
│   │   │   └── alerts.py
│   │   ├── http/                  # Layer 7 HTTP/1.1 REST API
│   │   │   ├── server.py
│   │   │   └── routes.py
│   │   ├── ftp/                   # Layer 7 FTP Report Generator & Server
│   │   │   ├── server.py
│   │   │   └── reports.py
│   │   └── smtp/                  # Layer 7 SMTP Mailer & MIME Construction
│   │       └── mailer.py
│   ├── data/
│   │   ├── raw/                   # Raw Hugging Face snapshot (medicines_raw.csv)
│   │   └── processed/             # Cleaned catalog (medicines.csv) and pharmacy.db
│   ├── reports/                   # Generated CSV audit reports
│   ├── scripts/                   # Data pipeline scripts
│   │   ├── download_dataset.py
│   │   ├── clean_dataset.py
│   │   └── generate_inventory.py
│   ├── tests/                     # 80 automated unit, protocol & integration tests
│   ├── main.py                    # Unified runner launching all 4 backend servers
│   ├── requirements.txt           # Backend dependencies
│   └── .env.example               # Environment template
│
├── frontend/
│   ├── app.py                     # Desktop GUI entrypoint
│   ├── gui/                       # PySide6 UI views
│   │   ├── login.py               # Server connection & UDP auto-discovery screen
│   │   ├── dashboard.py           # Network metrics & branch health overview
│   │   ├── search.py              # Real-time catalog search & branch stock lookup
│   │   ├── inventory.py           # Branch inventory manager & stock adjuster
│   │   ├── orders.py              # Order placement & fulfillment history
│   │   └── alerts.py              # Live UDP low-stock alert monitoring widget
│   ├── network/                   # Standalone client networking modules (Zero SQLite)
│   │   ├── config.py
│   │   ├── tcp_client.py          # Stream socket client with NDJSON parser
│   │   ├── udp_client.py          # Discovery probe & UDP datagram listener
│   │   ├── ftp_client.py          # ftplib report transfer client
│   │   └── protocol.py            # Request serializer & response decoder
│   ├── tests/                     # 11 frontend unit & GUI integration tests
│   └── requirements.txt           # Frontend dependencies (PySide6)
│
├── README.md                      # Comprehensive project documentation
└── VIVA_NOTES.md                  # Conceptual Q&A guide for viva examination
```

---

## 6. Database Schema

The backend relational store (`pharmacy.db`) uses SQLite with enforced foreign key integrity (`PRAGMA foreign_keys = ON;`) across 5 normalized tables:

```sql
-- 1. Medicines Master Catalog (Populated from Hugging Face dataset)
CREATE TABLE medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER UNIQUE,
    brand_name TEXT NOT NULL,
    manufacturer TEXT,
    price_inr REAL,
    dosage_form TEXT,
    pack_size REAL,
    pack_unit TEXT,
    primary_ingredient TEXT,
    primary_strength TEXT,
    therapeutic_class TEXT,
    is_discontinued INTEGER DEFAULT 0
);

-- 2. Pharmacy Branches
CREATE TABLE pharmacies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    ip_address TEXT,
    tcp_port INTEGER DEFAULT 5000,
    status TEXT DEFAULT 'offline'
);

-- 3. Branch Inventory
CREATE TABLE inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacy_id INTEGER NOT NULL,
    medicine_id INTEGER NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    minimum_stock INTEGER NOT NULL DEFAULT 10,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id) ON DELETE CASCADE,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
    UNIQUE(pharmacy_id, medicine_id)
);

-- 4. Customer Orders
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacy_id INTEGER NOT NULL,
    medicine_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id) ON DELETE RESTRICT,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE RESTRICT
);

-- 5. Audit Transactions Ledger
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacy_id INTEGER NOT NULL,
    medicine_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,  -- 'SALE', 'RESTOCK', 'ADJUSTMENT'
    quantity INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id) ON DELETE RESTRICT,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE RESTRICT
);
```

---

## 7. Protocol Workflows

### 7.1 TCP Application Workflow (Port 5000)
1. **Connection**: Client establishes stream connection via 3-way handshake (`SYN` → `SYN-ACK` → `ACK`).
2. **Thread Allocation**: Server's accept loop creates a dedicated daemon thread `ClientWorker-<IP>:<port>` for that connection.
3. **Request Framing**: Client encodes a JSON object, appends `\n`, and transmits UTF-8 bytes.
4. **Buffering & Demarcation**: Server accumulates stream chunks into a string buffer until `\n` is detected.
5. **Execution**: Protocol layer routes the action to the service layer; database updates run inside an atomic transaction.
6. **Response Framing**: Server serializes the response dictionary to JSON, appends `\n`, and sends it back.
7. **Clean Teardown**: When the client closes the socket, `recv()` returns 0 bytes (`EOF`), terminating the worker thread.

### 7.2 UDP Discovery Workflow (Port 5001)
1. Client sends a broadcast datagram `b"DISCOVER_PHARMACY_SERVER"` to port 5001.
2. `DiscoveryServer` receives the packet and replies with server metadata:
   ```json
   {"type": "SERVER_INFO", "tcp_port": 5000, "http_port": 8000}
   ```
3. Client extracts `tcp_port` and connects without hardcoding port numbers.

### 7.3 UDP Low-Stock Alert Workflow (Port 5002)
1. When an order placement or inventory update causes `stock_quantity <= minimum_stock`, the service layer fires a low-stock trigger.
2. `UDPAlertBroadcaster` creates a datagram socket and broadcasts a lightweight JSON payload to port 5002.
3. The client's background `UDPAlertListener` thread receives the datagram and delivers it to the PySide6 GUI via Qt signals.

### 7.4 HTTP REST API Workflow (Port 8000)
1. External or administrative clients submit standard `GET` requests (e.g., `curl http://127.0.0.1:8000/api/medicines/1`).
2. `ThreadingHTTPServer` parses URL path and query parameters in `routes.py`.
3. Routes call the **exact same service layer** used by the TCP protocol, preventing SQL duplication.
4. Handler returns HTTP status code (200, 400, 404, 405) with `Content-Type: application/json`.

### 7.5 FTP Report Transfer Workflow (Port 2121)
1. Administrative reports (`inventory_report.csv`, `order_report.csv`, `low_stock_report.csv`) are generated into `backend/reports/`.
2. `PharmacyFTPServer` (`pyftpdlib`) listens on control port 2121.
3. `PharmacyFTPClient` authenticates (`USER` / `PASS`), queries file listings (`NLST`), and initiates report download (`RETR`).
4. A dynamic passive TCP data channel (ports 60000–60099) transfers the bulk CSV file without blocking application commands.

### 7.6 SMTP Email Notification Workflow (Port 587 / Dry-Run)
1. Successful order placements trigger `notify_order_created()`.
2. Stock exhaustion triggers `notify_low_stock()`.
3. `SMTPMailer` constructs an RFC 5321 MIME `EmailMessage` containing order details or urgent reorder requirements.
4. By default (`SMTP_ENABLED=false`), messages are safely logged and stored in an in-memory outbox for inspection without contacting live mail relays. When enabled, it delivers via TLS over port 587.

### 7.7 Hugging Face Dataset Workflow
1. `download_dataset.py` fetches the Indian pharmaceutical dataset (`revooda/indian-pharma-data`) programmatically.
2. `clean_dataset.py` removes discontinued products, sanitizes prices and dosage forms, and imports 10,000 active records into SQLite.
3. `generate_inventory.py` distributes stock across 4 regional pharmacy branches with varied safety stock thresholds.

---

## 8. Installation Instructions

### Prerequisites
- Python 3.11+ installed
- Git

### Setup Steps
```bash
# 1. Clone repository and navigate to workspace
cd "pharmacy-network"

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install backend and frontend dependencies
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

---

## 9. How to Run

### Option A: Unified Launcher (Recommended)
Starts all backend services (TCP, UDP Discovery, HTTP REST API, and FTP Server) in a single command:
```bash
python3 backend/main.py
```

### Option B: Start Services Individually
Open separate terminal tabs:
```bash
# Terminal 1: TCP Socket Server (Port 5000)
python3 -m backend.app.tcp.server

# Terminal 2: UDP Discovery Server (Port 5001)
python3 -m backend.app.udp.discovery_server

# Terminal 3: HTTP REST API Server (Port 8000)
python3 -m backend.app.http.server

# Terminal 4: FTP Reports Server (Port 2121)
python3 -m backend.app.ftp.server
```

### Launching the PySide6 Desktop GUI
In a new terminal tab:
```bash
python3 frontend/app.py
```

---

## 10. How to Test Each Protocol

### Running the Full Automated Test Suite (91 Tests)
```bash
# Run all backend tests (80 tests: DB, Services, TCP, UDP, HTTP, FTP, SMTP, Import, E2E Integration)
python3 -m unittest discover -s backend/tests -p "test_*.py" -v

# Run frontend tests (11 tests: GUI widgets, TCP client framing, socket error recovery)
python3 -m unittest discover -s frontend/tests -p "test_*.py" -v

# Run the Phase 12 Full System Integration Test Suite specifically
python3 -m unittest backend/tests/test_full_system_integration.py -v
```

### Manual Protocol Testing Commands

#### 1. TCP Server (Netcat / Python)
```bash
# Test TCP PING
echo '{"action":"PING"}' | nc 127.0.0.1 5000

# Search medicine catalog
echo '{"action":"SEARCH_MEDICINE","query":"Augmentin"}' | nc 127.0.0.1 5000
```

#### 2. UDP Discovery
```bash
python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(2.0)
s.sendto(b'DISCOVER_PHARMACY_SERVER', ('127.0.0.1', 5001))
data, _ = s.recvfrom(1024)
print('Discovered:', data.decode())
"
```

#### 3. HTTP REST API
```bash
# Get medicine catalog info
curl -s http://127.0.0.1:8000/api/medicines/1 | jq .

# Check low-stock inventory
curl -s "http://127.0.0.1:8000/api/inventory?pharmacy_id=1&low_stock=true" | jq .
```

#### 4. FTP File Transfer
```bash
python3 -c "
from frontend.network.ftp_client import PharmacyFTPClient
client = PharmacyFTPClient(host='127.0.0.1', port=2121, user='pharma_admin', password='pharma_secure_pass')
client.connect()
print('Available reports on FTP:', client.list_reports())
client.download_report('inventory_report.csv', 'backend/reports/downloaded_inventory.csv')
client.disconnect()
"
```

#### 5. SMTP Email
```bash
python3 -c "
from backend.app.smtp.mailer import default_mailer
print('Outbox count:', len(default_mailer.outbox))
for msg in default_mailer.outbox:
    print('Email:', msg['Subject'])
"
```

---

## 11. Example Requests and Responses

### 1. TCP: `SEARCH_MEDICINE`
**Request:**
```json
{"action": "SEARCH_MEDICINE", "query": "Augmentin"}
```
**Response:**
```json
{
  "status": "success",
  "results": [
    {
      "id": 1,
      "product_id": 28503,
      "brand_name": "Augmentin 625 Duo Tablet",
      "manufacturer": "Glaxo SmithKline Pharmaceuticals Ltd",
      "price_inr": 201.71,
      "dosage_form": "Tablet",
      "pack_size": 10.0,
      "pack_unit": "Tablet",
      "primary_ingredient": "Amoxycillin",
      "primary_strength": "500 mg",
      "therapeutic_class": "Anti-Infectives"
    }
  ]
}
```

### 2. TCP: `PLACE_ORDER`
**Request:**
```json
{"action": "PLACE_ORDER", "pharmacy_id": 1, "medicine_id": 1, "quantity": 15}
```
**Response:**
```json
{
  "status": "success",
  "order": {
    "order_id": 3,
    "pharmacy_id": 1,
    "pharmacy_name": "City Health Central",
    "medicine_id": 1,
    "brand_name": "Augmentin 625 Duo Tablet",
    "unit_price": 201.71,
    "quantity": 15,
    "total_amount": 3025.65,
    "status": "confirmed",
    "created_at": "2026-09-17 12:16:36",
    "remaining_stock": 13,
    "is_now_low_stock": true
  }
}
```

### 3. UDP: `LOW_STOCK` Alert Packet
**Datagram Payload:**
```json
{
  "type": "LOW_STOCK",
  "medicine": "Augmentin 625 Duo Tablet",
  "pharmacy": "City Health Central",
  "stock": 13,
  "minimum": 17,
  "timestamp": "2026-09-17T06:46:36.621386+00:00"
}
```

### 4. HTTP: `GET /api/orders/3`
**Response (HTTP 200 OK):**
```json
{
  "order_id": 3,
  "pharmacy_id": 1,
  "pharmacy_name": "City Health Central",
  "medicine_id": 1,
  "brand_name": "Augmentin 625 Duo Tablet",
  "unit_price": 201.71,
  "quantity": 15,
  "total_amount": 3025.65,
  "status": "confirmed",
  "created_at": "2026-09-17 12:16:36"
}
```

---

## 12. Limitations

1. **Local Subnet Scope for UDP Broadcast**: UDP broadcast packets (`255.255.255.255` or subnet broadcast) are generally dropped by standard Layer 3 routers; cross-subnet discovery would require UDP unicast or multicast routing.
2. **Cleartext Transmissions (No TLS/SSL on TCP/FTP)**: Core socket and FTP transfers run unencrypted for academic packet inspection. In high-security production environments, TLS wrappers (`ssl.wrap_socket` and FTPS) must be added.
3. **SQLite Single-Writer Concurrency**: While SQLite handles concurrent readers via WAL mode, high-write contention across thousands of simultaneous branches would require a client-server RDBMS like PostgreSQL.
4. **Development SMTP Default**: Outbound email relies on dry-run mode unless valid credentials for an upstream SMTP relay (e.g., SendGrid, Mailgun) are provided in `.env`.

---

## 13. Future Improvements

1. **TLS / SSL Socket Encryption**: Wrap the raw TCP socket streams using Python's `ssl` module to demonstrate Layer 6 TLS encryption and certificate verification.
2. **WebSocket Gateway**: Introduce a WebSocket bridge over port 8001 to stream real-time UDP alerts directly into a web browser dashboard.
3. **Distributed Multicast (IGMP)**: Upgrade branch discovery from subnet broadcast to IP Multicast (`224.0.0.1`–`239.255.255.255`) to span multiple network segments cleanly.
4. **JWT Authentication**: Introduce JSON Web Token authentication over the TCP handshake to enforce role-based access control (Pharmacist vs. Administrator).
