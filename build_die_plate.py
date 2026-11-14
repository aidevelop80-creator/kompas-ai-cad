# build_die_plate.py — Параметрическая нижняя плита штампа
# Эталон: example/die_plate/die_plate_example.m3d
# Запуск: .venv\Scripts\python.exe build_die_plate.py

from kompas_core import (
    DT_NORMAL,
    PLANE_XZ,
    STYLE_MAIN,
    KompasPart,
)

# ========================= КОНСТРУКТОРСКИЕ ПАРАМЕТРЫ =========================
VARIABLES = {
    "l": (160.0, "Длина"),
    "b": (120.0, "Ширина"),
    "h": (25.0, "Высота"),
    "lo": (60.0, "Длина провального окна"),
    "bo": (40.0, "Ширина провального окна"),
    "dk": (20.0, "Диаметр отверстий под направляющие колонки"),
    "lk": (120.0, "Межосевое расстояние колонок по длине"),
    "bk": (80.0, "Межосевое расстояние колонок по ширине"),
    "ro": (5.0, "Скругление провального окна"),
    "f": (6.0, "Фаски углов плиты"),
    "fo": (1.0, "Заходные фаски отверстий направляющих"),
}

EXPECTED_VOLUME = 387060.87  # мм³ (из die_plate_example_blueprint.md)


