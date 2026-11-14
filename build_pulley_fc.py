# build_pulley_fc.py — Ролик со шкивом и шпоночным пазом во FreeCAD 1.1
# Эталон: example/pulley/pulley_example.m3d (80x24x80 мм, V=76858.08 мм³)
# Запуск: .venv\Scripts\python.exe run_freecad.py build_pulley_fc.py output/Pulley_D80_b24.FCStd


from freecad_core import (
    PLANE_XY,
    STYLE_AXIS,
    STYLE_MAIN,
    FreeCadPart,
)

VARIABLES = {
    "D": (80.0, "Наружный диаметр ролика"),
    "b": (24.0, "Ширина ролика"),
    "bp": (14.0, "Ширина паза"),
    "dp": (68.0, "Диаметр дна паза"),
    "d": (20.0, "Диаметр отверстия под вал"),
    "do": (12.0, "Диаметр отверстий облегчения"),
    "Do": (44.0, "Диаметр центров отверстий облегчения"),
    "bsp": (6.0, "Ширина шпоночного паза"),
    "hsp": (2.8, "Высота шпоночного паза"),
}

EXPECTED_VOLUME = 76858.08


def build_pulley(part: FreeCadPart):
    D = VARIABLES["D"][0]
    b = VARIABLES["b"][0]
    bp = VARIABLES["bp"][0]
    dp = VARIABLES["dp"][0]
    d = VARIABLES["d"][0]
    do = VARIABLES["do"][0]
    Do = VARIABLES["Do"][0]
    bsp = VARIABLES["bsp"][0]
    hsp = VARIABLES["hsp"][0]

    r_in = d / 2.0
    r_groove = dp / 2.0
    r_out = D / 2.0
    rim = (b - bp) / 2.0

    # Шаг 1-2: Вращение полусечения на XY вокруг оси Y (V_Axis)
    def sketch_revolve(b_sk):
        b_sk.axis(0.0, -5.0, 0.0, b + 5.0)
        pts = [
            (r_in, 0.0),
            (r_in, b),
            (r_out, b),
            (r_out, b - rim),
            (r_groove, b - rim),
            (r_groove, rim),
            (r_out, rim),
            (r_out, 0.0),
        ]
        b_sk.polygon(pts, closed=True, style=STYLE_MAIN)
        b_sk.dim_hor(y_line=-6.0, x1=0.0, x2=r_in, var_name="d/2", y1=0.0, y2=0.0)
        b_sk.dim_hor(y_line=-12.0, x1=0.0, x2=r_groove, var_name="dp/2", y1=0.0, y2=rim)
        b_sk.dim_hor(y_line=-18.0, x1=0.0, x2=r_out, var_name="D/2", y1=0.0, y2=0.0)
        b_sk.dim_ver(
            x_line=r_groove - 6.0, y1=rim, y2=b - rim, var_name="bp", x_pts=r_groove
        )
        b_sk.dim_ver(x_line=r_out + 8.0, y1=0.0, y2=b, var_name="b", x_pts=r_out)
        b_sk.align_h((r_in, 0.0), (0.0, 0.0))
        b_sk.equal_length((r_out, b, r_out, b - rim), (r_out, rim, r_out, 0.0))

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_revolve)
    part.revolve(sk1, angle=360.0)

    # Шаг 3-5: Отверстие облегчения + круговой массив (6 шт.)
    face_top = part.get_planar_face_at(axis="y", coord=b, mode="max")

    def sketch_light_hole(b_sk):
        b_sk.circle(0.0, 0.0, Do / 2.0, style=STYLE_AXIS).dim_diam(
            0.0, 0.0, Do / 2.0, var_name="Do"
        )
        b_sk.circle(0.0, Do / 2.0, do / 2.0, style=STYLE_MAIN).dim_diam(
            0.0, Do / 2.0, do / 2.0, var_name="do"
        )

    sk2 = part.create_sketch_on_face(face_top, draw_fn=sketch_light_hole)
    cut_hole = part.cut(sk2, through_all=True)

    axis_y = part.create_axis_by_2_planes("xy", "yz")
    part.circular_pattern(features=[cut_hole], axis_ent=axis_y, count=6, angle=360.0)

    # Шаг 6-7: Шпоночный паз (через всё)
    face_top = part.get_planar_face_at(axis="y", coord=b, mode="max")
    y_bot = r_in - 1.5
    y_top = r_in + hsp

    def sketch_keyway(b_sk):
        pts = [
            (-bsp / 2.0, y_bot),
            (bsp / 2.0, y_bot),
            (bsp / 2.0, y_top),
            (-bsp / 2.0, y_top),
        ]
        b_sk.polygon(pts, closed=True, style=STYLE_MAIN)
        b_sk.dim_hor(
            y_line=y_top + 4.0, x1=-bsp / 2.0, x2=bsp / 2.0, var_name="bsp", y_pts=y_top
        )
        b_sk.dim_ver(
            x_line=bsp / 2.0 + 6.0,
            y1=0.0,
            y2=y_top,
            var_name="d/2+hsp",
            x1=0.0,
            x2=bsp / 2.0,
        )
        b_sk.align_v((0.0, y_bot), (0.0, 0.0))

    sk3 = part.create_sketch_on_face(face_top, draw_fn=sketch_keyway)
    part.cut(sk3, through_all=True)

    # Валидация
    part.assert_bbox(exp_x=D, exp_y=b, exp_z=D, tol=0.1)
    vol = part.volume()
    if abs(vol - EXPECTED_VOLUME) > 0.5:
        raise ValueError(f"[FAIL VOLUME] Объём {vol:.2f} != {EXPECTED_VOLUME:.2f} мм³!")
    print(f"[OK VOLUME FREECAD] Объём совпал с эталоном: {vol:.2f} мм³")
    return part


_part = FreeCadPart(name="Pulley_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_pulley(_part)
    _part.save("output/Pulley_D80_b24.FCStd")
    print("[SUCCESS FREECAD] output/Pulley_D80_b24.FCStd и .stl сохранены")
finally:
    _part.close()
