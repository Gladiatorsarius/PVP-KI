# PyQt6 GUI entry point for PVP-KI
# This file will wire up all widgets and connect to backend logic (training_loop, etc.)

import sys

from PyQt6.QtWidgets import QApplication

try:
    # package-style imports (when running `python -m python.main`)
    from .frontend.UI import MainWindow
    from .backend.manager import Manager
except Exception:
    # script-style imports (when running `python python/main.py`)
    from frontend.UI import MainWindow
    from backend.manager import Manager

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow(manager=Manager())
    window.show()
    sys.exit(app.exec())