def build_die_plate(part: KompasPart):
    """Построение нижней плиты штампа по эталонной модели die_plate_example.m3d."""
    l = VARIABLES["l"][0]
    b = VARIABLES["b"][0]
    h = VARIABLES["h"][0]
    lo = VARIABLES["lo"][0]
    bo = VARIABLES["bo"][0]
    dk = VARIABLES["dk"][0]
    lk = VARIABLES["lk"][0]
    bk = VARIABLES["bk"][0]
    ro = VARIABLES["ro"][0]
    f = VARIABLES["f"][0]
    fo = VARIABLES["fo"][0]

    # --- Шаг 1-2: Базовая плита (l x b x h) на плоскости ZX ---
    def sketch_plate(b_sk):
        b_sk.rect(0.0, 0.0, l, b, centered=True, style=STYLE_MAIN)
        b_sk.dim_hor(
            y_line=b / 2.0 + 12.0, x1=-l / 2.0, x2=l / 2.0, var_name="l", y_pts=b / 2.0
        )
        b_sk.dim_ver(
            x_line=-l / 2.0 - 12.0,
            y1=-b / 2.0,
            y2=b / 2.0,
            var_name="b",
            x_pts=-l / 2.0,
        )
        b_sk.center_on_origin(l, b)

    sk1 = part.create_sketch(plane=PLANE_XZ, draw_fn=sketch_plate)
    part.extrude(sk1, depth=h, direction=DT_NORMAL, expr="h")

    # --- Шаг 3-4: Сквозное провальное окно (lo x bo) ---
    face_top = part.get_planar_face_at(axis="y", coord=h, mode="max")

    def sketch_window(b_sk):
        b_sk.rect(0.0, 0.0, lo, bo, centered=True, style=STYLE_MAIN)
        b_sk.dim_hor(
            y_line=bo / 2.0 + 10.0,
            x1=-lo / 2.0,
            x2=lo / 2.0,
            var_name="lo",
            y_pts=bo / 2.0,
        )
        b_sk.dim_ver(
            x_line=-lo / 2.0 - 10.0,
            y1=-bo / 2.0,
            y2=bo / 2.0,
            var_name="bo",
            x_pts=-lo / 2.0,
        )
        b_sk.center_on_origin(lo, bo)

    sk2 = part.create_sketch_on_face(face_top, draw_fn=sketch_window)
    part.cut(sk2, through_all=True)

    # --- Шаг 5-6: Первое отверстие под направляющую колонку ---
    face_top = part.get_planar_face_at(axis="y", coord=h, mode="max")
    cx, cy = -lk / 2.0, bk / 2.0

    def sketch_first_hole(b_sk):
        b_sk.circle(cx, cy, dk / 2.0, style=STYLE_MAIN).dim_diam(
            cx, cy, dk / 2.0, var_name="dk"
        )
        b_sk.dim_hor(y_line=cy + 20.0, x1=cx, x2=0.0, var_name="lk/2", y1=cy, y2=0.0)
        b_sk.dim_ver(x_line=cx - 20.0, y1=0.0, y2=cy, var_name="bk/2", x1=0.0, x2=cx)

    sk3 = part.create_sketch_on_face(face_top, draw_fn=sketch_first_hole)
    cut_hole1 = part.cut(sk3, through_all=True)

    # --- Шаг 7: Заходные фаски fo на верхнем и нижнем торцах первого отверстия ---
    face_top = part.get_planar_face_at(axis="y", coord=h, mode="max")
    face_bot = part.get_planar_face_at(axis="y", coord=0.0, mode="min")
    hole_edges = part.get_hole_entrance_edges(
        face_top, dk, lk, bk
    ) + part.get_hole_entrance_edges(face_bot, dk, lk, bk)
    if len(hole_edges) != 2:
        raise RuntimeError(
            f"[FAIL CHAMFER EDGES] Ожидалось 2 входных ребра первого отверстия, найдено {len(hole_edges)}!"
        )
    chamfer_hole = part.chamfer(hole_edges, distance=fo, expr="fo")

    # --- Шаг 8-9: Эскиз с 3 точками и Массив по точкам ---
    def sketch_pattern_points(b_sk):
        p0 = (lk / 2.0, bk / 2.0)
        p1 = (lk / 2.0, -bk / 2.0)
        p2 = (-lk / 2.0, -bk / 2.0)
        b_sk.point(*p0, style=STYLE_MAIN)
        b_sk.point(*p1, style=STYLE_MAIN)
        b_sk.point(*p2, style=STYLE_MAIN)
        # Ровно 3 точки и 2 размера (bk, lk), без лишней точки в (0,0)
        b_sk.fix_point(*p0)
        b_sk.align_v(p0, p1)
        b_sk.dim_ver(
            x_line=lk / 2.0 + 15.0,
            y1=p1[1],
            y2=p0[1],
            var_name="bk",
            x1=p1[0],
            x2=p0[0],
        )
        b_sk.align_h(p2, p1)
        b_sk.dim_hor(
            y_line=-bk / 2.0 - 15.0,
            x1=p2[0],
            x2=p1[0],
            var_name="lk",
            y1=p2[1],
            y2=p1[1],
        )

    sk4 = part.create_sketch_on_face(face_top, draw_fn=sketch_pattern_points)
    part.point_pattern(features=[cut_hole1, chamfer_hole], driven_obj=sk4)

    # --- Шаг 10: Скругление ro углов провального окна ---
    win_edges = part.get_window_vertical_edges(lo, bo)
    if len(win_edges) != 4:
        raise RuntimeError(
            f"[FAIL FILLET EDGES] Ожидалось 4 ребра окна, найдено {len(win_edges)}!"
        )
    part.fillet(win_edges, radius=ro, expr="ro")

    # --- Шаг 11: Фаска f углов плиты ---
    plate_edges = part.get_plate_corner_edges(l, b)
    if len(plate_edges) != 4:
        raise RuntimeError(
            f"[FAIL CHAMFER EDGES] Ожидалось 4 угловых ребра плиты, найдено {len(plate_edges)}!"
        )
    part.chamfer(plate_edges, distance=f, expr="f")

    # --- Финальная валидация габаритов и объёма ---
    part.assert_bbox(exp_x=l, exp_y=h, exp_z=b, tol=0.1)
    vol = part.volume()
    if abs(vol - EXPECTED_VOLUME) > 0.5:
        raise ValueError(
            f"[FAIL VOLUME] Объём {vol:.2f} мм³ отличается от эталона {EXPECTED_VOLUME:.2f} мм³!"
        )
    print(f"[OK VOLUME] Объём точно соответствует эталону: {vol:.2f} мм³")
    return part


if __name__ == "__main__":
    part = KompasPart(name="DiePlate", visible=True)
    part.create_variables_from_dict(VARIABLES)
    try:
        build_die_plate(part)
        part.save("output/DiePlate_160x120x25.m3d")
        part.save_screenshot("output/DiePlate_160x120x25.png")
        print("[SUCCESS] Деталь DiePlate_160x120x25 построена и провалидирована")
    except Exception:
        part.close()
        raise
