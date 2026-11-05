# build_die_plate_ref.py — Параметрическая нижняя плита штампа (по эталону example/die_plate/die_plate_example.m3d)
# Геометрия идентична эталону: ZX basis, Y-extrude, 4 holes at corners, fillets, chamfers
from kompas_core import DT_NORMAL, DT_REVERSE, STYLE_MAIN, KompasPart
import math


def build_die_plate():
    part = KompasPart(name="Нижняя плита штампа", visible=True)

    # ------------------------------------------------------------------
    # 1. Таблица пользовательских переменных конструктора (ТОЧНО по эталону)
    # ------------------------------------------------------------------
    l = 160.0   # Длина
    b = 120.0   # Ширина
    h = 25.0    # Высота (толщина)
    lo = 60.0   # Длина провального окна
    bo = 40.0   # Ширина провального окна
    dk = 20.0   # Диаметр отверстий под направляющие колонки
    lk = 120.0  # Межосевое расстояние колонок по длине
    bk = 80.0   # Межосевое расстояние колонок по ширине
    ro = 5.0    # Скругление провального окна
    f = 6.0     # Фаски углов плиты
    fo = 1.0    # Заходные фаски отверстий направляющих

    part.create_variables_from_dict({
        "l": (l, "Длина"),
        "b": (b, "Ширина"),
        "h": (h, "Высота"),
        "lo": (lo, "Длина провального окна"),
        "bo": (bo, "Ширина провального окна"),
        "dk": (dk, "Диаметр отверстий под направляющие колонки"),
        "lk": (lk, "Межосевое расстояние колонок по длине"),
        "bk": (bk, "Межосевое расстояние колонок по ширине"),
        "ro": (ro, "Скругление провального окна"),
        "f": (f, "Фаски углов плиты"),
        "fo": (fo, "Заходные фаски отверстий направляющих"),
    })

    # ------------------------------------------------------------------
    # Шаг 1-2: Базовая плита — прямоугольник l x b на плоскости ZX,
    # выдавливание на высоту h (вдоль Y)
    # В плоскости ZX: ось X — длина, ось Z — ширина
    # Центр в (0,0) -> углы: X=±l/2, Z=±b/2
    # ------------------------------------------------------------------
    sk1 = part.create_sketch(
        "zx",
        lambda sk: (
            sk.rect(0, 0, l, b, centered=True),
            # Линейные размеры: по X (длина l) и по Z (ширина b)
            sk.dim_hor(b / 2.0 + 10.0, -l / 2.0, l / 2.0, var_name="l", y_pts=b / 2.0),
            sk.dim_ver(l / 2.0 + 10.0, -b / 2.0, b / 2.0, var_name="b", x_pts=l / 2.0),
        ),
    )
    # Выдавливание из ZX вдоль Y (DT_NORMAL из ZX -> +Y)
    base_extrude = part.extrude(sk1, depth=h, direction=DT_NORMAL, expr="h")

    # ------------------------------------------------------------------
    # Шаг 3-4: Провальное окно lo x bo в центре верхней грани (Y = h), сквозной вырез
    # ------------------------------------------------------------------
    face_top = part.get_planar_face_at(axis="y", coord=h)
    sk2 = part.create_sketch_on_face(
        face_top,
        lambda sk: (
            sk.rect(0, 0, lo, bo, centered=True),
            sk.dim_hor(bo / 2.0 + 10.0, -lo / 2.0, lo / 2.0, var_name="lo", y_pts=bo / 2.0),
            sk.dim_ver(lo / 2.0 + 10.0, -bo / 2.0, bo / 2.0, var_name="bo", x_pts=lo / 2.0),
        ),
    )
    cut_window = part.cut(sk2, depth=h, direction=DT_NORMAL, expr="h", through_all=True)

    # ------------------------------------------------------------------
    # Шаг 5-8: 4 отверстия колонок dk в углах (±lk/2, ±bk/2) на верхней грани
    # Создаём 4 отдельных выреза с полной параметризацией (как в эталоне с point pattern)
    # Позиции: (-lk/2, bk/2), (lk/2, bk/2), (lk/2, -bk/2), (-lk/2, -bk/2)
    # ------------------------------------------------------------------
    hole_positions = [
        (-lk / 2.0,  bk / 2.0),   # лево-верх
        ( lk / 2.0,  bk / 2.0),   # право-верх
        ( lk / 2.0, -bk / 2.0),   # право-низ
        (-lk / 2.0, -bk / 2.0),   # лево-низ
    ]

    cut_holes = []
    for i, (hx, hz) in enumerate(hole_positions):
        sk_hole = part.create_sketch_on_face(
            face_top,
            lambda sk, hx=hx, hz=hz: (
                sk.circle(hx, hz, dk / 2.0, style=STYLE_MAIN),
                # Размеры позиционирования от центра (0,0)
                sk.dim_hor(hz + 10.0, min(0, hx), max(0, hx), var_name=f"lk/2_{i+1}", y_pts=hz),
                sk.dim_ver(hx - 10.0, min(0, hz), max(0, hz), var_name=f"bk/2_{i+1}", x_pts=hx),
                sk.dim_diam(hx, hz, dk / 2.0, var_name="dk"),
            ),
        )
        cut_hole = part.cut(sk_hole, depth=h, direction=DT_NORMAL, expr="h", through_all=True)
        cut_holes.append(cut_hole)

    # ------------------------------------------------------------------
    # Шаг 9: Скругление углов провального окна (радиус ro)
    # Находим 4 вертикальных ребра углов провального окна
    # ------------------------------------------------------------------
    window_edges = part.get_window_vertical_edges(lo, bo)
    if len(window_edges) >= 4:
        part.fillet(window_edges[:4], radius=ro, expr="ro")

    # ------------------------------------------------------------------
    # Шаг 10: Фаски углов плиты (расстояние f, 45°)
    # 4 верхних вертикальных ребра внешнего контура
    # ------------------------------------------------------------------
    outer_edges = part.get_plate_corner_edges(l, b)
    if len(outer_edges) >= 4:
        part.chamfer(outer_edges[:4], distance=f, angle=45.0, expr="f")

    # ------------------------------------------------------------------
    # Шаг 11: Заходные фаски отверстий (расстояние fo, 45°)
    # 4 круговые ребра входов в отверстия
    # ------------------------------------------------------------------
    hole_top_edges = part.get_hole_entrance_edges(face_top, dk, lk, bk)
    if hole_top_edges:
        part.chamfer(hole_top_edges, distance=fo, angle=45.0, expr="fo")

    # ------------------------------------------------------------------
    # Тройной контур самопроверки
    # Габариты эталона: 160 x 25 x 120 (X x Y x Z)
    # ------------------------------------------------------------------
    part.rebuild()
    part.assert_bbox(l, h, b, tol=0.1)
    part.save_screenshot("output/die_plate_ref.png")
    part.save("output/die_plate_ref.m3d")
    part.close()


if __name__ == "__main__":
    build_die_plate()