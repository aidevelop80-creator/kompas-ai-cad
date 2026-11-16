# build_cover_fc.py — Листовая крышка во FreeCAD 1.1 + параметрическая развёртка
# Эталон: example/Крышка_example.m3d (84.20 x 54.20 x 16.00 мм, V = 14650.56 мм³)
# Запуск: .venv\Scripts\python.exe run_freecad.py build_cover_fc.py output\Cover_84x54x16.FCStd

import math

from freecad_core import (
    DT_NORMAL,
    DT_REVERSE,
    PLANE_XY,
    STYLE_MAIN,
    FreeCadPart,
)

VARIABLES = {
    "L": (80.2, "Внутренняя длина между стенками крышки (80.0+0.2)"),
    "B": (50.2, "Внутренняя ширина между стенками крышки (50.0+0.2)"),
    "H": (16.0, "Высота бортов крышки (наружный габарит)"),
    "t": (2.0, "Толщина листа"),
    "R": (2.0, "Внутренний радиус гиба"),
}

EXPECTED_VOLUME = 14650.56


def build_cover(part: FreeCadPart):
    L = VARIABLES["L"][0]
    B = VARIABLES["B"][0]
    H = VARIABLES["H"][0]
    t = VARIABLES["t"][0]
    R = VARIABLES["R"][0]

    w_blank = L + 2.0 * t  # 84.20 мм (наружный габарит для Material Inside)
    h_blank = B + 2.0 * t  # 54.20 мм

    # Шаг 1-2: Базовый лист (L+2*t) x (B+2*t) x t на XY (Z: 0.0 -> t)
    def sketch_base(b_sk):
        b_sk.rect(0.0, 0.0, w_blank, h_blank, centered=True, style=STYLE_MAIN)
        b_sk.dim_hor(
            y_line=h_blank / 2.0 + 8.0,
            x1=-w_blank / 2.0,
            x2=w_blank / 2.0,
            var_name="L+2*t",
            y_pts=h_blank / 2.0,
        )
        b_sk.dim_ver(
            x_line=-w_blank / 2.0 - 8.0,
            y1=-h_blank / 2.0,
            y2=h_blank / 2.0,
            var_name="B+2*t",
            x_pts=-w_blank / 2.0,
        )
        b_sk.center_on_origin(w_blank, h_blank)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_base)
    part.extrude(sk1, depth=t, direction=DT_NORMAL, expr="t")

    # Шаг 3: Все 4 борта с Material Inside + AutoMiter (ровные замкнутые углы от Z=0 до Z=H)
    bend_edges = part.get_outer_edges_at_z(z_coord=t, min_len=30.0)
    if len(bend_edges) != 4:
        raise RuntimeError(
            f"[FAIL] Ожидалось 4 ребра на Z={t}, найдено {len(bend_edges)}!"
        )

    part.add_sheet_bend(
        bend_edges,
        length=H,
        bend_radius=R,
        angle=90.0,
        k_factor=0.4,
        bend_type="Material Inside",
        length_spec="Outer Sharp",
        auto_miter=True,
        min_gap=0.2,
        invert=False,
        length_expr="H",
        radius_expr="R",
    )

    # Шаг 3б: Круглые освобождения в 4 углах (SMCornerRelief Circle, R=3.5 мм)
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
            size=t,  # в режиме "Weld" size — диаметр скругления (= 2.0 мм <= t)
            k_factor=0.4,
        )

    # Шаг 4: Вырезы в дне крышки на PLANE_XY (X_fc = -X_kompas, Y_fc = +Y_kompas), рез вверх (+Z)
    def sketch_cutouts(b_sk):
        # 4.1 Прямоугольный вырез 12.10 x 6.00: X in [-23.40, -11.30], Y in [-16.10, -10.10]
        b_sk.rect(-23.40, -16.10, 12.10, 6.00, centered=False, style=STYLE_MAIN)
        b_sk.dim_hor(y_line=-18.5, x1=-23.40, x2=-11.30, y_pts=-16.10)
        b_sk.dim_ver(x_line=-26.0, y1=-16.10, y2=-10.10, x_pts=-23.40)
        b_sk.dim_hor(y_line=-8.0, x1=-11.30, x2=0.0, y1=-10.10, y2=0.0)
        b_sk.dim_ver(x_line=-8.0, y1=-10.10, y2=0.0, x1=-11.30, x2=0.0)

        # 4.2 Срезанный круглый вырез (овал с хордами): центр (-26.60, 6.10), R=6.00, Y=0.70 и 11.50
        xc_slot, yc_slot, r_slot, half_h = -26.60, 6.10, 6.00, 5.40
        dx = math.sqrt(r_slot**2 - half_h**2)
        x_l, x_r = xc_slot - dx, xc_slot + dx
        y_bot, y_top = yc_slot - half_h, yc_slot + half_h
        ang = math.degrees(math.asin(half_h / r_slot))

        b_sk.line(x_r, y_bot, x_l, y_bot, style=STYLE_MAIN)
        b_sk.line(x_l, y_top, x_r, y_top, style=STYLE_MAIN)
        b_sk.arc(
            xc_slot,
            yc_slot,
            r_slot,
            360.0 - ang,
            ang,
            direction=False,
            style=STYLE_MAIN,
        )
        b_sk.arc(
            xc_slot,
            yc_slot,
            r_slot,
            180.0 - ang,
            180.0 + ang,
            direction=False,
            style=STYLE_MAIN,
        )

        b_sk.constrain_h(x_r, y_bot, x_l, y_bot)
        b_sk.constrain_h(x_l, y_top, x_r, y_top)
        b_sk.concentric(xc_slot, yc_slot, equal_r=True)
        b_sk.dim_rad(xc_slot, yc_slot, r_slot)
        b_sk.dim_hor(y_line=yc_slot + 2.0, x1=xc_slot, x2=0.0, y1=yc_slot, y2=0.0)
        b_sk.dim_ver(x_line=xc_slot - 8.0, y1=0.0, y2=yc_slot, x1=0.0, x2=xc_slot)
        b_sk.dim_ver(x_line=x_l - 2.0, y1=y_bot, y2=yc_slot, x1=x_l, x2=xc_slot)
        b_sk.dim_ver(x_line=x_l - 2.0, y1=yc_slot, y2=y_top, x1=xc_slot, x2=x_l)

        # 4.3 12 круглых отверстий
        circles = [
            (-7.60, 6.10, 4.00),  # Ø8.00 #1
            (8.40, 6.10, 4.00),  # Ø8.00 #2
            (6.90, -13.10, 2.55),  # Ø5.10 #1
            (17.40, -13.10, 2.55),  # Ø5.10 #2
            (27.90, -13.10, 2.55),  # Ø5.10 #3
            (25.90, 6.10, 5.65),  # Ø11.30 большое
            (-3.10, -13.10, 1.80),  # Ø3.60 нижний ряд #1
            (-31.60, -13.10, 1.80),  # Ø3.60 нижний ряд #2
            (19.55, -0.25, 1.80),  # Ø3.60 квадрат 12.7x12.7
            (32.25, -0.25, 1.80),
            (32.25, 12.45, 1.80),
            (19.55, 12.45, 1.80),
        ]
        for xc, yc, rad in circles:
            b_sk.circle(xc, yc, rad, style=STYLE_MAIN)

        b_sk.dim_diam(-7.60, 6.10, 4.00)
        b_sk.equal_radius((-7.60, 6.10), (8.40, 6.10))

        b_sk.dim_diam(6.90, -13.10, 2.55)
        b_sk.equal_radius((6.90, -13.10), (17.40, -13.10))
        b_sk.equal_radius((6.90, -13.10), (27.90, -13.10))

        b_sk.dim_diam(25.90, 6.10, 5.65)

        b_sk.dim_diam(-3.10, -13.10, 1.80)
        for cx, cy in [
            (-31.60, -13.10),
            (19.55, -0.25),
            (32.25, -0.25),
            (32.25, 12.45),
            (19.55, 12.45),
        ]:
            b_sk.equal_radius((-3.10, -13.10), (cx, cy))

        # Верхний ряд (Y = 6.10)
        b_sk.align_h((-7.60, 6.10), (xc_slot, yc_slot))
        b_sk.align_h((8.40, 6.10), (-7.60, 6.10))
        b_sk.align_h((25.90, 6.10), (8.40, 6.10))
        b_sk.dim_hor(y_line=12.0, x1=-7.60, x2=0.0, y1=6.10, y2=0.0)
        b_sk.dim_hor(y_line=12.0, x1=0.0, x2=8.40, y1=0.0, y2=6.10)
        b_sk.dim_hor(y_line=14.0, x1=0.0, x2=25.90, y1=0.0, y2=6.10)

        # Нижний ряд (Y = -13.10)
        b_sk.dim_ver(x_line=2.0, y1=-13.10, y2=0.0, x1=6.90, x2=0.0)
        b_sk.align_h((-31.60, -13.10), (6.90, -13.10))
        b_sk.align_h((-3.10, -13.10), (6.90, -13.10))
        b_sk.align_h((17.40, -13.10), (6.90, -13.10))
        b_sk.align_h((27.90, -13.10), (17.40, -13.10))
        b_sk.dim_hor(y_line=-20.0, x1=-31.60, x2=0.0, y1=-13.10, y2=0.0)
        b_sk.dim_hor(y_line=-18.0, x1=-3.10, x2=0.0, y1=-13.10, y2=0.0)
        b_sk.dim_hor(y_line=-18.0, x1=0.0, x2=6.90, y1=0.0, y2=-13.10)
        b_sk.dim_hor(y_line=-18.0, x1=6.90, x2=17.40, y_pts=-13.10)
        b_sk.dim_hor(y_line=-18.0, x1=17.40, x2=27.90, y_pts=-13.10)

        # 4 отверстия вокруг Ø11.30 (квадрат 12.70 x 12.70)
        b_sk.align_h((19.55, -0.25), (32.25, -0.25))
        b_sk.align_h((19.55, 12.45), (32.25, 12.45))
        b_sk.align_v((19.55, -0.25), (19.55, 12.45))
        b_sk.align_v((32.25, -0.25), (32.25, 12.45))
        b_sk.dim_hor(y_line=-4.0, x1=0.0, x2=19.55, y1=0.0, y2=-0.25)
        b_sk.dim_ver(x_line=15.0, y1=-0.25, y2=0.0, x1=19.55, x2=0.0)
        b_sk.dim_hor(y_line=-4.0, x1=19.55, x2=32.25, y_pts=-0.25)
        b_sk.dim_ver(x_line=36.0, y1=-0.25, y2=12.45, x_pts=19.55)

    sk2 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_cutouts)
    part.cut(sk2, direction=DT_REVERSE, through_all=True)

    # Валидация 3D-детали
    part.assert_bbox(exp_x=L + 2.0 * t, exp_y=B + 2.0 * t, exp_z=H, tol=0.1)
    vol = part.volume()
    print(
        f"[INFO VOLUME FREECAD] Итоговый объём: {vol:.2f} мм³ (эталон: {EXPECTED_VOLUME:.2f} мм³)"
    )

    # Шаг 5: Развёртка от плоского дна Z=0.0 + экспорт в DXF/SVG
    face_bot = part.get_planar_face_at(axis="z", coord=0.0, mode="min")
    k_val = 0.4
    bend_allowance = 0.5 * math.pi * (R + k_val * t)
    exp_unfold_l = (w_blank - 2.0 * (R + t)) + 2.0 * (bend_allowance + (H - R - t))
    exp_unfold_b = (h_blank - 2.0 * (R + t)) + 2.0 * (bend_allowance + (H - R - t))

    part.unfold(
        face_bot,
        k_factor=k_val,
        k_factor_standard="ansi",
        generate_sketch=True,
        separate_sketch_layers=True,
        show_bend_angles=False,
        dxf_path="output/Cover_84x54x16_unfold.dxf",
        svg_path="output/Cover_84x54x16_unfold.svg",
        offset=(0.0, -85.0, 0.0),
        assert_dims=(exp_unfold_l, exp_unfold_b, t),
        tol=0.3,
    )
    return part


_part = FreeCadPart(name="Cover_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_cover(_part)
    _part.save("output/Cover_84x54x16.FCStd")
    print("[SUCCESS FREECAD] output/Cover_84x54x16.FCStd, .stl, .dxf и .svg сохранены")
finally:
    _part.close()
