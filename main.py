import sys
import cv2
import math
import numpy as np

from pathlib import Path
from collections import Counter

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage, QPainter, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
)

# ===============================================================
#                           Util
# ===============================================================
def hsv_to_name(hsv_pixel):
    color_h_dist = {
        "紅色": 0,
        "橘色": 15,
        "黃色": 30,
        "萊姆綠": 45,
        "綠色": 60,
        "春綠色": 75,
        "青色": 90,
        "天藍色": 105,
        "藍色": 120,
        "紫色": 135,
        "洋紅色": 150,
        "玫瑰紅": 165,
    }
    h, s, v = hsv_pixel

    # Black Gray White
    if v <= 30:
        return "黑色"
    if s <= 50:
        if v <= 65:
            return "深灰色"
        if v <= 130:
            return "灰色"
        if v <= 205:
            return "淺灰色"
        return "白色"

    # Other color
    min_dist = 180
    best_color = "unknown"
    for color, color_h in color_h_dist.items():
        dist = abs(int(h) - color_h)
        dist = min(dist, 180 - dist)
        if dist < min_dist:
            min_dist = dist
            best_color = color

    color_name = best_color

    # Dark or light
    if s < 150 and v < 130:
        if v > s - 25:
            color_name = "淺" + color_name
        elif v < s - 25:
            color_name = "深" + color_name

    return color_name

def count_color(pixels, all_color, batch_size=100000):
    original_dtype = np.asarray(pixels).dtype
    pixels = np.asarray(pixels, dtype=np.float32)
    colors = np.asarray(list(all_color.keys()), dtype=np.float32)

    H_weight = 1.0
    V_weight = 2.0
    weight = math.sqrt(H_weight**2 + V_weight**2)

    # 預先計算 color 座標
    H = colors[:, 0]
    S = colors[:, 1] / 255.0
    V = colors[:, 2] / 255.0

    angle = 2.0 * np.pi * H / 180.0

    color_x = np.cos(angle) * S * V * H_weight
    color_y = np.sin(angle) * S * V * H_weight
    color_z = V * V_weight

    result = np.empty(pixels.shape, dtype=original_dtype)

    total_counts = np.zeros(len(colors), dtype=np.int64)

    for start in range(0, len(pixels), batch_size):

        end = min(start + batch_size, len(pixels))

        batch = pixels[start:end]

        H = batch[:, 0]
        S = batch[:, 1] / 255.0
        V = batch[:, 2] / 255.0

        angle = 2.0 * np.pi * H / 180.0

        pixel_x = np.cos(angle) * S * V * H_weight
        pixel_y = np.sin(angle) * S * V * H_weight
        pixel_z = V * V_weight

        dx = pixel_x[:, None] - color_x[None, :]
        dy = pixel_y[:, None] - color_y[None, :]
        dz = pixel_z[:, None] - color_z[None, :]

        distance = np.sqrt(
            dx * dx +
            dy * dy +
            dz * dz
        )

        closest_index = np.argmin(distance, axis=1)

        result[start:end] = colors[closest_index].astype(original_dtype)

        total_counts += np.bincount(
            closest_index,
            minlength=len(colors)
        )

    for i, color in enumerate(all_color.keys()):
        all_color[color] += int(total_counts[i])

    return all_color, result

def load_pixels(file_path):
    """
    Load JPG / PNG / PDF

    Return:
        pixels
        display_image
        image_height
        image_width
    """
    # PDF
    if file_path.suffix.lower() == ".pdf":

        import pymupdf
        images = []

        with pymupdf.open(file_path) as document:
            if document.page_count == 0:
                raise RuntimeError("PDF 沒有可讀取的頁面")
            for page in document:
                pixmap = page.get_pixmap(alpha=False)
                rgb = np.frombuffer(pixmap.samples, dtype=np.uint8)
                rgb = rgb.reshape(pixmap.height, pixmap.width, pixmap.n)
                if pixmap.n == 4:
                    rgb = rgb[:, :, :3]
                image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                images.append(image)

        if len(images) == 1:
            display_image = images[0]
        else:
            max_width = max(
                image.shape[1]
                for image in images
            )

            resized_images = []
            for image in images:
                h, w = image.shape[:2]
                if w != max_width:
                    new_h = int(h * max_width / w)
                    image = cv2.resize(image, (max_width, new_h))
                resized_images.append(image)
            display_image = np.vstack(resized_images)

        hsv_images = []

        for image in images:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            hsv_images.append(hsv.reshape(-1, 3))

        pixels = np.concatenate(hsv_images, axis=0)

        return (pixels, display_image)

    # JPG PNG
    image = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"無法讀取圖片：{file_path}")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3)
    return (pixels, image)

