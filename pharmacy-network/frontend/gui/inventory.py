"""
Inventory Management Screen for PySide6 Desktop GUI.
Allows inspecting pharmacy inventories and adjusting/updating stock quantities over TCP.
Strictly decoupled from SQLite; interacts exclusively via PharmacyTCPClient.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from frontend.gui.worker import NetworkWorker
from frontend.network.tcp_client import PharmacyTCPClient


class InventoryWidget(QWidget):
    """View for viewing and updating pharmacy stock levels."""

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._pharmacies: list[dict] = []
        self._medicines: list[dict] = []
        self._current_inventory: list[dict] = []
        self._worker: NetworkWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # Header with Refresh
        header = QHBoxLayout()
        title = QLabel("Inventory Management")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.refresh_btn = QPushButton("Refresh Data")
        self.refresh_btn.clicked.connect(self.reload_data)
        header.addWidget(self.refresh_btn)
        main_layout.addLayout(header)

        # Controls & Update Box
        update_box = QGroupBox("Update Medicine Stock Quantity")
        update_box.setStyleSheet("font-weight: bold;")
        form = QFormLayout(update_box)

        self.pharmacy_combo = QComboBox()
        self.pharmacy_combo.currentIndexChanged.connect(self._on_pharmacy_changed)
        form.addRow("Select Pharmacy Branch:", self.pharmacy_combo)

        self.medicine_combo = QComboBox()
        self.medicine_combo.currentIndexChanged.connect(self._on_medicine_changed)
        form.addRow("Select Medicine:", self.medicine_combo)

        self.current_stock_lbl = QLabel("Current Stock: -")
        self.current_stock_lbl.setStyleSheet("font-weight: normal; color: #94a3b8;")
        form.addRow(self.current_stock_lbl)

        spin_layout = QHBoxLayout()
        self.new_qty_spin = QSpinBox()
        self.new_qty_spin.setRange(0, 10000)
        self.new_qty_spin.setValue(100)
        spin_layout.addWidget(self.new_qty_spin)

        self.update_btn = QPushButton("Save New Stock Quantity")
        self.update_btn.setStyleSheet(
            "padding: 6px 14px; font-weight: bold; background-color: #16a34a; color: white; border-radius: 5px;"
        )
        self.update_btn.clicked.connect(self._on_update_stock_clicked)
        spin_layout.addWidget(self.update_btn)
        spin_layout.addStretch()

        form.addRow("Set New Quantity:", spin_layout)
        main_layout.addWidget(update_box)

        # Inventory Table for Selected Pharmacy
        table_box = QGroupBox("Current Stock at Selected Pharmacy")
        table_layout = QVBoxLayout(table_box)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Medicine ID", "Brand Name", "Stock Quantity", "Min Reorder Level", "Alert Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.table)

        main_layout.addWidget(table_box)

    def reload_data(self) -> None:
        """Loads pharmacies, medicines, and inventory in one background worker."""
        if not self.client.is_connected():
            return
        if self._worker is not None and self._worker.isRunning():
            return

        def fetch():
            pharmacies = self.client.find_pharmacies()
            medicines = self.client.search_medicines("")
            initial_inv = []
            if pharmacies:
                initial_inv = self.client.get_pharmacy_inventory(pharmacies[0]["id"])
            return pharmacies, medicines, initial_inv

        self._worker = NetworkWorker(fetch)
        self._worker.result_ready.connect(self._on_data_loaded)
        self._worker.error_occurred.connect(lambda err: print(f"[Inventory Load Error]: {err}"))
        self._worker.start()

    def _on_data_loaded(self, result: tuple) -> None:
        self._pharmacies, self._medicines, initial_inv = result

        # Populate Combos without firing cascading events
        self.pharmacy_combo.blockSignals(True)
        self.pharmacy_combo.clear()
        for p in self._pharmacies:
            self.pharmacy_combo.addItem(f"{p['name']} ({p.get('location', '')})", p["id"])
        self.pharmacy_combo.blockSignals(False)

        self.medicine_combo.blockSignals(True)
        self.medicine_combo.clear()
        for m in self._medicines:
            self.medicine_combo.addItem(f"{m['brand_name']} - INR {m.get('price_inr', 0.0)}", m["id"])
        self.medicine_combo.blockSignals(False)

        self._on_inventory_table_ready(initial_inv)
        self._update_current_stock_label()

    def _on_pharmacy_changed(self) -> None:
        self._load_selected_pharmacy_inventory()
        self._update_current_stock_label()

    def _on_medicine_changed(self) -> None:
        self._update_current_stock_label()

    def _load_selected_pharmacy_inventory(self) -> None:
        pharma_id = self.pharmacy_combo.currentData()
        if not pharma_id or not self.client.is_connected():
            return

        def fetch_inventory():
            return self.client.get_pharmacy_inventory(pharma_id)

        w = NetworkWorker(fetch_inventory)
        w.result_ready.connect(self._on_inventory_table_ready)
        w.start()

    def _on_inventory_table_ready(self, items: list[dict]) -> None:
        self._current_inventory = items
        self.table.setRowCount(len(items))
        text_brush = QBrush(QColor("#f8fafc"))
        for row, item in enumerate(items):
            for col, val in enumerate([
                str(item.get("medicine_id", "")),
                str(item.get("brand_name", "")),
                str(item.get("stock_quantity", "")),
                str(item.get("minimum_stock", "")),
            ]):
                t_item = QTableWidgetItem(val)
                t_item.setForeground(text_brush)
                self.table.setItem(row, col, t_item)

            is_low = item.get("stock_quantity", 0) <= item.get("minimum_stock", 0)
            status_item = QTableWidgetItem("LOW STOCK" if is_low else "Normal")
            status_item.setForeground(QColor("#f87171") if is_low else QColor("#4ade80"))
            self.table.setItem(row, 4, status_item)

    def _update_current_stock_label(self) -> None:
        """Updates stock display label using currently loaded inventory records."""
        med_id = self.medicine_combo.currentData()
        if not med_id:
            return

        match = next(
            (item for item in self._current_inventory if item.get("medicine_id") == med_id),
            None,
        )
        if match:
            qty = match.get("stock_quantity", 0)
            min_s = match.get("minimum_stock", 10)
            self.current_stock_lbl.setText(f"Current Stock: {qty} units (Minimum Threshold: {min_s})")
            self.new_qty_spin.setValue(qty)
        else:
            self.current_stock_lbl.setText("Current Stock: Not carried at this pharmacy.")

    def _on_update_stock_clicked(self) -> None:
        pharma_id = self.pharmacy_combo.currentData()
        med_id = self.medicine_combo.currentData()
        new_qty = self.new_qty_spin.value()

        if not pharma_id or not med_id:
            QMessageBox.warning(self, "Selection Error", "Please select a pharmacy and a medicine.")
            return

        self.update_btn.setEnabled(False)

        def do_update():
            return self.client.update_stock(pharmacy_id=pharma_id, medicine_id=med_id, quantity=new_qty)

        w = NetworkWorker(do_update)
        w.result_ready.connect(self._on_update_success)
        w.error_occurred.connect(self._on_update_error)
        w.start()

    def _on_update_success(self, res: dict) -> None:
        self.update_btn.setEnabled(True)
        QMessageBox.information(self, "Stock Updated", f"Successfully updated stock to {res.get('stock_quantity')} units.")
        self._load_selected_pharmacy_inventory()
        self._update_current_stock_label()

    def _on_update_error(self, err_msg: str) -> None:
        self.update_btn.setEnabled(True)
        QMessageBox.critical(self, "Update Failed", f"Could not update stock: {err_msg}")
