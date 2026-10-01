from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
)

class CopyableTableWidget(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["色塊", "名稱", "比例", "總數"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 80)

        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectItems)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy_selection()
        else:
            super().keyPressEvent(event)

    def copy_selection(self):
        selection = self.selectedRanges()
        if not selection:
            return

        r_range = selection[0]
        top_row = r_range.topRow()
        bottom_row = r_range.bottomRow()
        left_col = r_range.leftColumn()
        right_col = r_range.rightColumn()

        lines = []
        for row in range(top_row, bottom_row + 1):
            row_cells = []
            for column in range(left_col, right_col + 1):
                item = self.item(row, column)
                text = item.text() if item is not None else ""
                row_cells.append(text)
            lines.append("\t".join(row_cells))

        QApplication.clipboard().setText("\n".join(lines))