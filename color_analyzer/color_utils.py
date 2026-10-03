import math
import os
import sys

import cv2
import numpy as np

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

def hsv_to_rgb(hsv_color):
    hsv = np.uint8([[hsv_color]])
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return tuple(map(int, rgb[0][0]))

def count_color(pixels, all_color, batch_size=100000):
    original_dtype = np.asarray(pixels).dtype
    pixels = np.asarray(pixels, dtype=np.float32)
    colors = np.asarray(list(all_color.keys()), dtype=np.float32)

    H_weight = 1.0
    V_weight = 2.0

    H = colors[:, 0]
    S = colors[:, 1] / 255.0
    V = colors[:, 2] / 255.0

    angle = 2.0 * np.pi * H / 180.0

    color_x = np.cos(angle) * S * V * H_weight
    color_y = np.sin(angle) * S * V * H_weight
    color_z = V * V_weight

    result_pixels = np.empty(pixels.shape, dtype=original_dtype)
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

        distance = np.sqrt(dx * dx + dy * dy + dz * dz)
        closest_index = np.argmin(distance, axis=1)

        result_pixels[start:end] = colors[closest_index].astype(original_dtype)
        total_counts += np.bincount(closest_index, minlength=len(colors))

    for i, color in enumerate(all_color.keys()):
        all_color[color] = int(total_counts[i])

    return all_color, result_pixels

def unique_color_counts(pixels):
    pixels = np.asarray(pixels, dtype=np.uint8).reshape(-1, 3)
    packed = (
        (pixels[:, 0].astype(np.uint32) << 16)
        | (pixels[:, 1].astype(np.uint32) << 8)
        | pixels[:, 2].astype(np.uint32)
    )
    packed_colors, counts = np.unique(packed, return_counts=True)
    colors = np.column_stack(
        (
            packed_colors >> 16,
            (packed_colors >> 8) & 0xFF,
            packed_colors & 0xFF,
        )
    ).astype(np.uint8)
    return colors, counts

def group_similar_colors(colors, counts, distance_threshold=20):
    colors = np.asarray(colors, dtype=np.float64).reshape(-1, 3)
    counts = np.asarray(counts)

    hues = colors[:, 0]
    saturations = colors[:, 1] / 255.0
    values = colors[:, 2] / 255.0
    angles = 2.0 * np.pi * hues / 180.0
    color_features = np.column_stack(
        (
            np.cos(angles) * saturations * values,
            np.sin(angles) * saturations * values,
            values * 2.0,
        )
    )

    grouped_counts = {}
    representative_colors = []
    spatial_buckets = {}
    cell_size = (distance_threshold + 0.5) * math.sqrt(5.0) / 255.0
    neighbor_offsets = tuple(
        (hue_offset, saturation_offset, value_offset)
        for hue_offset in (-1, 0, 1)
        for saturation_offset in (-1, 0, 1)
        for value_offset in (-1, 0, 1)
    )

    for color_values, count_value, color_feature in zip(
        colors, counts, color_features
    ):
        color = tuple(map(int, color_values))
        count = int(count_value)
        matched_color = None
        cell = tuple(
            math.floor(feature_value / cell_size)
            for feature_value in color_feature
        )

        for representative_index in spatial_buckets.get(cell, ()):
            selected_color = representative_colors[representative_index]
            if hsv_distance(color, selected_color) < distance_threshold:
                matched_color = selected_color
                break

        if matched_color is not None:
            grouped_counts[matched_color] += count
        else:
            grouped_counts[color] = count
            representative_index = len(representative_colors)
            representative_colors.append(color)
            for offset in neighbor_offsets:
                neighbor_cell = tuple(
                    cell[axis] + offset[axis] for axis in range(3)
                )
                spatial_buckets.setdefault(neighbor_cell, []).append(
                    representative_index
                )

    return grouped_counts

