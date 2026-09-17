"""
Dashboard Screen for PySide6 Desktop GUI.
Displays network metrics: total medicines, pharmacies, low-stock count,
pending orders, and a table of recent orders.
All data is fetched exclusively over TCP via PharmacyTCPClient.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from frontend.gui.worker import NetworkWorker
from frontend.network.tcp_client import PharmacyTCPClient


class MetricCard(QFrame):
    """Reusable visual summary card for key metrics."""

    def __init__(self, title: str, initial_value: str = "0", color: str = "#ffffff", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "background-color: #141414; border: 1px solid #282828; border-radius: 8px; padding: 12px;"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 12px; color: #a3a3a3; font-weight: 600;")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl)

        self.val_lbl = QLabel(initial_value)
        self.val_lbl.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {color}; margin-top: 4px;")
        self.val_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.val_lbl)

    def set_value(self, value: str | int) -> None:
        self.val_lbl.setText(str(value))


class DashboardWidget(QWidget):
    """
    Dashboard view aggregating network metrics: medicines, pharmacies,
    low-stock counts, and recent orders.
    """

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._worker: NetworkWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header with refresh button
        header_layout = QHBoxLayout()
        title = QLabel("System Dashboard")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh Dashboard")
        self.refresh_btn.setStyleSheet(
            "background-color: #242424; color: #ffffff; font-weight: 600; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #383838;"
        )
        self.refresh_btn.clicked.connect(self.load_metrics)
        header_layout.addWidget(self.refresh_btn)
        main_layout.addLayout(header_layout)

        # 4 Metric Cards in a Grid
        cards_grid = QGridLayout()
        self.card_medicines = MetricCard("Total Medicines", "...", "#ffffff")
        self.card_pharmacies = MetricCard("Registered Pharmacies", "...", "#22c55e")
        self.card_low_stock = MetricCard("Low-Stock Alerts", "...", "#f59e0b")
        self.card_pending_orders = MetricCard("Pending Orders", "...", "#eab308")

        cards_grid.addWidget(self.card_medicines, 0, 0)
        cards_grid.addWidget(self.card_pharmacies, 0, 1)
        cards_grid.addWidget(self.card_low_stock, 0, 2)
        cards_grid.addWidget(self.card_pending_orders, 0, 3)
        main_layout.addLayout(cards_grid)

        # Recent Orders Table Section
        orders_group = QGroupBox("Recent Orders Across Network")
        orders_group.setStyleSheet("font-weight: bold;")
        orders_layout = QVBoxLayout(orders_group)

        self.orders_table = QTableWidget(0, 7)
        self.orders_table.setHorizontalHeaderLabels(
            ["Order ID", "Pharmacy", "Medicine", "Qty", "Total (INR)", "Status", "Timestamp"]
        )
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.orders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        orders_layout.addWidget(self.orders_table)

        main_layout.addWidget(orders_group)

    def load_metrics(self) -> None:
        """Asynchronously loads all metrics from the backend over TCP."""
        if not self.client.is_connected():
            return

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Loading...")

        def fetch_data():
            # 1. Total medicines
            meds = self.client.search_medicines("")
            # 2. Total pharmacies
            pharmacies = self.client.find_pharmacies()
            # 3. Low stock count across inventory
            low_stock_items = self.client.get_low_stock()

            # 4. Recent orders across pharmacies
            all_orders = []
            pending_count = 0
            for p in pharmacies:
                orders = self.client.get_pharmacy_orders(p["id"])
                all_orders.extend(orders)
                for o in orders:
                    if o.get("status") == "pending":
                        pending_count += 1

            # Sort orders by created_at descending
            all_orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return {
                "total_medicines": len(meds),
                "total_pharmacies": len(pharmacies),
                "low_stock_count": len(low_stock_items),
                "pending_orders": pending_count,
                "recent_orders": all_orders[:15],
            }

        self._worker = NetworkWorker(fetch_data)
        self._worker.result_ready.connect(self._on_data_loaded)
        self._worker.error_occurred.connect(self._on_data_error)
        self._worker.start()

    def _on_data_loaded(self, data: dict) -> None:
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Dashboard")

        self.card_medicines.set_value(data["total_medicines"])
        self.card_pharmacies.set_value(data["total_pharmacies"])
        self.card_low_stock.set_value(data["low_stock_count"])
        self.card_pending_orders.set_value(data["pending_orders"])

        # Populate Recent Orders
        orders = data["recent_orders"]
        self.orders_table.setRowCount(len(orders))
        text_brush = QBrush(QColor("#f8fafc"))
        bold_font = QFont()
        bold_font.setBold(True)

        for row, order in enumerate(orders):
            for col, val in enumerate([
                str(order.get("order_id", "")),
                str(order.get("pharmacy_name", "")),
                str(order.get("brand_name", "")),
                str(order.get("quantity", "")),
                str(order.get("total_amount", "")),
            ]):
                it = QTableWidgetItem(val)
                it.setForeground(text_brush)
                self.orders_table.setItem(row, col, it)

            status_str = str(order.get("status", "")).upper()
            status_item = QTableWidgetItem(status_str)
            status_item.setFont(bold_font)
            if "COMPLETED" in status_str:
                status_item.setForeground(QColor("#22c55e"))
            elif "PENDING" in status_str:
                status_item.setForeground(QColor("#f59e0b"))
            else:
                status_item.setForeground(QColor("#ffffff"))
            self.orders_table.setItem(row, 5, status_item)

            time_item = QTableWidgetItem(str(order.get("created_at", "")))
            time_item.setForeground(text_brush)
            self.orders_table.setItem(row, 6, time_item)

    def _on_data_error(self, err_msg: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Dashboard")
        print(f"[Dashboard Error]: {err_msg}")
