"""
Automated Test Suite for Phase 10: SMTP Email Notifications.
Tests:
1. Order confirmation message structure and required fields.
2. Low-stock alert message structure and required fields.
3. Development safety / dry-run mode (SMTP_ENABLED=False).
4. SMTP client network delivery with TLS and authentication verification.
5. Service layer event integration (notification_service -> mailer).
"""

from email.message import EmailMessage
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.services import notification_service
from backend.app.smtp.mailer import (
    SMTPMailer,
    default_mailer,
    send_low_stock_alert,
    send_order_confirmation,
)


class TestSMTPEmail(unittest.TestCase):
    def setUp(self):
        # Reset outbox before each test
        default_mailer.outbox.clear()

    def test_01_order_confirmation_email_structure(self):
        """
        Verify order confirmation contains all required fields:
        - order ID, medicine, quantity, pharmacy, order status, timestamp.
        """
        mailer = SMTPMailer(
            from_email="orders@pharmacy.local",
            admin_email="manager@pharmacy.local",
            enabled=False,
        )

        sample_order = {
            "order_id": 42,
            "medicine": "Paracip 500",
            "quantity": 5,
            "pharmacy": "City Health Central",
            "status": "confirmed",
            "total_amount": 102.50,
            "created_at": "2026-09-17T12:00:00Z",
        }

        msg = mailer.send_order_confirmation(sample_order, recipient="customer@example.com")
        self.assertIsInstance(msg, EmailMessage)
        self.assertEqual(msg["From"], "orders@pharmacy.local")
        self.assertEqual(msg["To"], "customer@example.com")
        self.assertIn("Order #42 Confirmation", msg["Subject"])
        self.assertIn("Paracip 500", msg["Subject"])

        body = msg.get_content()
        self.assertIn("Order ID:      42", body)
        self.assertIn("Medicine:      Paracip 500", body)
        self.assertIn("Quantity:      5", body)
        self.assertIn("Pharmacy:      City Health Central", body)
        self.assertIn("Order Status:  CONFIRMED", body)
        self.assertIn("INR 102.5", body)
        self.assertIn("2026-09-17T12:00:00Z", body)

    def test_02_low_stock_alert_email_structure(self):
        """
        Verify low-stock email contains all required fields:
        - medicine, pharmacy, current stock, minimum stock.
        """
        mailer = SMTPMailer(
            from_email="alerts@pharmacy.local",
            admin_email="admin@pharmacy.local",
            enabled=False,
        )

        sample_low = {
            "medicine": "Mox 500",
            "pharmacy": "Metro Care Chemist",
            "stock": 3,
            "minimum": 10,
            "timestamp": "2026-09-17T12:05:00Z",
        }

        msg = mailer.send_low_stock_alert(sample_low)
        self.assertIsInstance(msg, EmailMessage)
        self.assertEqual(msg["From"], "alerts@pharmacy.local")
        self.assertEqual(msg["To"], "admin@pharmacy.local")
        self.assertIn("Low Stock Notice: Mox 500", msg["Subject"])

        body = msg.get_content()
        self.assertIn("Medicine:       Mox 500", body)
        self.assertIn("Pharmacy:       Metro Care Chemist", body)
        self.assertIn("Current Stock:  3 units", body)
        self.assertIn("Minimum Stock:  10 units", body)
        self.assertIn("2026-09-17T12:05:00Z", body)

    def test_03_dry_run_safety(self):
        """
        Verify that when enabled=False (safe dev/test default),
        no network socket connection is attempted and messages are recorded to outbox.
        """
        mailer = SMTPMailer(
            host="non.existent.smtp.server.invalid",
            port=587,
            enabled=False,
        )

        sample_order = {
            "order_id": 99,
            "medicine": "Augmentin",
            "quantity": 1,
            "pharmacy": "Central Branch",
            "status": "confirmed",
        }

        # If network socket were attempted, this would raise gaierror or ConnectionRefused
        msg = mailer.send_order_confirmation(sample_order)
        self.assertIsNotNone(msg)
        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0]["Subject"], msg["Subject"])

    @patch("smtplib.SMTP")
    def test_04_smtp_network_delivery_protocol(self, mock_smtp_cls):
        """
        Verify wire-level SMTP interaction:
        EHLO -> STARTTLS -> LOGIN -> SEND_MESSAGE -> QUIT.
        """
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        mailer = SMTPMailer(
            host="smtp.provider.local",
            port=587,
            user="user@provider.local",
            password="secret_password",
            from_email="notifications@pharmacy.local",
            admin_email="admin@pharmacy.local",
            enabled=True,
            use_tls=True,
        )

        sample_order = {
            "order_id": 77,
            "medicine": "Cetzine 10",
            "quantity": 2,
            "pharmacy": "City Health Central",
            "status": "confirmed",
        }

        msg = mailer.send_order_confirmation(sample_order)

        # 1. Verify host and port passed to smtplib.SMTP
        mock_smtp_cls.assert_called_once_with("smtp.provider.local", 587, timeout=10.0)

        # 2. Verify protocol handshake calls
        self.assertTrue(mock_server.ehlo.called)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@provider.local", "secret_password")

        # 3. Verify message transmitted
        mock_server.send_message.assert_called_once_with(msg)

    def test_05_service_layer_event_integration(self):
        """
        Verify notification_service event dispatchers invoke the mailer.
        """
        order_dict = {
            "order_id": 55,
            "pharmacy_name": "Metro Care Chemist",
            "brand_name": "Glycomet 500",
            "quantity": 4,
            "status": "confirmed",
            "total_amount": 180.00,
        }
        low_stock_dict = {
            "medicine_name": "Mox 500",
            "pharmacy_name": "City Health Central",
            "current_stock": 2,
            "minimum_stock": 10,
        }

        msg_order = notification_service.notify_order_created(order_dict)
        msg_alert = notification_service.notify_low_stock(low_stock_dict)

        self.assertIsNotNone(msg_order)
        self.assertIsNotNone(msg_alert)
        self.assertEqual(len(default_mailer.outbox), 2)
        self.assertIn("Order #55 Confirmation", default_mailer.outbox[0]["Subject"])
        self.assertIn("Low Stock Notice: Mox 500", default_mailer.outbox[1]["Subject"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