def load_pixels(file_path):
    """Load a JPG, PNG, or PDF and return its HSV pixels and BGR display image."""
    # PDF
    if file_path.suffix.lower() == ".pdf":
        import pymupdf

        images = []
        with pymupdf.open(file_path) as document:
            if document.page_count == 0:
                raise RuntimeError("PDF 沒有可讀取的頁面")
            for page in document:
                pixmap = page.get_pixmap(dpi=300,alpha=False)
                rgb = np.frombuffer(pixmap.samples, dtype=np.uint8)
                rgb = rgb.reshape(pixmap.height, pixmap.width, pixmap.n)
                if pixmap.n == 4:
                    rgb = rgb[:, :, :3]
                image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                images.append(image)

        if len(images) == 1:
            display_image = images[0]
        else:
            max_width = max(image.shape[1] for image in images)
            resized_images = []
            for image in images:
                height, width = image.shape[:2]
                if width != max_width:
                    new_height = int(height * max_width / width)
                    image = cv2.resize(image, (max_width, new_height))
                resized_images.append(image)
            display_image = np.vstack(resized_images)

        hsv_images = []
        for image in images:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            hsv_images.append(hsv.reshape(-1, 3))

        pixels = np.concatenate(hsv_images, axis=0)
        return pixels, display_image

    
    
    image = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"無法讀取圖片：{file_path}")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3)
    return pixels, image

def hsv_distance(point_a, point_b) -> float:
    """Calculate distance between two HSV colors using a cone-shaped model."""
    H1, S1, V1 = map(int, point_a)
    H2, S2, V2 = map(int, point_b)
    H_weight, V_weight = 1.0, 2.0
    weight = math.sqrt(H_weight**2 + V_weight**2)

    angle1 = 2.0 * math.pi * H1 / 180.0
    angle2 = 2.0 * math.pi * H2 / 180.0

    x1 = math.cos(angle1) * S1 / 255 * V1 / 255 * H_weight
    y1 = math.sin(angle1) * S1 / 255 * V1 / 255 * H_weight
    z1 = V1 / 255 * V_weight

    x2 = math.cos(angle2) * S2 / 255 * V2 / 255 * H_weight
    y2 = math.sin(angle2) * S2 / 255 * V2 / 255 * H_weight
    z2 = V2 / 255 * V_weight

    distance = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)
    return round(distance / weight * 255)

def resource_path(filename):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, filename)

def pop_transition(sorted_colors, total_pixels, distance_threshold=12):
    colors = list(sorted_colors)
    excluded = set()

    for i in range(len(colors) - 1, -1, -1):
        candidate_hsv, candidate_count = colors[i]
        if candidate_count >= 0.01 * total_pixels:
            continue

        candidate_rgb = hsv_to_rgb(candidate_hsv)
        best_match = None

        for j in range(i):
            color_a_hsv, _ = colors[j]
            color_a_rgb = hsv_to_rgb(color_a_hsv)

            for k in range(j + 1, i):
                color_b_hsv, _ = colors[k]
                color_b_rgb = hsv_to_rgb(color_b_hsv)
                distance, t, _ = point_to_segment_distance(
                    candidate_rgb,
                    color_a_rgb,
                    color_b_rgb,
                )

                if 0 <= t <= 1 and distance <= distance_threshold:
                    if best_match is None or distance < best_match[0]:
                        best_match = (distance, j, k, t)

        if best_match is not None:
            _, j, k, t = best_match
            excluded.add(candidate_hsv)
            target_index = j if t < 0.5 else k
            target_hsv, target_count = colors[target_index]
            colors[target_index] = (target_hsv, target_count + candidate_count)

    return [
        (color, count)
        for color, count in colors
        if color not in excluded
    ]





def pop_ringing(sorted_colors):
    pass

def point_to_segment_distance(C, A, B):

    C = np.asarray(C, dtype=np.float64)
    A = np.asarray(A, dtype=np.float64)
    B = np.asarray(B, dtype=np.float64)

    AB = B - A
    AB2 = np.dot(AB, AB)

    if AB2 == 0:
        return np.linalg.norm(C - A), 0.0, A

    t = np.dot(C - A, AB) / AB2

    projection = A + t * AB

    distance = np.linalg.norm(C - projection)

    return distance, t, projection




