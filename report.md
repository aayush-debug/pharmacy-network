
## System Architecture

The Pharmacy Stock Query System utilizes a distributed, multi-protocol client-server architecture to ensure security, efficiency, and real-time communication:

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

## Technology Stack

The project relies on native Python libraries and robust frameworks:

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Native support for networking libraries. |
| **Desktop GUI** | PySide6 (Qt 6) | Professional desktop client with non-blocking async workers. |
| **Transport Layer** | `socket` (TCP/UDP) | Low-level Layer 4 networking (stream bytes and datagram packets). |
| **Message Framing** | NDJSON | Newline-Delimited JSON for TCP byte-stream boundary aggregation. |
| **Database** | SQLite 3 | Embedded ACID-compliant relational store encapsulated on the backend. |
| **HTTP Server** | `http.server` | Multi-threaded REST API for external inspection. |
| **FTP Server** | `pyftpdlib` | RFC 959 dual-channel file transfer for bulk report retrieval. |
| **SMTP Delivery** | `smtplib` + `email` | Transactional email generation for low-stock alerts. |
| **Dataset Source** | Hugging Face `datasets` | Indian pharmaceutical master catalog dataset. |
