# build_flange.py — Эталонный скрипт построения параметрической фланцевой втулки (по образцу flange_example.m3d)
from kompas_core import DT_NORMAL, DT_REVERSE, STYLE_AXIS, STYLE_MAIN, KompasPart


def build_flange():
    part = KompasPart(name="Деталь", visible=True)

    # 1. Таблица пользовательских переменных конструктора
    D, s, h, ds, o1, o2, do = 100.0, 12.0, 60.0, 50.0, 30.0, 10.0, 75.0
    part.create_variables_from_dict(
        {
            "D": (D, "Наружный диаметр фланца"),
            "s": (s, "Толщина фланца"),
            "h": (h, "Высота"),
            "ds": (ds, "Диаметр ступицы"),
            "o1": (o1, "Отверстие сквозное"),
            "o2": (o2, "Отверстие крепёжное"),
            "do": (do, "Диаметр центров отверстий"),
        }
    )

    # Шаг 1 и 2: Эскиз 1 на плоскости ZX (XZ) -> Выдавливание диска фланца на высоту s
    sk1 = part.create_sketch(
        "xz",
        lambda b: (
            b.circle(0, 0, D / 2.0, style=STYLE_MAIN),
            b.dim_diam(0, 0, D / 2.0, angle_deg=45.0, var_name="D"),
        ),
    )
    part.extrude(sk1, depth=s, direction=DT_NORMAL, expr="s")

    # Шаг 3 и 4: Эскиз 2 на верхней грани фланца (Y = s) -> Выдавливание ступицы на высоту (h - s)
    face_flange_top = part.get_planar_face_at(axis="y", coord=s)
    sk2 = part.create_sketch_on_face(
        face_flange_top,
        lambda b: (
            b.circle(0, 0, ds / 2.0, style=STYLE_MAIN),
            b.dim_diam(0, 0, ds / 2.0, angle_deg=45.0, var_name="ds"),
        ),
    )
    part.extrude(sk2, depth=h - s, direction=DT_NORMAL, expr="h-s")

    # Шаг 5 и 6: Эскиз 3 на верхнем торце ступицы (Y = h) -> Сквозной вырез центрального отверстия o1
    face_hub_top = part.get_planar_face_at(axis="y", coord=h)
    sk3 = part.create_sketch_on_face(
        face_hub_top,
        lambda b: (
            b.circle(0, 0, o1 / 2.0, style=STYLE_MAIN),
            b.dim_diam(0, 0, o1 / 2.0, angle_deg=45.0, var_name="o1"),
        ),
    )
    part.cut(sk3, depth=h, direction=DT_NORMAL, through_all=True)

    # Шаг 7 и 8: Эскиз 4 на НИЖНЕЙ грани фланца (Y = 0) -> Вырез одного крепежного отверстия o2 на глубину s
    # Линейный размер do/2 от начала координат до центра отверстия (dim_ver) + диаметральный размер o2
    face_flange_bottom = part.get_planar_face_at(axis="y", coord=0.0)
    sk4 = part.create_sketch_on_face(
        face_flange_bottom,
        lambda b: (
            b.circle(0, do / 2.0, o2 / 2.0, style=STYLE_MAIN),
            # dim_ver: вертикальный размер от (0,0) до (0, do/2), линия размера смещена влево на -10
            b.dim_ver(-10.0, 0, do / 2.0, var_name="do/2"),
            b.dim_diam(0, do / 2.0, o2 / 2.0, angle_deg=135.0, var_name="o2"),
        ),
    )
    # ВАЖНО: Эскиз на НИЖНЕЙ грани фланца (Y=0), вырез идёт ВНУТРЬ фланца (направление DT_NORMAL)
    cut_hole = part.cut(sk4, depth=s, direction=DT_NORMAL, expr="s")

    # Шаг 9: Массив по концентрической сетке (4 отверстия вокруг цилиндрической грани отверстия o1)
    cyl_face = part.get_cylindrical_face(radius=o1 / 2.0)
    part.circular_pattern(features=[cut_hole], axis_ent=cyl_face, count=4, angle=360.0)

    # Тройной контур самопроверки
    part.rebuild()
    part.assert_bbox(D, h, D, tol=0.1)
    part.save_screenshot("output/flange.png")
    part.save("output/flange.m3d")


if __name__ == "__main__":
    build_flange()
