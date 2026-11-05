# build_pulley.py — Параметрический направляющий ролик под профильную ленту (метод вращения)
from kompas_core import DT_NORMAL, DT_REVERSE, STYLE_MAIN, STYLE_AXIS, KompasPart


def build_pulley():
    part = KompasPart(name="Направляющий ролик", visible=True)

    # 1. Таблица пользовательских переменных конструктора
    D = 80.0
    B = 24.0
    d_axis = 20.0
    d_groove = 68.0
    b_groove = 14.0
    d_light = 12.0
    D_light = 44.0

    part.create_variables_from_dict(
        {
            "D": (D, "Наружный диаметр ролика"),
            "B": (B, "Общая ширина ролика"),
            "d_axis": (d_axis, "Посадочное отверстие под ось"),
            "d_groove": (d_groove, "Диаметр дна ручья под ленту"),
            "b_groove": (b_groove, "Ширина ручья под ленту"),
            "d_light": (d_light, "Диаметр отверстий облегчения"),
            "D_light": (D_light, "Диаметр центров отверстий облегчения"),
        }
    )

    # ------------------------------------------------------------------
    # Шаг 1-2: Базовое тело ролика с ручьем — ОДИН эскиз вращения на XY + part.revolve
    # Профиль сечения включает ручей на внешнем диаметре
    # Контур: ЗАМКНУТЫЙ контур профиля (лежит по одну сторону от оси — X >= 0)
    # Ось вращения — ось Y (горизонтальная в плоскости XY), ширина ролика лежит по Y
    # ------------------------------------------------------------------
    half_B = B / 2.0
    half_b_groove = b_groove / 2.0
    R_outer = D / 2.0
    R_groove_bottom = d_groove / 2.0

    sk1 = part.create_sketch(
        "xy",
        lambda b: (
            # Осевая линия для вращения — ось Y (горизонтальная в плоскости XY), стиль=3 (осевая)
            b.axis(0, -half_B, 0, half_B),
            # Замкнутый контур профиля ролика (лежит по одну сторону от оси — X >= 0)
            # Координаты в плоскости XY: X = радиус, Y = ширина
            b.line(0, -half_B, R_outer, -half_B),                    # низ внешний
            b.line(R_outer, -half_B, R_outer, -half_b_groove),       # стойка до ручья
            b.line(R_outer, -half_b_groove, R_groove_bottom, -half_b_groove),  # дно ручья (внизу)
            b.line(R_groove_bottom, -half_b_groove, R_groove_bottom, half_b_groove),  # внутренняя стенка ручья
            b.line(R_groove_bottom, half_b_groove, R_outer, half_b_groove),  # дно ручья (вверху)
            b.line(R_outer, half_b_groove, R_outer, half_B),         # стойка после ручья
            b.line(R_outer, half_B, 0, half_B),                      # верх внешний к центру
            b.line(0, half_B, 0, -half_B),                           # замыкание контура ПО ОСИ (X=0)
            # Управляющие размеры
            b.dim_hor(-15, 0, R_outer, var_name="D/2"),
            b.dim_ver(R_outer + 5, -half_B, -half_b_groove, var_name="(B-b_groove)/2"),
            b.dim_ver(R_outer + 5, -half_b_groove, half_b_groove, var_name="b_groove"),
            b.dim_hor(R_groove_bottom - 5, 0, R_groove_bottom, var_name="d_groove/2"),
            b.dim_ver(-15, -half_B, half_B, var_name="B"),
        ),
    )
    part.revolve(sk1, angle=360.0, cut=False)

    # ------------------------------------------------------------------
    # Шаг 3-4: Сквозной вырез центрального отверстия d_axis
    # Эскиз на передней торцевой грани (Y = B/2 = half_B)
    # ------------------------------------------------------------------
    face_front = part.get_planar_face_at(axis="y", coord=half_B)
    sk2 = part.create_sketch_on_face(
        face_front,
        lambda b: (
            b.circle(0, 0, d_axis / 2.0, style=STYLE_MAIN),
            b.dim_diam(0, 0, d_axis / 2.0, angle_deg=45.0, var_name="d_axis"),
        ),
    )
    part.cut(sk2, depth=B, direction=DT_NORMAL, through_all=True)

    # ------------------------------------------------------------------
    # Шаг 5-6: Одно отверстие облегчения на передней грани
    # ------------------------------------------------------------------
    sk3 = part.create_sketch_on_face(
        face_front,
        lambda b: (
            b.circle(D_light / 2.0, 0, d_light / 2.0, style=STYLE_MAIN),
            b.dim_diam(D_light / 2.0, 0, d_light / 2.0, angle_deg=45.0, var_name="d_light"),
            b.dim_hor(0, 0, D_light / 2.0, var_name="D_light/2"),
        ),
    )
    cut_light = part.cut(sk3, depth=B, direction=DT_NORMAL, expr="B", through_all=True)

    # ------------------------------------------------------------------
    # Шаг 7: Массив 6 отверстий облегчения по цилиндрической грани посадочного отверстия
    # ------------------------------------------------------------------
    cyl_face = part.get_cylindrical_face(radius=d_axis / 2.0)
    part.circular_pattern(features=[cut_light], axis_ent=cyl_face, count=6, angle=360.0)

    # ------------------------------------------------------------------
    # Тройной контур самопроверки
    # ------------------------------------------------------------------
    part.rebuild()
    part.assert_bbox(D, B, D, tol=0.1)
    part.save_screenshot("output/pulley.png")
    part.save("output/pulley.m3d")


if __name__ == "__main__":
    build_pulley()