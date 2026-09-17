"""
SMTP Package for Pharmacy Stock Network.
Exposes SMTPMailer, send_order_confirmation, and send_low_stock_alert.
"""

from backend.app.smtp.mailer import (
    SMTPMailer,
    default_mailer,
    send_low_stock_alert,
    send_order_confirmation,
)

__all__ = [
    "SMTPMailer",
    "default_mailer",
    "send_order_confirmation",
    "send_low_stock_alert",
]
