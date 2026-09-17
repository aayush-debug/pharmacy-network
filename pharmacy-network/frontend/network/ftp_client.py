"""
Frontend FTP Client Module.
Provides file transfer capabilities (listing, downloading, uploading, and verification)
for pharmacy bulk reports using Python's standard library 'ftplib'.

FTP Protocol: Layer 7 (File Transfer Protocol)
Transport: Layer 4 TCP (Dual-channel: Command Control on Port 21/2121 + Data channel)
"""

import ftplib
import os
from pathlib import Path
from typing import Self


class PharmacyFTPClient:
    """
    FTP Client for transferring bulk inventory, order, and alert reports.
    Does NOT replace TCP/HTTP for interactive medicine search or orders.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 2121,
        user: str = "pharma_admin",
        password: str = "pharma_secure_pass",
        timeout: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.timeout = timeout
        self.ftp: ftplib.FTP | None = None

    def connect(self) -> None:
        """Establishes TCP control connection and authenticates with FTP server."""
        self.ftp = ftplib.FTP(timeout=self.timeout)
        self.ftp.connect(self.host, self.port)
        try:
            self.ftp.login(self.user, self.password)
            print(f"[FTP Client] Connected to ftp://{self.host}:{self.port} as '{self.user}'")
        except Exception:
            self.disconnect()
            raise

    def is_connected(self) -> bool:
        """Returns True if FTP client has an active connection."""
        if not self.ftp:
            return False
        try:
            self.ftp.voidcmd("NOOP")
            return True
        except Exception:
            return False

    def list_reports(self) -> list[str]:
        """
        Retrieves the list of available report files on the FTP server.
        Uses the NLST command over the data channel.
        """
        if not self.ftp:
            raise ConnectionError("FTP client is not connected.")
        files = self.ftp.nlst()
        # Filter out directories or self/parent links if any
        return [f for f in files if f not in (".", "..")]

    def download_report(
        self, remote_filename: str, local_dest_path: Path | str
    ) -> Path:
        """
        Downloads a remote report file from the FTP server to the local filesystem.
        Uses the RETR command over a separate TCP data channel.
        """
        if not self.ftp:
            raise ConnectionError("FTP client is not connected.")

        target = Path(local_dest_path)
        if target.is_dir():
            target = target / remote_filename
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "wb") as local_file:
            self.ftp.retrbinary(f"RETR {remote_filename}", local_file.write)

        print(f"[FTP Client] Downloaded '{remote_filename}' -> {target}")
        return target

    def upload_report(
        self, local_source_path: Path | str, remote_filename: str | None = None
    ) -> str:
        """
        Uploads a local report file to the FTP server.
        Uses the STOR command over a separate TCP data channel.
        """
        if not self.ftp:
            raise ConnectionError("FTP client is not connected.")

        source = Path(local_source_path)
        if not source.is_file():
            raise FileNotFoundError(f"Local file does not exist: {source}")

        target_name = remote_filename or source.name
        with open(source, "rb") as local_file:
            self.ftp.storbinary(f"STOR {target_name}", local_file)

        print(f"[FTP Client] Uploaded {source} -> '{target_name}' on FTP server")
        return target_name

    def verify_file(self, local_path: Path | str, remote_filename: str) -> bool:
        """
        Verifies that a downloaded or uploaded file matches the remote file on the server.
        Checks remote existence and compares exact byte size.
        """
        if not self.ftp:
            raise ConnectionError("FTP client is not connected.")

        local_file = Path(local_path)
        if not local_file.is_file():
            return False

        local_size = local_file.stat().st_size
        try:
            # Query remote file size using SIZE command
            remote_size = self.ftp.size(remote_filename)
            if remote_size is not None:
                return local_size == remote_size
        except Exception:
            pass

        # Fallback: check if remote file appears in file list
        files = self.list_reports()
        return remote_filename in files

    def disconnect(self) -> None:
        """Sends QUIT command and closes TCP connection."""
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                try:
                    self.ftp.close()
                except Exception:
                    pass
            finally:
                self.ftp = None
            print(f"[FTP Client] Disconnected from {self.host}:{self.port}")

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()


if __name__ == "__main__":
    client = PharmacyFTPClient()
    try:
        client.connect()
        reports = client.list_reports()
        print(f"Available reports on FTP server: {reports}")
    except Exception as err:
        print(f"FTP Connection Error: {err}")
    finally:
        client.disconnect()
