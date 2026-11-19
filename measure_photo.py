# measure_photo.py — Калибровка, выравнивание перспективы и замер геометрии по фото для ИИ-агента
# Использование:
#   .venv\Scripts\python.exe measure_photo.py input\latch\top_m.jpg
#   .venv\Scripts\python.exe measure_photo.py input\latch\
#   .venv\Scripts\python.exe measure_photo.py input\latch\top.jpg --width 68
#   .venv\Scripts\python.exe measure_photo.py input\latch\top.jpg --bbox 68 49

import argparse
import glob
import math
import os
import sys

import cv2
import numpy as np

from generate_aruco_mat import (
    ARUCO_DICT_ID,
    MARKER_MM,
    MARKER_POSITIONS_MM,
    PAGE_H_MM,
    PAGE_W_MM,
    WORK_AREA_MM,
)

OUT_PX_PER_MM = 10.0  # 10 px/мм (разрешение 0.1 мм/пиксель)
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def _imread_unicode(filepath: str) -> np.ndarray:
    data = np.fromfile(filepath, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(
            f"[FAIL READ] Не удалось прочитать изображение: {filepath}"
        )
    return img


def _imwrite_unicode(filepath: str, img: np.ndarray):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError(f"[FAIL WRITE] Не удалось закодировать PNG: {filepath}")
    buf.tofile(filepath)


def _rectify_by_aruco(img_bgr: np.ndarray):
    """Ищет 4 ArUco-маркера (ID 0..3) и выравнивает фото в масштаб OUT_PX_PER_MM."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    corners, ids, _ = detector.detectMarkers(img_bgr)
    if ids is None:
        return None, None

    found = {}
    for corner_set, mid in zip(corners, ids.flatten()):
        mid_int = int(mid)
        if mid_int in MARKER_POSITIONS_MM:
            found[mid_int] = corner_set.reshape(4, 2)

    if len(found) < 4:
        return None, None

    # Гомография по всем 16 углам 4 маркеров (порядок OpenCV: TL, TR, BR, BL)
    src_pts = []
    dst_pts = []
    for mid in (0, 1, 2, 3):
        mx, my = MARKER_POSITIONS_MM[mid]
        dst_mm = [
            (mx, my),
            (mx + MARKER_MM, my),
            (mx + MARKER_MM, my + MARKER_MM),
            (mx, my + MARKER_MM),
        ]
        for s_pt, (dx_mm, dy_mm) in zip(found[mid], dst_mm):
            src_pts.append(s_pt)
            dst_pts.append([dx_mm * OUT_PX_PER_MM, dy_mm * OUT_PX_PER_MM])

    src_arr = np.array(src_pts, dtype=np.float32).reshape(-1, 1, 2)
    dst_arr = np.array(dst_pts, dtype=np.float32).reshape(-1, 1, 2)
    H, _ = cv2.findHomography(src_arr, dst_arr, cv2.RANSAC, 3.0)
    if H is None:
        return None, None

    proj = cv2.perspectiveTransform(src_arr, H)
    reproj_err_mm = float(
        np.linalg.norm(proj - dst_arr, axis=2).mean() / OUT_PX_PER_MM
    )

    out_w = int(round(PAGE_W_MM * OUT_PX_PER_MM))
    out_h = int(round(PAGE_H_MM * OUT_PX_PER_MM))
    warped = cv2.warpPerspective(img_bgr, H, (out_w, out_h), flags=cv2.INTER_CUBIC)

    wx1, wy1, wx2, wy2 = [int(round(v * OUT_PX_PER_MM)) for v in WORK_AREA_MM]
    roi = warped[wy1:wy2, wx1:wx2]
    return roi, reproj_err_mm


def _segment_part(roi_bgr: np.ndarray) -> np.ndarray:
    """Выделяет бинарную маску детали через честную цветовую дистанцию CIELAB (отсекает мягкие тени)."""
    blur = cv2.GaussianBlur(roi_bgr, (5, 5), 0)
    lab = cv2.cvtColor(blur, cv2.COLOR_BGR2LAB).astype(np.float32)

    h, w = lab.shape[:2]
    b = max(8, min(h, w) // 25)
    border_pixels = np.concatenate(
        [
            lab[:b, :, :].reshape(-1, 3),
            lab[-b:, :, :].reshape(-1, 3),
            lab[:, :b, :].reshape(-1, 3),
            lab[:, -b:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg_lab = np.median(border_pixels, axis=0)
    dist = np.linalg.norm(lab - bg_lab, axis=2)
    dist_u8 = np.clip(dist, 0, 255).astype(np.uint8)

    otsu_val, _ = cv2.threshold(dist_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Отсекаем светло-серую сетку и мягкие тени на белом листе
    thresh_val = max(float(otsu_val), 32.0)
    _, mask = cv2.threshold(dist_u8, thresh_val, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def _find_main_contour(mask: np.ndarray):
    contours, hierarchy = cv2.findContours(
        mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours or hierarchy is None:
        return None, None, None
    hier = hierarchy[0]
    h, w = mask.shape[:2]
    best_idx = -1
    best_area = 0.0
    for idx, cnt in enumerate(contours):
        if hier[idx][3] != -1:
            continue
        area = cv2.contourArea(cnt)
        if area < 0.002 * w * h:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw > 0.96 * w and bh > 0.96 * h:
            continue
        if area > best_area:
            best_area = area
            best_idx = idx
    if best_idx < 0:
        return None, None, None
    return best_idx, contours, hier


def _deskew_roi(roi_bgr: np.ndarray, mask: np.ndarray, cnt: np.ndarray):
    """Выравнивает небольшой поворот детали строго в пределах [-45°, +45°) без 90°-переворотов."""
    rect = cv2.minAreaRect(cnt)
    angle = float(rect[2])
    rot_deg = ((angle + 45.0) % 90.0) - 45.0
    if abs(rot_deg) < 0.4:
        return roi_bgr, mask, 0.0

    h, w = roi_bgr.shape[:2]
    center = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(center, rot_deg, 1.0)
    bg_val = tuple(int(v) for v in np.median(roi_bgr[:10, :10].reshape(-1, 3), axis=0))
    rot_img = cv2.warpAffine(
        roi_bgr, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=bg_val
    )
    rot_mask = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    return rot_img, rot_mask, rot_deg


def _put_label_box(img: np.ndarray, text: str, org: tuple[int, int], fg_color: tuple):
    """Рисует контрастную подпись на тёмной подложке."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thick = 0.44, 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    x, y = org
    h, w = img.shape[:2]
    x = max(2, min(x, w - tw - 4))
    y = max(th + 4, min(y, h - 4))
    cv2.rectangle(img, (x - 2, y - th - 2), (x + tw + 2, y + 3), (25, 25, 25), -1)
    cv2.putText(img, text, (x, y), font, scale, fg_color, thick, cv2.LINE_AA)


def _draw_grid_overlay(
    crop_bgr: np.ndarray,
    px_per_mm: float,
    origin_px: tuple[float, float],
    outer_cnt: np.ndarray,
    crop_offset: tuple[int, int],
    holes: list[dict],
    windows: list[dict],
    part_w_mm: float,
    part_h_mm: float,
    mode_label: str,
) -> np.ndarray:
    """Накладывает миллиметровую сетку (5/10 мм), оси X/Y через центр детали и подписи замеров."""
    vis = crop_bgr.copy()
    h, w = vis.shape[:2]
    ox = origin_px[0] - crop_offset[0]
    oy = origin_px[1] - crop_offset[1]

    x_min_mm = int(math.floor(-ox / px_per_mm / 5.0) * 5)
    x_max_mm = int(math.ceil((w - ox) / px_per_mm / 5.0) * 5)
    y_min_mm = int(math.floor(-(h - oy) / px_per_mm / 5.0) * 5)
    y_max_mm = int(math.ceil(oy / px_per_mm / 5.0) * 5)

    for xm in range(x_min_mm, x_max_mm + 1, 5):
        px = int(round(ox + xm * px_per_mm))
        if 0 <= px < w:
            if xm == 0:
                color, thick = (0, 0, 220), 2
            elif xm % 10 == 0:
                color, thick = (180, 180, 180), 1
            else:
                color, thick = (222, 222, 222), 1
            cv2.line(vis, (px, 0), (px, h), color, thick)
            if xm % 10 == 0 and 15 < px < w - 25:
                cv2.putText(
                    vis,
                    f"{xm:+d}" if xm != 0 else "0",
                    (px - 12, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (50, 50, 50),
                    1,
                    cv2.LINE_AA,
                )

    for ym in range(y_min_mm, y_max_mm + 1, 5):
        py = int(round(oy - ym * px_per_mm))
        if 0 <= py < h:
            if ym == 0:
                color, thick = (0, 160, 0), 2
            elif ym % 10 == 0:
                color, thick = (180, 180, 180), 1
            else:
                color, thick = (222, 222, 222), 1
            cv2.line(vis, (0, py), (w, py), color, thick)
            if ym % 10 == 0 and 20 < py < h - 20:
                cv2.putText(
                    vis,
                    f"{ym:+d}" if ym != 0 else "0",
                    (6, py + 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (50, 50, 50),
                    1,
                    cv2.LINE_AA,
                )

    shifted_outer = outer_cnt - np.array([[[crop_offset[0], crop_offset[1]]]])
    cv2.drawContours(vis, [shifted_outer], -1, (0, 210, 0), 2)

    for item in holes:
        cx_px = int(round(ox + item["x"] * px_per_mm))
        cy_px = int(round(oy - item["y"] * px_per_mm))
        r_px = max(2, int(round(item["d"] * 0.5 * px_per_mm)))
        cv2.circle(vis, (cx_px, cy_px), r_px, (255, 200, 0), 2)
        cv2.circle(vis, (cx_px, cy_px), 2, (255, 200, 0), -1)
        _put_label_box(vis, f"D{item['d']:.1f}", (cx_px + 4, cy_px - 4), (255, 220, 80))

    for item in windows:
        shifted_c = item["cnt"] - np.array([[[crop_offset[0], crop_offset[1]]]])
        cv2.drawContours(vis, [shifted_c], -1, (0, 140, 255), 2)
        cx_px = int(round(ox + item["x"] * px_per_mm))
        cy_px = int(round(oy - item["y"] * px_per_mm))
        _put_label_box(
            vis, f"{item['w']:.1f}x{item['h']:.1f}", (cx_px - 28, cy_px), (80, 190, 255)
        )

    cv2.rectangle(vis, (0, 0), (w, 28), (30, 30, 30), -1)
    cv2.putText(
        vis,
        f"BBOX: {part_w_mm:.2f} x {part_h_mm:.2f} mm | Grid: 5/10 mm | {mode_label}",
        (10, 19),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.54,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return vis


def measure_photo(
    filepath: str,
    bbox_mm: tuple[float, float] = None,
    width_mm: float = None,
    min_area_mm2: float = 8.0,
    no_deskew: bool = False,
) -> tuple[str, str]:
    """Выполняет калибровку, выравнивание и замер одной фотографии детали."""
    abs_path = os.path.abspath(filepath)
    img = _imread_unicode(abs_path)

    roi, reproj_err_mm = _rectify_by_aruco(img)
    if roi is not None:
        px_per_mm = OUT_PX_PER_MM
        mode_label = f"ArUco 4x4 (err={reproj_err_mm:.2f} mm)"
    elif width_mm is not None:
        roi = img.copy()
        px_per_mm = None
        mode_label = f"Manual Width ({width_mm:.1f} mm)"
    elif bbox_mm is not None:
        roi = img.copy()
        px_per_mm = None
        mode_label = f"Manual BBox ({bbox_mm[0]:.1f}x{bbox_mm[1]:.1f} mm)"
    else:
        raise RuntimeError(
            f"[FAIL CALIBRATION] На фото '{os.path.basename(abs_path)}' не найдены все 4 ArUco-маркера (ID 0..3). "
            "Снимите деталь на листе input\\aruco_mat_A4.png либо укажите --width W или --bbox L B (в мм)."
        )

    mask = _segment_part(roi)
    main_idx, contours, hier = _find_main_contour(mask)
    if main_idx is None:
        raise RuntimeError(
            f"[FAIL SEGMENT] Не удалось выделить контур детали на '{os.path.basename(abs_path)}'!"
        )

    rot_deg = 0.0
    if not no_deskew:
        roi, mask, rot_deg = _deskew_roi(roi, mask, contours[main_idx])
        main_idx, contours, hier = _find_main_contour(mask)
        if main_idx is None:
            raise RuntimeError("[FAIL DESKEW] Потерян контур детали после поворота!")

    outer_cnt = contours[main_idx]
    bx, by, bw, bh = cv2.boundingRect(outer_cnt)

    if px_per_mm is None:
        if width_mm is not None:
            px_per_mm = bw / float(width_mm)
        else:
            exp_long, exp_short = max(bbox_mm), min(bbox_mm)
            px_long, px_short = max(bw, bh), min(bw, bh)
            px_per_mm = 0.5 * (px_long / exp_long + px_short / exp_short)

    part_w_mm = bw / px_per_mm
    part_h_mm = bh / px_per_mm
    origin_px = (bx + bw / 2.0, by + bh / 2.0)

    holes = []
    windows = []
    min_feat_area_px = float(min_area_mm2) * (px_per_mm**2)
    for idx, cnt in enumerate(contours):
        if hier[idx][3] != main_idx:
            continue
        area_px = cv2.contourArea(cnt)
        if area_px < min_feat_area_px:
            continue
        perim_px = cv2.arcLength(cnt, True)
        if perim_px <= 1e-6:
            continue
        circ = 4.0 * math.pi * area_px / (perim_px**2)
        fx, fy, fw, fh = cv2.boundingRect(cnt)
        cx_mm = (fx + fw / 2.0 - origin_px[0]) / px_per_mm
        cy_mm = (origin_px[1] - (fy + fh / 2.0)) / px_per_mm
        w_mm = fw / px_per_mm
        h_mm = fh / px_per_mm
        area_mm2 = area_px / (px_per_mm**2)

        if circ > 0.80 and abs(w_mm - h_mm) / max(w_mm, h_mm) < 0.15:
            d_eq = 2.0 * math.sqrt(area_mm2 / math.pi)
            holes.append(
                {"x": cx_mm, "y": cy_mm, "d": d_eq, "circ": circ, "area": area_mm2}
            )
        else:
            windows.append(
                {
                    "x": cx_mm,
                    "y": cy_mm,
                    "w": w_mm,
                    "h": h_mm,
                    "area": area_mm2,
                    "cnt": cnt,
                }
            )

    holes.sort(key=lambda d: (-round(d["y"], 1), round(d["x"], 1)))
    windows.sort(key=lambda d: (-round(d["y"], 1), round(d["x"], 1)))

    pad_px = int(round(15.0 * px_per_mm))
    rh, rw = roi.shape[:2]
    cx1 = max(0, bx - pad_px)
    cy1 = max(0, by - pad_px)
    cx2 = min(rw, bx + bw + pad_px)
    cy2 = min(rh, by + bh + pad_px)
    crop = roi[cy1:cy2, cx1:cx2]

    scale_vis = min(1.0, 1400.0 / max(crop.shape[:2]))
    if scale_vis < 0.99:
        crop = cv2.resize(
            crop,
            (int(crop.shape[1] * scale_vis), int(crop.shape[0] * scale_vis)),
            interpolation=cv2.INTER_AREA,
        )
        vis_ppm = px_per_mm * scale_vis
        vis_origin = (
            (origin_px[0] - cx1) * scale_vis,
            (origin_px[1] - cy1) * scale_vis,
        )
        vis_outer = ((outer_cnt - np.array([[[cx1, cy1]]])) * scale_vis).astype(
            np.int32
        )
        vis_windows = [
            {
                **item,
                "cnt": ((item["cnt"] - np.array([[[cx1, cy1]]])) * scale_vis).astype(
                    np.int32
                ),
            }
            for item in windows
        ]
        vis_offset = (0, 0)
    else:
        vis_ppm = px_per_mm
        vis_origin = origin_px
        vis_outer = outer_cnt
        vis_windows = windows
        vis_offset = (cx1, cy1)

    grid_img = _draw_grid_overlay(
        crop,
        vis_ppm,
        vis_origin,
        vis_outer,
        vis_offset,
        holes,
        vis_windows,
        part_w_mm,
        part_h_mm,
        mode_label,
    )

    stem = os.path.splitext(abs_path)[0]
    out_png = f"{stem}_rectified_grid.png"
    out_md = f"{stem}_photo_blueprint.md"
    _imwrite_unicode(out_png, grid_img)

    md = [
        f"# Инженерный замер по фотографии: `{os.path.basename(abs_path)}`",
        f"- **Режим калибровки:** `{mode_label}`",
        f"- **Выравнивание поворота (deskew):** `{rot_deg:+.2f}°`",
        f"- **Габариты контура (DX × DY):** **`{part_w_mm:.2f} × {part_h_mm:.2f}` мм**",
        f"- **Начало координат `(0, 0)`:** центр габаритного прямоугольника детали (`+X` вправо, `+Y` вверх)",
        f"- **Визуальная сетка для VLM-анализа:** `{os.path.basename(out_png)}` (шаг сетки `5 / 10` мм)\n",
    ]

    md.append("## 1. Обнаруженные круглые отверстия")
    if holes:
        md.append("| # | Центр X (мм) | Центр Y (мм) | Диаметр D (мм) | Круглость |")
        md.append("| :--- | :---: | :---: | :---: | :---: |")
        for idx, h_item in enumerate(holes, 1):
            md.append(
                f"| {idx} | `{h_item['x']:+.2f}` | `{h_item['y']:+.2f}` | **`{h_item['d']:.2f}`** | {h_item['circ']:.2f} |"
            )
    else:
        md.append("_Круглые сквозные отверстия на контрастном фоне не обнаружены._")

    md.append("\n## 2. Обнаруженные внутренние окна / пазы / карманы")
    if windows:
        md.append(
            "| # | Центр X (мм) | Центр Y (мм) | Ширина W (мм) | Высота H (мм) | Площадь (мм²) |"
        )
        md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for idx, w_item in enumerate(windows, 1):
            md.append(
                f"| {idx} | `{w_item['x']:+.2f}` | `{w_item['y']:+.2f}` | **`{w_item['w']:.2f}`** | **`{w_item['h']:.2f}`** | {w_item['area']:.1f} |"
            )
    else:
        md.append("_Внутренние сквозные окна/пазы не обнаружены._")

    md.append(
        "\n> **Примечание для агента:** обязательно открой `*_rectified_grid.png` через `Read` — "
        "по миллиметровой сетке сверь размеры глухих карманов, выступов и элементов, "
        "которые не дали сквозного контраста при бинаризации."
    )

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(
        f"[OK PHOTO] {os.path.basename(abs_path)} -> "
        f"{part_w_mm:.2f} x {part_h_mm:.2f} мм | отверстий={len(holes)}, окон={len(windows)}"
    )
    print(f"  ├── {out_png}")
    print(f"  └── {out_md}")
    return out_png, out_md


def main():
    parser = argparse.ArgumentParser(
        description="Выравнивание и замер фотографий деталей (ArUco-лист, --width W или --bbox L B)."
    )
    parser.add_argument(
        "target", help="Путь к фото или папке с фотографиями (input\\...)"
    )
    parser.add_argument(
        "--width",
        type=float,
        default=None,
        help="Известная горизонтальная ширина детали в мм (режим без ArUco-листа)",
    )
    parser.add_argument(
        "--bbox",
        nargs=2,
        type=float,
        metavar=("L", "B"),
        default=None,
        help="Габариты детали L B в мм (резервный режим без ArUco-листа)",
    )
    parser.add_argument(
        "--min-area",
        type=float,
        default=8.0,
        help="Минимальная площадь внутренних отверстий/окон в мм² (отсечка бликов, по умолч. 8.0)",
    )
    parser.add_argument(
        "--no-deskew",
        action="store_true",
        help="Не доворачивать деталь автоматически по минимальному прямоугольнику",
    )
    args = parser.parse_args()

    if os.path.isdir(args.target):
        files = [
            p
            for p in sorted(glob.glob(os.path.join(args.target, "*")))
            if os.path.splitext(p)[1].lower() in IMAGE_EXTS
            and not p.lower().endswith("_rectified_grid.png")
            and os.path.basename(p).lower() != "aruco_mat_a4.png"
        ]
    else:
        files = [args.target]

    if not files:
        print(f"[WARN] Не найдено изображений в: {args.target}")
        sys.exit(1)

    bbox_tuple = tuple(args.bbox) if args.bbox else None
    for fpath in files:
        measure_photo(
            fpath,
            bbox_mm=bbox_tuple,
            width_mm=args.width,
            min_area_mm2=args.min_area,
            no_deskew=args.no_deskew,
        )


if __name__ == "__main__":
    main()