"""
Point of Sale (POS) Management Screen for PySide6 Desktop GUI.
Enterprise pharmacy billing, checkout, and dispensing system.
Features:
- Fast multi-item cart management with real-time stock validation.
- Critical safety check: Blocks dispensing expired medicines with clear warnings.
- Real-time billing calculations (Subtotal, GST 5%, Grand Total in ₹).
- Atomic POS checkout over TCP with instant invoice receipt generation.
Decoupled from SQLite; strictly uses PharmacyTCPClient.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from frontend.gui.worker import NetworkWorker
from frontend.network.tcp_client import PharmacyTCPClient


class ReceiptDialog(QDialog):
    """Modal dialog displaying a formatted tax invoice receipt."""

    def __init__(self, invoice_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Tax Invoice — {invoice_data.get('invoice_no', 'APOLLO')}")
        self.resize(460, 520)

        layout = QVBoxLayout(self)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Courier New", 10))

        # Build clean ASCII receipt
        inv_no = invoice_data.get("invoice_no")
        pharma = invoice_data.get("pharmacy_name")
        customer = invoice_data.get("customer_name")
        pay_mode = invoice_data.get("payment_method")
        timestamp = invoice_data.get("timestamp")
        items = invoice_data.get("items", [])
        subtotal = invoice_data.get("subtotal", 0.0)
        gst = invoice_data.get("tax_gst", 0.0)
        total = invoice_data.get("grand_total", 0.0)

        receipt_lines = [
            "=" * 44,
            "           APOLLO PHARMACY NETWORK",
            f"          Branch: {pharma}",
            "=" * 44,
            f"Invoice No : {inv_no}",
            f"Date & Time: {timestamp}",
            f"Customer   : {customer}",
            f"Payment    : {pay_mode}",
            "-" * 44,
            f"{'Item':<20} {'Batch':<8} {'Qty':<4} {'Price':>8}",
            "-" * 44,
        ]

        for it in items:
            name = it.get("brand_name", "")[:19]
            batch = it.get("batch_no", "")[:8]
            qty = it.get("quantity", 0)
            lt = it.get("line_total", 0.0)
            receipt_lines.append(f"{name:<20} {batch:<8} {qty:<4} ₹{lt:>7.2f}")

        receipt_lines.extend([
            "-" * 44,
            f"{'Subtotal:':<32} ₹{subtotal:>8.2f}",
            f"{'GST (5%):':<32} ₹{gst:>8.2f}",
            "=" * 44,
            f"{'GRAND TOTAL:':<32} ₹{total:>8.2f}",
            "=" * 44,
            "",
            "   *** Thank you for your visit! ***",
            "   Goods once sold can only be returned",
            "   within 7 days with valid batch seal.",
        ])

        text_edit.setText("\n".join(receipt_lines))
        layout.addWidget(text_edit)

        close_btn = QPushButton("Close & Continue")
        close_btn.setStyleSheet("background-color: #0b69a3; color: white; font-weight: bold; padding: 6px 14px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class POSWidget(QWidget):
    """Point of Sale dispensing and billing view."""

    def __init__(self, client: PharmacyTCPClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._pharmacies: list[dict] = []
        self._catalog: list[dict] = []
        self._cart: list[dict] = []
        self._worker: NetworkWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Point of Sale (POS) Billing & Dispensing")
        title.setStyleSheet("font-size: 19px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()

        self.reload_btn = QPushButton("🔄 Reload Catalog")
        self.reload_btn.setStyleSheet(
            "padding: 5px 12px; background-color: #242424; color: #ffffff; border: 1px solid #383838; border-radius: 4px;"
        )
        self.reload_btn.clicked.connect(self.reload_data)
        header.addWidget(self.reload_btn)
        main_layout.addLayout(header)

        # Main Splitter: Left Item Selection & Right Cart/Billing
        splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL: Customer Details & Item Selector
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(12)

        # Customer Group
        cust_box = QGroupBox("Customer & Prescription Details")
        cust_box.setStyleSheet("font-weight: bold; color: #ffffff;")
        cust_layout = QFormLayout(cust_box)

        self.cust_name_input = QLineEdit()
        self.cust_name_input.setPlaceholderText("e.g. Rahul Sharma")
        cust_layout.addRow("Patient Name:", self.cust_name_input)

        self.doctor_input = QLineEdit()
        self.doctor_input.setPlaceholderText("e.g. Dr. A. K. Verma")
        cust_layout.addRow("Prescribing Doctor:", self.doctor_input)

        self.payment_combo = QComboBox()
        self.payment_combo.addItems(["Cash", "UPI / QR Code", "Debit/Credit Card", "Insurance"])
        cust_layout.addRow("Payment Method:", self.payment_combo)

        left_layout.addWidget(cust_box)

        # Item Selection Group
        item_box = QGroupBox("Add Medicine to Cart")
        item_box.setStyleSheet("font-weight: bold; color: #ffffff;")
        item_layout = QVBoxLayout(item_box)
        item_layout.setSpacing(8)

        pharma_row = QHBoxLayout()
        pharma_row.addWidget(QLabel("Dispensing Pharmacy:"))
        self.pharma_combo = QComboBox()
        self.pharma_combo.currentIndexChanged.connect(self._on_pharmacy_changed)
        pharma_row.addWidget(self.pharma_combo)
        item_layout.addLayout(pharma_row)

        med_row = QHBoxLayout()
        med_row.addWidget(QLabel("Select Medicine:"))
        self.medicine_combo = QComboBox()
        self.medicine_combo.currentIndexChanged.connect(self._on_medicine_selected)
        med_row.addWidget(self.medicine_combo)
        item_layout.addLayout(med_row)

        # Medicine Details & Safety Banner
        self.info_frame = QFrame()
        self.info_frame.setFrameShape(QFrame.StyledPanel)
        self.info_frame.setStyleSheet(
            "background-color: #141414; border: 1px solid #282828; border-radius: 6px; padding: 8px;"
        )
        info_layout = QVBoxLayout(self.info_frame)
        self.stock_lbl = QLabel("Stock: Select an item")
        self.stock_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffffff;")
        info_layout.addWidget(self.stock_lbl)

        self.price_lbl = QLabel("Price: -")
        self.price_lbl.setStyleSheet("font-size: 12px; color: #ffffff;")
        info_layout.addWidget(self.price_lbl)

        self.safety_alert = QLabel()
        self.safety_alert.setWordWrap(True)
        self.safety_alert.setVisible(False)
        info_layout.addWidget(self.safety_alert)

        item_layout.addWidget(self.info_frame)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Quantity:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1000)
        self.qty_spin.setValue(1)
        qty_row.addWidget(self.qty_spin)
        qty_row.addStretch()

        self.add_cart_btn = QPushButton("➕ Add to Cart")
        self.add_cart_btn.setStyleSheet(
            "background-color: #16a34a; color: white; font-weight: bold; padding: 7px 16px; border-radius: 4px; border: none;"
        )
        self.add_cart_btn.clicked.connect(self._on_add_to_cart_clicked)
        qty_row.addWidget(self.add_cart_btn)

        item_layout.addLayout(qty_row)
        left_layout.addWidget(item_box)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # RIGHT PANEL: Cart Table & Summary
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        cart_box = QGroupBox("Current Bill / Dispensing Cart")
        cart_box.setStyleSheet("font-weight: bold; color: #ffffff;")
        cart_box_layout = QVBoxLayout(cart_box)

        self.cart_table = QTableWidget(0, 6)
        self.cart_table.setHorizontalHeaderLabels(["ID", "Medicine Name", "Batch", "Unit Price", "Qty", "Total (₹)"])
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cart_table.setStyleSheet("font-size: 12px; font-weight: normal;")
        cart_box_layout.addWidget(self.cart_table)

        btn_row = QHBoxLayout()
        self.remove_item_btn = QPushButton("Remove Selected Item")
        self.remove_item_btn.setStyleSheet("padding: 4px 10px; border: 1px solid #cbd5e1; border-radius: 4px;")
        self.remove_item_btn.clicked.connect(self._on_remove_item_clicked)
        btn_row.addWidget(self.remove_item_btn)

        self.clear_cart_btn = QPushButton("Clear Cart")
        self.clear_cart_btn.setStyleSheet("padding: 4px 10px; border: 1px solid #cbd5e1; border-radius: 4px;")
        self.clear_cart_btn.clicked.connect(self._on_clear_cart_clicked)
        btn_row.addWidget(self.clear_cart_btn)
        btn_row.addStretch()
        cart_box_layout.addLayout(btn_row)

        right_layout.addWidget(cart_box)

        # Checkout Summary Frame
        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px;")
        summary_layout = QGridLayout(summary_frame)
        summary_layout.setSpacing(8)

        summary_layout.addWidget(QLabel("Subtotal:"), 0, 0)
        self.subtotal_lbl = QLabel("₹ 0.00")
        self.subtotal_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        summary_layout.addWidget(self.subtotal_lbl, 0, 1)

        summary_layout.addWidget(QLabel("GST Tax (5%):"), 1, 0)
        self.tax_lbl = QLabel("₹ 0.00")
        self.tax_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        summary_layout.addWidget(self.tax_lbl, 1, 1)

        grand_title = QLabel("Grand Total:")
        grand_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        summary_layout.addWidget(grand_title, 2, 0)

        self.total_lbl = QLabel("₹ 0.00")
        self.total_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #047857;")
        summary_layout.addWidget(self.total_lbl, 2, 1)

        self.checkout_btn = QPushButton("🧾 Process Checkout & Print Receipt")
        self.checkout_btn.setStyleSheet(
            "background-color: #10b981; color: white; font-weight: bold; font-size: 14px; padding: 10px; border-radius: 4px;"
        )
        self.checkout_btn.clicked.connect(self._on_checkout_clicked)
        summary_layout.addWidget(self.checkout_btn, 3, 0, 1, 2)

        right_layout.addWidget(summary_frame)
        splitter.addWidget(right_widget)

        splitter.setSizes([420, 540])
        main_layout.addWidget(splitter)

    def reload_data(self) -> None:
        """Loads registered pharmacies and catalog over TCP."""
        if not self.client.is_connected():
            return
        if self._worker is not None and self._worker.isRunning():
            return

        def fetch():
            pharmas = self.client.find_pharmacies()
            items = self.client.get_stock_query()
            return pharmas, items

        self._worker = NetworkWorker(fetch)
        self._worker.result_ready.connect(self._on_data_loaded)
        self._worker.error_occurred.connect(lambda err: print(f"[POS Load Error]: {err}"))
        self._worker.start()

    def _on_data_loaded(self, result: tuple) -> None:
        self._pharmacies, self._catalog = result

        # Populate Pharmacies
        self.pharma_combo.blockSignals(True)
        self.pharma_combo.clear()
        for p in self._pharmacies:
            self.pharma_combo.addItem(f"{p['name']} ({p.get('location', '')})", p["id"])
        self.pharma_combo.blockSignals(False)

        # Populate Medicines
        self.med_combo.blockSignals(True)
        self.med_combo.clear()
        for m in self._catalog:
            status = m.get("stock_status", "")
            self.med_combo.addItem(f"{m['brand_name']} — ₹{m['price_inr']:.2f} [{status}]", m["id"])
        self.med_combo.blockSignals(False)

        self._on_medicine_selected()

    def _on_pharmacy_changed(self) -> None:
        self._on_medicine_selected()

    def _on_medicine_selected(self) -> None:
        med_id = self.med_combo.currentData()
        if not med_id:
            return

        med = next((m for m in self._catalog if m["id"] == med_id), None)
        if not med:
            return

        price = med.get("price_inr", 0.0)
        stock = med.get("stock_quantity", 0)
        batch = med.get("batch_no", "-")
        expiry = med.get("expiry_date", "-")
        status_code = med.get("status_code", "IN_STOCK")

        self.med_info_lbl.setText(
            f"Price: ₹{price:.2f} | Available Stock: {stock} | Batch: {batch} | Expiry: {expiry}"
        )

        is_expired = status_code == "EXPIRED"
        self.safety_alert.setVisible(is_expired)
        if is_expired:
            self.safety_alert.setText(f"⛔ SALE BLOCKED: {med['brand_name']} expired on {expiry}!")
            self.add_cart_btn.setEnabled(False)
        else:
            self.add_cart_btn.setEnabled(stock > 0)

        self.qty_spin.setMaximum(max(1, stock))

    def _on_add_to_cart_clicked(self) -> None:
        med_id = self.med_combo.currentData()
        if not med_id:
            return

        med = next((m for m in self._catalog if m["id"] == med_id), None)
        if not med:
            return

        # Double check expiry guard
        if med.get("status_code") == "EXPIRED":
            QMessageBox.critical(
                self,
                "Safety Violation",
                f"Cannot add '{med['brand_name']}' to bill: Medicine has EXPIRED! Sale is legally prohibited.",
            )
            return

        qty = self.qty_spin.value()
        stock = med.get("stock_quantity", 0)

        # Check existing cart quantity
        existing = next((item for item in self._cart if item["medicine_id"] == med_id), None)
        total_qty = qty + (existing["quantity"] if existing else 0)

        if total_qty > stock:
            QMessageBox.warning(
                self,
                "Stock Limit Exceeded",
                f"Requested quantity ({total_qty}) exceeds available stock ({stock}) for '{med['brand_name']}'.",
            )
            return

        price = float(med.get("price_inr", 0.0))
        if existing:
            existing["quantity"] = total_qty
            existing["line_total"] = round(total_qty * price, 2)
        else:
            self._cart.append({
                "medicine_id": med_id,
                "brand_name": med["brand_name"],
                "batch_no": med.get("batch_no", "-"),
                "unit_price": price,
                "quantity": qty,
                "line_total": round(qty * price, 2),
            })

        self._render_cart()

    def _on_remove_item_clicked(self) -> None:
        selected = self.cart_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if 0 <= row < len(self._cart):
            self._cart.pop(row)
            self._render_cart()

    def _on_clear_cart_clicked(self) -> None:
        self._cart.clear()
        self._render_cart()

    def _render_cart(self) -> None:
        self.cart_table.setRowCount(len(self._cart))
        subtotal = 0.0

        for row, item in enumerate(self._cart):
            subtotal += item["line_total"]
            self.cart_table.setItem(row, 0, QTableWidgetItem(str(item["medicine_id"])))
            self.cart_table.setItem(row, 1, QTableWidgetItem(item["brand_name"]))
            self.cart_table.setItem(row, 2, QTableWidgetItem(item["batch_no"]))
            self.cart_table.setItem(row, 3, QTableWidgetItem(f"₹{item['unit_price']:.2f}"))
            self.cart_table.setItem(row, 4, QTableWidgetItem(str(item["quantity"])))
            self.cart_table.setItem(row, 5, QTableWidgetItem(f"₹{item['line_total']:.2f}"))

        tax = round(subtotal * 0.05, 2)
        grand_total = round(subtotal + tax, 2)

        self.subtotal_lbl.setText(f"₹ {subtotal:.2f}")
        self.tax_lbl.setText(f"₹ {tax:.2f}")
        self.total_lbl.setText(f"₹ {grand_total:.2f}")
        self.checkout_btn.setEnabled(len(self._cart) > 0)

    def _on_checkout_clicked(self) -> None:
        if not self._cart:
            QMessageBox.warning(self, "Empty Bill", "Please add at least one item to checkout.")
            return

        pharma_id = self.pharma_combo.currentData() or 1
        customer = self.customer_input.text().strip() or "Walk-in Customer"
        pay_mode = self.payment_combo.currentText()

        self.checkout_btn.setEnabled(False)
        self.checkout_btn.setText("Processing Sale...")

        def do_sale():
            return self.client.process_pos_sale(
                pharmacy_id=pharma_id,
                items=[{"medicine_id": i["medicine_id"], "quantity": i["quantity"]} for i in self._cart],
                customer_name=customer,
                payment_method=pay_mode,
            )

        w = NetworkWorker(do_sale)
        w.result_ready.connect(self._on_checkout_success)
        w.error_occurred.connect(self._on_checkout_error)
        w.start()

    def _on_checkout_success(self, invoice: dict) -> None:
        self.checkout_btn.setEnabled(True)
        self.checkout_btn.setText("🧾 Process Checkout & Print Receipt")
        self._cart.clear()
        self._render_cart()
        self.reload_data()

        # Display Printable Invoice
        dlg = ReceiptDialog(invoice, self)
        dlg.exec()

    def _on_checkout_error(self, err_msg: str) -> None:
        self.checkout_btn.setEnabled(True)
        self.checkout_btn.setText("🧾 Process Checkout & Print Receipt")
        QMessageBox.critical(self, "Checkout Rejected", f"POS Transaction could not be completed:\n\n{err_msg}")