def hsv_distance(point_a, point_b) -> float:
    """Calculate distance between two HSV colors using a cone-shaped model."""

    H1, S1, V1 = map(int, point_a)
    H2, S2, V2 = map(int, point_b)
    H_weight, V_weight = 1.0, 2.0
    weight = math.sqrt(H_weight**2 + V_weight**2)

    # OpenCV H: 0 ~ 179
    angle1 = 2.0 * math.pi * H1 / 180.0
    angle2 = 2.0 * math.pi * H2 / 180.0

    # HSV -> cone coordinates
    x1 = math.cos(angle1) * S1/255 * V1/255 * H_weight
    y1 = math.sin(angle1) * S1/255 * V1/255 * H_weight
    z1 = V1 / 255                           * V_weight

    x2 = math.cos(angle2) * S2/255 * V2/255 * H_weight
    y2 = math.sin(angle2) * S2/255 * V2/255 * H_weight
    z2 = V2 / 255                           * V_weight

    # Euclidean distance
    distance = math.sqrt(
        (x1 - x2) ** 2 +
        (y1 - y2) ** 2 +
        (z1 - z2) ** 2
    )
    # distance: 0 ~ weight
    # return 0 ~ 255
    return round(distance / weight * 255)

# ===============================================================
#                           UI
# ===============================================================
class CopyableTableWidget(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["色塊", "名稱", "比例", "總數"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 80)
        
        self.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch)
        
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
        for r in range(top_row, bottom_row + 1):
            row_cells = []
            for c in range(left_col, right_col + 1):
                item = self.item(r, c)
                text = item.text() if item is not None else ""
                row_cells.append(text)
            lines.append("\t".join(row_cells))

        clipboard_text = "\n".join(lines)

        QApplication.clipboard().setText(clipboard_text)

