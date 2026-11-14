# build_cover_fc.py — Листовая крышка во FreeCAD 1.1 (нативный AutoMiter на 4 угла)
# Эталон: example/Крышка_example.m3d (84.20x54.20x16.00 мм, V=14650.56 мм³)
# Запуск: .venv\Scripts\python.exe run_freecad.py build_cover_fc.py output/Cover_84x54x16.FCStd

import math

from freecad_core import (
    DT_NORMAL,
    PLANE_XY,
    STYLE_MAIN,
    FreeCadPart,
)

VARIABLES = {
    "H": (16.0, "Высота бортов крышки"),
}

EXPECTED_VOLUME = 14650.56


def build_cover(part: FreeCadPart):
    H = VARIABLES["H"][0]
    w_base = 80.2
    h_base = 50.2

    # Шаг 1-2: Базовый лист 80.2 x 50.2 x 2.0 на XY (Z: 0.0 -> 2.0)
    def sketch_base(b_sk):
        b_sk.rect(0.0, 0.0, w_base, h_base, centered=True, style=STYLE_MAIN)
        b_sk.dim_hor(
            y_line=h_base / 2.0 + 8.0,
            x1=-w_base / 2.0,
            x2=w_base / 2.0,
            var_name="80.0+0.2",
            y_pts=h_base / 2.0,
        )
        b_sk.dim_ver(
            x_line=-w_base / 2.0 - 8.0,
            y1=-h_base / 2.0,
            y2=h_base / 2.0,
            var_name="50.0+0.2",
            x_pts=-w_base / 2.0,
        )
        b_sk.center_on_origin(w_base, h_base)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_base)
    part.extrude(sk1, depth=2.0, direction=DT_NORMAL)

    # Шаг 3а: Все 4 борта одним сгибом (Thickness Outside -> ровно 84.20 x 54.20 x 16.00)
    bend_edges = part.get_outer_edges_at_z(z_coord=2.0, min_len=30.0)
    if len(bend_edges) != 4:
        raise RuntimeError(
            f"[FAIL] Ожидалось 4 ребра на Z=2.0, найдено {len(bend_edges)}!"
        )

    part.add_sheet_bend(
        bend_edges,
        length=H,
        bend_radius=2.0,
        angle=90.0,
        k_factor=0.4,
        bend_type="Thickness Outside",
        length_spec="Outer Sharp",
        auto_miter=True,
        invert=False,
        length_expr="H",
    )

    # Шаг 3б: Нативное замыкание 4 углов через SMExtrudeWall по торцам длинных стенок
    end_faces = part.find_wall_end_faces(normal_axis="x", min_z_height=8.0)
    if len(end_faces) != 4:
        raise RuntimeError(
            f"[FAIL] Ожидалось 4 торцовых грани длинных стенок, найдено {len(end_faces)}!"
        )

    part.add_sheet_extend(
        end_faces,
        length=2.0,
        use_subtraction=True,
        offset=0.2,
        refine=True,
    )

    # Шаг 4: Вырезы в дне крышки (грань Z=0.0, через всё дно)
    face_bot = part.get_planar_face_at(axis="z", coord=0.0, mode="min")

    def sketch_cutouts(b_sk):
        b_sk.rect(
            11.30,
            -16.10,
            23.40 - 11.30,
            -10.10 - (-16.10),
            centered=False,
            style=STYLE_MAIN,
        )

        dx = math.sqrt(6.00**2 - 5.40**2)
        x_l, x_r = 26.60 - dx, 26.60 + dx
        ang = math.degrees(math.asin(5.40 / 6.00))
        b_sk.line(x_r, 0.70, x_l, 0.70, style=STYLE_MAIN)
        b_sk.line(x_l, 11.50, x_r, 11.50, style=STYLE_MAIN)
        b_sk.arc(26.60, 6.10, 6.00, 360.0 - ang, ang, direction=False, style=STYLE_MAIN)
        b_sk.arc(
            26.60,
            6.10,
            6.00,
            180.0 - ang,
            180.0 + ang,
            direction=False,
            style=STYLE_MAIN,
        )

        circles = [
            (7.60, 6.10, 4.00),
            (-8.40, 6.10, 4.00),
            (-27.90, -13.10, 2.55),
            (-17.40, -13.10, 2.55),
            (-6.90, -13.10, 2.55),
            (-25.90, 6.10, 5.65),
            (31.60, -13.10, 1.80),
            (3.10, -13.10, 1.80),
            (-19.55, -0.25, 1.80),
            (-32.25, -0.25, 1.80),
            (-32.25, 12.45, 1.80),
            (-19.55, 12.45, 1.80),
        ]
        for xc, yc, rad in circles:
            b_sk.circle(xc, yc, rad, style=STYLE_MAIN)

    sk2 = part.create_sketch_on_face(face_bot, draw_fn=sketch_cutouts)
    part.cut(sk2, depth=2.0)

    # Валидация
    part.assert_bbox(exp_x=84.20, exp_y=54.20, exp_z=16.00, tol=0.2)
    vol = part.volume()
    print(
        f"[INFO VOLUME FREECAD] Итоговый объём: {vol:.2f} мм³ (эталон: {EXPECTED_VOLUME:.2f} мм³)"
    )
    return part


_part = FreeCadPart(name="Cover_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_cover(_part)
    _part.save("output/Cover_84x54x16.FCStd")
    print("[SUCCESS FREECAD] output/Cover_84x54x16.FCStd и .stl сохранены")
finally:
    _part.close()
