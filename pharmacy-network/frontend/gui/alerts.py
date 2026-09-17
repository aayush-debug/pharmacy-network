"""
Alerts Screen for PySide6 Desktop GUI.
Displays low-stock warnings queried over TCP as well as live push alerts
received asynchronously via the background UDP Datagram Listener (SOCK_DGRAM).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from frontend.gui.worker import NetworkWorker
from frontend.network.tcp_client import PharmacyTCPClient
from frontend.network.udp_client import UDPAlertListener


class AlertsWidget(QWidget):
    """
    Alerts view combining:
    1. Polled low-stock conditions queried over TCP.
    2. Real-time push alert datagrams received over a background UDP socket.
    """
    udp_alert_received = Signal(dict)

    def __init__(self, client: PharmacyTCPClient, udp_port: int = 5002, parent=None):
        super().__init__(parent)
        self.client = client
        self.udp_port = udp_port
        self._worker: NetworkWorker | None = None
        self._udp_listener: UDPAlertListener | None = None

        self._init_ui()
        self._init_udp_listener()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # Header with actions
        header = QHBoxLayout()
        title = QLabel("Stock Alerts & Real-Time Push Notifications")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.refresh_btn = QPushButton("Scan Catalog via TCP")
        self.refresh_btn.clicked.connect(self.reload_alerts)
        header.addWidget(self.refresh_btn)
        main_layout.addLayout(header)

        # Educational Architecture Banner (Viva Ready)
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_frame.setStyleSheet(
            "background-color: #141414; border: 1px solid #282828; border-radius: 6px; padding: 10px;"
        )
        info_layout = QVBoxLayout(info_frame)
        banner_title = QLabel("📡 UDP Datagram Push Subsystem (Port 5002)")
        banner_title.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px;")
        info_layout.addWidget(banner_title)

        banner_text = QLabel(
            "• TCP (Stream Socket): Used for reliable request-response operations (Search, Stock, Orders).\n"
            "• UDP (Datagram Socket): Used for instant, lightweight push notifications without connection overhead.\n"
            "When any pharmacy's inventory drops below minimum stock, the backend dispatches a UDP datagram."
        )
        banner_text.setStyleSheet("color: #a3a3a3; font-size: 12px; margin-top: 2px;")
        info_layout.addWidget(banner_text)
        main_layout.addWidget(info_frame)

        splitter = QSplitter(Qt.Vertical)

        # 1. Live UDP Push Alerts Table
        live_box = QGroupBox("Live Real-Time UDP Push Alerts (SOCK_DGRAM Stream)")
        live_box.setStyleSheet("font-weight: bold; color: #ffffff;")
        live_layout = QVBoxLayout(live_box)

        self.live_status_lbl = QLabel(f"● UDP Listener Active on 127.0.0.1:{self.udp_port}")
        self.live_status_lbl.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 11px;")
        live_layout.addWidget(self.live_status_lbl)

        self.live_table = QTableWidget(0, 6)
        self.live_table.setHorizontalHeaderLabels(
            ["Timestamp", "Pharmacy Branch", "Medicine", "Current Stock", "Min Level", "Transport"]
        )
        self.live_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.live_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.live_table.setEditTriggers(QTableWidget.NoEditTriggers)
        live_layout.addWidget(self.live_table)
        splitter.addWidget(live_box)

        # 2. Polled Active Low-Stock Table (TCP)
        active_box = QGroupBox("Current Inventory Low-Stock Audit (Polled via TCP)")
        active_box.setStyleSheet("font-weight: bold; color: #ffffff;")
        active_layout = QVBoxLayout(active_box)

        self.active_table = QTableWidget(0, 5)
        self.alerts_table = self.active_table  # Backwards compatibility alias
        self.active_table.setHorizontalHeaderLabels(
            ["Pharmacy Branch", "Location", "Medicine", "Current Stock", "Reorder Level"]
        )
        self.active_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.active_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.active_table.setEditTriggers(QTableWidget.NoEditTriggers)
        active_layout.addWidget(self.active_table)
        splitter.addWidget(active_box)

        main_layout.addWidget(splitter)

    def _init_udp_listener(self) -> None:
        """Starts the background UDP datagram socket listener."""
        self.udp_alert_received.connect(self._on_udp_alert_pushed)

        def callback(alert_dict):
            # Emit Qt signal to safely transfer execution to Qt UI main thread
            self.udp_alert_received.emit(alert_dict)

        try:
            self._udp_listener = UDPAlertListener(listen_port=self.udp_port, on_alert_received=callback)
            self._udp_listener.start()
        except Exception as err:
            self.live_status_lbl.setText(f"○ UDP Listener Offline: {err}")
            self.live_status_lbl.setStyleSheet("color: red; font-size: 11px;")

    def _on_udp_alert_pushed(self, alert: dict) -> None:
        """Invoked on the Qt main thread whenever a new UDP datagram is received."""
        row = self.live_table.rowCount()
        self.live_table.insertRow(row)
        text_brush = QBrush(QColor("#f8fafc"))

        for col, val in enumerate([
            str(alert.get("timestamp", "")),
            str(alert.get("pharmacy", "")),
            str(alert.get("medicine", "")),
        ]):
            it = QTableWidgetItem(val)
            it.setForeground(text_brush)
            self.live_table.setItem(row, col, it)

        stock_item = QTableWidgetItem(str(alert.get("stock", "")))
        stock_item.setForeground(QColor("#f87171"))
        self.live_table.setItem(row, 3, stock_item)

        min_item = QTableWidgetItem(str(alert.get("minimum", "")))
        min_item.setForeground(text_brush)
        self.live_table.setItem(row, 4, min_item)

        protocol_item = QTableWidgetItem("UDP Datagram")
        protocol_item.setForeground(QColor("#c084fc"))
        self.live_table.setItem(row, 5, protocol_item)

    def reload_alerts(self) -> None:
        """Queries the network for items with stock below reorder level via TCP."""
        if not self.client.is_connected():
            return

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Scanning...")

        def fetch():
            return self.client.get_low_stock()

        self._worker = NetworkWorker(fetch)
        self._worker.result_ready.connect(self._on_alerts_loaded)
        self._worker.error_occurred.connect(self._on_alerts_error)
        self._worker.start()

    def _on_alerts_loaded(self, low_items: list[dict]) -> None:
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Scan Catalog via TCP")

        self.active_table.setRowCount(len(low_items))
        text_brush = QBrush(QColor("#f8fafc"))
        for row, item in enumerate(low_items):
            for col, val in enumerate([
                str(item.get("pharmacy_name", "")),
                str(item.get("location", "")),
                str(item.get("brand_name", "")),
            ]):
                t_item = QTableWidgetItem(val)
                t_item.setForeground(text_brush)
                self.active_table.setItem(row, col, t_item)

            stock_item = QTableWidgetItem(str(item.get("stock_quantity", "")))
            stock_item.setForeground(QColor("#f87171"))
            self.active_table.setItem(row, 3, stock_item)

            min_item = QTableWidgetItem(str(item.get("minimum_stock", "")))
            min_item.setForeground(text_brush)
            self.active_table.setItem(row, 4, min_item)

    def _on_alerts_error(self, err_msg: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Scan Catalog via TCP")
        print(f"[Alerts Error]: {err_msg}")

    def closeEvent(self, event) -> None:
        if self._udp_listener:
            self._udp_listener.stop()
        event.accept()