class ImageViewer(QLabel):
    def __init__(self):
        super().__init__()
        
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 400)
        self.setStyleSheet(
            """
            background-color: #eeeeee;
            border: 1px solid #cccccc;
            """
        )
        self.pixmap_original = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.last_pos = None

    # Set Image
    def set_image(self, pixmap):
        self.pixmap_original = pixmap

        w = pixmap.width()
        h = pixmap.height()
        self.scale = min(self.width()/w , self.height()/h)

        self.offset_x = 0
        self.offset_y = 0
        self.update_image()

    # Zoom
    def wheelEvent(self, event):
        if self.pixmap_original is None:
            return

        # Get mouse position
        mouse_x = event.position().x()
        mouse_y = event.position().y()

        # old size
        old_width = (self.pixmap_original.width() * self.scale)
        old_height = (self.pixmap_original.height() * self.scale)

        # old position
        old_x = (self.width() - old_width) / 2 + self.offset_x
        old_y = (self.height() - old_height) / 2 + self.offset_y

        # Get mouse position on image
        image_x = (mouse_x - old_x) / self.scale
        image_y = (mouse_y - old_y) / self.scale

        # Zoom

        if event.angleDelta().y() > 0:
            new_scale = self.scale * 1.2
        else:
            new_scale = self.scale / 1.2

        new_scale = max(0.1, min(new_scale, 10.0))

        # Updaye scale
        self.scale = new_scale

        # Calculate new size
        new_width = (self.pixmap_original.width() * self.scale)
        new_height = (self.pixmap_original.height() * self.scale)


        # offset to fixed the zoom point
        new_x = (mouse_x - image_x * self.scale)
        new_y = (mouse_y - image_y * self.scale)

        center_x = (self.width() - new_width) / 2
        center_y = (self.height() - new_height) / 2

        self.offset_x = (new_x - center_x)
        self.offset_y = (new_y - center_y)

        # update
        self.update_image()

    # Mouse Press
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()

    # Mouse Move
    def mouseMoveEvent(self, event):
        if self.last_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.pos() - self.last_pos

            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_pos = event.pos()

            self.update_image()

    # Mouse Release
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = None

    # Resize
    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)

    #  Update Image
    def update_image(self):
        if self.pixmap_original is None:
            return

        # Scale
        pixmap = self.pixmap_original.scaled(
            self.pixmap_original.size() * self.scale,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Set background
        canvas = QPixmap(self.size())
        canvas.fill(Qt.lightGray)

        # Painter
        painter = QPainter(canvas)
        x = int((self.width() - pixmap.width()) // 2 + self.offset_x)
        y = int((self.height() - pixmap.height()) // 2 + self.offset_y)
        
        painter.drawPixmap(x, y, pixmap)
        painter.end()

        self.setPixmap(canvas)

class ColorAnalyzer(QWidget):
    def __init__(self, image_path = None):

        super().__init__()

        self.pixels = None
        self.original_image = None

        if image_path:
            try:
                pixels, image = load_pixels(image_path)
            except Exception as error:
                QMessageBox.critical(self,"錯誤",str(error))
                sys.exit(1)

            self.pixels = pixels
            self.original_image = image

        self.init_ui()
        self.show_image(self.pixels)

    def init_ui(self):

        # Basic
        self.setWindowTitle("Color Analyzer")
        self.resize(1200, 700)

        # Layout
        main_layout = QHBoxLayout()
        data_layout = QVBoxLayout()
        image_layout = QVBoxLayout()
        main_layout.addLayout(data_layout,1)
        main_layout.addLayout(image_layout,1)

        # Menubar
        #menubar = self.menuBar()
        #file_menu = menubar.addMenu("檔案")
        #open_action = file_menu.addAction("開啟")
        #open_action.triggered.connect(self.open_file)

        # Input
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

        # Table
        self.table = CopyableTableWidget()
        data_layout.addWidget(self.table)

        # Image
        self.image_label = ImageViewer()
        image_layout.addWidget(self.image_label)
        self.setLayout(main_layout)

    def analyze(self):

        text = self.color_input.text().strip()

        # Check if input is int
        try:
            how_many_color = int(text)
            if how_many_color <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "輸入錯誤", "請輸入大於 0 的整數")
            return
        color_number = how_many_color + 1

        # Group simular color 
        pre_color_count = Counter(map(tuple, self.pixels))
        grouped_count = {}

        for color, count in pre_color_count.most_common():
            color = tuple(map(int, color))
            matched_color = None

            for selected_color in grouped_count:
                d = hsv_distance(color, selected_color)
                if d < 30:
                    matched_color = selected_color
                    break

            if matched_color is not None:
                grouped_count[matched_color] += count
            else:
                grouped_count[color] = count

        # Sort the most common color
        color_count = dict(
            sorted(
                grouped_count.items(),
                key=lambda x: x[1],
                reverse=True
            )[:color_number]
        )

        # Count color, get result pixels
        color_count, result_pixels = count_color(self.pixels, color_count)

        # Sort from many to few
        sorted_colors = sorted(color_count.items(), key=lambda x: x[1], reverse=True)

        self.table.setRowCount(0)

        name_count = {}
        for color, count in sorted_colors:
            # Name
            name = hsv_to_name(color)
            # make sure there is no the same name
            if name in name_count:
                name_count[name] += 1
                display_name = (f"{name}{name_count[name]}")
            else:
                name_count[name] = 1
                display_name = name

            # Percentage
            percentage = (count / self.pixels.shape[0] * 100)

            # show on table
            row = self.table.rowCount()
            self.table.insertRow(row)

            # color
            color_widget = QWidget()
            rgb = self.hsv_to_rgb(color)
            color_widget.setStyleSheet(
                f"background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]});"
            )
            self.table.setCellWidget(row,0, color_widget)

            # name
            name_item = QTableWidgetItem(display_name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row,1,name_item)

            # Percentage
            percentage_item = QTableWidgetItem(f"{percentage:.2f}%")
            percentage_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, percentage_item)

            # Count
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, count_item)

        # Image
        self.show_image(result_pixels)

    def show_image(self, result_pixels):
        """show [(h, s, v)] as qimage"""
        # Reshape
        height, width = (self.original_image.shape[:2])
        result_hsv = result_pixels.reshape(height,width,3)

        # HSV -> BGR -> Array
        result_bgr = cv2.cvtColor(result_hsv,cv2.COLOR_HSV2BGR)
        result_bgr = np.ascontiguousarray(result_bgr)

        qimage = QImage(
            result_bgr.data,
            width,
            height,
            result_bgr.strides[0],
            QImage.Format_BGR888
        ).copy()

        pixmap = QPixmap.fromImage(qimage)

        self.image_label.set_image(pixmap)

    @staticmethod
    def hsv_to_rgb(hsv_color):
        hsv = np.uint8([[hsv_color]])
        rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        return tuple(map(int,rgb[0][0]))

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