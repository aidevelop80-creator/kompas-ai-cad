# build_flange_fc.py — Фланцевая втулка во FreeCAD 1.1 (эталон: 100x60x100, V=142314.15 мм³)
# Запуск: .venv\Scripts\python.exe run_freecad.py build_flange_fc.py output/Flange_D100_h60.FCStd

from freecad_core import (
    DT_NORMAL,
    PLANE_XZ,
    STYLE_AXIS,
    STYLE_MAIN,
    FreeCadPart,
)

VARIABLES = {
    "D": (100.0, "Наружный диаметр фланца"),
    "s": (12.0, "Толщина фланца"),
    "h": (60.0, "Высота"),
    "ds": (50.0, "Диаметр ступицы"),
    "o1": (30.0, "Отверстие сквозное"),
    "o2": (10.0, "Отверстие крепёжное"),
    "do": (75.0, "Диаметр центров отверстий"),
}

EXPECTED_VOLUME = 142314.15


def build_flange(part: FreeCadPart):
    D = VARIABLES["D"][0]
    s = VARIABLES["s"][0]
    h = VARIABLES["h"][0]
    ds = VARIABLES["ds"][0]
    o1 = VARIABLES["o1"][0]
    o2 = VARIABLES["o2"][0]
    do = VARIABLES["do"][0]

    # Шаг 1: Фланец на плоскости XZ -> Pad в +Y на s
    def sketch_flange(b):
        b.circle(0, 0, D / 2.0, style=STYLE_MAIN).dim_diam(0, 0, D / 2.0, var_name="D")

    sk1 = part.create_sketch(plane=PLANE_XZ, draw_fn=sketch_flange)
    part.extrude(sk1, depth=s, direction=DT_NORMAL, expr="s")

    # Шаг 2: Ступица на грани Y=s -> Pad на h-s
    face_hub = part.get_planar_face_at(axis="y", coord=s)

    def sketch_hub(b):
        b.circle(0, 0, ds / 2.0, style=STYLE_MAIN).dim_diam(
            0, 0, ds / 2.0, var_name="ds"
        )

    sk2 = part.create_sketch_on_face(face_hub, draw_fn=sketch_hub)
    part.extrude(sk2, depth=h - s, direction=DT_NORMAL, expr="h-s")

    # Шаг 3: Центральное сквозное отверстие от Y=h
    face_top = part.get_planar_face_at(axis="y", coord=h, mode="max")

    def sketch_center_hole(b):
        b.circle(0, 0, o1 / 2.0, style=STYLE_MAIN).dim_diam(
            0, 0, o1 / 2.0, var_name="o1"
        )

    sk3 = part.create_sketch_on_face(face_top, draw_fn=sketch_center_hole)
    part.cut(sk3, through_all=True)

    # Шаг 4: Одно крепёжное отверстие на грани фланца Y=s
    face_flange = part.get_planar_face_at(axis="y", coord=s, mode="max")

    def sketch_bolt_hole(b):
        b.circle(0, 0, do / 2.0, style=STYLE_AXIS).dim_diam(
            0, 0, do / 2.0, var_name="do"
        )
        b.circle(0, do / 2.0, o2 / 2.0, style=STYLE_MAIN).dim_diam(
            0, do / 2.0, o2 / 2.0, var_name="o2"
        )

    sk4 = part.create_sketch_on_face(face_flange, draw_fn=sketch_bolt_hole)
    cut_hole = part.cut(sk4, depth=s, direction=DT_NORMAL, expr="s")

    # Шаг 5: Круговой массив (4 отверстия вокруг оси Y)
    axis_y = part.create_axis_by_2_planes("xy", "yz")
    part.circular_pattern(features=[cut_hole], axis_ent=axis_y, count=4, angle=360.0)

    # Валидация
    part.assert_bbox(exp_x=D, exp_y=h, exp_z=D, tol=0.1)
    vol = part.volume()
    if abs(vol - EXPECTED_VOLUME) > 0.5:
        raise ValueError(f"[FAIL VOLUME] Объём {vol:.2f} != {EXPECTED_VOLUME:.2f} мм³!")
    print(f"[OK VOLUME FREECAD] Объём совпал с эталоном: {vol:.2f} мм³")
    return part


# ВАЖНО: FreeCADCmd.exe импортирует скрипт как модуль (__name__ != "__main__"), поэтому вызываем напрямую
_part = FreeCadPart(name="Flange_FC")
try:
    _part.create_variables_from_dict(VARIABLES)
    build_flange(_part)
    _part.save("output/Flange_D100_h60.FCStd")
    print("[SUCCESS FREECAD] output/Flange_D100_h60.FCStd и .step сохранены")
finally:
    _part.close()
