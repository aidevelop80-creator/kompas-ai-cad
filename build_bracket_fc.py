# build_bracket_fc.py — Параметрический кронштейн опоры Bracket_120x80x70 во FreeCAD 1.1+
# Запуск: .venv\Scripts\python.exe run_freecad.py build_bracket_fc.py output\Bracket_120x80x70.FCStd

from freecad_core import (
    DT_NORMAL,
    DT_REVERSE,
    DT_BOTH,
    PLANE_XY,
    PLANE_YZ,
    STYLE_MAIN,
    STYLE_AXIS,
    FreeCadPart,
)

# ========================= КОНСТРУКТОРСКИЕ ПАРАМЕТРЫ =========================
VARIABLES = {
    "L": (120.0, "Длина основания кронштейна (по оси X, симметрично ±60)"),
    "B": (80.0, "Ширина основания кронштейна (по оси Y, симметрично ±40)"),
    "H": (70.0, "Общая высота кронштейна (по оси Z: 0..70)"),
    "s": (12.0, "Толщина основания и вертикальной стойки"),
    "db": (40.0, "Наружный диаметр цилиндрической бобышки"),
    "lb": (12.0, "Вылет бобышки вперёд от внутренней грани стойки"),
    "hb": (44.0, "Высота оси бобышки от опорной плоскости"),
    "d0": (24.0, "Диаметр центрального сквозного отверстия в бобышке и стойке"),
    "tr": (10.0, "Толщина центрального ребра жёсткости"),
    "dm": (9.0, "Диаметр 4 крепёжных отверстий в основании"),
    "lx": (84.0, "Межосевое расстояние крепёжных отверстий по X (±42)"),
    "ly": (36.0, "Межосевое расстояние крепёжных отверстий по Y (центр Y=-8, отступы -26 и +10)"),
    "R": (6.0, "Радиус скругления двух передних вертикальных углов основания"),
}

EXPECTED_VOLUME = None  # type: float | None  # будет определено после первой сборки


