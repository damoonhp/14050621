from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("CodexBot")
    window = MainWindow(); window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

