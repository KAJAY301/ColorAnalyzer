import sys

import cv2
import numpy as np
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QImage, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .color_utils import (
    count_color,
    hsv_distance,
    hsv_to_name,
    load_pixels,
    resource_path,
    unique_color_counts,
)
from .image_viewer import ImageViewer
from .copyable_table import CopyableTableWidget


class ColorAnalyzer(QWidget):
    def __init__(self, image_path=None):
        super().__init__()

        self.pixels = None
        self.showed_image = None

        if image_path:
            try:
                pixels, image = load_pixels(image_path)
            except Exception as error:
                QMessageBox.critical(self, "錯誤", str(error))
                sys.exit(1)

            self.pixels = pixels
            self.showed_image = image
            self.image_height = image.shape[0]
            self.image_width = image.shape[1]
            self.original_image_height = image.shape[0]
            self.original_image_width = image.shape[1]

        self.init_ui()
        self.show_image(fixed_view=False)

    def init_ui(self):
        self.setWindowTitle("Color Analyzer")
        self.resize(1200, 700)

        main_layout = QHBoxLayout()
        data_layout = QVBoxLayout()
        image_layout = QVBoxLayout()
        main_layout.addLayout(data_layout, 1)
        main_layout.addLayout(image_layout, 1)

        input_layout = QHBoxLayout()
        input_label = QLabel("顏色數量：")

        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("輸入印刷顏色數量")
        self.color_input.setFixedWidth(150)

        self.analyze_button = QPushButton("開始分析")
        self.analyze_button.clicked.connect(self.analyze)
        self.color_input.returnPressed.connect(self.analyze_button.click)

        input_layout.addWidget(input_label)
        input_layout.addWidget(self.color_input)
        input_layout.addWidget(self.analyze_button)
        input_layout.addStretch()
        data_layout.addLayout(input_layout)

        self.table = CopyableTableWidget()
        data_layout.addWidget(self.table)

        self.image_label = ImageViewer()
        tool_layout = QHBoxLayout()

        select_button = QPushButton()
        select_icon = QIcon(resource_path("resources/select.png"))
        select_button.setIcon(select_icon)
        select_button.setIconSize(QSize(29, 29))
        select_button.setToolTip("Select")
        select_button.setStyleSheet(
            """
            QPushButton {
                padding: 0px;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #CCCCCC;
            }
            """
        )
        select_button.clicked.connect(
            lambda: self.image_label.set_roi_mode(True)
        )

        rotate_button = QPushButton()
        rotate_icon = QIcon(resource_path("resources/rotate.png"))
        rotate_button.setIcon(rotate_icon)
        rotate_button.setIconSize(QSize(29, 29))
        rotate_button.setToolTip("Rotate")
        rotate_button.setStyleSheet(
            """
            QPushButton {
                padding: 0px;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #CCCCCC;
            }
            """
        )
        rotate_button.clicked.connect(self.rotate)

        mirror_button = QPushButton()
        mirror_icon = QIcon(resource_path("resources/mirror.png"))
        mirror_button.setIcon(mirror_icon)
        mirror_button.setIconSize(QSize(29, 29))
        mirror_button.setToolTip("Mirror")
        mirror_button.setStyleSheet(
            """
            QPushButton {
                padding: 0px;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #CCCCCC;
            }
            """
        )
        mirror_button.clicked.connect(self.mirror_horizontal)

        tool_layout.addWidget(select_button)
        tool_layout.addWidget(rotate_button)
        tool_layout.addWidget(mirror_button)
        tool_layout.addStretch()

        image_layout.addLayout(tool_layout)
        image_layout.addWidget(self.image_label)
        self.setLayout(main_layout)

    def analyze(self):
        text = self.color_input.text().strip()

        try:
            how_many_color = int(text)
            if how_many_color <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "輸入錯誤", "請輸入大於 0 的整數")
            return
        color_number = how_many_color + 1

        if self.image_label.roi.is_on:
            x1 = round(self.image_label.roi.left_offset)
            x2 = round(self.image_label.roi.right_offset) + self.original_image_width
            y1 = round(self.image_label.roi.top_offset)
            y2 = round(self.image_label.roi.bottom_offset) + self.original_image_height

            x1 = max(0, min(x1, self.original_image_width))
            x2 = max(0, min(x2, self.original_image_width))
            y1 = max(0, min(y1, self.original_image_height))
            y2 = max(0, min(y2, self.original_image_height))

            pixels_2d = self.pixels.reshape(
                self.original_image_height,
                self.original_image_width,
                3,
            )
            roi_pixels = pixels_2d[y1:y2, x1:x2].reshape(-1, 3)
            if roi_pixels.size == 0:
                QMessageBox.warning(self, "選取區域錯誤", "選取區域沒有像素")
                return

            colors, counts = unique_color_counts(roi_pixels)
            
        else:
            colors, counts = unique_color_counts(self.pixels)

        order = np.argsort(counts)[::-1]
        colors = colors[order]
        counts = counts[order]

        grouped_count = {}
        for color, count in zip(colors, counts):
            color = tuple(map(int, color))
            count = int(count)

            matched_color = None

            for selected_color in grouped_count:
                distance = hsv_distance(color, selected_color)
                if distance < 20:
                    matched_color = selected_color
                    break

            if matched_color is not None:
                grouped_count[matched_color] += count
            else:
                grouped_count[color] = count

        color_count = dict(
            sorted(
                grouped_count.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:color_number]
        )

        if self.image_label.roi.is_on:
            color_count, _ = count_color(roi_pixels, color_count)
            _, result_pixels = count_color(self.pixels, color_count.copy())
            percentage_total = len(roi_pixels)
        else:
            color_count, result_pixels = count_color(self.pixels, color_count)
            percentage_total = len(self.pixels)

        sorted_colors = sorted(
            color_count.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        self.table.setRowCount(0)

        name_count = {}
        for color, count in sorted_colors:
            name = hsv_to_name(color)
            if name in name_count:
                name_count[name] += 1
                display_name = f"{name}{name_count[name]}"
            else:
                name_count[name] = 1
                display_name = name

            percentage = count / percentage_total * 100

            row = self.table.rowCount()
            self.table.insertRow(row)

            color_widget = QWidget()
            rgb = self.hsv_to_rgb(color)
            color_widget.setStyleSheet(
                f"background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]});"
            )
            self.table.setCellWidget(row, 0, color_widget)

            name_item = QTableWidgetItem(display_name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, name_item)

            percentage_item = QTableWidgetItem(f"{percentage:.2f}%")
            percentage_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, percentage_item)

            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, count_item)

        cv2_hsv = result_pixels.reshape(
            self.original_image_height,
            self.original_image_width,
            3,
        )
        cv2_bgr = cv2.cvtColor(cv2_hsv, cv2.COLOR_HSV2BGR)
        self.showed_image = cv2_bgr
        self.image_height = self.showed_image.shape[0]
        self.image_width = self.showed_image.shape[1]
        self.show_image(fixed_view=True)

    def rotate(self):
        rotated_image = cv2.rotate(self.showed_image, cv2.ROTATE_90_CLOCKWISE)
        self.showed_image = rotated_image
        self.image_height = self.showed_image.shape[0]
        self.image_width = self.showed_image.shape[1]
        self.show_image()

    def mirror_horizontal(self):
        mirrored_image = cv2.flip(self.showed_image, 1)
        self.showed_image = mirrored_image
        self.show_image()

    def show_image(self, fixed_view=True):
        result_bgr = np.ascontiguousarray(self.showed_image)
        qimage = QImage(
            result_bgr.data,
            self.image_width,
            self.image_height,
            result_bgr.strides[0],
            QImage.Format_BGR888,
        ).copy()

        pixmap = QPixmap.fromImage(qimage)
        self.image_label.set_image(pixmap, fixed_view=fixed_view)

    @staticmethod
    def hsv_to_rgb(hsv_color):
        hsv = np.uint8([[hsv_color]])
        rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        return tuple(map(int, rgb[0][0]))
