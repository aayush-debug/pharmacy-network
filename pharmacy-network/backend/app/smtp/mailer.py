"""
SMTP Mailer Module.
Implements email delivery for order confirmations and low-stock alerts using
Python's standard library 'smtplib' and 'email.message.EmailMessage'.

Layer 7 Protocol: SMTP (Simple Mail Transfer Protocol, RFC 5321)
Transport: Layer 4 TCP (Port 587 Submission / Port 25 / Port 1025)
"""

from datetime import datetime, timezone
from email.message import EmailMessage
import smtplib
from typing import Any

from backend.app import config


class SMTPMailer:
    """
    SMTP Mailer handling MIME message construction and delivery.
    Supports dry-run / disabled mode for academic development and offline testing.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        from_email: str | None = None,
        admin_email: str | None = None,
        enabled: bool | None = None,
        use_tls: bool | None = None,
    ):
        self.host = host if host is not None else config.SMTP_HOST
        self.port = port if port is not None else config.SMTP_PORT
        self.user = user if user is not None else config.SMTP_USER
        self.password = password if password is not None else config.SMTP_PASSWORD
        self.from_email = from_email if from_email is not None else config.SMTP_FROM
        self.admin_email = admin_email if admin_email is not None else config.ADMIN_EMAIL
        self.enabled = enabled if enabled is not None else config.SMTP_ENABLED
        self.use_tls = use_tls if use_tls is not None else config.SMTP_USE_TLS

        # In-memory outbox recording all generated messages (ideal for inspection/tests)
        self.outbox: list[EmailMessage] = []

    def build_order_confirmation_message(
        self, order: dict[str, Any], recipient: str | None = None
    ) -> EmailMessage:
        """
        Constructs a standard MIME EmailMessage for an order confirmation.
        Contains: order ID, medicine, quantity, pharmacy, order status, timestamp.
        """
        order_id = order.get("order_id") or order.get("id") or "N/A"
        medicine = order.get("medicine") or order.get("brand_name") or order.get("medicine_name") or "Unknown"
        quantity = order.get("quantity") or 0
        pharmacy = order.get("pharmacy") or order.get("pharmacy_name") or "Unknown Branch"
        status = order.get("status") or "confirmed"
        total_amount = order.get("total_amount")
        timestamp = order.get("created_at") or order.get("timestamp") or datetime.now(timezone.utc).isoformat()

        target_to = recipient or self.admin_email

        msg = EmailMessage()
        msg["Subject"] = f"[Pharmacy Network] Order #{order_id} Confirmation - {medicine}"
        msg["From"] = self.from_email
        msg["To"] = target_to

        amount_line = f"Total Amount: INR {total_amount}\n" if total_amount is not None else ""

        body = (
            "====================================================\n"
            "         PHARMACY ORDER CONFIRMATION NOTICE         \n"
            "====================================================\n\n"
            f"Order ID:      {order_id}\n"
            f"Medicine:      {medicine}\n"
            f"Quantity:      {quantity}\n"
            f"Pharmacy:      {pharmacy}\n"
            f"Order Status:  {status.upper()}\n"
            f"{amount_line}"
            f"Timestamp:     {timestamp}\n\n"
            "Thank you for ordering through the Pharmacy Network.\n"
            "This is an automated notification."
        )
        msg.set_content(body)
        return msg

    def build_low_stock_alert_message(
        self, item: dict[str, Any], recipient: str | None = None
    ) -> EmailMessage:
        """
        Constructs a standard MIME EmailMessage for an urgent low-stock alert.
        Contains: medicine, pharmacy, current stock, minimum stock, timestamp.
        """
        medicine = item.get("medicine") or item.get("brand_name") or item.get("medicine_name") or "Unknown"
        pharmacy = item.get("pharmacy") or item.get("pharmacy_name") or "Unknown Branch"
        stock = item.get("stock") if item.get("stock") is not None else item.get("stock_quantity", 0)
        minimum = item.get("minimum") if item.get("minimum") is not None else item.get("minimum_stock", 0)
        timestamp = item.get("timestamp") or datetime.now(timezone.utc).isoformat()

        target_to = recipient or self.admin_email

        msg = EmailMessage()
        msg["Subject"] = f"[URGENT ALERT] Low Stock Notice: {medicine} at {pharmacy}"
        msg["From"] = self.from_email
        msg["To"] = target_to

        body = (
            "====================================================\n"
            "           URGENT LOW-STOCK REORDER ALERT           \n"
            "====================================================\n\n"
            f"Medicine:       {medicine}\n"
            f"Pharmacy:       {pharmacy}\n"
            f"Current Stock:  {stock} units\n"
            f"Minimum Stock:  {minimum} units\n"
            f"Timestamp:      {timestamp}\n\n"
            "ACTION REQUIRED:\n"
            f"Inventory for '{medicine}' at '{pharmacy}' has fallen below\n"
            f"the safety reorder threshold of {minimum} units.\n"
            "Please restock immediately to avoid supply disruption."
        )
        msg.set_content(body)
        return msg

    def deliver(self, msg: EmailMessage) -> bool:
        """
        Delivers the message over SMTP.
        If SMTP_ENABLED is False (default in dev), logs dry-run output and records to outbox.
        """
        self.outbox.append(msg)

        if not self.enabled:
            print(
                f"[SMTP Mailer] (DRY-RUN / DISABLED) Stored in outbox for '{msg['To']}': "
                f"Subject: \"{msg['Subject']}\""
            )
            return True

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10.0) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()
                if self.user and self.password:
                    server.login(self.user, self.password)

                server.send_message(msg)
                print(
                    f"[SMTP Mailer] Delivered email to '{msg['To']}' via SMTP ({self.host}:{self.port})"
                )
                return True
        except Exception as err:
            print(f"[SMTP Mailer ERROR]: Failed to send email to '{msg['To']}': {err}")
            raise

    def send_order_confirmation(
        self, order: dict[str, Any], recipient: str | None = None
    ) -> EmailMessage:
        """Builds and delivers an order confirmation email."""
        msg = self.build_order_confirmation_message(order, recipient)
        self.deliver(msg)
        return msg

    def send_low_stock_alert(
        self, item: dict[str, Any], recipient: str | None = None
    ) -> EmailMessage:
        """Builds and delivers a low-stock alert email."""
        msg = self.build_low_stock_alert_message(item, recipient)
        self.deliver(msg)
        return msg


# Module-level default mailer
default_mailer = SMTPMailer()


def send_order_confirmation(
    order: dict[str, Any], recipient: str | None = None
) -> EmailMessage:
    """Convenience function sending an order confirmation using default configuration."""
    return default_mailer.send_order_confirmation(order, recipient)


def send_low_stock_alert(
    item: dict[str, Any], recipient: str | None = None
) -> EmailMessage:
    """Convenience function sending a low-stock alert using default configuration."""
    return default_mailer.send_low_stock_alert(item, recipient)


if __name__ == "__main__":
    print("=== Pharmacy Network SMTP Mailer Demo ===")
    print(f"SMTP Server: {config.SMTP_HOST}:{config.SMTP_PORT}")
    print(f"From Address: {config.SMTP_FROM}")
    print(f"Admin Recipient: {config.ADMIN_EMAIL}")
    print(f"SMTP Enabled: {config.SMTP_ENABLED}")

    # Demo 1: Order Confirmation
    sample_order = {
        "order_id": 101,
        "medicine": "Paracip 500",
        "quantity": 3,
        "pharmacy": "City Health Central",
        "status": "confirmed",
        "total_amount": 61.50,
    }
    order_msg = default_mailer.send_order_confirmation(sample_order)
    print("\n[Preview: Order Confirmation Email]")
    print(order_msg.get_content())

    # Demo 2: Low-Stock Alert
    sample_low = {
        "medicine": "Mox 500",
        "pharmacy": "Metro Care Chemist",
        "stock": 4,
        "minimum": 10,
    }
    alert_msg = default_mailer.send_low_stock_alert(sample_low)
    print("\n[Preview: Low Stock Alert Email]")
    print(alert_msg.get_content())
