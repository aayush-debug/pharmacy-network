"""
Centralized Configuration Module for Backend Services.
Reads settings from environment variables with safe development defaults.
Uses only the Python standard library.
"""

import os
from pathlib import Path

# Directory paths
# BASE_DIR points to pharmacy-network/backend
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"


def load_env_file(env_path: Path | None = None) -> None:
    """
    Lightweight .env file parser using only Python standard library.
    Loads key-value pairs into os.environ if not already defined.
    """
    target = env_path or (BASE_DIR / ".env")
    if not target.is_file():
        return

    with open(target, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            # Ignore empty lines and comment lines
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            # Do not overwrite existing environment variables
            if key not in os.environ:
                os.environ[key] = val


# Attempt to load local .env if present
load_env_file()

# ==============================================================================
# Networking Configurations (Safe Development Defaults)
# ==============================================================================

# 1. TCP Server (Primary client-server application communication)
TCP_HOST: str = os.environ.get("TCP_HOST", "127.0.0.1")
TCP_PORT: int = int(os.environ.get("TCP_PORT", "5000"))

# 2. UDP Server (Service discovery & low-stock alerts)
UDP_HOST: str = os.environ.get("UDP_HOST", "127.0.0.1")
UDP_PORT: int = int(os.environ.get("UDP_PORT", "5001"))
UDP_ALERT_PORT: int = int(os.environ.get("UDP_ALERT_PORT", "5002"))

# 3. HTTP Server (REST API endpoints)
HTTP_HOST: str = os.environ.get("HTTP_HOST", "127.0.0.1")
HTTP_PORT: int = int(os.environ.get("HTTP_PORT", "8000"))

# 4. FTP Server (Inventory & order file transfers)
FTP_HOST: str = os.environ.get("FTP_HOST", "127.0.0.1")
FTP_PORT: int = int(os.environ.get("FTP_PORT", "2121"))
FTP_USER: str = os.environ.get("FTP_USER", "pharma_admin")
FTP_PASS: str = os.environ.get("FTP_PASS", "pharma_secure_pass")

# 5. SMTP Email Configuration (Order confirmations & alerts)
SMTP_HOST: str = os.environ.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER: str = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", os.environ.get("SMTP_PASS", ""))
SMTP_PASS: str = SMTP_PASSWORD  # Alias for backward compatibility
SMTP_FROM: str = os.environ.get("SMTP_FROM", "notifications@pharmacynetwork.local")
ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", os.environ.get("SMTP_ALERT_RECIPIENT", "admin@pharmacynetwork.local"))
SMTP_ALERT_RECIPIENT: str = ADMIN_EMAIL  # Alias for backward compatibility
SMTP_ENABLED: bool = os.environ.get("SMTP_ENABLED", "false").lower() in ("true", "1", "yes")
SMTP_USE_TLS: bool = os.environ.get("SMTP_USE_TLS", "false").lower() in ("true", "1", "yes")

# 6. Database Location
DB_PATH: Path = Path(os.environ.get("DB_PATH", str(DATA_PROCESSED_DIR / "pharmacy.db")))


def get_config_summary() -> dict:
    """Returns a dictionary summary of active configuration for verification."""
    return {
        "TCP_HOST": TCP_HOST,
        "TCP_PORT": TCP_PORT,
        "UDP_HOST": UDP_HOST,
        "UDP_PORT": UDP_PORT,
        "HTTP_HOST": HTTP_HOST,
        "HTTP_PORT": HTTP_PORT,
        "FTP_HOST": FTP_HOST,
        "FTP_PORT": FTP_PORT,
        "FTP_USER": FTP_USER,
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
        "DB_PATH": str(DB_PATH),
        "BASE_DIR": str(BASE_DIR),
        "DATA_RAW_DIR": str(DATA_RAW_DIR),
        "DATA_PROCESSED_DIR": str(DATA_PROCESSED_DIR),
        "REPORTS_DIR": str(REPORTS_DIR),
    }


if __name__ == "__main__":
    print("=== Backend Configuration Summary ===")
    for key, value in get_config_summary().items():
        print(f"  {key}: {value}")
