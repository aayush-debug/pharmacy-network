"""
GUI Package for Pharmacy Stock Query System Frontend.
Contains PySide6 screens and widgets communicating exclusively via TCP client.
"""

from frontend.gui.alerts import AlertsWidget
from frontend.gui.dashboard import DashboardWidget
from frontend.gui.expiry_audit import ExpiryAuditWidget
from frontend.gui.inventory import InventoryWidget
from frontend.gui.login import LoginWidget
from frontend.gui.orders import OrdersWidget
from frontend.gui.pos import POSWidget
from frontend.gui.sales_history import SalesHistoryWidget
from frontend.gui.search import SearchWidget
from frontend.gui.worker import NetworkWorker

__all__ = [
    "LoginWidget",
    "DashboardWidget",
    "SearchWidget",
    "InventoryWidget",
    "OrdersWidget",
    "AlertsWidget",
    "POSWidget",
    "ExpiryAuditWidget",
    "SalesHistoryWidget",
    "NetworkWorker",
]
