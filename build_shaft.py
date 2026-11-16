# build_shaft.py — Параметрический ступенчатый вал в КОМПАС-3D
# Эталон: example/Shaft_D44_L135_example.m3d (135.00 x 44.00 x 44.00 мм, V = 98907.60 мм³)
# Запуск: .venv\Scripts\python.exe build_shaft.py

from kompas_core import (
    DT_NORMAL,
    DT_REVERSE,
    PLANE_XY,
    STYLE_MAIN,
    KompasPart,
    _wrap,
)
from sdk_ref import kompas_api5_v16 as K5

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


def _get_face_circular_edge(face_ent):
    """Извлекает круговое ребро торцовой плоской грани вала."""
    fdef = _wrap(K5.ksFaceDefinition, face_ent.GetDefinition())
    loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
    loop = _wrap(K5.ksLoop, loops.GetByIndex(0))
    edges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
    return _wrap(K5.ksEdgeDefinition, edges.GetByIndex(0))


def build_shaft(part: KompasPart):
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

    # Шаг 1-2: Контур вращения (4 ступени) на Плоскости XY + осевая линия по X
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

        b_sk.align_h((x4, 0.0), (0.0, 0.0))
        b_sk.align_v((0.0, r1), (0.0, 0.0))

        b_sk.dim_hor(y_line=-8.0, x1=0.0, x2=x1, var_name="l1", y1=r1, y2=r1)
        b_sk.dim_hor(y_line=-8.0, x1=x1, x2=x2, var_name="l2", y1=r2, y2=r2)
        b_sk.dim_hor(y_line=-8.0, x1=x2, x2=x3, var_name="l3", y1=r3, y2=r3)
        b_sk.dim_hor(y_line=-8.0, x1=x3, x2=x4, var_name="l4", y1=r4, y2=r4)

        b_sk.dim_ver(x_line=-8.0, y1=0.0, y2=r1, var_name="d1/2", x1=0.0, x2=0.0)
        b_sk.dim_ver(x_line=x1 + 5.0, y1=0.0, y2=r2, var_name="d2/2", x1=0.0, x2=x1)
        b_sk.dim_ver(x_line=x2 + 5.0, y1=0.0, y2=r3, var_name="d3/2", x1=0.0, x2=x2)
        b_sk.dim_ver(x_line=x4 + 8.0, y1=0.0, y2=r4, var_name="d4/2", x1=0.0, x2=x4)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_profile)
    part.revolve(sk1, angle=360.0)

    # Шаг 3-4: Торцовые фаски c x 45° на левом (X=0) и правом (X=l1+l2+l3+l4) торцах
    face_left = part.get_planar_face_at(axis="x", coord=0.0, mode="min")
    part.chamfer([_get_face_circular_edge(face_left)], distance=c, expr="c")

    face_right = part.get_planar_face_at(axis="x", coord=x4, mode="max")
    part.chamfer([_get_face_circular_edge(face_right)], distance=c, expr="c")

    # Шаг 5-7: Смещённая плоскость Z=+d2/2 и вырез шпоночного паза глубиной up
    plane_key = part.create_offset_plane("xy", r2, expr="d2/2")
    rk = dp / 2.0
    x_kl = l1
    x_kr = l1 + lp

    def sketch_keyway(b_sk):
        b_sk.arc(x_kl, 0.0, rk, 90.0, 270.0, direction=False, style=STYLE_MAIN)
        b_sk.line(x_kl, -rk, x_kr, -rk, style=STYLE_MAIN)
        b_sk.arc(x_kr, 0.0, rk, 270.0, 90.0, direction=False, style=STYLE_MAIN)
        b_sk.line(x_kr, rk, x_kl, rk, style=STYLE_MAIN)

        b_sk.dim_hor(
            y_line=rk + 6.0, x1=0.0, x2=x_kl, var_name="l1", y1=0.0, y2=rk
        )
        b_sk.dim_hor(
            y_line=rk + 6.0, x1=x_kl, x2=x_kr, var_name="lp", y_pts=rk
        )
        b_sk.dim_ver(
            x_line=x_kl - 8.0, y1=-rk, y2=rk, var_name="dp", x_pts=x_kl
        )
        b_sk.dim_ver(
            x_line=x_kr + 8.0, y1=0.0, y2=rk, var_name="dp/2", x1=0.0, x2=x_kr
        )

    sk_key = part.create_sketch(plane=plane_key, draw_fn=sketch_keyway)
    part.cut(sk_key, depth=up, direction=DT_NORMAL, expr="up")

    # Валидация
    part.assert_bbox(exp_x=x4, exp_y=d3, exp_z=d3, tol=0.1)
    vol = part.volume()
    print(
        f"[INFO VOLUME KOMPAS] Итоговый объём вала: {vol:.2f} мм³ (эталон: {EXPECTED_VOLUME:.2f} мм³)"
    )
    return part


if __name__ == "__main__":
    part = KompasPart(name="Shaft", visible=True)
    part.create_variables_from_dict(VARIABLES)
    try:
        build_shaft(part)
        part.save("output/Shaft_D44_L135.m3d")
        part.save_screenshot("output/Shaft_D44_L135.png")
        print("[SUCCESS] Деталь Shaft_D44_L135 построена и провалидирована")
    except Exception:
        part.close()
        raise