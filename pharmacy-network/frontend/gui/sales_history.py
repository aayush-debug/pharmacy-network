"""
Sales History Screen for PySide6 Desktop GUI.
Displays auditable POS transactions and orders across all network pharmacies.
Strictly decoupled from SQLite; interacts exclusively via PharmacyTCPClient.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
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


class SalesHistoryWidget(QWidget):
    """View displaying historical transactions and POS receipts."""

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._sales: list[dict] = []
        self._worker: NetworkWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Sales History & POS Transaction Ledger")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()

        filter_label = QLabel("Filter by Pharmacy:")
        filter_label.setStyleSheet("color: #a3a3a3; font-weight: 500;")
        header.addWidget(filter_label)
        self.pharma_filter = QComboBox()
        self.pharma_filter.addItem("All Pharmacies", None)
        self.pharma_filter.currentIndexChanged.connect(self.reload_sales)
        header.addWidget(self.pharma_filter)

        self.refresh_btn = QPushButton("🔄 Refresh Sales")
        self.refresh_btn.setStyleSheet(
            "background-color: #242424; color: #ffffff; font-weight: 600; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #383838;"
        )
        self.refresh_btn.clicked.connect(self.reload_sales)
        header.addWidget(self.refresh_btn)

        main_layout.addLayout(header)

        # Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Tx ID",
            "Timestamp",
            "Pharmacy Branch",
            "Medicine Name",
            "Quantity",
            "Unit Price (₹)",
            "Total Amount (₹)",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        main_layout.addWidget(self.table)

    def reload_sales(self) -> None:
        """Loads pharmacies list and transaction records over TCP."""
        if not self.client.is_connected():
            return
        if self._worker is not None and self._worker.isRunning():
            return

        p_id = self.pharma_filter.currentData()

        def fetch():
            pharmas = self.client.find_pharmacies()
            sales = self.client.get_sales_history(pharmacy_id=p_id)
            return pharmas, sales

        self._worker = NetworkWorker(fetch)
        self._worker.result_ready.connect(self._on_data_loaded)
        self._worker.error_occurred.connect(lambda err: print(f"[Sales History Error]: {err}"))
        self._worker.start()

    def _on_data_loaded(self, result: tuple) -> None:
        pharmas, sales = result
        self._sales = sales

        # Populate filter combo if not populated
        if self.pharma_filter.count() <= 1 and pharmas:
            self.pharma_filter.blockSignals(True)
            for p in pharmas:
                self.pharma_filter.addItem(p["name"], p["id"])
            self.pharma_filter.blockSignals(False)

        self.table.setRowCount(len(sales))
        bold_font = QFont()
        bold_font.setBold(True)
        text_brush = QBrush(QColor("#f8fafc"))
        total_brush = QBrush(QColor("#4ade80"))

        for row, s in enumerate(sales):
            for col, val in enumerate([
                str(s.get("transaction_id", "")),
                str(s.get("timestamp", "")),
                str(s.get("pharmacy_name", "")),
                str(s.get("brand_name", "")),
                str(s.get("quantity", "")),
                f"₹{float(s.get('unit_price', 0.0)):.2f}",
            ]):
                item = QTableWidgetItem(val)
                item.setForeground(text_brush)
                self.table.setItem(row, col, item)

            total_item = QTableWidgetItem(f"₹{float(s.get('total_amount', 0.0)):.2f}")
            total_item.setFont(bold_font)
            total_item.setForeground(total_brush)
            self.table.setItem(row, 6, total_item)
