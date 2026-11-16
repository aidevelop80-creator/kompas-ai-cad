# build_bracket.py — Параметрический кронштейн опоры Bracket_120x80x70 в КОМПАС-3D
# Запуск: .venv\Scripts\python.exe build_bracket.py

from kompas_core import (
    DT_NORMAL,
    DT_REVERSE,
    DT_BOTH,
    OBJ_FACE,
    PLANE_XY,
    PLANE_XZ,
    PLANE_YZ,
    STYLE_MAIN,
    STYLE_AXIS,
    KompasPart,
    _wrap,
)
from sdk_ref import kompas_api5_v16 as K5

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

EXPECTED_VOLUME = None  # type: float | None


def _find_vertical_edge(part: KompasPart, x_coord: float, y_coord: float, z_min: float = 0.0, z_max: float = 12.0):
    """Находит вертикальное ребро по заданным X, Y координатам в диапазоне Z."""
    part_ents = _wrap(K5.ksEntityCollection, part.part.EntityCollection(OBJ_FACE))
    for i in range(part_ents.GetCount()):
        ent = _wrap(K5.ksEntity, part_ents.GetByIndex(i))
        fdef = _wrap(K5.ksFaceDefinition, ent.GetDefinition())
        if not fdef or not fdef.IsPlanar():
            continue
        bbox = part._get_face_bbox(fdef)
        if not bbox:
            continue
        if (
            bbox[0] <= x_coord + 0.5 and bbox[3] >= x_coord - 0.5
            and bbox[1] <= y_coord + 0.5 and bbox[4] >= y_coord - 0.5
            and bbox[2] <= z_min + 0.5
            and bbox[5] >= z_max - 0.5
        ):
            loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
            if not loops:
                continue
            for li in range(loops.GetCount()):
                edges = _wrap(K5.ksEdgeCollection, _wrap(K5.ksLoop, loops.GetByIndex(li)).EdgeCollection())
                if not edges:
                    continue
                for j in range(edges.GetCount()):
                    ed = _wrap(K5.ksEdgeDefinition, edges.GetByIndex(j))
                    v1 = _wrap(K5.ksVertexDefinition, ed.GetVertex(True))
                    v2 = _wrap(K5.ksVertexDefinition, ed.GetVertex(False))
                    if not v1 or not v2:
                        continue
                    ok1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                    ok2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                    if not (ok1 and ok2):
                        continue
                    if abs(x1 - x2) < 0.1 and abs(y1 - y2) < 0.1 and abs(z1 - z2) > 1.0:
                        if abs(x1 - x_coord) < 0.5 and abs(y1 - y_coord) < 0.5:
                            return ed
    return None


