# build_shaft_fc.py — Параметрический ступенчатый вал во FreeCAD 1.1
# Эталон: example/Shaft_D44_L135_example.m3d (135.00 x 44.00 x 44.00 мм, V = 98907.60 мм³)
# Запуск: .venv\Scripts\python.exe run_freecad.py build_shaft_fc.py output\Shaft_D44_L135.FCStd

import math

from freecad_core import (
    DT_NORMAL,
    PLANE_XY,
    STYLE_MAIN,
    FreeCadPart,
)

VARIABLES = {
    "d1": (24.0, "Диаметр левой цапфы"),
    "l1": (35.0, "Длина левой цапфы"),
    "d2": (32.0, "Диаметр посадочной ступени"),
    "l2": (45.0, "Длина посадочной ступени"),
    "d3": (44.0, "Диаметр упорного буртика"),
    "l3": (15.0, "Длина упорного буртика"),
    "d4": (28.0, "Диаметр правой цапфы"),
    "l4": (40.0, "Длина правой цапфы"),
    "c": (1.5, "Катет торцовых фасок"),
    "dp": (6.0, "Ширина шпоночного паза"),
    "lp": (18.0, "Межцентровая длина шпоночного паза"),
    "up": (3.2, "Глубина шпоночного паза от верхней образующей"),
}

EXPECTED_VOLUME = 98907.60


def _find_end_circular_edges(part: FreeCadPart, l_tot: float, r1: float, r4: float):
    """Находит круговые рёбра левого (X=0) и правого (X=l_tot) торцов вала."""
    tip = part.body.Tip
    found = []
    for idx, edge in enumerate(tip.Shape.Edges):
        if edge.Curve.TypeId != "Part::GeomCircle":
            continue
        ctr = edge.Curve.Center
        rad = edge.Curve.Radius
        if math.hypot(ctr.y, ctr.z) > 0.1:
            continue
        if (abs(ctr.x) < 0.1 and abs(rad - r1) < 0.1) or (
            abs(ctr.x - l_tot) < 0.1 and abs(rad - r4) < 0.1
        ):
            found.append(f"Edge{idx + 1}")
    if len(found) != 2:
        raise RuntimeError(
            f"[FAIL EDGE] Ожидалось 2 торцовых круговых ребра, найдено {len(found)}!"
        )
    return (tip, found)


