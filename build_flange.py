# build_flange.py — Параметрическая фланцевая втулка (эталон: example/flange/flange_example.m3d)
# Запуск: .venv\Scripts\python.exe build_flange.py

from kompas_core import (
    DT_NORMAL,
    OBJ_FACE,
    PLANE_XZ,
    STYLE_AXIS,
    STYLE_MAIN,
    KompasPart,
    _wrap,
)
from sdk_ref import kompas_api5_v16 as K5

# ========================= КОНСТРУКТОРСКИЕ ПАРАМЕТРЫ =========================
VARIABLES = {
    "D": (100.0, "Наружный диаметр фланца"),
    "s": (12.0, "Толщина фланца"),
    "h": (60.0, "Высота"),
    "ds": (50.0, "Диаметр ступицы"),
    "o1": (30.0, "Отверстие сквозное"),
    "o2": (10.0, "Отверстие крепёжное"),
    "do": (75.0, "Диаметр центров отверстий"),
}

EXPECTED_VOLUME = 142314.15  # мм³ (из flange_example_blueprint.md)


def _find_flange_top_face(part: KompasPart, s_val: float, d_val: float):
    """Находит верхнюю кольцевую грань фланца на Y=s с наружным габаритом D."""
    part_ents = _wrap(K5.ksEntityCollection, part.part.EntityCollection(OBJ_FACE))
    for i in range(part_ents.GetCount()):
        ent = _wrap(K5.ksEntity, part_ents.GetByIndex(i))
        fdef = _wrap(K5.ksFaceDefinition, ent.GetDefinition())
        if not fdef or not fdef.IsPlanar():
            continue
        bbox = part._get_face_bbox(fdef)
        if not bbox:
            continue
        y_min, y_max = bbox[1], bbox[4]
        dx = bbox[3] - bbox[0]
        dz = bbox[5] - bbox[2]
        if (
            abs(y_min - s_val) < 0.5
            and abs(y_max - s_val) < 0.5
            and abs(dx - d_val) < 1.0
            and abs(dz - d_val) < 1.0
        ):
            return ent
    return part.get_planar_face_at(axis="y", coord=s_val, mode="max")


def build_flange(part: KompasPart):
    """Построение фланцевой втулки по эталонной модели flange_example.m3d."""
    D = VARIABLES["D"][0]
    s = VARIABLES["s"][0]
    h = VARIABLES["h"][0]
    ds = VARIABLES["ds"][0]
    o1 = VARIABLES["o1"][0]
    o2 = VARIABLES["o2"][0]
    do = VARIABLES["do"][0]

    # --- Шаг 1: Эскиз и выдавливание фланца на плоскости ZX ---
    def sketch_flange(b):
        b.circle(0, 0, D / 2.0, style=STYLE_MAIN).dim_diam(0, 0, D / 2.0, var_name="D")

    sk1 = part.create_sketch(plane=PLANE_XZ, draw_fn=sketch_flange)
    part.extrude(sk1, depth=s, direction=DT_NORMAL, expr="s")

    # --- Шаг 2: Эскиз и выдавливание ступицы на торце фланца (Y=s) ---
    face_hub = part.get_planar_face_at(axis="y", coord=s)

    def sketch_hub(b):
        b.circle(0, 0, ds / 2.0, style=STYLE_MAIN).dim_diam(
            0, 0, ds / 2.0, var_name="ds"
        )

    sk2 = part.create_sketch_on_face(face_hub, draw_fn=sketch_hub)
    part.extrude(sk2, depth=h - s, direction=DT_NORMAL, expr="h-s")

    # --- Шаг 3: Сквозное центральное отверстие от верхнего торца ступицы (Y=h) ---
    face_top = part.get_planar_face_at(axis="y", coord=h, mode="max")

    def sketch_center_hole(b):
        b.circle(0, 0, o1 / 2.0, style=STYLE_MAIN).dim_diam(
            0, 0, o1 / 2.0, var_name="o1"
        )

    sk3 = part.create_sketch_on_face(face_top, draw_fn=sketch_center_hole)
    part.cut(sk3, through_all=True)

    # --- Шаг 4: Одно крепёжное отверстие на осевой делительной окружности ---
    face_flange_top = _find_flange_top_face(part, s_val=s, d_val=D)

    def sketch_bolt_hole(b):
        # Делительная окружность — осевая (STYLE_AXIS), чтобы не резалась контуром
        b.circle(0, 0, do / 2.0, style=STYLE_AXIS).dim_diam(
            0, 0, do / 2.0, var_name="do"
        )
        # Одно базовое крепёжное отверстие (привязывается на кривую и по вертикали автоматически)
        b.circle(0, do / 2.0, o2 / 2.0, style=STYLE_MAIN).dim_diam(
            0, do / 2.0, o2 / 2.0, var_name="o2"
        )

    sk4 = part.create_sketch_on_face(face_flange_top, draw_fn=sketch_bolt_hole)
    cut_ent = part.cut(sk4, depth=s, direction=DT_NORMAL, expr="s")

    # --- Шаг 5: Массив по концентрической сетке (4 отверстия) ---
    axis_y = part.create_axis_by_2_planes("xy", "yz")
    part.circular_pattern(
        features=[cut_ent],
        axis_ent=axis_y,
        count=4,
        angle=360.0,
    )

    # --- Финальная валидация габаритов и объёма ---
    part.assert_bbox(exp_x=D, exp_y=h, exp_z=D, tol=0.1)
    vol = part.volume()
    if abs(vol - EXPECTED_VOLUME) > 0.5:
        raise ValueError(
            f"[FAIL VOLUME] Объём {vol:.2f} мм³ отличается от эталона {EXPECTED_VOLUME:.2f} мм³!"
        )
    print(f"[OK VOLUME] Объём точно соответствует эталону: {vol:.2f} мм³")
    return part


if __name__ == "__main__":
    part = KompasPart(name="Flange", visible=True)
    part.create_variables_from_dict(VARIABLES)
    try:
        build_flange(part)
        part.save("output/Flange_D100_h60.m3d")
        part.save_screenshot("output/Flange_D100_h60.png")
        print("[SUCCESS] Деталь Flange_D100_h60 построена и провалидирована")
    except Exception:
        part.close()
        raise
