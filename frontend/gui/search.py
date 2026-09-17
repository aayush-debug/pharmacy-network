"""
Medicine Search Screen for PySide6 Desktop GUI.
Allows searching the master catalog and inspecting medicine details
along with real-time stock availability across all pharmacy branches.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from frontend.gui.worker import NetworkWorker
from frontend.network.tcp_client import PharmacyTCPClient


class SearchWidget(QWidget):
    """Search catalog and inspect cross-pharmacy medicine availability."""

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._current_medicines: list[dict] = []
        self._search_worker: NetworkWorker | None = None
        self._stock_worker: NetworkWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Search Bar Section
        search_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search medicine by brand name, ingredient, or therapeutic category...")
        self.search_input.returnPressed.connect(self.do_search)
        search_bar.addWidget(self.search_input)

        self.search_btn = QPushButton("Search")
        self.search_btn.setStyleSheet(
            "padding: 6px 16px; font-weight: bold; background-color: #242424; color: white; border: 1px solid #383838; border-radius: 4px;"
        )
        self.search_btn.clicked.connect(self.do_search)
        search_bar.addWidget(self.search_btn)

        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setStyleSheet(
            "padding: 6px 14px; font-weight: bold; background-color: #1a1a1a; color: white; border: 1px solid #2e2e2e; border-radius: 4px;"
        )
        self.show_all_btn.clicked.connect(lambda: self._trigger_search(""))
        search_bar.addWidget(self.show_all_btn)

        main_layout.addLayout(search_bar)

        # Splitter dividing Results Table and Details/Availability Panel
        splitter = QSplitter(Qt.Vertical)

        # Top: Results Table
        top_box = QGroupBox("Search Results")
        top_box.setStyleSheet("font-weight: bold;")
        top_layout = QVBoxLayout(top_box)

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Brand Name", "Primary Ingredient", "Strength", "Dosage Form", "Price (INR)"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.itemSelectionChanged.connect(self._on_row_selected)
        top_layout.addWidget(self.results_table)
        splitter.addWidget(top_box)

        # Bottom: Medicine Details & Pharmacy Availability
        bottom_box = QGroupBox("Medicine Details & Availability by Pharmacy")
        bottom_box.setStyleSheet("font-weight: bold;")
        bottom_layout = QVBoxLayout(bottom_box)

        self.details_label = QLabel("Select a medicine from the results table above to view availability.")
        self.details_label.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: normal; margin-bottom: 6px;")
        bottom_layout.addWidget(self.details_label)

        self.stock_table = QTableWidget(0, 5)
        self.stock_table.setHorizontalHeaderLabels(
            ["Pharmacy Branch", "Location", "Available Stock", "Min Stock", "Status"]
        )
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stock_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stock_table.setEditTriggers(QTableWidget.NoEditTriggers)
        bottom_layout.addWidget(self.stock_table)

        splitter.addWidget(bottom_box)
        main_layout.addWidget(splitter)

    def do_search(self) -> None:
        query = self.search_input.text().strip()
        self._trigger_search(query)

    def _trigger_search(self, query: str) -> None:
        if not self.client.is_connected():
            QMessageBox.warning(self, "Disconnected", "Please connect to the TCP server first.")
            return

        self.search_btn.setEnabled(False)
        self.search_btn.setText("Searching...")

        self._search_worker = NetworkWorker(self.client.search_medicines, query)
        self._search_worker.result_ready.connect(self._on_search_success)
        self._search_worker.error_occurred.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_success(self, results: list[dict]) -> None:
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        self._current_medicines = results

        self.results_table.setRowCount(len(results))
        text_brush = QBrush(QColor("#f8fafc"))
        for row, med in enumerate(results):
            for col, val in enumerate([
                str(med.get("id", "")),
                str(med.get("brand_name", "")),
                str(med.get("primary_ingredient", "")),
                str(med.get("primary_strength", "")),
                str(med.get("dosage_form", "")),
                f"INR {med.get('price_inr', 0.0):.2f}",
            ]):
                item = QTableWidgetItem(val)
                item.setForeground(text_brush)
                self.results_table.setItem(row, col, item)

        if results:
            self.results_table.selectRow(0)
        else:
            self.details_label.setText("No medicines matched your search query.")
            self.stock_table.setRowCount(0)

    def _on_search_error(self, err_msg: str) -> None:
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        QMessageBox.critical(self, "Search Error", f"Failed to search medicines: {err_msg}")

    def _on_row_selected(self) -> None:
        selected_rows = self.results_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row_idx = selected_rows[0].row()
        if row_idx >= len(self._current_medicines):
            return

        med = self._current_medicines[row_idx]
        med_id = med["id"]

        self.details_label.setText(
            f"Brand: {med.get('brand_name')} | Manufacturer: {med.get('manufacturer', 'N/A')} | "
            f"Category: {med.get('therapeutic_class', 'N/A')} | Unit Price: INR {med.get('price_inr', 0.0)}"
        )

        # Query availability across pharmacies asynchronously
        self._stock_worker = NetworkWorker(self.client.find_pharmacies, medicine_id=med_id)
        self._stock_worker.result_ready.connect(self._on_stock_loaded)
        self._stock_worker.error_occurred.connect(
            lambda err: print(f"[Search Stock Error]: {err}")
        )
        self._stock_worker.start()

    def _on_stock_loaded(self, availability: list[dict]) -> None:
        self.stock_table.setRowCount(len(availability))
        text_brush = QBrush(QColor("#f8fafc"))
        for row, item in enumerate(availability):
            for col, val in enumerate([
                str(item.get("pharmacy_name", "")),
                str(item.get("location", "")),
                str(item.get("stock_quantity", "")),
                str(item.get("minimum_stock", "")),
            ]):
                t_item = QTableWidgetItem(val)
                t_item.setForeground(text_brush)
                self.stock_table.setItem(row, col, t_item)

            is_low = item.get("is_low_stock")
            status_str = "LOW STOCK ALERT" if is_low else "Sufficient Stock"
            status_item = QTableWidgetItem(status_str)
            if is_low:
                status_item.setForeground(QColor("#f87171"))
            else:
                status_item.setForeground(QColor("#4ade80"))
            self.stock_table.setItem(row, 4, status_item)
