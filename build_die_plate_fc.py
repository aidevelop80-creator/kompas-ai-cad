# build_die_plate_fc.py — Нижняя плита штампа во FreeCAD 1.1
# Эталон: example/die_plate/die_plate_example.m3d (160x25x120 мм, V=387060.87 мм³)
# Запуск: .venv\Scripts\python.exe run_freecad.py build_die_plate_fc.py output/DiePlate_160x120x25.FCStd

from freecad_core import (
    DT_NORMAL,
    PLANE_XZ,
    STYLE_MAIN,
    FreeCadPart,
)

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

EXPECTED_VOLUME = 387060.87


def build_die_plate(part: FreeCadPart):
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

    # Шаг 1-2: Базовая плита l x b x h на XZ
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

    # Шаг 3-4: Сквозное провальное окно lo x bo
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

    # Шаг 5-6: 4 симметричных отверстия под направляющие колонки
    face_top = part.get_planar_face_at(axis="y", coord=h, mode="max")

    def sketch_holes(b_sk):
        c0 = (-lk / 2.0, bk / 2.0)
        c1 = (lk / 2.0, bk / 2.0)
        c2 = (-lk / 2.0, -bk / 2.0)
        c3 = (lk / 2.0, -bk / 2.0)
        for c in (c0, c1, c2, c3):
            b_sk.circle(c[0], c[1], dk / 2.0, style=STYLE_MAIN)
        b_sk.dim_diam(c0[0], c0[1], dk / 2.0, var_name="dk")
        b_sk.equal_radius(c0, c1)
        b_sk.equal_radius(c0, c2)
        b_sk.equal_radius(c0, c3)
        b_sk.symmetric_pts(c0, c1, axis="y")
        b_sk.symmetric_pts(c2, c3, axis="y")
        b_sk.symmetric_pts(c0, c2, axis="x")
        b_sk.dim_hor(
            y_line=bk / 2.0 + 15.0, x1=c0[0], x2=c1[0], var_name="lk", y_pts=c0[1]
        )
        b_sk.dim_ver(
            x_line=lk / 2.0 + 15.0,
            y1=c2[1],
            y2=c0[1],
            var_name="bk",
            x1=c2[0],
            x2=c0[0],
        )

    sk3 = part.create_sketch_on_face(face_top, draw_fn=sketch_holes)
    part.cut(sk3, through_all=True)

    # Шаг 7: Заходные фаски fo на обоих торцах всех 4 отверстий (8 рёбер)
    face_top = part.get_planar_face_at(axis="y", coord=h, mode="max")
    face_bot = part.get_planar_face_at(axis="y", coord=0.0, mode="min")
    _, top_edges = part.get_hole_entrance_edges(face_top, dk, lk, bk)
    _, bot_edges = part.get_hole_entrance_edges(face_bot, dk, lk, bk)
    hole_edges = top_edges + bot_edges
    if len(hole_edges) != 8:
        raise RuntimeError(
            f"[FAIL CHAMFER EDGES] Ожидалось 8 рёбер отверстий, найдено {len(hole_edges)}!"
        )
    part.chamfer(hole_edges, distance=fo, expr="fo")

    # Шаг 8: Скругление ro углов провального окна (4 ребра)
    _, win_edges = part.get_window_vertical_edges(lo, bo)
    if len(win_edges) != 4:
        raise RuntimeError(
            f"[FAIL FILLET EDGES] Ожидалось 4 ребра окна, найдено {len(win_edges)}!"
        )
    part.fillet(win_edges, radius=ro, expr="ro")

    # Шаг 9: Фаска f углов плиты (4 ребра)
    _, plate_edges = part.get_plate_corner_edges(l, b)
    if len(plate_edges) != 4:
        raise RuntimeError(
            f"[FAIL CHAMFER EDGES] Ожидалось 4 угловых ребра плиты, найдено {len(plate_edges)}!"
        )
    part.chamfer(plate_edges, distance=f, expr="f")

    # Валидация
    part.assert_bbox(exp_x=l, exp_y=h, exp_z=b, tol=0.1)
    vol = part.volume()
    if abs(vol - EXPECTED_VOLUME) > 0.5:
        raise ValueError(f"[FAIL VOLUME] Объём {vol:.2f} != {EXPECTED_VOLUME:.2f} мм³!")
    print(f"[OK VOLUME FREECAD] Объём совпал с эталоном: {vol:.2f} мм³")
    return part


_part = FreeCadPart(name="DiePlate_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_die_plate(_part)
    _part.save("output/DiePlate_160x120x25.FCStd")
    print("[SUCCESS FREECAD] output/DiePlate_160x120x25.FCStd и .stl сохранены")
finally:
    _part.close()
