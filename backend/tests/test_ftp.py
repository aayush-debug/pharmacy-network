"""
Automated Test Suite for Phase 9: FTP File Transfer.
Tests:
1. Generation of CSV reports from backend database/services.
2. FTP server startup and file listing.
3. Downloading reports over FTP and verifying file integrity.
4. Uploading reports over FTP and verifying storage.
5. Security / Authentication enforcement with invalid credentials.
"""

import csv
import ftplib
from pathlib import Path
import sys
import tempfile
import time
import unittest

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.database.init_db import init_database
from backend.app.database.seed import seed_database
from backend.app.ftp.reports import generate_all_reports
from backend.app.ftp.server import PharmacyFTPServer
from frontend.network.ftp_client import PharmacyFTPClient


class TestFTPFileTransfer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Create temporary directory for database and FTP reports
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_dir = Path(cls.temp_dir.name)

        cls.test_db = cls.test_dir / "test_ftp.db"
        init_database(cls.test_db)
        seed_database(cls.test_db)

        # 2. Setup isolated FTP root folder and generate reports
        cls.ftp_root = cls.test_dir / "ftp_reports"
        cls.ftp_root.mkdir(parents=True, exist_ok=True)
        generate_all_reports(output_dir=cls.ftp_root, db_path=cls.test_db)

        # 3. Start FTP server on ephemeral port (port 0)
        cls.user = "pharma_test_user"
        cls.password = "secret_pass_123"
        cls.server = PharmacyFTPServer(
            host="127.0.0.1",
            port=0,
            user=cls.user,
            password=cls.password,
            reports_dir=cls.ftp_root,
        )
        cls.server.start(blocking=False)
        time.sleep(0.2)
        cls.ftp_port = cls.server.port

        # 4. Directory for client downloads
        cls.client_downloads = cls.test_dir / "client_downloads"
        cls.client_downloads.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.temp_dir.cleanup()

    def test_01_report_generation(self):
        """Verify that reports.py generates valid CSV files with expected records."""
        inv_path = self.ftp_root / "inventory_report.csv"
        order_path = self.ftp_root / "order_report.csv"
        low_path = self.ftp_root / "low_stock_report.csv"

        self.assertTrue(inv_path.is_file(), "inventory_report.csv missing")
        self.assertTrue(order_path.is_file(), "order_report.csv missing")
        self.assertTrue(low_path.is_file(), "low_stock_report.csv missing")

        # Check inventory CSV content
        with open(inv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 7, "Inventory report must contain 7 rows")
            brand_names = [r["brand_name"] for r in rows]
            self.assertIn("Paracip 500", brand_names)
            self.assertIn("Mox 500", brand_names)

        # Check low stock CSV content
        with open(low_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            low_rows = list(reader)
            self.assertEqual(len(low_rows), 1, "Low stock report must contain 1 row")
            self.assertEqual(low_rows[0]["brand_name"], "Mox 500")

    def test_02_ftp_listing(self):
        """Verify client connects and lists reports on the FTP server."""
        with PharmacyFTPClient(
            host="127.0.0.1",
            port=self.ftp_port,
            user=self.user,
            password=self.password,
        ) as client:
            files = client.list_reports()
            self.assertIn("inventory_report.csv", files)
            self.assertIn("order_report.csv", files)
            self.assertIn("low_stock_report.csv", files)

    def test_03_ftp_download_and_verify(self):
        """Verify downloading a report and checking file integrity."""
        client = PharmacyFTPClient(
            host="127.0.0.1",
            port=self.ftp_port,
            user=self.user,
            password=self.password,
        )
        client.connect()
        try:
            dest_file = self.client_downloads / "downloaded_inventory.csv"
            result_path = client.download_report("inventory_report.csv", dest_file)
            self.assertTrue(result_path.is_file())

            # Verify byte-level equality with server source
            server_file = self.ftp_root / "inventory_report.csv"
            self.assertEqual(result_path.stat().st_size, server_file.stat().st_size)
            self.assertEqual(result_path.read_bytes(), server_file.read_bytes())

            # Verify client's verify_file method
            is_valid = client.verify_file(result_path, "inventory_report.csv")
            self.assertTrue(is_valid, "verify_file returned False for matching file")
        finally:
            client.disconnect()

    def test_04_ftp_upload_report(self):
        """Verify uploading a new report to the FTP server."""
        # Create a sample local audit file to upload
        upload_source = self.client_downloads / "branch_audit_upload.csv"
        with open(upload_source, "w", encoding="utf-8") as f:
            f.write("audit_id,branch_name,status\n1,City Health Central,VERIFIED\n")

        with PharmacyFTPClient(
            host="127.0.0.1",
            port=self.ftp_port,
            user=self.user,
            password=self.password,
        ) as client:
            client.upload_report(upload_source, "branch_audit_upload.csv")

            # Check that file now appears on server list
            files = client.list_reports()
            self.assertIn("branch_audit_upload.csv", files)

            # Check file exists on server filesystem
            server_uploaded = self.ftp_root / "branch_audit_upload.csv"
            self.assertTrue(server_uploaded.is_file())
            self.assertEqual(server_uploaded.read_text(), upload_source.read_text())

    def test_05_ftp_authentication_failure(self):
        """Verify that incorrect credentials raise ftplib.error_perm (530 Login incorrect)."""
        bad_client = PharmacyFTPClient(
            host="127.0.0.1",
            port=self.ftp_port,
            user=self.user,
            password="wrong_password_xyz",
        )
        with self.assertRaises(ftplib.error_perm):
            bad_client.connect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
