import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from color_analyzer.analyzer import ColorAnalyzer
from color_analyzer.color_utils import resource_path


def main():
    app = QApplication(sys.argv)

    qss_path = Path(resource_path("stylesheet.qss"))
    qss_text = qss_path.read_text(encoding='utf-8')
    app.setStyleSheet(qss_text)

    image_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    window = ColorAnalyzer(image_path)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