def build_bracket(part: FreeCadPart):
    """Построение кронштейна опоры Bracket_120x80x70 во FreeCAD 1.1+."""
    L = VARIABLES["L"][0]
    B = VARIABLES["B"][0]
    H = VARIABLES["H"][0]
    s = VARIABLES["s"][0]
    db = VARIABLES["db"][0]
    lb = VARIABLES["lb"][0]
    hb = VARIABLES["hb"][0]
    d0 = VARIABLES["d0"][0]
    tr = VARIABLES["tr"][0]
    dm = VARIABLES["dm"][0]
    lx = VARIABLES["lx"][0]
    ly = VARIABLES["ly"][0]
    R = VARIABLES["R"][0]

    half_L = L / 2.0
    half_B = B / 2.0
    y_stand_inner = half_B - s  # +28.0
    y_boss_front = y_stand_inner - lb  # +16.0

    # --- Шаг 1: Основание — прямоугольник L x B на PLANE_XY, centred, Pad +Z на s ---
    def sketch_base(b):
        b.rect(0.0, 0.0, L, B, centered=True, style=STYLE_MAIN)
        b.dim_hor(y_line=half_B + 10.0, x1=-half_L, x2=half_L, var_name="L")
        b.dim_ver(x_line=-half_L - 10.0, y1=-half_B, y2=half_B, var_name="B")
        b.center_on_origin(L, B)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_base)
    part.extrude(sk1, depth=s, direction=DT_NORMAL, expr="s")

    # --- Шаг 2: Вертикальная стойка на грани Z=s, Y от +28 до +40 ---
    face_stand_base = part.get_planar_face_at(axis="z", coord=s)

    def sketch_stand(b):
        # Прямоугольник через rect (левый нижний угол, ширина, высота)
        b.rect(-half_L, y_stand_inner, L, s, centered=False, style=STYLE_MAIN)
        b.dim_hor(y_line=half_B + 5.0, x1=-half_L, x2=half_L, var_name="L")
        b.dim_ver(x_line=half_L + 5.0, y1=y_stand_inner, y2=half_B, var_name="s")
        # Позиционирование: левая сторона привязана к X=-half_L, нижняя к Y=y_stand_inner
        b.align_v((-half_L, y_stand_inner), (-half_L, 0.0))
        b.align_h((-half_L, y_stand_inner), (-half_L, 0.0))

    sk2 = part.create_sketch_on_face(face_stand_base, draw_fn=sketch_stand)
    part.extrude(sk2, depth=H - s, direction=DT_NORMAL, expr="H-s")

    # --- Шаг 3: Бобышка на глобальной плоскости XZ со смещением по Y ---
    # В FreeCAD нет offset_plane для XZ, используем create_sketch_on_face на грани стойки
    face_boss_base = part.get_planar_face_at(axis="y", coord=y_stand_inner)

    def sketch_boss(b):
        b.circle(0.0, hb, db / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, hb, db / 2.0, var_name="db")

    sk3 = part.create_sketch_on_face(face_boss_base, draw_fn=sketch_boss)
    part.extrude(sk3, depth=lb, direction=DT_REVERSE, expr="lb")

    # --- Шаг 4: Ребро жёсткости на плоскости PLANE_YZ ---
    # В FreeCAD Midplane (DT_BOTH) принимает полную толщину tr, а не tr/2!
    def sketch_rib(b):
        pts = [
            (-30.0, s),
            (y_stand_inner, 30.0),
            (y_stand_inner, s),
        ]
        b.polygon(pts, closed=True, style=STYLE_MAIN)

        # Горизонтальный катет = y_stand_inner - (-30) = 58, вертикальный = 30 - s = 18
        b.dim_hor(y_line=30.0 + 5.0, x1=-30.0, x2=y_stand_inner, var_name="B/2-s+30")
        b.dim_ver(x_line=y_stand_inner + 5.0, y1=s, y2=30.0, var_name="30-s")
        b.align_h((y_stand_inner, s), (y_stand_inner, 0.0))
        b.align_v((-30.0, s), (0.0, s))

    sk4 = part.create_sketch(plane=PLANE_YZ, draw_fn=sketch_rib)
    # ВАЖНО: В FreeCAD DT_BOTH = Midplane использует полную толщину tr!
    part.extrude(sk4, depth=tr, direction=DT_BOTH, expr="tr")

    # --- Шаг 5: Сквозное отверстие в бобышке и стойке ---
    face_hole = part.get_planar_face_at(axis="y", coord=y_boss_front)

    def sketch_through_hole(b):
        b.circle(0.0, hb, d0 / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, hb, d0 / 2.0, var_name="d0")

    sk5 = part.create_sketch_on_face(face_hole, draw_fn=sketch_through_hole)
    part.cut(sk5, through_all=True)

    # --- Шаг 6: 4 крепёжных отверстия в основании ---
    # Во FreeCAD: симметричный эскиз с equal_radius + расстояниями (DoF = 0)
    face_mount = part.get_planar_face_at(axis="z", coord=s)

    def sketch_mount_holes(b):
        # 4 отверстия: (±42, -26) и (±42, +10)
        b.circle(lx / 2.0, -26.0, dm / 2.0, style=STYLE_MAIN)
        b.circle(-lx / 2.0, -26.0, dm / 2.0, style=STYLE_MAIN)
        b.circle(lx / 2.0, 10.0, dm / 2.0, style=STYLE_MAIN)
        b.circle(-lx / 2.0, 10.0, dm / 2.0, style=STYLE_MAIN)

        # Равенство радиусов всех 4 отверстий
        b.equal_radius((lx / 2.0, -26.0), (-lx / 2.0, -26.0))
        b.equal_radius((lx / 2.0, -26.0), (lx / 2.0, 10.0))
        b.equal_radius((lx / 2.0, -26.0), (-lx / 2.0, 10.0))

        # Симметрия по X (ось X=0) для левых и правых пар
        b.symmetric_pts((lx / 2.0, -26.0), (-lx / 2.0, -26.0), "x")
        b.symmetric_pts((lx / 2.0, 10.0), (-lx / 2.0, 10.0), "x")
        # Симметрия по Y (ось Y=0) для верхних и нижних пар — но центр Y=-8, не 0!
        # Используем расстояния вместо симметрии относительно Y=-8
        # Равные вертикальные расстояния от центра Y=-8 до Y=-26 и Y=10 (оба = 18)
        # Но FreeCAD symmetric_pts только относительно осей 0. Используем расстояния:

        # Размеры: lx, ly, 26, 10
        b.dim_hor(y_line=-26.0 - 8.0, x1=-lx / 2.0, x2=lx / 2.0, var_name="lx")
        b.dim_ver(x_line=lx / 2.0 + 8.0, y1=-26.0, y2=10.0, var_name="ly")
        b.dim_ver(x_line=lx / 2.0 + 8.0, y1=0.0, y2=-26.0, var_name="26")
        b.dim_ver(x_line=lx / 2.0 + 8.0, y1=0.0, y2=10.0, var_name="10")
        # Радиус
        b.dim_diam(lx / 2.0, -26.0, dm / 2.0, var_name="dm")

    sk6 = part.create_sketch_on_face(face_mount, draw_fn=sketch_mount_holes)
    part.cut(sk6, through_all=True, direction=DT_REVERSE)

    # --- Шаг 7: Скругление двух передних вертикальных рёбер основания ---
    # Рёбра: X = ±half_L (±60), Y = -half_B (-40), Z: 0..s
    # Ищем вертикальные ребра в углах основания вручную
    tip = part.body.Tip
    front_edge_names = []
    for idx, edge in enumerate(tip.Shape.Edges):
        if len(edge.Vertexes) != 2:
            continue
        v1, v2 = edge.Vertexes[0].Point, edge.Vertexes[1].Point
        # Вертикальное ребро: X и Y совпадают, Z разные
        if abs(v1.x - v2.x) < 1e-3 and abs(v1.y - v2.y) < 1e-3 and abs(v1.z - v2.z) > 1e-3:
            mx, my = 0.5 * (v1.x + v2.x), 0.5 * (v1.y + v2.y)
            # Передний левый угол: X=-60, Y=-40; Передний правый: X=60, Y=-40
            if (abs(mx - half_L) < 0.5 and abs(my + half_B) < 0.5) or \
               (abs(mx + half_L) < 0.5 and abs(my + half_B) < 0.5):
                front_edge_names.append(f"Edge{idx + 1}")

    print(f"[DEBUG FILLET] front_edges = {front_edge_names}")

    if len(front_edge_names) != 2:
        raise RuntimeError(f"[FAIL FILLET] Ожидалось 2 передние ребра, найдено {len(front_edge_names)}: {front_edge_names}")

    part.fillet(front_edge_names, radius=R, expr="R")

    # --- Финальная валидация габаритов ---
    part.assert_bbox(exp_x=L, exp_y=B, exp_z=H, tol=0.1)
    vol = part.volume()
    print(f"[INFO VOLUME FREECAD] Итоговый объём кронштейна: {vol:.2f} мм³")
    return part


# ВАЖНО: FreeCADCmd.exe импортирует скрипт как модуль, поэтому вызываем напрямую
_part = FreeCadPart(name="Bracket_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_bracket(_part)
    _part.save("output/Bracket_120x80x70.FCStd")
    print("[SUCCESS FREECAD] output/Bracket_120x80x70.FCStd и .stl сохранены")
finally:
    _part.close()