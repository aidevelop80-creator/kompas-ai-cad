# generate_aruco_mat.py — Генератор калибровочного листа A4 (300 DPI) с ArUco-маркерами для measure_photo.py
# Запуск: .venv\Scripts\python.exe generate_aruco_mat.py

import os
import struct
import zlib

import cv2
import numpy as np

# ===================== ЕДИНАЯ ГЕОМЕТРИЯ КАЛИБРОВОЧНОГО ЛИСТА (мм) =====================
ARUCO_DICT_ID = cv2.aruco.DICT_4X4_50
PAGE_W_MM = 297.0  # A4 альбомный
PAGE_H_MM = 210.0
DPI = 300
PX_PER_MM = DPI / 25.4  # ~11.8110236 px/мм

MARGIN_MM = 12.0  # Отступ маркеров от краёв листа (внутри печатного поля принтера)
MARKER_MM = 22.0  # Размер стороны каждого ArUco-маркера (22 x 22 мм)

# Координаты верхнего левого угла каждого маркера (ID: (x_mm, y_mm))
MARKER_POSITIONS_MM = {
    0: (MARGIN_MM, MARGIN_MM),  # Верхний левый (TL)
    1: (PAGE_W_MM - MARGIN_MM - MARKER_MM, MARGIN_MM),  # Верхний правый (TR)
    2: (
        PAGE_W_MM - MARGIN_MM - MARKER_MM,
        PAGE_H_MM - MARGIN_MM - MARKER_MM,
    ),  # Нижний правый (BR)
    3: (MARGIN_MM, PAGE_H_MM - MARGIN_MM - MARKER_MM),  # Нижний левый (BL)
}

# Рабочая зона укладки детали внутри маркеров (мм): X=38..259 (221 мм), Y=38..172 (134 мм)
WORK_AREA_MM = (
    MARGIN_MM + MARKER_MM + 4.0,
    MARGIN_MM + MARKER_MM + 4.0,
    PAGE_W_MM - MARGIN_MM - MARKER_MM - 4.0,
    PAGE_H_MM - MARGIN_MM - MARKER_MM - 4.0,
)


def _mm(val: float) -> int:
    return int(round(val * PX_PER_MM))


def _save_png_with_dpi(filepath: str, img_bgr: np.ndarray, dpi: int = 300):
    """Сохраняет PNG с поддержкой кириллических путей и точным pHYs-тегом DPI для печати 1:1."""
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise RuntimeError("[FAIL PNG] Не удалось закодировать PNG!")
    png_bytes = buf.tobytes()

    # Формируем стандартный PNG-чанк pHYs (пикселей на метр, unit=1)
    ppm = int(round(dpi / 0.0254))
    phys_data = struct.pack(">IIB", ppm, ppm, 1)
    phys_crc = zlib.crc32(b"pHYs" + phys_data) & 0xFFFFFFFF
    phys_chunk = (
        struct.pack(">I", len(phys_data))
        + b"pHYs"
        + phys_data
        + struct.pack(">I", phys_crc)
    )

    # Вставляем pHYs сразу после PNG-сигнатуры (8 байт) и IHDR-чанка (25 байт)
    out_bytes = png_bytes[:33] + phys_chunk + png_bytes[33:]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(out_bytes)


def generate_aruco_mat(output_path: str = "input/aruco_mat_A4.png") -> str:
    w_px = _mm(PAGE_W_MM)
    h_px = _mm(PAGE_H_MM)
    img = np.full((h_px, w_px, 3), 255, dtype=np.uint8)

    # 1. Тонкая светло-серая ориентировочная сетка 10 мм в рабочей зоне (не мешает детекции контуров)
    wx1, wy1, wx2, wy2 = WORK_AREA_MM
    x_start = int(np.ceil(wx1 / 10.0) * 10)
    y_start = int(np.ceil(wy1 / 10.0) * 10)
    grid_color = (236, 236, 236)
    for x_mm in range(x_start, int(wx2) + 1, 10):
        cv2.line(img, (_mm(x_mm), _mm(wy1)), (_mm(x_mm), _mm(wy2)), grid_color, 1)
    for y_mm in range(y_start, int(wy2) + 1, 10):
        cv2.line(img, (_mm(wx1), _mm(y_mm)), (_mm(wx2), _mm(y_mm)), grid_color, 1)

    # Рамка рабочей зоны (светло-серая)
    cv2.rectangle(img, (_mm(wx1), _mm(wy1)), (_mm(wx2), _mm(wy2)), (215, 215, 215), 2)

    # 2. 4 ArUco-маркера DICT_4X4_50 (ID 0, 1, 2, 3)
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    m_px = _mm(MARKER_MM)
    for marker_id, (mx_mm, my_mm) in MARKER_POSITIONS_MM.items():
        marker_gray = cv2.aruco.generateImageMarker(aruco_dict, marker_id, m_px)
        marker_bgr = cv2.cvtColor(marker_gray, cv2.COLOR_GRAY2BGR)
        x0, y0 = _mm(mx_mm), _mm(my_mm)
        img[y0 : y0 + m_px, x0 : x0 + m_px] = marker_bgr
        cv2.putText(
            img,
            f"ID:{marker_id}",
            (x0, y0 - 12 if my_mm > 50 else y0 + m_px + 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (90, 90, 90),
            2,
            cv2.LINE_AA,
        )

    # 3. Заголовок сверху и контрольная линейка 100.0 мм снизу (для проверки масштаба 100% после печати)
    cv2.putText(
        img,
        "AI-CAD CALIBRATION MAT | A4 LANDSCAPE 297x210 mm | PRINT AT 100% SCALE (NO FIT)",
        (_mm(48.0), _mm(22.0)),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.05,
        (60, 60, 60),
        2,
        cv2.LINE_AA,
    )

    ruler_x0 = (PAGE_W_MM - 100.0) / 2.0
    ruler_y = PAGE_H_MM - 18.0
    cv2.line(
        img,
        (_mm(ruler_x0), _mm(ruler_y)),
        (_mm(ruler_x0 + 100.0), _mm(ruler_y)),
        (40, 40, 40),
        3,
    )
    for step in range(0, 101, 10):
        tick_h = 5.0 if step % 50 == 0 else 3.0
        tx = _mm(ruler_x0 + step)
        cv2.line(img, (tx, _mm(ruler_y - tick_h)), (tx, _mm(ruler_y)), (40, 40, 40), 2)
    cv2.putText(
        img,
        "CHECK SCALE: 100.0 mm",
        (_mm(ruler_x0 + 18.0), _mm(ruler_y + 7.5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
        (40, 40, 40),
        2,
        cv2.LINE_AA,
    )

    # 4. Встроенная самопроверка детектором OpenCV
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())
    _, ids, _ = detector.detectMarkers(img)
    found_ids = sorted(int(i) for i in ids.flatten()) if ids is not None else []
    if found_ids != [0, 1, 2, 3]:
        raise RuntimeError(
            f"[FAIL SELF-TEST] Ожидались маркеры [0, 1, 2, 3], найдено: {found_ids}"
        )

    abs_path = os.path.abspath(output_path)
    _save_png_with_dpi(abs_path, img, dpi=DPI)
    print(
        f"[OK MAT] Сохранён калибровочный лист A4 ({w_px}x{h_px} px, {DPI} DPI): {abs_path}"
    )
    print(
        f"[OK SELF-TEST] Все 4 маркера ArUco распознаны: {found_ids} | "
        f"Рабочая зона: {wx2 - wx1:.0f} x {wy2 - wy1:.0f} мм"
    )
    return abs_path


if __name__ == "__main__":
    generate_aruco_mat()