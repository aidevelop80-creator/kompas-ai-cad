# build_housing_fc.py — Параметрический листовой корпус во FreeCAD 1.1 + развёртка
# Эталон: example/Корпус_example.m3d (194.00 x 36.02 x 147.00 мм, V = 100703.89 мм³)
# Запуск: .venv\Scripts\python.exe run_freecad.py build_housing_fc.py output\Housing_194x36x147.FCStd

import math

from freecad_core import (
    DT_NORMAL,
    DT_REVERSE,
    PLANE_XY,
    STYLE_MAIN,
    FreeCadPart,
)

VARIABLES = {
    "ro": (1.5, "Радиус технологического освобождения углов"),
    "r": (1.0, "Внутренний радиус сгибов стенок и полок"),
    "zv": (11.0, "Длина отгибной полки"),
    "tk": (133.0, "Межосевое расстояние крепёжных отверстий по ширине"),
    "dk": (2.5, "Диаметр крепёжных отверстий на полках"),
    "t": (2.0, "Толщина листа"),
}

EXPECTED_VOLUME = 100703.89


def build_housing(part: FreeCadPart):
    r = VARIABLES["r"][0]
    zv = VARIABLES["zv"][0]
    tk = VARIABLES["tk"][0]
    dk = VARIABLES["dk"][0]
    t = VARIABLES["t"][0]

    W_in, H_in = 190.0, 143.0
    W_ext, H_ext = W_in + 2.0 * t, H_in + 2.0 * t  # 194.00, 147.00
    hw_ext, hh_ext = W_ext / 2.0, H_ext / 2.0
    hh_in = H_in / 2.0
    # Высота стенки при длине полки развёртки 35.0 от границы (r=1.0, t=2.0, K=0.45 -> 36.02 мм)
    h_wall = 3.0 + (36.0 - 0.5 * math.pi * (r + 0.45 * t))

    # Шаг 1-2: Прямоугольное дно по наружному габариту 194.0 x 147.0 x 2.0 на XY (Z: 0 -> t)
    def sketch_blank(b_sk):
        b_sk.rect(0.0, 0.0, W_ext, H_ext, centered=True, style=STYLE_MAIN)
        b_sk.dim_hor(y_line=hh_ext + 8.0, x1=-hw_ext, x2=hw_ext, y_pts=hh_ext)
        b_sk.dim_ver(x_line=-hw_ext - 8.0, y1=-hh_ext, y2=hh_ext, x_pts=-hw_ext)
        b_sk.center_on_origin(W_ext, H_ext)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_blank)
    part.extrude(sk1, depth=t, direction=DT_NORMAL, expr="t")

    # Шаг 3: 4 борта (Material Inside + AutoMiter, минимальный зазор 0.1 мм)
    bend_edges = part.get_outer_edges_at_z(z_coord=t, min_len=50.0)
    if len(bend_edges) != 4:
        raise RuntimeError(
            f"[FAIL] Ожидалось 4 ребра на Z={t}, найдено {len(bend_edges)}!"
        )

    part.add_sheet_bend(
        bend_edges,
        length=h_wall,
        bend_radius=r,
        angle=90.0,
        k_factor=0.45,
        bend_type="Material Inside",
        length_spec="Outer Sharp",
        auto_miter=True,
        min_gap=0.1,
        invert=False,
        radius_expr="r",
    )

    # Шаг 4: Замыкание 4 углов под сварку (SMCornerRelief Weld, Ø=t=2.0 мм) по внешним рёбрам Z=0.0
    done_quads = set()
    for _ in range(4):
        remaining = [
            (quad, edges)
            for quad, edges in part.find_corner_bend_edges(z_coord=0.0)
            if quad not in done_quads
        ]
        if not remaining:
            raise RuntimeError("[FAIL CORNER] Не найдена следующая пара рёбер угла!")
        quad, edge_pair = remaining[0]
        done_quads.add(quad)
        part.add_corner_relief(
            edge_pair,
            relief_type="Weld",
            size=t,
            k_factor=0.45,
        )

    # Шаг 5-6: 2 внутренние полки Сгиб:1 (Y=+71.5) и Сгиб:2 (Y=-71.5), ширина 90 мм, длина zv=11
    for y_edge in (hh_in, -hh_in):
        edge_name, edge_len = part.find_edge_at(
            z_coord=h_wall, y_coord=y_edge, min_len=150.0, tol=0.5
        )
        side_gap = (edge_len - 90.0) / 2.0
        part.add_sheet_bend(
            [edge_name],
            length=zv,
            bend_radius=r,
            angle=90.0,
            k_factor=0.45,
            bend_type="Material Inside",
            length_spec="Outer Sharp",
            auto_miter=False,
            gap1=side_gap,
            gap2=side_gap,
            invert=False,
            length_expr="zv",
            radius_expr="r",
        )

    # Шаг 7: 7 групп отверстий под разъёмы на дне (глубина t+1.0 вверх, не задевая полки)
    conn_centers = [
        (-25.0, 0.0),
        (-75.0, 50.0),
        (-75.0, -50.0),
        (25.0, 50.0),
        (25.0, -50.0),
        (75.0, 50.0),
        (75.0, -50.0),
    ]

    def sketch_connectors(b_sk):
        for cx, cy in conn_centers:
            b_sk.circle(cx, cy, 8.0, style=STYLE_MAIN)
            for dx in (-9.1, 9.1):
                for dy in (-9.1, 9.1):
                    b_sk.circle(cx + dx, cy + dy, 1.7, style=STYLE_MAIN)

        b_sk.dim_diam(-25.0, 0.0, 8.0)
        for cx, cy in conn_centers[1:]:
            b_sk.equal_radius((-25.0, 0.0), (cx, cy))

        ref_small = (-25.0 - 9.1, 0.0 + 9.1)
        b_sk.dim_diam(ref_small[0], ref_small[1], 1.7)
        for cx, cy in conn_centers:
            for dx in (-9.1, 9.1):
                for dy in (-9.1, 9.1):
                    pt = (cx + dx, cy + dy)
                    if pt != ref_small:
                        b_sk.equal_radius(ref_small, pt)

        # Позиционирование 7 центров (14 DoF -> ровно 14 ограничений)
        b_sk.align_h((-25.0, 0.0), (0.0, 0.0))
        b_sk.dim_hor(y_line=15.0, x1=-25.0, x2=0.0, y_pts=0.0)

        b_sk.dim_ver(x_line=-85.0, y1=0.0, y2=50.0, x1=0.0, x2=-75.0)
        b_sk.align_h((-75.0, 50.0), (25.0, 50.0))
        b_sk.align_h((25.0, 50.0), (75.0, 50.0))

        b_sk.dim_ver(x_line=-85.0, y1=-50.0, y2=0.0, x1=-75.0, x2=0.0)
        b_sk.align_h((-75.0, -50.0), (25.0, -50.0))
        b_sk.align_h((25.0, -50.0), (75.0, -50.0))

        b_sk.align_v((-75.0, 50.0), (-75.0, -50.0))
        b_sk.align_v((25.0, 50.0), (25.0, -50.0))
        b_sk.align_v((75.0, 50.0), (75.0, -50.0))

        b_sk.dim_hor(y_line=65.0, x1=-75.0, x2=0.0, y1=50.0, y2=0.0)
        b_sk.dim_hor(y_line=65.0, x1=0.0, x2=25.0, y1=0.0, y2=50.0)
        b_sk.dim_hor(y_line=65.0, x1=25.0, x2=75.0, y_pts=50.0)

        # Позиционирование 4 малых отверстий вокруг каждого центра
        for cx, cy in conn_centers:
            b_sk.align_h((cx - 9.1, cy + 9.1), (cx + 9.1, cy + 9.1))
            b_sk.align_h((cx - 9.1, cy - 9.1), (cx + 9.1, cy - 9.1))
            b_sk.align_v((cx - 9.1, cy + 9.1), (cx - 9.1, cy - 9.1))
            b_sk.align_v((cx + 9.1, cy + 9.1), (cx + 9.1, cy - 9.1))
            b_sk.dim_hor(y_line=cy + 13.0, x1=cx - 9.1, x2=cx, y1=cy + 9.1, y2=cy)
            b_sk.dim_hor(y_line=cy + 13.0, x1=cx, x2=cx + 9.1, y1=cy, y2=cy + 9.1)
            b_sk.dim_ver(x_line=cx - 14.0, y1=cy, y2=cy + 9.1, x1=cx, x2=cx - 9.1)
            b_sk.dim_ver(x_line=cx - 14.0, y1=cy - 9.1, y2=cy, x1=cx - 9.1, x2=cx)

    sk_conn = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_connectors)
    part.cut(sk_conn, depth=t + 1.0, direction=DT_REVERSE)

    # Шаг 8: 4 крепёжных отверстия D=dk на верхних полках (Z=36.02 -> рез вниз 4.0 мм)
    def sketch_tab_holes(b_sk):
        for sx in (-30.0, 30.0):
            for sy in (-tk / 2.0, tk / 2.0):
                b_sk.circle(sx, sy, dk / 2.0, style=STYLE_MAIN)
        b_sk.dim_diam(-30.0, tk / 2.0, dk / 2.0, var_name="dk")
        for sx, sy in [(30.0, tk / 2.0), (-30.0, -tk / 2.0), (30.0, -tk / 2.0)]:
            b_sk.equal_radius((-30.0, tk / 2.0), (sx, sy))

        b_sk.align_h((-30.0, tk / 2.0), (30.0, tk / 2.0))
        b_sk.align_h((-30.0, -tk / 2.0), (30.0, -tk / 2.0))
        b_sk.align_v((-30.0, tk / 2.0), (-30.0, -tk / 2.0))
        b_sk.align_v((30.0, tk / 2.0), (30.0, -tk / 2.0))

        b_sk.dim_hor(y_line=tk / 2.0 + 6.0, x1=-30.0, x2=0.0, y1=tk / 2.0, y2=0.0)
        b_sk.dim_hor(y_line=tk / 2.0 + 10.0, x1=-30.0, x2=30.0, y_pts=tk / 2.0)
        b_sk.dim_ver(x_line=40.0, y1=0.0, y2=tk / 2.0, x1=0.0, x2=30.0, var_name="tk/2")
        b_sk.dim_ver(x_line=50.0, y1=-tk / 2.0, y2=tk / 2.0, x_pts=30.0, var_name="tk")

    sk_tabs = part.create_sketch(
        plane=PLANE_XY, offset_z=h_wall + 0.1, draw_fn=sketch_tab_holes
    )
    part.cut(sk_tabs, depth=4.0, direction=DT_NORMAL)

    # Валидация 3D-корпуса
    part.assert_bbox(exp_x=194.00, exp_y=147.00, exp_z=36.02, tol=0.2)
    vol = part.volume()
    print(
        f"[INFO VOLUME FREECAD] Итоговый объём: {vol:.2f} мм³ (эталон: {EXPECTED_VOLUME:.2f} мм³)"
    )

    # Шаг 9: Развёртка корпуса + экспорт .dxf / .svg
    face_bot = part.get_planar_face_at(axis="z", coord=0.0, mode="min")
    part.unfold(
        face_bot,
        k_factor=0.45,
        k_factor_standard="ansi",
        generate_sketch=True,
        separate_sketch_layers=True,
        show_bend_angles=False,
        dxf_path="output/Housing_194x36x147_unfold.dxf",
        svg_path="output/Housing_194x36x147_unfold.svg",
        offset=(0.0, -210.0, 0.0),
    )
    return part


_part = FreeCadPart(name="Housing_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_housing(_part)
    _part.save("output/Housing_194x36x147.FCStd")
    print(
        "[SUCCESS FREECAD] output/Housing_194x36x147.FCStd, .stl, .dxf и .svg сохранены"
    )
finally:
    _part.close()
