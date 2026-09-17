"""
Expiry Audit Screen for PySide6 Desktop GUI.
Enterprise shelf-life monitoring, compliance audit, and expired batch disposal.
Strictly decoupled from SQLite; interacts exclusively via PharmacyTCPClient.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend.gui.worker import NetworkWorker
from frontend.network.tcp_client import PharmacyTCPClient


class ExpiryMetricCard(QFrame):
    """Visual metric card for expiry dashboard."""

    def __init__(self, title: str, initial_value: str = "0", color: str = "#ef4444", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "background-color: #141414; border: 1px solid #282828; border-radius: 8px; padding: 12px;"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 11px; color: #a3a3a3; font-weight: bold;")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl)

        self.val_lbl = QLabel(initial_value)
        self.val_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color}; margin-top: 4px;")
        self.val_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.val_lbl)

    def set_value(self, value: str | int) -> None:
        self.val_lbl.setText(str(value))


class ExpiryAuditWidget(QWidget):
    """Auditing screen for batch shelf-life and regulatory compliance."""

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._audit_data: dict = {}
        self._displayed_items: list[dict] = []
        self._worker: NetworkWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Medicine Expiry & Shelf-Life Compliance Audit")
        title.setStyleSheet("font-size: 19px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()

        self.refresh_btn = QPushButton("🔄 Run Expiry Audit")
        self.refresh_btn.setStyleSheet("padding: 6px 14px; background-color: #242424; color: #ffffff; border: 1px solid #383838; border-radius: 4px; font-weight: bold;")
        self.refresh_btn.clicked.connect(self.reload_audit)
        header.addWidget(self.refresh_btn)
        main_layout.addLayout(header)

        # Metric Cards Grid
        grid = QGridLayout()
        self.card_expired = ExpiryMetricCard("⛔ Expired Batches (Sale Blocked)", "...", "#ef4444")
        self.card_expiring = ExpiryMetricCard("⏳ Expiring in ≤ 30 Days (Urgent)", "...", "#f97316")
        self.card_watchlist = ExpiryMetricCard("⚠️ 31–90 Days Watchlist", "...", "#f59e0b")
        self.card_loss = ExpiryMetricCard("💰 Total Value at Risk (INR)", "...", "#eab308")

        grid.addWidget(self.card_expired, 0, 0)
        grid.addWidget(self.card_expiring, 0, 1)
        grid.addWidget(self.card_watchlist, 0, 2)
        grid.addWidget(self.card_loss, 0, 3)
        main_layout.addLayout(grid)

        # Filter Tabs Row
        filter_row = QHBoxLayout()
        btn_style = "QPushButton { background-color: #1a1a1a; color: #ffffff; border: 1px solid #2e2e2e; border-radius: 4px; padding: 6px 14px; font-weight: 500; } QPushButton:hover { background-color: #282828; }"
        self.btn_all = QPushButton("All At-Risk Items")
        self.btn_all.setStyleSheet(btn_style)
        self.btn_all.clicked.connect(lambda: self._filter_view("ALL"))
        filter_row.addWidget(self.btn_all)

        self.btn_expired = QPushButton("⛔ Expired Only")
        self.btn_expired.setStyleSheet(btn_style)
        self.btn_expired.clicked.connect(lambda: self._filter_view("EXPIRED"))
        filter_row.addWidget(self.btn_expired)

        self.btn_expiring = QPushButton("⏳ Expiring ≤ 30 Days")
        self.btn_expiring.setStyleSheet(btn_style)
        self.btn_expiring.clicked.connect(lambda: self._filter_view("EXPIRING_SOON"))
        filter_row.addWidget(self.btn_expiring)

        self.btn_watch = QPushButton("⚠️ Watchlist (31–90 Days)")
        self.btn_watch.setStyleSheet(btn_style)
        self.btn_watch.clicked.connect(lambda: self._filter_view("WATCHLIST"))
        filter_row.addWidget(self.btn_watch)

        filter_row.addStretch()

        self.quarantine_btn = QPushButton("🚫 Quarantine Selected Expired Batch")
        self.quarantine_btn.setStyleSheet(
            "background-color: #dc2626; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; border: none;"
        )
        self.quarantine_btn.clicked.connect(self._on_quarantine_clicked)
        filter_row.addWidget(self.quarantine_btn)

        main_layout.addLayout(filter_row)

        # Audit Table
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Medicine Name",
            "Manufacturer",
            "Batch No",
            "Expiry Date",
            "Days Remaining",
            "Price (₹)",
            "Stock Qty",
            "Compliance Status",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 95)
        self.table.setColumnWidth(4, 95)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 85)
        self.table.setColumnWidth(7, 80)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        main_layout.addWidget(self.table)

    def reload_audit(self) -> None:
        """Asynchronously executes expiry audit over TCP."""
        if not self.client.is_connected():
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Auditing...")

        def fetch():
            return self.client.get_expiry_audit()

        self._worker = NetworkWorker(fetch)
        self._worker.result_ready.connect(self._on_audit_loaded)
        self._worker.error_occurred.connect(lambda err: print(f"[Expiry Audit Error]: {err}"))
        self._worker.start()

    def _on_audit_loaded(self, audit: dict) -> None:
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Run Expiry Audit")
        self._audit_data = audit

        self.card_expired.set_value(audit.get("expired_count", 0))
        self.card_expiring.set_value(audit.get("expiring_soon_count", 0))
        self.card_watchlist.set_value(audit.get("watchlist_count", 0))
        total_risk = audit.get("loss_value_inr", 0.0) + audit.get("at_risk_value_inr", 0.0)
        self.card_loss.set_value(f"₹ {total_risk:.2f}")

        self._filter_view("ALL")

    def _filter_view(self, category: str) -> None:
        if not self._audit_data:
            return

        if category == "EXPIRED":
            items = self._audit_data.get("expired_items", [])
        elif category == "EXPIRING_SOON":
            items = self._audit_data.get("expiring_soon_items", [])
        elif category == "WATCHLIST":
            items = self._audit_data.get("watchlist_items", [])
        else:
            items = self._audit_data.get("all_audited_items", [])

        self._displayed_items = items
        self.table.setRowCount(len(items))

        bold_font = QFont()
        bold_font.setBold(True)
        text_brush = QBrush(QColor("#f8fafc"))

        for row, item in enumerate(items):
            days = item.get("days_to_expiry", 0)
            status_code = item.get("status_code", "IN_STOCK")

            if status_code == "EXPIRED" or days < 0:
                bg = QColor("#3b1219")  # Dark wine red tint
                status_text = "⛔ EXPIRED (Blocked)"
                status_fg = QColor("#f87171")
                days_str = f"{abs(days)}d Overdue"
            elif status_code == "EXPIRING_SOON" or days <= 30:
                bg = QColor("#3b1e08")  # Dark amber tint
                status_text = "⏳ EXPIRING SOON"
                status_fg = QColor("#fb923c")
                days_str = f"{days} days left"
            else:
                bg = QColor("#22271b")  # Dark subtle watchlist tint
                status_text = "⚠️ Watchlist (≤ 90d)"
                status_fg = QColor("#fbbf24")
                days_str = f"{days} days left"

            brush = QBrush(bg)

            vals = [
                str(item.get("id")),
                str(item.get("brand_name")),
                str(item.get("manufacturer")),
                str(item.get("batch_no")),
                str(item.get("expiry_date")),
                days_str,
                f"₹{float(item.get('price_inr', 0.0)):.2f}",
                str(item.get("stock_quantity", 0)),
                status_text,
            ]

            for col, val in enumerate(vals):
                t_item = QTableWidgetItem(val)
                t_item.setBackground(brush)
                if col == 8:
                    t_item.setFont(bold_font)
                    t_item.setForeground(QBrush(status_fg))
                    t_item.setTextAlignment(Qt.AlignCenter)
                else:
                    t_item.setForeground(text_brush)
                    if col in (0, 5, 6, 7):
                        t_item.setTextAlignment(Qt.AlignCenter if col in (0, 5) else Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, t_item)

    def _on_quarantine_clicked(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Selection Required", "Select an expired batch to quarantine.")
            return

        row = selected[0].row()
        item = self._displayed_items[row]

        if item.get("status_code") != "EXPIRED":
            QMessageBox.warning(self, "Action Denied", "Only expired items can be quarantined/discontinued.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Batch Quarantine",
            f"Quarantine and remove expired batch '{item.get('batch_no')}' of '{item.get('brand_name')}'?\n"
            "This will discontinue the inventory item.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            def do_del():
                return self.client.delete_medicine(item["id"])

            w = NetworkWorker(do_del)
            w.result_ready.connect(lambda res: self._on_quarantined_success())
            w.error_occurred.connect(lambda err: QMessageBox.critical(self, "Quarantine Failed", str(err)))
            w.start()

    def _on_quarantined_success(self) -> None:
        QMessageBox.information(self, "Quarantine Complete", "Batch successfully quarantined and removed from active inventory.")
        self.reload_audit()
