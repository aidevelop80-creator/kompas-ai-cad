# build_bracket.py — Параметрический кронштейн опоры Bracket_120x80x70 в КОМПАС-3D
# Запуск: .venv\Scripts\python.exe build_bracket.py

from kompas_core import (
    DT_BOTH,
    DT_NORMAL,
    DT_REVERSE,
    OBJ_FACE,
    PLANE_XY,
    PLANE_YZ,
    STYLE_MAIN,
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
    "ly": (36.0, "Межосевое расстояние крепёжных отверстий по Y (Y=-26 и Y=+10)"),
    "R": (6.0, "Радиус скругления двух передних вертикальных углов основания"),
}


def _find_vertical_edge(
    part: KompasPart,
    x_coord: float,
    y_coord: float,
    z_min: float = 0.0,
    z_max: float = 12.0,
):
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
            bbox[0] <= x_coord + 0.5
            and bbox[3] >= x_coord - 0.5
            and bbox[1] <= y_coord + 0.5
            and bbox[4] >= y_coord - 0.5
            and bbox[2] <= z_min + 0.5
            and bbox[5] >= z_max - 0.5
        ):
            loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
            if not loops:
                continue
            for li in range(loops.GetCount()):
                edges = _wrap(
                    K5.ksEdgeCollection,
                    _wrap(K5.ksLoop, loops.GetByIndex(li)).EdgeCollection(),
                )
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
                    if (
                        abs(x1 - x2) < 0.1
                        and abs(y1 - y2) < 0.1
                        and abs(x1 - x_coord) < 0.5
                        and abs(y1 - y_coord) < 0.5
                        and abs(min(z1, z2) - z_min) < 0.5
                        and abs(max(z1, z2) - z_max) < 0.5
                    ):
                        return ed
    return None


