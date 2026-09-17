"""
Orders Screen for PySide6 Desktop GUI.
Allows placing orders at a selected pharmacy, viewing live stock verification,
filtering medicines with a search bar, and inspecting order history over TCP.
Strictly decoupled from SQLite; interacts exclusively via PharmacyTCPClient.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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


class OrdersWidget(QWidget):
    """View for placing orders and reviewing order history."""

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._pharmacies: list[dict] = []
        self._medicines: list[dict] = []
        self._filtered_medicines: list[dict] = []
        self._worker: NetworkWorker | None = None
        self._stock_worker: NetworkWorker | None = None
        self._stock_query_id: int = 0
        self._available_stock: int = 0

        # Debounce timer (250ms) to prevent socket queries on every single keystroke
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._filter_and_populate_medicines)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Place Order Form
        order_box = QGroupBox("Place New Order")
        form = QFormLayout(order_box)
        form.setSpacing(10)

        # Pharmacy Selection
        self.pharmacy_combo = QComboBox()
        self.pharmacy_combo.currentIndexChanged.connect(self._on_pharmacy_changed)
        form.addRow("Select Pharmacy:", self.pharmacy_combo)

        # Medicine Search Filter
        search_layout = QHBoxLayout()
        self.med_search_input = QLineEdit()
        self.med_search_input.setPlaceholderText("🔍 Type to search medicine (e.g., Dolo, Augmentin, Paracip)...")
        self.med_search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.med_search_input)

        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.setStyleSheet(
            "padding: 4px 10px; font-weight: normal; background-color: #262626; color: #ffffff; border: 1px solid #3a3a3a; border-radius: 4px;"
        )
        self.clear_search_btn.clicked.connect(lambda: self.med_search_input.clear())
        search_layout.addWidget(self.clear_search_btn)
        form.addRow("Search Medicine:", search_layout)

        # Medicine Dropdown
        self.medicine_combo = QComboBox()
        self.medicine_combo.currentIndexChanged.connect(self._on_medicine_changed)
        form.addRow("Select Medicine:", self.medicine_combo)

        # Stock Availability Banner
        self.stock_status_lbl = QLabel("Select a medicine to inspect branch stock availability.")
        self.stock_status_lbl.setStyleSheet("font-weight: normal; color: #a3a3a3; font-size: 12px;")
        form.addRow("Stock Status:", self.stock_status_lbl)

        # Quantity & Total Price Preview
        qty_layout = QHBoxLayout()
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1000)
        self.qty_spin.setValue(1)
        self.qty_spin.valueChanged.connect(self._update_price_preview)
        qty_layout.addWidget(self.qty_spin)

        self.price_preview_lbl = QLabel("Total: ₹ 0.00")
        self.price_preview_lbl.setStyleSheet("font-weight: bold; color: #ffffff; margin-left: 12px; font-size: 13px;")
        qty_layout.addWidget(self.price_preview_lbl)
        qty_layout.addStretch()

        form.addRow("Order Quantity:", qty_layout)

        # Submit Button
        self.place_order_btn = QPushButton("Submit Order via TCP")
        self.place_order_btn.setStyleSheet(
            "padding: 9px 20px; font-weight: bold; background-color: #16a34a; color: white; border-radius: 5px; border: none;"
        )
        self.place_order_btn.clicked.connect(self._on_place_order_clicked)
        form.addRow("", self.place_order_btn)

        main_layout.addWidget(order_box)

        # Order History Table Section
        history_box = QGroupBox("Order History")
        history_layout = QVBoxLayout(history_box)
        history_layout.setSpacing(8)

        history_header = QHBoxLayout()
        history_header.addWidget(QLabel("Showing orders for the selected pharmacy:"))
        history_header.addStretch()
        self.refresh_orders_btn = QPushButton("🔄 Refresh History")
        self.refresh_orders_btn.setStyleSheet(
            "padding: 4px 12px; background-color: #262626; color: #ffffff; border: 1px solid #3a3a3a; border-radius: 4px;"
        )
        self.refresh_orders_btn.clicked.connect(self._load_order_history)
        history_header.addWidget(self.refresh_orders_btn)
        history_layout.addLayout(history_header)

        self.orders_table = QTableWidget(0, 7)
        self.orders_table.setHorizontalHeaderLabels(
            ["Order ID", "Pharmacy", "Medicine", "Qty", "Unit Price", "Total Amount", "Status"]
        )
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.orders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        history_layout.addWidget(self.orders_table)

        main_layout.addWidget(history_box)

    def reload_data(self) -> None:
        """Populates pharmacies, medicines, and orders in one background worker."""
        if not self.client.is_connected():
            return
        if self._worker is not None and self._worker.isRunning():
            return

        def fetch():
            pharmacies = self.client.find_pharmacies()
            medicines = self.client.search_medicines("")
            initial_orders = []
            if pharmacies:
                initial_orders = self.client.get_pharmacy_orders(pharmacies[0]["id"])
            return pharmacies, medicines, initial_orders

        self._worker = NetworkWorker(fetch)
        self._worker.result_ready.connect(self._on_data_loaded)
        self._worker.error_occurred.connect(lambda err: print(f"[Orders Load Error]: {err}"))
        self._worker.start()

    def _on_data_loaded(self, result: tuple) -> None:
        self._pharmacies, self._medicines, initial_orders = result

        # Populate Pharmacies
        self.pharmacy_combo.blockSignals(True)
        self.pharmacy_combo.clear()
        for p in self._pharmacies:
            self.pharmacy_combo.addItem(f"{p['name']} ({p.get('location', '')})", p["id"])
        self.pharmacy_combo.blockSignals(False)

        # Populate Medicines
        self._filter_and_populate_medicines()
        self._on_orders_loaded(initial_orders)

    def _on_search_changed(self, query: str) -> None:
        self._search_timer.start()

    def _filter_and_populate_medicines(self) -> None:
        search_text = self.med_search_input.text().strip().lower()

        if search_text:
            self._filtered_medicines = [
                m for m in self._medicines
                if search_text in m.get("brand_name", "").lower()
                or search_text in m.get("primary_ingredient", "").lower()
                or search_text in m.get("therapeutic_class", "").lower()
            ]
        else:
            self._filtered_medicines = self._medicines

        self.medicine_combo.blockSignals(True)
        self.medicine_combo.clear()

        for m in self._filtered_medicines:
            brand = m.get("brand_name", "")
            price = float(m.get("price_inr", 0.0))
            self.medicine_combo.addItem(f"{brand} (₹{price:.2f})", m)

        self.medicine_combo.blockSignals(False)
        self._on_medicine_changed()

    def _on_pharmacy_changed(self) -> None:
        self._check_branch_stock()
        self._load_order_history()

    def _on_medicine_changed(self) -> None:
        self._check_branch_stock()
        self._update_price_preview()

    def _update_price_preview(self) -> None:
        med_data = self.medicine_combo.currentData()
        if isinstance(med_data, dict):
            unit_price = float(med_data.get("price_inr", 0.0))
            qty = self.qty_spin.value()
            total = unit_price * qty
            self.price_preview_lbl.setText(f"Total: ₹ {total:.2f}")

    def _check_branch_stock(self) -> None:
        """Verifies if the selected medicine is stocked at the selected pharmacy."""
        pharma_id = self.pharmacy_combo.currentData()
        med_data = self.medicine_combo.currentData()

        if not pharma_id or not isinstance(med_data, dict):
            self.stock_status_lbl.setText("Select a medicine and pharmacy to verify stock.")
            self.stock_status_lbl.setStyleSheet("color: #64748b;")
            self.place_order_btn.setEnabled(False)
            return

        med_id = med_data["id"]
        self._stock_query_id += 1
        query_id = self._stock_query_id

        def query_stock():
            # Check stock at selected branch and check network availability
            stock_info = None
            try:
                stock_info = self.client.check_stock(pharmacy_id=pharma_id, medicine_id=med_id)
            except Exception:
                stock_info = None

            network_avail = self.client.find_pharmacies(medicine_id=med_id)
            return query_id, stock_info, network_avail

        self._stock_worker = NetworkWorker(query_stock)
        self._stock_worker.result_ready.connect(self._on_stock_check_finished)
        self._stock_worker.start()

    def _on_stock_check_finished(self, result: tuple) -> None:
        query_id, stock_info, network_avail = result
        if query_id != self._stock_query_id:
            # Stale query response; discard cleanly
            return

        med_data = self.medicine_combo.currentData()
        brand = med_data.get("brand_name", "Medicine") if isinstance(med_data, dict) else "Medicine"

        if stock_info and stock_info.get("stock_quantity", 0) > 0:
            qty = stock_info["stock_quantity"]
            min_s = stock_info.get("minimum_stock", 15)
            self._available_stock = qty

            self.stock_status_lbl.setText(f"✓ In Stock at selected branch: {qty} units available (Min Reorder: {min_s})")
            self.stock_status_lbl.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 12px;")
            self.qty_spin.setMaximum(qty)
            self.place_order_btn.setEnabled(True)
            self.place_order_btn.setText("Submit Order via TCP")
            self.place_order_btn.setStyleSheet(
                "padding: 9px 20px; font-weight: bold; background-color: #16a34a; color: white; border-radius: 5px; border: none;"
            )
        else:
            self._available_stock = 0
            # Check other branches carrying this item
            other_branches = [
                f"{a['pharmacy_name']} ({a['stock_quantity']} units)"
                for a in network_avail if a.get("stock_quantity", 0) > 0
            ]

            if other_branches:
                branches_str = ", ".join(other_branches[:2])
                self.stock_status_lbl.setText(
                    f"⚠️ Not stocked at this branch! Available at: {branches_str}."
                )
            else:
                self.stock_status_lbl.setText(f"❌ '{brand}' is currently OUT OF STOCK across the network.")

            self.stock_status_lbl.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 12px;")
            self.qty_spin.setMaximum(1)
            self.place_order_btn.setEnabled(False)
            self.place_order_btn.setText("Cannot Order: Out of Stock at Selected Branch")
            self.place_order_btn.setStyleSheet(
                "padding: 9px 20px; font-weight: bold; background-color: #242424; color: #777777; border-radius: 5px; border: 1px solid #333333;"
            )

    def _on_place_order_clicked(self) -> None:
        pharma_id = self.pharmacy_combo.currentData()
        med_data = self.medicine_combo.currentData()
        qty = self.qty_spin.value()

        if not pharma_id or not isinstance(med_data, dict):
            QMessageBox.warning(self, "Selection Error", "Please select a pharmacy and medicine.")
            return

        med_id = med_data["id"]

        self.place_order_btn.setEnabled(False)
        self.place_order_btn.setText("Processing Order...")

        def do_order():
            return self.client.place_order(pharmacy_id=pharma_id, medicine_id=med_id, quantity=qty)

        self._worker = NetworkWorker(do_order)
        self._worker.result_ready.connect(self._on_order_success)
        self._worker.error_occurred.connect(self._on_order_error)
        self._worker.start()

    def _on_order_success(self, order: dict) -> None:
        self.place_order_btn.setEnabled(True)
        self.place_order_btn.setText("Submit Order via TCP")

        QMessageBox.information(
            self,
            "Order Confirmed!",
            f"Order #{order.get('order_id')} successfully created!\n\n"
            f"Pharmacy: {order.get('pharmacy_name')}\n"
            f"Medicine: {order.get('brand_name')} x {order.get('quantity')}\n"
            f"Total Amount: ₹ {order.get('total_amount'):.2f}\n"
            f"Remaining Stock: {order.get('remaining_stock')} units\n"
            f"Status: {order.get('status', '').upper()}",
        )
        self._check_branch_stock()
        self._load_order_history()

    def _on_order_error(self, err_msg: str) -> None:
        self.place_order_btn.setEnabled(True)
        self.place_order_btn.setText("Submit Order via TCP")
        QMessageBox.critical(self, "Order Failed", f"Order could not be placed:\n\n{err_msg}")

    def _load_order_history(self) -> None:
        pharma_id = self.pharmacy_combo.currentData()
        if not pharma_id or not self.client.is_connected():
            return

        self.refresh_orders_btn.setEnabled(False)

        def fetch():
            return self.client.get_pharmacy_orders(pharma_id)

        w = NetworkWorker(fetch)
        w.result_ready.connect(self._on_orders_loaded)
        w.start()

    def _on_orders_loaded(self, orders: list[dict]) -> None:
        self.refresh_orders_btn.setEnabled(True)
        self.orders_table.setRowCount(len(orders))
        text_brush = QBrush(QColor("#f8fafc"))
        for row, o in enumerate(orders):
            for col, val in enumerate([
                str(o.get("order_id", "")),
                str(o.get("pharmacy_name", "")),
                str(o.get("brand_name", "")),
                str(o.get("quantity", "")),
                f"₹{float(o.get('unit_price', 0.0)):.2f}",
                f"₹{float(o.get('total_amount', 0.0)):.2f}",
            ]):
                item = QTableWidgetItem(val)
                item.setForeground(text_brush)
                self.orders_table.setItem(row, col, item)

            status_item = QTableWidgetItem(str(o.get("status", "")).upper())
            status_item.setForeground(QColor("#4ade80"))
            self.orders_table.setItem(row, 6, status_item)
