# build_die_plate.py — Параметрическая нижняя плита штампа/приспособления
from kompas_core import DT_NORMAL, DT_REVERSE, STYLE_MAIN, STYLE_THIN, KompasPart


def build_die_plate():
    part = KompasPart(name="Нижняя плита штампа", visible=True)

    # ------------------------------------------------------------------
    # 1. Таблица пользовательских переменных конструктора
    # ------------------------------------------------------------------
    L = 160.0   # Длина плиты
    W = 120.0   # Ширина плиты
    H = 25.0    # Толщина плиты
    a_win = 60.0   # Длина провального окна
    b_win = 40.0   # Ширина провального окна
    d_col = 20.0   # Диаметр отверстий под направляющие колонки
    Lx = 120.0     # Межосевое расстояние колонок по X
    Ly = 80.0      # Межосевое расстояние колонок по Y

    part.create_variables_from_dict({
        "L": (L, "Длина плиты"),
        "W": (W, "Ширина плиты"),
        "H": (H, "Толщина плиты"),
        "a_win": (a_win, "Длина провального окна"),
        "b_win": (b_win, "Ширина провального окна"),
        "d_col": (d_col, "Диаметр отверстий под направляющие колонки"),
        "Lx": (Lx, "Межосевое расстояние колонок по X"),
        "Ly": (Ly, "Межосевое расстояние колонок по Y"),
    })

    # ------------------------------------------------------------------
    # Шаг 1-2: Базовая плита — симметричный прямоугольник L x W на XY,
    # выдавливание на толщину H
    # ------------------------------------------------------------------
    sk1 = part.create_sketch(
        "xy",
        lambda sk: (
            sk.rect(0, 0, L, W, centered=True),
            # Размер по верхнему краю прямоугольника (y = W/2)
            sk.dim_hor(W / 2.0 + 10.0, -L / 2.0, L / 2.0, var_name="L", y_pts=W / 2.0),
            # Размер по правому краю прямоугольника (x = L/2)
            sk.dim_ver(L / 2.0 + 10.0, -W / 2.0, W / 2.0, var_name="W", x_pts=L / 2.0),
        ),
    )
    part.extrude(sk1, depth=H, direction=DT_NORMAL, expr="H")

    # ------------------------------------------------------------------
    # Шаг 3-4: Провальное окно a_win x b_win в центре плиты, сквозной вырез
    # ------------------------------------------------------------------
    face_front = part.get_planar_face_at(axis="z", coord=H)
    sk2 = part.create_sketch_on_face(
        face_front,
        lambda sk: (
            sk.rect(0, 0, a_win, b_win, centered=True),
            # Размер по верхнему краю окна (y = b_win/2)
            sk.dim_hor(b_win / 2.0 + 10.0, -a_win / 2.0, a_win / 2.0, var_name="a_win", y_pts=b_win / 2.0),
            # Размер по правому краю окна (x = a_win/2)
            sk.dim_ver(a_win / 2.0 + 10.0, -b_win / 2.0, b_win / 2.0, var_name="b_win", x_pts=a_win / 2.0),
        ),
    )
    part.cut(sk2, depth=H, direction=DT_NORMAL, expr="H", through_all=True)

    # ------------------------------------------------------------------
    # Шаг 5-6: 4 сквозных отверстия диаметром d_col по углам
    # Координаты центров: (±Lx/2, ±Ly/2)
    # ------------------------------------------------------------------
    face_front = part.get_planar_face_at(axis="z", coord=H)
    sk3 = part.create_sketch_on_face(
        face_front,
        lambda sk: (
            # 4 отверстия колонок d_col по углам (±Lx/2, ±Ly/2)
            sk.circle(Lx / 2.0, Ly / 2.0, d_col / 2.0, style=STYLE_MAIN),
            sk.circle(-Lx / 2.0, Ly / 2.0, d_col / 2.0, style=STYLE_MAIN),
            sk.circle(Lx / 2.0, -Ly / 2.0, d_col / 2.0, style=STYLE_MAIN),
            sk.circle(-Lx / 2.0, -Ly / 2.0, d_col / 2.0, style=STYLE_MAIN),
            # Конструктивные оси для позиционирования отверстия (первая четверть)
            sk.line(0, 0, Lx / 2.0, 0, style=STYLE_THIN),       # горизонтальная ось X к центру отверстия
            sk.line(Lx / 2.0, 0, Lx / 2.0, Ly / 2.0, style=STYLE_THIN),  # вертикальная ось Y к центру отверстия
            # Управляющие размеры (ссылаются на конструктивные линии)
            sk.dim_hor(Ly / 2.0 + 10.0, 0, Lx / 2.0, var_name="Lx/2", y_pts=0.0),
            sk.dim_ver(Lx / 2.0 + 10.0, 0, Ly / 2.0, var_name="Ly/2", x_pts=Lx / 2.0),
            sk.dim_diam(Lx / 2.0, Ly / 2.0, d_col / 2.0, var_name="d_col"),
        ),
    )
    part.cut(sk3, depth=H, direction=DT_NORMAL, expr="H", through_all=True)

    # ------------------------------------------------------------------
    # Тройной контур самопроверки
    # ------------------------------------------------------------------
    part.rebuild()
    part.assert_bbox(L, W, H, tol=0.1)
    part.save_screenshot("output/die_plate.png")
    part.save("output/die_plate.m3d")


if __name__ == "__main__":
    build_die_plate()