def build_bracket(part: KompasPart):
    """Построение кронштейна опоры Bracket_120x80x70 в КОМПАС-3D."""
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
    y_hole_front = -8.0 - ly / 2.0  # -26.0
    y_hole_back = y_hole_front + ly  # +10.0

    # --- Шаг 1: Основание L × B × s на PLANE_XY (2D X=+X, 2D Y=+Y, DT_NORMAL=+Z) ---
    def sketch_base(b):
        b.rect(0.0, 0.0, L, B, centered=True, style=STYLE_MAIN)
        b.dim_hor(
            y_line=half_B + 10.0,
            x1=-half_L,
            x2=half_L,
            y1=half_B,
            y2=half_B,
            var_name="L",
        )
        b.dim_ver(
            x_line=-half_L - 10.0,
            y1=-half_B,
            y2=half_B,
            x1=-half_L,
            x2=-half_L,
            var_name="B",
        )
        b.center_on_origin(L, B)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_base)
    part.extrude(sk1, depth=s, direction=DT_NORMAL, expr="s")

    # --- Шаг 2: Вертикальная стойка на плоскости Z = s ---
    plane_stand = part.create_offset_plane("xy", s, expr="s")

    def sketch_stand(b):
        b.rect(-half_L, y_stand_inner, L, s, centered=False, style=STYLE_MAIN)
        b.dim_hor(
            y_line=half_B + 10.0,
            x1=-half_L,
            x2=half_L,
            y1=half_B,
            y2=half_B,
            var_name="L",
        )
        b.dim_ver(
            x_line=half_L + 10.0,
            y1=y_stand_inner,
            y2=half_B,
            x1=half_L,
            x2=half_L,
            var_name="s",
        )
        b.dim_ver(
            x_line=-half_L - 10.0,
            y1=0.0,
            y2=half_B,
            x1=0.0,
            x2=-half_L,
            var_name="B/2",
        )
        b.align_v((0.0, half_B), (0.0, 0.0))

    sk2 = part.create_sketch(plane=plane_stand, draw_fn=sketch_stand)
    part.boss_extrude(sk2, depth=H - s, direction=DT_NORMAL, expr="H-s")

    # --- Шаг 3: Бобышка на передней грани стойки (Y = +28.0) ---
    # На PLANE_XZ ("Плоскость ZX"): 2D x = +X, 2D y = -Z, DT_NORMAL = +Y, DT_REVERSE = -Y
    plane_boss = part.create_offset_plane("xz", y_stand_inner, expr="B/2-s")

    def sketch_boss(b):
        b.circle(0.0, -hb, db / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, -hb, db / 2.0, var_name="db")
        b.align_v((0.0, -hb), (0.0, 0.0))
        b.dim_ver(x_line=db / 2.0 + 10.0, y1=-hb, y2=0.0, var_name="hb")

    sk3 = part.create_sketch(plane=plane_boss, draw_fn=sketch_boss)
    part.boss_extrude(sk3, depth=lb, direction=DT_REVERSE, expr="lb")

    # --- Шаг 4: Ребро жёсткости на PLANE_YZ ---
    # На PLANE_YZ ("Плоскость ZY"): 2D x = -Z, 2D y = -Y
    # 3D (Y, Z): (-30, s) -> (+28, 30) -> (+28, s) => 2D (-Z, -Y): (-s, +30) -> (-30, -28) -> (-s, -28)
    def sketch_rib(b):
        pts = [
            (-s, 30.0),
            (-30.0, -y_stand_inner),
            (-s, -y_stand_inner),
        ]
        b.polygon(pts, closed=True, style=STYLE_MAIN)
        b.dim_hor(
            y_line=-y_stand_inner - 8.0,
            x1=-s,
            x2=0.0,
            y1=-y_stand_inner,
            y2=0.0,
            var_name="s",
        )
        b.dim_hor(
            y_line=-y_stand_inner - 16.0,
            x1=-30.0,
            x2=0.0,
            y1=-y_stand_inner,
            y2=0.0,
            var_name="30",
        )
        b.dim_ver(
            x_line=-s + 8.0,
            y1=-y_stand_inner,
            y2=0.0,
            x1=-s,
            x2=0.0,
            var_name="B/2-s",
        )
        b.dim_ver(
            x_line=-s + 8.0,
            y1=0.0,
            y2=30.0,
            x1=0.0,
            x2=-s,
            var_name="30",
        )

    sk4 = part.create_sketch(plane=PLANE_YZ, draw_fn=sketch_rib)
    part.boss_extrude(sk4, depth=tr / 2.0, direction=DT_BOTH, expr="tr/2")

    # --- Шаг 5: Сквозное отверстие d0 от задней плоскости Y = B/2 + 1 в -Y (DT_NORMAL) ---
    plane_hole = part.create_offset_plane("xz", half_B + 1.0, expr="B/2+1")

    def sketch_through_hole(b):
        b.circle(0.0, -hb, d0 / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, -hb, d0 / 2.0, var_name="d0")
        b.align_v((0.0, -hb), (0.0, 0.0))
        b.dim_ver(x_line=d0 / 2.0 + 10.0, y1=-hb, y2=0.0, var_name="hb")

    sk5 = part.create_sketch(plane=plane_hole, draw_fn=sketch_through_hole)
    part.cut(sk5, depth=s + lb + 2.0, direction=DT_NORMAL, expr="s+lb+2")

    # --- Шаг 6: 4 крепёжных отверстия dm в основании через point_pattern (сверху вниз от Z = s + 0.5) ---
    plane_mount = part.create_offset_plane("xy", s + 0.5, expr="s+0.5")

    def sketch_base_mount_hole(b):
        b.circle(lx / 2.0, y_hole_front, dm / 2.0, style=STYLE_MAIN)
        b.dim_diam(lx / 2.0, y_hole_front, dm / 2.0, var_name="dm")
        b.dim_hor(
            y_line=y_hole_front - 8.0,
            x1=0.0,
            x2=lx / 2.0,
            y1=0.0,
            y2=y_hole_front,
            var_name="lx/2",
        )
        b.dim_ver(
            x_line=lx / 2.0 + 8.0,
            y1=y_hole_front,
            y2=0.0,
            x1=lx / 2.0,
            x2=0.0,
            var_name="ly/2+8",
        )

    sk6 = part.create_sketch(plane=plane_mount, draw_fn=sketch_base_mount_hole)
    cut_mount = part.cut(sk6, depth=s + 1.0, direction=DT_NORMAL, expr="s+1")

    def sketch_mount_points(b):
        b.point(lx / 2.0, y_hole_front, style=STYLE_MAIN)
        b.point(-lx / 2.0, y_hole_front, style=STYLE_MAIN)
        b.point(lx / 2.0, y_hole_back, style=STYLE_MAIN)
        b.point(-lx / 2.0, y_hole_back, style=STYLE_MAIN)
        b.fix_point(lx / 2.0, y_hole_front)
        b.align_v((lx / 2.0, y_hole_front), (lx / 2.0, y_hole_back))
        b.align_v((-lx / 2.0, y_hole_front), (-lx / 2.0, y_hole_back))
        b.align_h((lx / 2.0, y_hole_front), (-lx / 2.0, y_hole_front))
        b.align_h((lx / 2.0, y_hole_back), (-lx / 2.0, y_hole_back))
        b.dim_hor(
            y_line=y_hole_front - 8.0,
            x1=-lx / 2.0,
            x2=lx / 2.0,
            y_pts=y_hole_front,
            var_name="lx",
        )
        b.dim_ver(
            x_line=lx / 2.0 + 8.0,
            y1=y_hole_front,
            y2=y_hole_back,
            x_pts=lx / 2.0,
            var_name="ly",
        )

    sk_points = part.create_sketch(plane=plane_mount, draw_fn=sketch_mount_points)
    part.point_pattern(features=[cut_mount], driven_obj=sk_points)

    # --- Шаг 7: Скругление двух передних вертикальных рёбер основания ---
    edge_left = _find_vertical_edge(
        part, x_coord=-half_L, y_coord=-half_B, z_min=0.0, z_max=s
    )
    edge_right = _find_vertical_edge(
        part, x_coord=half_L, y_coord=-half_B, z_min=0.0, z_max=s
    )
    if not edge_left or not edge_right:
        raise RuntimeError(
            "[FAIL FILLET] Не найдены передние вертикальные рёбра основания!"
        )
    part.fillet([edge_left, edge_right], radius=R, expr="R")

    part.assert_bbox(exp_x=L, exp_y=B, exp_z=H, tol=0.1)
    print(f"[INFO VOLUME KOMPAS] Итоговый объём кронштейна: {part.volume():.2f} мм3")
    return part


if __name__ == "__main__":
    part = KompasPart(name="Bracket", visible=True)
    part.create_variables_from_dict(VARIABLES)
    try:
        build_bracket(part)
        part.save("output/Bracket_120x80x70.m3d")
        part.save_screenshot("output/Bracket_120x80x70.png")
    except Exception:
        part.close()
        raise
