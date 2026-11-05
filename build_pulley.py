# build_pulley.py — Параметрический направляющий ролик под профильную ленту
# Соответствует эталону example/pulley/pulley_example.m3d
# Конструкция: один эскиз вращения (включает отверстие под вал и ручей) +
# отверстия облегчения (массив 6x) + шпоночный паз

from kompas_core import DT_NORMAL, DT_REVERSE, STYLE_MAIN, STYLE_AXIS, KompasPart
import math


def build_pulley():
    part = KompasPart(name="Направляющий ролик", visible=True)

    # ------------------------------------------------------------------
    # 1. Таблица пользовательских переменных конструктора (по эталону pulley_example)
    # ------------------------------------------------------------------
    D = 80.0   # Наружный диаметр ролика
    b = 24.0   # Ширина ролика
    bp = 14.0  # Ширина паза (ручья)
    dp = 68.0  # Диаметр дна паза
    d = 20.0   # Диаметр отверстия под вал
    do = 12.0  # Диаметр отверстий облегчения
    Do = 44.0  # Диаметр центров отверстий облегчения
    bsp = 6.0  # Ширина шпоночного паза
    hsp = 2.8  # Высота шпоночного паза

    part.create_variables_from_dict({
        "D": (D, "Наружный диаметр ролика"),
        "b": (b, "Ширина ролика"),
        "bp": (bp, "Ширина паза (ручья)"),
        "dp": (dp, "Диаметр дна паза"),
        "d": (d, "Диаметр отверстия под вал"),
        "do": (do, "Диаметр отверстий облегчения"),
        "Do": (Do, "Диаметр центров отверстий облегчения"),
        "bsp": (bsp, "Ширина шпоночного паза"),
        "hsp": (hsp, "Высота шпоночного паза"),
    })

    # ------------------------------------------------------------------
    # Шаг 1-2: Базовое тело ролика — ОДИН эскиз вращения на XY + part.revolve
    # Ось вращения — ось Y от 0 до b (корпус сидит на XY плоскости)
    # Контур ЗАМКНУТЫЙ, лежит по одну сторону от оси (X >= d/2 > 0)
    # Включает отверстие под вал (внутренний радиус d/2) и ручей на внешнем диаметре
    # Координаты профиля (по эталону):
    #   (d/2, 0) -> (d/2, b) -> (D/2, b) -> (D/2, b/2+bp/2) ->
    #   (dp/2, b/2+bp/2) -> (dp/2, b/2-bp/2) -> (D/2, b/2-bp/2) ->
    #   (D/2, 0) -> замыкание к (d/2, 0)
    # ------------------------------------------------------------------
    R_outer = D / 2.0
    R_groove_bottom = dp / 2.0
    R_bore = d / 2.0
    half_bp = bp / 2.0
    y_groove_top = b / 2.0 + half_bp
    y_groove_bottom = b / 2.0 - half_bp

    sk1 = part.create_sketch(
        "xy",
        lambda sk: (
            # Осевая линия для вращения — ось Y (горизонтальная в плоскости XY), стиль=3 (осевая)
            sk.axis(0, 0, 0, b),
            # Замкнутый контур профиля ролика (лежит по одну сторону от оси — X >= d/2 > 0)
            sk.line(R_bore, 0, R_bore, b),                    # внутренний радиус снизу вверх (стенка отверстия под вал)
            sk.line(R_bore, b, R_outer, b),                   # верх внешний
            sk.line(R_outer, b, R_outer, y_groove_top),       # стойка до ручья (сверху)
            sk.line(R_outer, y_groove_top, R_groove_bottom, y_groove_top),  # дно ручья (вверху)
            sk.line(R_groove_bottom, y_groove_top, R_groove_bottom, y_groove_bottom),  # внутренняя стенка ручья
            sk.line(R_groove_bottom, y_groove_bottom, R_outer, y_groove_bottom),  # дно ручья (внизу)
            sk.line(R_outer, y_groove_bottom, R_outer, 0),    # стойка после ручья (снизу)
            sk.line(R_outer, 0, R_bore, 0),                   # низ внешний к внутреннему радиусу (замыкание)
            # Управляющие размеры
            sk.dim_hor(-15, 0, R_outer, var_name="D/2"),
            sk.dim_hor(R_groove_bottom + 5, 0, R_groove_bottom, var_name="dp/2"),
            sk.dim_hor(R_bore + 5, 0, R_bore, var_name="d/2"),
            sk.dim_ver(R_outer + 5, y_groove_bottom, y_groove_top, var_name="bp"),
            sk.dim_ver(-15, 0, b, var_name="b"),
        ),
    )
    part.revolve(sk1, angle=360.0, cut=False)

    # ------------------------------------------------------------------
    # Шаг 3-4: Вырез одного отверстия облегчения do на радиусе Do/2
    # Эскиз на передней торцевой грани (Y = b)
    # ------------------------------------------------------------------
    face_front = part.get_planar_face_at(axis="y", coord=b)
    sk2 = part.create_sketch_on_face(
        face_front,
        lambda sk: (
            sk.circle(Do / 2.0, 0, do / 2.0, style=STYLE_MAIN),
            sk.dim_diam(Do / 2.0, 0, do / 2.0, angle_deg=45.0, var_name="do"),
            sk.dim_hor(0, 0, Do / 2.0, var_name="Do/2"),
        ),
    )
    cut_light = part.cut(sk2, depth=b, direction=DT_NORMAL, expr="b", through_all=True)

    # ------------------------------------------------------------------
    # Шаг 5: Массив 6 отверстий облегчения по цилиндрической грани отверстия под вал
    # ------------------------------------------------------------------
    cyl_face = part.get_cylindrical_face(radius=R_bore)
    part.circular_pattern(features=[cut_light], axis_ent=cyl_face, count=6, angle=360.0)

    # ------------------------------------------------------------------
    # Шаг 6-7: Шпоночный паз на передней грани
    # Прямоугольник: X от -bsp/2 до bsp/2, Z от d/2 до d/2+hsp
    # Нижние углы ключа лежат на окружности радиуса d/2 (геометрия шпоночного паза)
    # key_bottom_z = sqrt((d/2)^2 - (bsp/2)^2) ≈ 9.54 (как в эталоне)
    # ------------------------------------------------------------------
    key_bottom_z = math.sqrt((d / 2.0) ** 2 - (bsp / 2.0) ** 2)  # ~9.54
    key_top_z = d / 2.0 + hsp  # 12.8 = d/2+hsp

    sk3 = part.create_sketch_on_face(
        face_front,
        lambda sk: (
            sk.line(-bsp / 2.0, key_bottom_z, bsp / 2.0, key_bottom_z),   # низ паза
            sk.line(bsp / 2.0, key_bottom_z, bsp / 2.0, key_top_z),        # правая стенка паза
            sk.line(bsp / 2.0, key_top_z, -bsp / 2.0, key_top_z),          # верх паза
            sk.line(-bsp / 2.0, key_top_z, -bsp / 2.0, key_bottom_z),      # левая стенка паза
            # Управляющие размеры
            sk.dim_hor(-15, -bsp / 2.0, bsp / 2.0, var_name="bsp"),
            sk.dim_ver(Do / 2.0 + 10, key_bottom_z, key_top_z, var_name="d/2+hsp"),
        ),
    )
    part.cut(sk3, depth=b, direction=DT_NORMAL, expr="b", through_all=True)

    # ------------------------------------------------------------------
    # Тройной контур самопроверки
    # ------------------------------------------------------------------
    part.rebuild()
    part.assert_bbox(D, b, D, tol=0.1)
    part.save_screenshot("output/pulley.png")
    part.save("output/pulley.m3d")


if __name__ == "__main__":
    build_pulley()