def build_bracket(part: KompasPart):
    """Построение кронштейна опоры Bracket_120x80x70.

    Топология: сплошной блок L×B×H → вырез фасада → бобышка → отверстие → ребро → крепёжи → скругления.
    """
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
    y_stand_inner = half_B - s      # +28.0 — внутренняя грань стойки (начало стойки)
    y_boss_front = y_stand_inner - lb  # +16.0 — передний торец бобышки

    # --- Шаг 1: Сплошной блок L × B × H на PLANE_XY ---
    def sketch_block(b):
        b.rect(0.0, 0.0, L, B, centered=True, style=STYLE_MAIN)
        b.dim_hor(y_line=half_B + 10.0, x1=-half_L, x2=half_L, var_name="L")
        b.dim_ver(x_line=-half_L - 10.0, y1=-half_B, y2=half_B, var_name="B")
        b.center_on_origin(L, B)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_block)
    part.extrude(sk1, depth=H, direction=DT_NORMAL, expr="H")

    # --- Шаг 2: Вырез фасада (удаляем материал перед стойкой: Y=-40..+28, Z=12..70) ---
    plane_front_cut = part.create_offset_plane("xz", y_stand_inner, expr="B/2-s")

    def sketch_front_cut(b):
        b.rect(0.0, s, L, H - s, centered=True, style=STYLE_MAIN)
        b.dim_hor(y_line=(s + H) / 2.0 + 10.0, x1=-half_L, x2=half_L, var_name="L")
        b.dim_ver(x_line=half_L + 10.0, y1=s, y2=H, var_name="H-s")
        b.center_on_origin(L, H - s)

    sk2 = part.create_sketch(plane=plane_front_cut, draw_fn=sketch_front_cut)
    part.cut(sk2, through_all=True, direction=DT_REVERSE)

    # --- Шаг 3: Бобышка на передней грани стойки (Y = y_stand_inner = +28) ---
    plane_boss = part.create_offset_plane("xz", y_stand_inner, expr="B/2-s")

    def sketch_boss(b):
        b.circle(0.0, hb, db / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, hb, db / 2.0, var_name="db")
        b.align_h((0.0, hb), (0.0, 0.0))
        b.dim_ver(x_line=5.0, y1=0.0, y2=hb, var_name="hb")

    sk3 = part.create_sketch(plane=plane_boss, draw_fn=sketch_boss)
    part.boss_extrude(sk3, depth=lb, direction=DT_REVERSE, expr="lb")

    # --- Шаг 4: Сквозное отверстие в бобышке и стойке ---
    plane_hole = part.create_offset_plane("xz", y_boss_front, expr="B/2-s-lb")

    def sketch_through_hole(b):
        b.circle(0.0, hb, d0 / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, hb, d0 / 2.0, var_name="d0")
        b.align_h((0.0, hb), (0.0, 0.0))
        b.dim_ver(x_line=5.0, y1=0.0, y2=hb, var_name="hb")

    sk4 = part.create_sketch(plane=plane_hole, draw_fn=sketch_through_hole)
    part.cut(sk4, through_all=True)

    # --- Шаг 5: Ребро жёсткости — создаём через выдавливание на PLANE_XZ и поворот ---
    # В KOMPAS проще: создаём ребро как выдавливание на PLANE_XZ (профиль в XZ),
    # а затем поворачиваем/позиционируем. Но KOMPAS не имеет простого поворота тел.
    # Альтернатива: создаём ребро через boss_extrude на PLANE_YZ с правильными координатами.
    # На PLANE_YZ: 2D X → 3D Y, 2D Y → 3D Z.
    # Треугольник в (Y, Z): (-30, s) -> (y_stand_inner, 30) -> (y_stand_inner, s).
    # Используем смещённую плоскость X = -tr/2 и DT_NORMAL выдавливание на tr.

    plane_rib = part.create_offset_plane("yz", -tr / 2.0, expr="tr/2")

    def sketch_rib(b):
        pts = [
            (-30.0, s),
            (y_stand_inner, 30.0),
            (y_stand_inner, s),
        ]
        b.polygon(pts, closed=True, style=STYLE_MAIN)
        b.dim_hor(y_line=30.0 + 5.0, x1=-30.0, x2=y_stand_inner, var_name="B/2-s+30")
        b.dim_ver(x_line=y_stand_inner + 5.0, y1=s, y2=30.0, var_name="30-s")
        b.align_h((y_stand_inner, s), (y_stand_inner, 0.0))
        b.align_v((-30.0, s), (0.0, s))

    sk5 = part.create_sketch(plane=plane_rib, draw_fn=sketch_rib)
    part.boss_extrude(sk5, depth=tr, direction=DT_NORMAL, expr="tr")
    # Debug bbox после ребра
    dx, dy, dz = part.bbox()
    print(f"[DEBUG BBOX after rib] dx={dx:.2f}, dy={dy:.2f}, dz={dz:.2f}")

    # --- Шаг 6: 4 крепёжных отверстия в основании (сквозные) ---
    plane_mount = part.create_offset_plane("xy", s, expr="s")

    def sketch_base_mount_hole(b):
        b.circle(lx / 2.0, -26.0, dm / 2.0, style=STYLE_MAIN)
        b.dim_diam(lx / 2.0, -26.0, dm / 2.0, var_name="dm")
        b.dim_hor(y_line=-26.0 - 8.0, x1=0.0, x2=lx / 2.0, var_name="lx/2")
        b.dim_ver(x_line=lx / 2.0 + 8.0, y1=0.0, y2=-26.0, var_name="26")
        b.align_h((lx / 2.0, -26.0), (0.0, 0.0))

    sk6 = part.create_sketch(plane=plane_mount, draw_fn=sketch_base_mount_hole)
    cut_mount = part.cut(sk6, through_all=True)

    # Эскиз управляющих точек для point_pattern (4 точки)
    def sketch_mount_points(b):
        b.point(lx / 2.0, -26.0, style=STYLE_MAIN)
        b.point(-lx / 2.0, -26.0, style=STYLE_MAIN)
        b.point(lx / 2.0, 10.0, style=STYLE_MAIN)
        b.point(-lx / 2.0, 10.0, style=STYLE_MAIN)
        b.fix_point(lx / 2.0, -26.0)
        b.align_v((lx / 2.0, -26.0), (lx / 2.0, 10.0))
        b.align_v((-lx / 2.0, -26.0), (-lx / 2.0, 10.0))
        b.align_h((lx / 2.0, -26.0), (-lx / 2.0, -26.0))
        b.align_h((lx / 2.0, 10.0), (-lx / 2.0, 10.0))
        b.dim_hor(y_line=-26.0 - 8.0, x1=-lx / 2.0, x2=lx / 2.0, var_name="lx")
        b.dim_ver(x_line=lx / 2.0 + 8.0, y1=-26.0, y2=10.0, var_name="ly")
        b.dim_ver(x_line=lx / 2.0 + 8.0, y1=0.0, y2=-26.0, var_name="26")
        b.dim_ver(x_line=lx / 2.0 + 8.0, y1=0.0, y2=10.0, var_name="10")

    sk_points = part.create_sketch(plane=plane_mount, draw_fn=sketch_mount_points)
    part.point_pattern(features=[cut_mount], driven_obj=sk_points)

    # --- Шаг 7: Скругление двух передних вертикальных рёбер основания ---
    edge_left = _find_vertical_edge(part, x_coord=-half_L, y_coord=-half_B, z_min=0.0, z_max=s)
    edge_right = _find_vertical_edge(part, x_coord=half_L, y_coord=-half_B, z_min=0.0, z_max=s)

    if not edge_left or not edge_right:
        raise RuntimeError("[FAIL FILLET] Не найдены передние вертикальные ребра для скругления!")

    part.fillet([edge_left, edge_right], radius=R, expr="R")

    # --- Финальная валидация габаритов ---
    part.assert_bbox(exp_x=L, exp_y=B, exp_z=H, tol=0.1)
    vol = part.volume()
    print(f"[INFO VOLUME KOMPAS] Итоговый объём кронштейна: {vol:.2f} мм3")
    return part


if __name__ == "__main__":
    part = KompasPart(name="Bracket", visible=True)
    part.create_variables_from_dict(VARIABLES)
    try:
        build_bracket(part)
        part.save("output/Bracket_120x80x70.m3d")
        part.save_screenshot("output/Bracket_120x80x70.png")
        print("[SUCCESS] Деталь Bracket_120x80x70 построена и провалидирована")
    except Exception:
        part.close()
        raise