def build_shaft(part: FreeCadPart):
    d1, l1 = VARIABLES["d1"][0], VARIABLES["l1"][0]
    d2, l2 = VARIABLES["d2"][0], VARIABLES["l2"][0]
    d3, l3 = VARIABLES["d3"][0], VARIABLES["l3"][0]
    d4, l4 = VARIABLES["d4"][0], VARIABLES["l4"][0]
    c = VARIABLES["c"][0]
    dp, lp, up = VARIABLES["dp"][0], VARIABLES["lp"][0], VARIABLES["up"][0]

    r1, r2, r3, r4 = d1 / 2.0, d2 / 2.0, d3 / 2.0, d4 / 2.0
    x1 = l1
    x2 = l1 + l2
    x3 = x2 + l3
    x4 = x3 + l4

    # Шаг 1-2: Контур вращения (4 ступени) + осевая линия по оси X (DoF = 0)
    def sketch_profile(b_sk):
        pts = [
            (0.0, 0.0),
            (0.0, r1),
            (x1, r1),
            (x1, r2),
            (x2, r2),
            (x2, r3),
            (x3, r3),
            (x3, r4),
            (x4, r4),
            (x4, 0.0),
        ]
        b_sk.polygon(pts, closed=True, style=STYLE_MAIN)
        b_sk.axis(-10.0, 0.0, x4 + 10.0, 0.0)
        b_sk.fix_point(-10.0, 0.0)

        b_sk.align_h((x4, 0.0), (0.0, 0.0))
        b_sk.align_v((0.0, r1), (0.0, 0.0))

        b_sk.dim_hor(y_line=-8.0, x1=0.0, x2=x1, y1=r1, y2=r1, var_name="l1")
        b_sk.dim_hor(y_line=-8.0, x1=x1, x2=x2, y1=r2, y2=r2, var_name="l2")
        b_sk.dim_hor(y_line=-8.0, x1=x2, x2=x3, y1=r3, y2=r3, var_name="l3")
        b_sk.dim_hor(y_line=-8.0, x1=x3, x2=x4, y1=r4, y2=r4, var_name="l4")

        b_sk.dim_ver(x_line=-8.0, y1=0.0, y2=r1, x1=0.0, x2=0.0, var_name="d1/2")
        b_sk.dim_ver(x_line=x1 + 5.0, y1=0.0, y2=r2, x1=0.0, x2=x1, var_name="d2/2")
        b_sk.dim_ver(x_line=x2 + 5.0, y1=0.0, y2=r3, x1=0.0, x2=x2, var_name="d3/2")
        b_sk.dim_ver(x_line=x4 + 8.0, y1=0.0, y2=r4, x1=0.0, x2=x4, var_name="d4/2")

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_profile)
    part.revolve(sk1, angle=360.0)

    # Шаг 3-4: Торцовые фаски c x 45° на обоих концах вала
    end_edges = _find_end_circular_edges(part, x4, r1, r4)
    part.chamfer(end_edges, distance=c, expr="c")

    # Шаг 5-7: Шпоночный паз на ступени 2 (от X=l1 до X=l1+lp, Z=+d2/2, глубина up)
    rk = dp / 2.0
    x_kl = l1
    x_kr = l1 + lp

    def sketch_keyway(b_sk):
        b_sk.arc(x_kl, 0.0, rk, 90.0, 270.0, direction=True, style=STYLE_MAIN)
        b_sk.line(x_kl, -rk, x_kr, -rk, style=STYLE_MAIN)
        b_sk.arc(x_kr, 0.0, rk, 270.0, 90.0, direction=True, style=STYLE_MAIN)
        b_sk.line(x_kr, rk, x_kl, rk, style=STYLE_MAIN)

        b_sk.align_h((x_kl, 0.0), (0.0, 0.0))
        b_sk.align_h((x_kr, 0.0), (0.0, 0.0))
        b_sk.constrain_h(x_kl, -rk, x_kr, -rk)
        b_sk.align_v((x_kl, rk), (x_kl, 0.0))
        b_sk.align_v((x_kl, -rk), (x_kl, 0.0))
        b_sk.align_v((x_kr, rk), (x_kr, 0.0))
        b_sk.align_v((x_kr, -rk), (x_kr, 0.0))

        b_sk.dim_hor(
            y_line=rk + 6.0, x1=0.0, x2=x_kl, y1=0.0, y2=0.0, var_name="l1"
        )
        b_sk.dim_hor(
            y_line=rk + 6.0, x1=x_kl, x2=x_kr, y1=0.0, y2=0.0, var_name="lp"
        )
        b_sk.dim_ver(
            x_line=x_kl - 8.0, y1=-rk, y2=rk, x1=x_kl, x2=x_kl, var_name="dp"
        )

    sk_key = part.create_sketch(plane=PLANE_XY, offset_z=r2, draw_fn=sketch_keyway)
    part.cut(sk_key, depth=up, direction=DT_NORMAL, expr="up")

    # Валидация
    part.assert_bbox(exp_x=x4, exp_y=d3, exp_z=d3, tol=0.1)
    vol = part.volume()
    print(
        f"[INFO VOLUME FREECAD] Итоговый объём вала: {vol:.2f} мм³ (эталон: {EXPECTED_VOLUME:.2f} мм³)"
    )
    return part


_part = FreeCadPart(name="Shaft_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_shaft(_part)
    _part.save("output/Shaft_D44_L135.FCStd")
    print("[SUCCESS FREECAD] output/Shaft_D44_L135.FCStd и .stl сохранены")
finally:
    _part.close()