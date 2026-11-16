# build_bracket_fc.py — Параметрический кронштейн опоры Bracket_120x80x70 во FreeCAD 1.1+
# Запуск: .venv\Scripts\python.exe run_freecad.py build_bracket_fc.py output\Bracket_120x80x70.FCStd

from freecad_core import (
    DT_BOTH,
    DT_NORMAL,
    DT_REVERSE,
    PLANE_XY,
    PLANE_XZ,
    PLANE_YZ,
    STYLE_MAIN,
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
    "ly": (36.0, "Межосевое расстояние крепёжных отверстий по Y (Y=-26 и Y=+10)"),
    "R": (6.0, "Радиус скругления двух передних вертикальных углов основания"),
}


def build_bracket(part: FreeCadPart):
    """Построение кронштейна опоры Bracket_120x80x70 во FreeCAD 1.1+ (DoF=0 в каждом эскизе)."""
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
    y_hole_front = -8.0 - ly / 2.0  # -26.0
    y_hole_back = y_hole_front + ly  # +10.0

    # --- Шаг 1: Основание L × B × s на PLANE_XY ---
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
    def sketch_stand(b):
        b.rect(-half_L, y_stand_inner, L, s, centered=False, style=STYLE_MAIN)
        b.dim_hor(
            y_line=half_B + 5.0,
            x1=-half_L,
            x2=half_L,
            y1=half_B,
            y2=half_B,
            var_name="L",
        )
        b.dim_ver(
            x_line=half_L + 5.0,
            y1=y_stand_inner,
            y2=half_B,
            x1=half_L,
            x2=half_L,
            var_name="s",
        )
        b.dim_hor(
            y_line=half_B + 12.0,
            x1=0.0,
            x2=half_L,
            y1=0.0,
            y2=half_B,
            var_name="L/2",
        )
        b.dim_ver(
            x_line=-half_L - 5.0,
            y1=0.0,
            y2=half_B,
            x1=0.0,
            x2=-half_L,
            var_name="B/2",
        )

    sk2 = part.create_sketch(plane=PLANE_XY, offset_z=s, draw_fn=sketch_stand)
    sk2.setExpression("AttachmentOffset.Base.z", part._translate_expr("s"))
    part.extrude(sk2, depth=H - s, direction=DT_NORMAL, expr="H-s")

    # --- Шаг 3: Бобышка на передней грани стойки (Y = +28.0) ---
    # На XZ_Plane во FreeCAD: 2D X = +X, 2D Y = +Z, нормаль = -Y (offset_z=-28 -> Y=+28)
    def sketch_boss(b):
        b.circle(0.0, hb, db / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, hb, db / 2.0, var_name="db")
        b.align_v((0.0, hb), (0.0, 0.0))
        b.dim_ver(
            x_line=db / 2.0 + 8.0,
            y1=0.0,
            y2=hb,
            x1=0.0,
            x2=0.0,
            var_name="hb",
        )

    sk3 = part.create_sketch(
        plane=PLANE_XZ, offset_z=-y_stand_inner, draw_fn=sketch_boss
    )
    sk3.setExpression("AttachmentOffset.Base.z", part._translate_expr("-(B/2 - s)"))
    part.extrude(sk3, depth=lb, direction=DT_REVERSE, expr="lb")

    # --- Шаг 4: Ребро жёсткости на PLANE_YZ (2D X = +Y, 2D Y = +Z), Midplane на tr ---
    def sketch_rib(b):
        pts = [
            (-30.0, s),
            (y_stand_inner, 30.0),
            (y_stand_inner, s),
        ]
        b.polygon(pts, closed=True, style=STYLE_MAIN)
        b.dim_hor(
            y_line=s - 6.0,
            x1=-30.0,
            x2=0.0,
            y1=s,
            y2=0.0,
            var_name=None,
        )
        b.dim_hor(
            y_line=s - 6.0,
            x1=0.0,
            x2=y_stand_inner,
            y1=0.0,
            y2=s,
            var_name="B/2-s",
        )
        b.dim_ver(
            x_line=y_stand_inner + 6.0,
            y1=0.0,
            y2=s,
            x1=0.0,
            x2=y_stand_inner,
            var_name="s",
        )
        b.dim_ver(
            x_line=y_stand_inner + 14.0,
            y1=0.0,
            y2=30.0,
            x1=0.0,
            x2=y_stand_inner,
            var_name=None,
        )

    sk4 = part.create_sketch(plane=PLANE_YZ, draw_fn=sketch_rib)
    part.extrude(sk4, depth=tr, direction=DT_BOTH, expr="tr")

    # --- Шаг 5: Сквозное отверстие d0 в бобышке и стойке (от Y = +16.0 в +Y) ---
    def sketch_through_hole(b):
        b.circle(0.0, hb, d0 / 2.0, style=STYLE_MAIN)
        b.dim_diam(0.0, hb, d0 / 2.0, var_name="d0")
        b.align_v((0.0, hb), (0.0, 0.0))
        b.dim_ver(
            x_line=d0 / 2.0 + 8.0,
            y1=0.0,
            y2=hb,
            x1=0.0,
            x2=0.0,
            var_name="hb",
        )

    sk5 = part.create_sketch(
        plane=PLANE_XZ, offset_z=-y_boss_front, draw_fn=sketch_through_hole
    )
    sk5.setExpression(
        "AttachmentOffset.Base.z", part._translate_expr("-(B/2 - s - lb)")
    )
    part.cut(sk5, through_all=True, direction=DT_NORMAL)

    # --- Шаг 6: 4 крепёжных отверстия dm в основании (один эскиз, DoF = 0) ---
    def sketch_mount_holes(b):
        c1 = (lx / 2.0, y_hole_front)
        c2 = (-lx / 2.0, y_hole_front)
        c3 = (lx / 2.0, y_hole_back)
        c4 = (-lx / 2.0, y_hole_back)
        for cx, cy in (c1, c2, c3, c4):
            b.circle(cx, cy, dm / 2.0, style=STYLE_MAIN)
        b.dim_diam(c1[0], c1[1], dm / 2.0, var_name="dm")
        b.equal_radius(c1, c2)
        b.equal_radius(c1, c3)
        b.equal_radius(c1, c4)
        b.symmetric_pts(c1, c2, axis="y")
        b.symmetric_pts(c3, c4, axis="y")
        b.align_v(c1, c3)
        b.dim_hor(
            y_line=y_hole_front - 8.0,
            x1=c2[0],
            x2=c1[0],
            y1=c2[1],
            y2=c1[1],
            var_name="lx",
        )
        b.dim_ver(
            x_line=c1[0] + 8.0,
            y1=c1[1],
            y2=c3[1],
            x1=c1[0],
            x2=c3[0],
            var_name="ly",
        )
        b.dim_ver(
            x_line=c1[0] + 16.0,
            y1=c1[1],
            y2=0.0,
            x1=c1[0],
            x2=0.0,
            var_name="ly/2 + 8 mm",
        )

    sk6 = part.create_sketch(
        plane=PLANE_XY, offset_z=s + 0.5, draw_fn=sketch_mount_holes
    )
    sk6.setExpression("AttachmentOffset.Base.z", part._translate_expr("s + 0.5 mm"))
    part.cut(sk6, depth=s + 1.0, direction=DT_NORMAL, expr="s + 1 mm")

    # --- Шаг 7: Скругление двух передних вертикальных рёбер основания ---
    tip = part.body.Tip
    front_edge_names = []
    for idx, edge in enumerate(tip.Shape.Edges):
        if len(edge.Vertexes) != 2:
            continue
        v1, v2 = edge.Vertexes[0].Point, edge.Vertexes[1].Point
        if (
            abs(v1.x - v2.x) < 1e-3
            and abs(v1.y - v2.y) < 1e-3
            and abs(v1.z - v2.z) > 1e-3
        ):
            mx, my = 0.5 * (v1.x + v2.x), 0.5 * (v1.y + v2.y)
            z_lo, z_hi = min(v1.z, v2.z), max(v1.z, v2.z)
            if (
                abs(my + half_B) < 0.5
                and (abs(mx - half_L) < 0.5 or abs(mx + half_L) < 0.5)
                and abs(z_lo) < 0.5
                and abs(z_hi - s) < 0.5
            ):
                front_edge_names.append(f"Edge{idx + 1}")

    if len(front_edge_names) != 2:
        raise RuntimeError(
            f"[FAIL FILLET] Ожидалось 2 передних ребра, найдено {len(front_edge_names)}: {front_edge_names}"
        )

    part.fillet(front_edge_names, radius=R, expr="R")

    part.assert_bbox(exp_x=L, exp_y=B, exp_z=H, tol=0.1)
    print(f"[INFO VOLUME FREECAD] Итоговый объём кронштейна: {part.volume():.2f} мм3")
    return part


_part = FreeCadPart(name="Bracket_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_bracket(_part)
    _part.save("output/Bracket_120x80x70.FCStd")
finally:
    _part.close()
