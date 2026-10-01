from dataclasses import dataclass

from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QKeySequence, QPen, QColor, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
)

@dataclass
class ROIState:
    is_on: bool = False
    start: QPoint = None
    end: QPoint = None
    left_offset: float = 0.0
    top_offset: float = 0.0
    right_offset: float = 0.0
    bottom_offset: float = 0.0

@dataclass
class MouseState:
    last_pos: QPoint = None
    on_top: bool = False
    on_bottom: bool = False
    on_left: bool = False
    on_right: bool = False

@dataclass
class ImageState:
    pixmap_original: QPixmap = None
    scale: float = 1.0
    offset_x: int = 0
    offset_y: int = 0

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

        self.image = ImageState()
        self.roi = ROIState()
        self.mouse = MouseState()

    def set_roi_mode(self, toggle):
        if not self.roi.is_on:
            self.roi.is_on = True
        else:
            self.roi.is_on = False

        if self.roi.is_on:
            self.roi.start = QPoint(self.x, self.y)
            self.roi.end = QPoint(
                int(-self.x + self.width() + 2 * self.image.offset_x),
                int(-self.y + self.height() + 2 * self.image.offset_y),
            )
            self.roi.left_offset = 0
            self.roi.top_offset = 0
            self.roi.right_offset = 0
            self.roi.bottom_offset = 0
        else:
            self.roi.start = None
            self.roi.end = None

        self.update()

    def set_image(self, pixmap, fixed_view):
        self.image.pixmap_original = pixmap

        if not fixed_view:
            width = pixmap.width()
            height = pixmap.height()
            self.image.scale = min(self.width() / width, self.height() / height)
            self.image.offset_x = 0
            self.image.offset_y = 0
        self.update_image()

    def wheelEvent(self, event):
        if self.image.pixmap_original is None:
            return

        mouse_x = event.position().x()
        mouse_y = event.position().y()

        old_width = self.image.pixmap_original.width() * self.image.scale
        old_height = self.image.pixmap_original.height() * self.image.scale

        old_x = (self.width() - old_width) / 2 + self.image.offset_x
        old_y = (self.height() - old_height) / 2 + self.image.offset_y

        image_x = (mouse_x - old_x) / self.image.scale
        image_y = (mouse_y - old_y) / self.image.scale

        if event.angleDelta().y() > 0:
            new_scale = self.image.scale * 1.2
        else:
            new_scale = self.image.scale / 1.2

        self.image.scale = max(0.1, min(new_scale, 10.0))

        new_width = self.image.pixmap_original.width() * self.image.scale
        new_height = self.image.pixmap_original.height() * self.image.scale

        new_x = mouse_x - image_x * self.image.scale
        new_y = mouse_y - image_y * self.image.scale

        center_x = (self.width() - new_width) / 2
        center_y = (self.height() - new_height) / 2

        self.image.offset_x = new_x - center_x
        self.image.offset_y = new_y - center_y
        self.update_image()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse.last_pos = event.pos()

            self.mouse.on_top = False
            self.mouse.on_bottom = False
            self.mouse.on_left = False
            self.mouse.on_right = False

            if self.roi.is_on and self.roi.start and self.roi.end:
                rect = QRect(self.roi.start, self.roi.end).normalized()
                margin = 6

                self.mouse.on_top = (
                    rect.left() - margin <= event.pos().x() <= rect.right() + margin
                    and abs(event.pos().y() - rect.top()) <= margin
                )
                self.mouse.on_bottom = (
                    rect.left() - margin <= event.pos().x() <= rect.right() + margin
                    and abs(event.pos().y() - rect.bottom()) <= margin
                )
                self.mouse.on_left = (
                    rect.top() - margin <= event.pos().y() <= rect.bottom() + margin
                    and abs(event.pos().x() - rect.left()) <= margin
                )
                self.mouse.on_right = (
                    rect.top() - margin <= event.pos().y() <= rect.bottom() + margin
                    and abs(event.pos().x() - rect.right()) <= margin
                )

    def mouseMoveEvent(self, event):
        self.update_cursor(event.pos())

        if self.mouse.last_pos is None:
            return

        delta = event.pos() - self.mouse.last_pos

        if self.roi.is_on:
            moved = False
            if self.mouse.on_top:
                self.roi.top_offset += delta.y() / self.image.scale
                moved = True
            if self.mouse.on_bottom:
                self.roi.bottom_offset += delta.y() / self.image.scale
                moved = True
            if self.mouse.on_left:
                self.roi.left_offset += delta.x() / self.image.scale
                moved = True
            if self.mouse.on_right:
                self.roi.right_offset += delta.x() / self.image.scale
                moved = True

            if moved:
                self.update_roi()
            else:
                self.image.offset_x += delta.x()
                self.image.offset_y += delta.y()
                self.update_image()
        elif event.buttons() & Qt.LeftButton:
            self.image.offset_x += delta.x()
            self.image.offset_y += delta.y()
            self.update_image()

        self.mouse.last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse.last_pos = None

    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.roi.is_on and self.roi.start and self.roi.end:
            painter = QPainter(self)
            rect = QRect(self.roi.start, self.roi.end).normalized()

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
        if self.image.pixmap_original is None:
            return

        self.pixmap_scaled = self.image.pixmap_original.scaled(
            self.image.pixmap_original.size() * self.image.scale,
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )

        canvas = QPixmap(self.size())
        canvas.fill(Qt.lightGray)

        painter = QPainter(canvas)
        self.x = int(
            (self.width() - self.pixmap_scaled.width()) // 2 + self.image.offset_x
        )
        self.y = int(
            (self.height() - self.pixmap_scaled.height()) // 2 + self.image.offset_y
        )

        painter.drawPixmap(self.x, self.y, self.pixmap_scaled)
        painter.end()

        self.setPixmap(canvas)
        self.update_roi()

    def update_roi(self):
        if not self.roi.is_on:
            return

        self.roi.start = QPoint(
            int(self.x + round(self.roi.left_offset) * self.image.scale),
            int(self.y + round(self.roi.top_offset) * self.image.scale),
        )
        self.roi.end = QPoint(
            int(
                self.x
                + self.pixmap_scaled.width()
                + round(self.roi.right_offset) * self.image.scale
            ),
            int(
                self.y
                + self.pixmap_scaled.height()
                + round(self.roi.bottom_offset) * self.image.scale
            ),
        )
        self.update()

    def update_cursor(self, pos):
        if not self.roi.is_on or self.roi.start is None or self.roi.end is None:
            self.setCursor(Qt.ArrowCursor)
            return

        rect = QRect(self.roi.start, self.roi.end).normalized()
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
