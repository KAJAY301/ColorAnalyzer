from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QKeySequence, QPen, QColor, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
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


class ImageViewer(QLabel):
    def __init__(self):
        super().__init__()

        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 400)
        self.setStyleSheet(
            """
            background-color: #eeeeee;
            border: 0px;
            """
        )

        self.pixmap_original = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.last_pos = None

        self.roi_is_on = False
        self.roi_start = None
        self.roi_end = None
        self.roi_left_offset = 0
        self.roi_top_offset = 0
        self.roi_right_offset = 0
        self.roi_bottom_offset = 0

    def set_roi_mode(self, toggle):
        if not self.roi_is_on:
            self.roi_is_on = True
        else:
            self.roi_is_on = False

        if self.roi_is_on:
            self.roi_start = QPoint(self.x, self.y)
            self.roi_end = QPoint(
                int(-self.x + self.width() + 2 * self.offset_x),
                int(-self.y + self.height() + 2 * self.offset_y),
            )
            self.roi_left_offset = 0
            self.roi_top_offset = 0
            self.roi_right_offset = 0
            self.roi_bottom_offset = 0
        else:
            self.roi_start = None
            self.roi_end = None

        self.update()

    def set_image(self, pixmap, fixed_view):
        self.pixmap_original = pixmap

        if not fixed_view:
            width = pixmap.width()
            height = pixmap.height()
            self.scale = min(self.width() / width, self.height() / height)
            self.offset_x = 0
            self.offset_y = 0
        self.update_image()

    def wheelEvent(self, event):
        if self.pixmap_original is None:
            return

        mouse_x = event.position().x()
        mouse_y = event.position().y()

        old_width = self.pixmap_original.width() * self.scale
        old_height = self.pixmap_original.height() * self.scale

        old_x = (self.width() - old_width) / 2 + self.offset_x
        old_y = (self.height() - old_height) / 2 + self.offset_y

        image_x = (mouse_x - old_x) / self.scale
        image_y = (mouse_y - old_y) / self.scale

        if event.angleDelta().y() > 0:
            new_scale = self.scale * 1.2
        else:
            new_scale = self.scale / 1.2

        self.scale = max(0.1, min(new_scale, 10.0))

        new_width = self.pixmap_original.width() * self.scale
        new_height = self.pixmap_original.height() * self.scale

        new_x = mouse_x - image_x * self.scale
        new_y = mouse_y - image_y * self.scale

        center_x = (self.width() - new_width) / 2
        center_y = (self.height() - new_height) / 2

        self.offset_x = new_x - center_x
        self.offset_y = new_y - center_y
        self.update_image()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()

            self.on_top = False
            self.on_bottom = False
            self.on_left = False
            self.on_right = False

            if self.roi_is_on and self.roi_start and self.roi_end:
                rect = QRect(self.roi_start, self.roi_end).normalized()
                margin = 6

                self.on_top = (
                    rect.left() - margin <= event.pos().x() <= rect.right() + margin
                    and abs(event.pos().y() - rect.top()) <= margin
                )
                self.on_bottom = (
                    rect.left() - margin <= event.pos().x() <= rect.right() + margin
                    and abs(event.pos().y() - rect.bottom()) <= margin
                )
                self.on_left = (
                    rect.top() - margin <= event.pos().y() <= rect.bottom() + margin
                    and abs(event.pos().x() - rect.left()) <= margin
                )
                self.on_right = (
                    rect.top() - margin <= event.pos().y() <= rect.bottom() + margin
                    and abs(event.pos().x() - rect.right()) <= margin
                )

    def mouseMoveEvent(self, event):
        self.update_cursor(event.pos())

        if self.last_pos is None:
            return

        delta = event.pos() - self.last_pos

        if self.roi_is_on:
            moved = False
            if self.on_top:
                self.roi_top_offset += delta.y() / self.scale
                moved = True
            if self.on_bottom:
                self.roi_bottom_offset += delta.y() / self.scale
                moved = True
            if self.on_left:
                self.roi_left_offset += delta.x() / self.scale
                moved = True
            if self.on_right:
                self.roi_right_offset += delta.x() / self.scale
                moved = True

            if moved:
                self.update_roi()
            else:
                self.offset_x += delta.x()
                self.offset_y += delta.y()
                self.update_image()
        elif event.buttons() & Qt.LeftButton:
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.update_image()

        self.last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = None

    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.roi_is_on and self.roi_start and self.roi_end:
            painter = QPainter(self)
            rect = QRect(self.roi_start, self.roi_end).normalized()

            painter.setBrush(QColor(0, 0, 0, 100))
            painter.setPen(Qt.NoPen)
            painter.drawRect(0, 0, self.width(), rect.top())
            painter.drawRect(
                0,
                rect.bottom() + 1,
                self.width(),
                self.height() - rect.bottom(),
            )
            painter.drawRect(0, rect.top(), rect.left(), rect.height())
            painter.drawRect(
                rect.right(),
                rect.top(),
                self.width() - rect.right(),
                rect.height(),
            )

            pen = QPen(Qt.black)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            line_length = 30
            line_width = 4
            offset = line_width // 2

            pen = QPen(Qt.black)
            pen.setWidth(line_width)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            painter.drawLine(
                rect.left() - offset,
                rect.top() - offset,
                rect.left() + line_length,
                rect.top() - offset,
            )
            painter.drawLine(
                (rect.left() + rect.right() - line_length) // 2,
                rect.top() - offset,
                (rect.left() + rect.right() + line_length) // 2,
                rect.top() - offset,
            )
            painter.drawLine(
                rect.right() + offset,
                rect.top() - offset,
                rect.right() - line_length,
                rect.top() - offset,
            )
            painter.drawLine(
                rect.left() - offset,
                rect.bottom() + offset,
                rect.left() + line_length,
                rect.bottom() + offset,
            )
            painter.drawLine(
                (rect.left() + rect.right() - line_length) // 2,
                rect.bottom() + offset,
                (rect.left() + rect.right() + line_length) // 2,
                rect.bottom() + offset,
            )
            painter.drawLine(
                rect.right() + offset,
                rect.bottom() + offset,
                rect.right() - line_length,
                rect.bottom() + offset,
            )
            painter.drawLine(
                rect.left() - offset,
                rect.top() - offset,
                rect.left() - offset,
                rect.top() + line_length,
            )
            painter.drawLine(
                rect.left() - offset,
                (rect.top() + rect.bottom() - line_length) // 2,
                rect.left() - offset,
                (rect.top() + rect.bottom() + line_length) // 2,
            )
            painter.drawLine(
                rect.left() - offset,
                rect.bottom() + offset,
                rect.left() - offset,
                rect.bottom() - line_length,
            )
            painter.drawLine(
                rect.right() + offset,
                rect.top() - offset,
                rect.right() + offset,
                rect.top() + line_length,
            )
            painter.drawLine(
                rect.right() + offset,
                (rect.top() + rect.bottom() - line_length) // 2,
                rect.right() + offset,
                (rect.top() + rect.bottom() + line_length) // 2,
            )
            painter.drawLine(
                rect.right() + offset,
                rect.bottom() + offset,
                rect.right() + offset,
                rect.bottom() - line_length,
            )

            painter.end()

    def update_image(self):
        if self.pixmap_original is None:
            return

        self.pixmap_scaled = self.pixmap_original.scaled(
            self.pixmap_original.size() * self.scale,
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )

        canvas = QPixmap(self.size())
        canvas.fill(Qt.lightGray)

        painter = QPainter(canvas)
        self.x = int(
            (self.width() - self.pixmap_scaled.width()) // 2 + self.offset_x
        )
        self.y = int(
            (self.height() - self.pixmap_scaled.height()) // 2 + self.offset_y
        )

        painter.drawPixmap(self.x, self.y, self.pixmap_scaled)
        painter.end()

        self.setPixmap(canvas)
        self.update_roi()

    def update_roi(self):
        if not self.roi_is_on:
            return

        self.roi_start = QPoint(
            int(self.x + round(self.roi_left_offset) * self.scale),
            int(self.y + round(self.roi_top_offset) * self.scale),
        )
        self.roi_end = QPoint(
            int(
                self.x
                + self.pixmap_scaled.width()
                + round(self.roi_right_offset) * self.scale
            ),
            int(
                self.y
                + self.pixmap_scaled.height()
                + round(self.roi_bottom_offset) * self.scale
            ),
        )
        self.update()

    def update_cursor(self, pos):
        if not self.roi_is_on or self.roi_start is None or self.roi_end is None:
            self.setCursor(Qt.ArrowCursor)
            return

        rect = QRect(self.roi_start, self.roi_end).normalized()
        margin = 6
        on_top = (
            rect.left() - margin <= pos.x() <= rect.right() + margin
            and abs(pos.y() - rect.top()) <= margin
        )
        on_bottom = (
            rect.left() - margin <= pos.x() <= rect.right() + margin
            and abs(pos.y() - rect.bottom()) <= margin
        )
        on_left = (
            rect.top() - margin <= pos.y() <= rect.bottom() + margin
            and abs(pos.x() - rect.left()) <= margin
        )
        on_right = (
            rect.top() - margin <= pos.y() <= rect.bottom() + margin
            and abs(pos.x() - rect.right()) <= margin
        )

        if on_top:
            if on_left:
                self.setCursor(Qt.SizeFDiagCursor)
                return
            if on_right:
                self.setCursor(Qt.SizeBDiagCursor)
                return
            self.setCursor(Qt.SizeVerCursor)
            return
        if on_bottom:
            if on_left:
                self.setCursor(Qt.SizeBDiagCursor)
                return
            if on_right:
                self.setCursor(Qt.SizeFDiagCursor)
                return
            self.setCursor(Qt.SizeVerCursor)
            return
        if on_left or on_right:
            self.setCursor(Qt.SizeHorCursor)
            return

        self.setCursor(Qt.CrossCursor)
