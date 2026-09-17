"""
Unified True Black Theme for Pharmacy Stock Query System GUI.
Provides clean, high-contrast dark mode styling with pure black backgrounds,
neutral dark charcoal cards, crisp white text, and vibrant status indicators.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Theme Color Tokens - True Black Dark Theme
COLOR_BG_MAIN = "#000000"        # True Black
COLOR_BG_CARD = "#141414"        # Neutral Dark Charcoal
COLOR_BG_INPUT = "#0a0a0a"       # Deep Black for Inputs
COLOR_BG_HOVER = "#242424"       # Neutral Dark Hover
COLOR_BORDER = "#282828"         # Neutral Border
COLOR_BORDER_FOCUS = "#555555"   # Neutral Focus Border

COLOR_TEXT_MAIN = "#ffffff"      # Pure Crisp White
COLOR_TEXT_MUTED = "#a3a3a3"     # Neutral Muted Silver
COLOR_TEXT_ACCENT = "#ffffff"    # Pure White Accent

COLOR_STATUS_SUCCESS = "#22c55e" # Green (In Stock, Normal)
COLOR_STATUS_WARNING = "#f59e0b" # Amber (Low Stock, Watchlist)
COLOR_STATUS_EXPIRING = "#f97316"# Orange (Expiring Soon)
COLOR_STATUS_DANGER = "#ef4444"  # Red (Expired, Alert)

DARK_THEME_QSS = """
/* ========================================================= */
/* Global Application True Black Dark Theme                  */
/* ========================================================= */

QWidget {
    background-color: #000000;
    color: #ffffff;
    font-family: "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #000000;
}

/* --------------------------------------------------------- */
/* Tab Widget & Tab Bar                                      */
/* --------------------------------------------------------- */
QTabWidget::pane {
    border: 1px solid #282828;
    background-color: #000000;
    border-top: none;
}

QTabBar::tab {
    background-color: #141414;
    color: #a3a3a3;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #282828;
    border-bottom: none;
    font-weight: 500;
}

QTabBar::tab:hover {
    background-color: #222222;
    color: #ffffff;
}

QTabBar::tab:selected {
    background-color: #242424;
    color: #ffffff;
    font-weight: bold;
    border-top: 2px solid #ffffff;
    border-left: 1px solid #333333;
    border-right: 1px solid #333333;
}

/* --------------------------------------------------------- */
/* Group Boxes & Panels                                      */
/* --------------------------------------------------------- */
QGroupBox {
    background-color: #141414;
    border: 1px solid #282828;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: bold;
    color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: #ffffff;
    background-color: #000000;
    border-radius: 3px;
}

/* --------------------------------------------------------- */
/* Labels & Form Elements                                    */
/* --------------------------------------------------------- */
QLabel {
    color: #ffffff;
    background-color: transparent;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0a0a0a;
    color: #ffffff;
    border: 1px solid #2e2e2e;
    border-radius: 5px;
    padding: 6px 10px;
    selection-background-color: #333333;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #666666;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #2e2e2e;
}

QComboBox QAbstractItemView {
    background-color: #141414;
    color: #ffffff;
    selection-background-color: #2a2a2a;
    selection-color: #ffffff;
    border: 1px solid #2e2e2e;
    padding: 4px;
}

/* --------------------------------------------------------- */
/* Buttons                                                   */
/* --------------------------------------------------------- */
QPushButton {
    background-color: #242424;
    color: #ffffff;
    border: 1px solid #383838;
    border-radius: 5px;
    padding: 7px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #333333;
    border-color: #484848;
}

QPushButton:pressed {
    background-color: #1a1a1a;
}

QPushButton:disabled {
    background-color: #1a1a1a;
    color: #555555;
    border-color: #242424;
}

/* --------------------------------------------------------- */
/* Tables                                                    */
/* --------------------------------------------------------- */
QTableWidget {
    background-color: #101010;
    alternate-background-color: #161616;
    color: #ffffff;
    gridline-color: #222222;
    border: 1px solid #282828;
    border-radius: 6px;
    font-size: 12px;
}

QTableWidget::item {
    color: #ffffff;
    padding: 5px;
}

QTableWidget::item:selected {
    background-color: #2a2a2a;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #181818;
    color: #ffffff;
    font-weight: bold;
    border: 1px solid #282828;
    padding: 6px;
}

QHeaderView::section:vertical {
    background-color: #181818;
    color: #888888;
    font-weight: bold;
    border: 1px solid #282828;
    padding: 4px;
}

/* --------------------------------------------------------- */
/* Status Bar & Scroll Bars                                  */
/* --------------------------------------------------------- */
QStatusBar {
    background-color: #080808;
    color: #a3a3a3;
    border-top: 1px solid #1e1e1e;
}

QScrollBar:vertical {
    background-color: #0a0a0a;
    width: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #2a2a2a;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3a3a3a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #0a0a0a;
    height: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #2a2a2a;
    min-width: 20px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3a3a3a;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""


def apply_dark_theme(app: QApplication) -> None:
    """Applies the master true black dark theme and QPalette to the QApplication."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLOR_BG_MAIN))
    palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT_MAIN))
    palette.setColor(QPalette.Base, QColor(COLOR_BG_CARD))
    palette.setColor(QPalette.AlternateBase, QColor("#181818"))
    palette.setColor(QPalette.ToolTipBase, QColor(COLOR_BG_CARD))
    palette.setColor(QPalette.ToolTipText, QColor(COLOR_TEXT_MAIN))
    palette.setColor(QPalette.Text, QColor(COLOR_TEXT_MAIN))
    palette.setColor(QPalette.Button, QColor("#1c1c1c"))
    palette.setColor(QPalette.ButtonText, QColor(COLOR_TEXT_MAIN))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Highlight, QColor("#2a2a2a"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Link, QColor(COLOR_TEXT_ACCENT))

    app.setPalette(palette)
    app.setStyleSheet(DARK_THEME_QSS)
