import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from color_analyzer.analyzer import ColorAnalyzer


def main():
    if len(sys.argv) > 1:
        image_path = Path(sys.argv[1])
    else:
        print("Error")

    app = QApplication(sys.argv)
    window = ColorAnalyzer(image_path)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
