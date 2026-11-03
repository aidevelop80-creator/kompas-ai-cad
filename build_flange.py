# build_flange.py — Эталонное построение фланцевой втулки (по стандарту конструктора)
import os
from kompas_core import KompasPart, SketchBuilder, PLANE_XY, PLANE_XZ, DT_NORMAL, DT_REVERSE

# 1. Только чистые конструкторские переменные чертежа (никаких лишних r, R, Rk, h_cut!)
VARS = {
    "D":  (100.0, "Наружный диаметр фланца"),
    "s":  (12.0,  "Толщина фланца"),
    "h":  (60.0,  "Высота"),
    "ds": (50.0,  "Диаметр ступицы"),
    "o1": (30.0,  "Отверстие сквозное"),
    "o2": (10.0,  "Отверстие крепёжное"),
    "do": (75.0,  "Диаметр центров отверстий"),
}


def main():
    D, s, h, ds, o1, o2, do = [VARS[k][0] for k in ("D", "s", "h", "ds", "o1", "o2", "do")]
    r_in = o1 / 2.0      # 15.0 мм
    r_hub = ds / 2.0     # 25.0 мм
    r_flange = D / 2.0   # 50.0 мм
    r_bolt_circle = do / 2.0  # 37.5 мм
    r_bolt = o2 / 2.0    # 5.0 мм

    part = KompasPart(name="Деталь", visible=True)

    # 1. Создаем таблицу переменных с русскими комментариями
    part.create_variables_from_dict(VARS)

    # 2. Эскиз:1 на Синей плоскости XY — сразу Г-образное сечение с центральным отверстием!
    # Ось вращения — вертикальная ось Y (от X=0, Y=0 до X=0, Y=h), фланец лежит внизу на базе Y=0..s
    def draw_revolve_section(b: SketchBuilder):
        b.axis(0, 0, 0, h)  # Вертикальная ось вращения вдоль Y
        b.polygon([
            (r_in, 0),          # Внутренняя кромка низа
            (r_flange, 0),      # Наружная кромка фланца внизу
            (r_flange, s),      # Верхняя полка фланца
            (r_hub, s),         # Переход на ступицу
            (r_hub, h),         # Верхний торец ступицы
            (r_in, h),          # Внутренняя кромка верха
        ], closed=True)

        # Проставляем 5 управляющих размеров с формулами из таблицы переменных:
        b.dim_hor(y_line=-18.0, x1=0, x2=r_flange, var_name="D/2",  y_pts=0)
        b.dim_hor(y_line=-10.0, x1=0, x2=r_in,     var_name="o1/2", y_pts=0)
        b.dim_hor(y_line=28.0,  x1=0, x2=r_hub,    var_name="ds/2", y_pts=h)
        b.dim_ver(x_line=r_flange + 10.0, y1=0, y2=s, var_name="s", x_pts=r_flange)
        b.dim_ver(x_line=r_flange + 22.0, y1=0, y2=h, var_name="h", x_pts=r_hub)

    sk1 = part.create_sketch(PLANE_XY, draw_revolve_section)
    part.revolve(sk1, angle=360.0, cut=False)

    # 3. Эскиз:2 на Зеленой плоскости XZ (основание фланца Y=0) — ОДНО крепежное отверстие!
    def draw_single_hole(b: SketchBuilder):
        b.line(0, 0, 0, r_bolt_circle, style=3)  # Осевая линия к центру отверстия
        b.circle(0, r_bolt_circle, r_bolt)       # Одно отверстие ⌀10 на радиусе 37.5 мм
        b.dim_diam(0, r_bolt_circle, r_bolt, angle_deg=35.0, var_name="o2")
        b.dim_ver(x_line=-15.0, y1=0, y2=r_bolt_circle, var_name="do/2", x_pts=0)

    sk2 = part.create_sketch(PLANE_XZ, draw_single_hole)
    # Вырезаем строго на толщину фланца s (с привязкой выражения 's' к Расстоянию 1)
    try:
        cut_hole = part.cut(sk2, depth=s, direction=DT_NORMAL, expr="s")
    except RuntimeError:
        cut_hole = part.cut(sk2, depth=s, direction=DT_REVERSE, expr="s")

    # 4. Массив по концентрической сетке:1 (4 отверстия на 360 градусов вокруг оси вращения Y)
    axis_y = part.create_axis_by_2_planes("xy", "yz")
    part.circular_pattern([cut_hole], axis_ent=axis_y, count=4, angle=360.0)

    # 5. Контроль габаритов и сохранение
    part.assert_bbox(D, h, D)
    os.makedirs("output", exist_ok=True)
    part.save("output/flange.m3d")
    part.save_screenshot("output/flange.png")
    print("[SUCCESS] Эталонная фланцевая втулка построена!")


if __name__ == "__main__":
    main()