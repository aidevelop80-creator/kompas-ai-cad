# build_uleyma_lid.py — Построение параметрической детали "Крышка" (Uleyma-T.01.01.02_Крышка)
# Листовая деталь с 4 сгибами, образующая коробочную форму с вырезами и отверстиями
# Реализовано через обычные операции выдавливания/вырезания для совместимости с API5
# Запуск: .\.venv\Scripts\python.exe build_uleyma_lid.py

from kompas_core import (
    KompasPart,
    PLANE_XY,
    DT_NORMAL,
    DT_REVERSE,
    DT_BOTH,
)

def main():
    # ============================================================
    # 1. СОЗДАНИЕ ДЕТАЛИ И ПЕРЕМЕННЫХ
    # ============================================================
    part = KompasPart(name="Uleyma-T.01.01.02_Крышка", visible=True)

    # Конструкторские переменные (ТОЛЬКО основные размеры с чертежа)
    variables = {
        "L_base": (80.0, "Длина основания крышки (внутренняя)"),
        "W_base": (50.0, "Ширина основания крышки (внутренняя)"),
        "TOL": (0.2, "Технологический припуск на размер основания (±0.1 с каждой стороны)"),
        "t": (2.0, "Толщина листа (Sheet Metal Thickness)"),
        "H_flange": (16.0, "Высота вертикальных фланцев (критических стенок)"),
        "R_bend": (2.0, "Радиус сгиба (внутренний)"),
        "K_factor": (0.4, "Коэффициент нейтрального слоя"),
        "BA": (10.0, "Величина сгиба (Bend Allowance)"),
        "BD": (0.0, "Уменьшение сгиба (Bend Deduction)"),
        "Bend_Angle": (90.0, "Угол сгиба"),
        "Relief_H": (0.0, "Глубина освобождения сгиба"),
        "Relief_W": (3.0, "Ширина освобождения сгиба"),
        # Размеры отверстий и вырезов с чертежа
        "D_rect_w": (12.1, "Ширина прямоугольного выреза на верхнем фланце"),
        "D_rect_h": (6.0, "Высота прямоугольного выреза на верхнем фланце"),
        "D_large": (12.1, "Диаметр крупных отверстий на верхнем фланце"),
        "D_med": (8.0, "Диаметр средних отверстий на верхнем фланце"),
        "D_small": (6.0, "Диаметр малых отверстий на верхнем фланце"),
        "D_tiny": (3.6, "Диаметр мелких отверстий на верхнем фланце"),
        "D_vtiny": (2.9, "Диаметр очень мелких отверстий на верхнем фланце"),
        "D_side_hole": (3.6, "Диаметр боковых отверстий на вертикальном фланце"),
    }
    part.create_variables_from_dict(variables)

    # Вычисляемые размеры для геометрии
    L_total = 80.2   # L_base + TOL (внутренняя длина)
    W_total = 50.2   # W_base + TOL (внутренняя ширина)
    L_half = L_total / 2.0   # 40.1
    W_half = W_total / 2.0   # 25.1
    # Внешние размеры с учетом толщины стенок t=2:
    L_outer = L_total + 2 * 2.0   # 84.2
    W_outer = W_total + 2 * 2.0   # 54.2
    L_outer_half = L_outer / 2.0   # 42.1
    W_outer_half = W_outer / 2.0   # 27.1

    # ============================================================
    # 2. ЭСКИЗ 1 — БАЗА (на плоскости XY, Z=0)
    # Прямоугольник 80.2 × 50.2 (внутренний), центрированный
    # База будет выдавлена вверх на толщину t=2 (Z=0..2)
    # ============================================================
    def draw_base_sketch(b):
        b.rect(
            x=0, y=0,
            w=L_total,
            h=W_total,
            centered=True,
        )
        b.dim_hor(
            y_line=-W_half,
            x1=-L_half,
            x2=L_half,
            var_name="L_base+TOL",
            y_pts=-W_half - 5.0,
        )
        b.dim_ver(
            x_line=L_half + 5.0,
            y1=-W_half,
            y2=W_half,
            var_name="W_base+TOL",
            x_pts=L_half + 5.0,
        )

    sketch_base = part.create_sketch("xy", draw_base_sketch)

    # ============================================================
    # 3. БАЗОВОЕ ВЫДАВЛИВАНИЕ — основание (Z=0..2)
    # ============================================================
    base_extrude = part.extrude(
        sketch_ent=sketch_base,
        depth=2.0,  # t = 2.0
        direction=DT_NORMAL,
        expr="t",
    )

    # ============================================================
    # 4. ЧЕТЫРЕ СТЕНЫ (фланцы) — вертикальные пластины по внешним краям базы
    # Создаются как выдавливание прямоугольников на плоскости XY (Z=0)
    # вверх на высоту H_flange=16 (Z=0..16)
    #
    # Y+ стена (передняя): X=-42.1..42.1, Y=25.1..27.1, Z=0..16
    # Y- стена (задняя):  X=-42.1..42.1, Y=-27.1..-25.1, Z=0..16
    # X+ стена (правая):  X=40.1..42.1, Y=-27.1..27.1, Z=0..16
    # X- стена (левая):   X=-42.1..-40.1, Y=-27.1..27.1, Z=0..16
    # ============================================================

    # Функция для построения эскиза стены на плоскости XY
    def draw_wall_sketch_y_plus(b):
        # Y+ стена: Y=25.1..27.1, X=-42.1..42.1
        b.rect(
            x=-L_outer_half,
            y=W_half,
            w=L_outer,
            h=2.0,  # t = 2.0
            centered=False,
        )
        b.dim_hor(
            y_line=W_half - 3.0,
            x1=-L_outer_half,
            x2=L_outer_half,
            var_name="L_base+TOL",
            y_pts=W_half - 3.0,
        )
        b.dim_ver(
            x_line=L_outer_half + 3.0,
            y1=W_half,
            y2=W_outer_half,
            var_name="t",
            x_pts=L_outer_half + 3.0,
        )

    def draw_wall_sketch_y_minus(b):
        # Y- стена: Y=-27.1..-25.1, X=-42.1..42.1
        b.rect(
            x=-L_outer_half,
            y=-W_outer_half,
            w=L_outer,
            h=2.0,
            centered=False,
        )
        b.dim_hor(
            y_line=-W_outer_half - 3.0,
            x1=-L_outer_half,
            x2=L_outer_half,
            var_name="L_base+TOL",
            y_pts=-W_outer_half - 3.0,
        )
        b.dim_ver(
            x_line=L_outer_half + 3.0,
            y1=-W_outer_half,
            y2=-W_half,
            var_name="t",
            x_pts=L_outer_half + 3.0,
        )

    def draw_wall_sketch_x_plus(b):
        # X+ стена: X=40.1..42.1, Y=-27.1..27.1
        b.rect(
            x=L_half,
            y=-W_outer_half,
            w=2.0,  # t = 2.0
            h=W_outer,
            centered=False,
        )
        b.dim_hor(
            y_line=-W_outer_half - 3.0,
            x1=L_half,
            x2=L_outer_half,
            var_name="t",
            y_pts=-W_outer_half - 3.0,
        )
        b.dim_ver(
            x_line=L_outer_half + 3.0,
            y1=-W_outer_half,
            y2=W_outer_half,
            var_name="W_base+TOL",
            x_pts=L_outer_half + 3.0,
        )

    def draw_wall_sketch_x_minus(b):
        # X- стена: X=-42.1..-40.1, Y=-27.1..27.1
        b.rect(
            x=-L_outer_half,
            y=-W_outer_half,
            w=2.0,
            h=W_outer,
            centered=False,
        )
        b.dim_hor(
            y_line=-W_outer_half - 3.0,
            x1=-L_outer_half,
            x2=-L_half,
            var_name="t",
            y_pts=-W_outer_half - 3.0,
        )
        b.dim_ver(
            x_line=-L_outer_half - 3.0,
            y1=-W_outer_half,
            y2=W_outer_half,
            var_name="W_base+TOL",
            x_pts=-L_outer_half - 3.0,
        )

    # Y+ стена (передняя)
    sketch_wall_y_plus = part.create_sketch("xy", draw_wall_sketch_y_plus)
    part.extrude(
        sketch_ent=sketch_wall_y_plus,
        depth=16.0,  # H_flange
        direction=DT_NORMAL,
        expr="H_flange",
    )

    # Y- стена (задняя)
    sketch_wall_y_minus = part.create_sketch("xy", draw_wall_sketch_y_minus)
    part.extrude(
        sketch_ent=sketch_wall_y_minus,
        depth=16.0,
        direction=DT_NORMAL,
        expr="H_flange",
    )

    # X+ стена (правая)
    sketch_wall_x_plus = part.create_sketch("xy", draw_wall_sketch_x_plus)
    part.extrude(
        sketch_ent=sketch_wall_x_plus,
        depth=16.0,
        direction=DT_NORMAL,
        expr="H_flange",
    )

    # X- стена (левая)
    sketch_wall_x_minus = part.create_sketch("xy", draw_wall_sketch_x_minus)
    part.extrude(
        sketch_ent=sketch_wall_x_minus,
        depth=16.0,
        direction=DT_NORMAL,
        expr="H_flange",
    )

    # ============================================================
    # 5. ЭСКИЗ НА ВЕРХНЕЙ ПЛОСКОСТИ (Z=16) — вырезы и отверстия на верхах стен
    # Получаем верхнюю грань передней стены (Y+ стена, верхняя грань на Z=16)
    # Эта грань лежит в плоскости Z=16 и подходит для эскиза сверху
    # ============================================================
    # Y+ стена: Y=25.1..27.1, её верхняя грань на Z=16, центр Y=26.1
    top_face_y_plus = part.get_planar_face_at(axis="z", coord=16.0, mode="max")
    # Используем эту грань как плоскость для эскиза (плоскость Z=16)
    plane_top = top_face_y_plus

    def draw_holes_sketch_top(b):
        holes = [
            ("rect", 17.35, -12.90, ("D_rect_w", "D_rect_h"), None),
            ("circle", 26.60, 5.10, "D_large", "D_large"),
            ("circle", 7.60, 5.10, "D_med", "D_med"),
            ("circle", -8.40, 5.10, "D_med", "D_med"),
            ("circle", -29.90, -12.90, "D_small", "D_small"),
            ("circle", -17.90, -12.90, "D_small", "D_small"),
            ("circle", -5.90, -12.90, "D_small", "D_small"),
            ("circle", -25.90, 5.10, "D_large", "D_large"),
            ("circle", 31.60, -12.90, "D_tiny", "D_tiny"),
            ("circle", 3.10, -12.90, "D_tiny", "D_tiny"),
            ("circle", -19.55, -1.25, "D_vtiny", "D_vtiny"),
            ("circle", -32.25, -1.25, "D_vtiny", "D_vtiny"),
            ("circle", -32.25, 11.45, "D_vtiny", "D_vtiny"),
            ("circle", -19.55, 11.45, "D_vtiny", "D_vtiny"),
        ]

        diam_values = {
            "D_large": 12.1, "D_med": 8.0, "D_small": 6.0,
            "D_tiny": 3.6, "D_vtiny": 2.9,
            "D_rect_w": 12.1, "D_rect_h": 6.0
        }

        for hole in holes:
            typ, x, y, params, var_name = hole
            if typ == "rect":
                w_var, h_var = params
                w_val = diam_values[w_var]
                h_val = diam_values[h_var]
                b.rect(x=x - w_val/2, y=y - h_val/2, w=w_val, h=h_val, centered=False)
                b.dim_hor(y_line=y - h_val/2 - 3, x1=x - w_val/2, x2=x + w_val/2, var_name=w_var, y_pts=y - h_val/2 - 3)
                b.dim_ver(x_line=x + w_val/2 + 3, y1=y - h_val/2, y2=y + h_val/2, var_name=h_var, x_pts=x + w_val/2 + 3)
            else:
                D_var = params
                D_val = diam_values[D_var]
                r = D_val / 2.0
                b.circle(x, y, r)
                b.dim_diam(x, y, r, angle_deg=45.0, var_name=D_var)

    sketch_holes_top = part.create_sketch_on_face(plane_top, draw_holes_sketch_top)

    # Вырез "Через всё" вниз (-Z)
    part.cut(
        sketch_ent=sketch_holes_top,
        depth=50.0,
        direction=DT_REVERSE,
        through_all=True,
    )

    # ============================================================
    # 6. БОКОВЫЕ ОТВЕРСТИЯ (на передней стене Y=27.1)
    # Создаем плоскость Y=27.1 через 3 точки на передней грани
    # ============================================================
    # ============================================================
    # 6. БОКОВЫЕ ОТВЕРСТИЯ (на передней стене Y=27.1)
    # Получаем внешнюю грань передней стены (Y=27.1)
    # ============================================================
    plane_front = part.get_planar_face_at(axis="y", coord=W_outer_half, mode="max")  # Y=27.1

    def draw_side_holes(b):
        r = 1.8  # D=3.6 -> R=1.8
        b.circle(-32.0, 10.0, r)
        b.dim_diam(-32.0, 10.0, r, angle_deg=45.0, var_name="D_side_hole")
        b.circle(32.0, 10.0, r)
        b.dim_diam(32.0, 10.0, r, angle_deg=45.0, var_name="D_side_hole")

    sketch_side_holes = part.create_sketch_on_face(plane_front, draw_side_holes)

    # Вырез сквозной в -Y (внутрь коробки)
    part.cut(
        sketch_ent=sketch_side_holes,
        depth=50.0,
        direction=DT_REVERSE,
        through_all=True,
    )

    # ============================================================
    # 7. СКРУГЛЕНИЯ В УГЛАХ (R_bend = 2.0)
    # 4 вертикальных ребра углов коробки
    # ============================================================
    corner_coords = [
        (-L_outer_half, -W_outer_half),
        (L_outer_half, -W_outer_half),
        (L_outer_half, W_outer_half),
        (-L_outer_half, W_outer_half),
    ]

    fillet_edges = []
    for cx, cy in corner_coords:
        edges = part._find_edges_by_midpoint(cx, 8.0, tol=2.0, vertical_only=True, cylindrical_only=False)
        if edges:
            fillet_edges.append(edges[0])

    if fillet_edges:
        part.fillet(fillet_edges, radius="R_bend", expr="R_bend")

    # ============================================================
    # 8. ВАЛИДАЦИЯ И СОХРАНЕНИЕ
    # ============================================================
    # Габариты: 84.2 × 54.2 × 16.0 мм (X × Y × Z)
    part.assert_bbox(84.2, 54.2, 16.0, tol=0.15)

    # Сохранение
    output_dir = "output"
    part.save(f"{output_dir}/Uleyma-T.01.01.02_Крышка.m3d")
    part.save_screenshot(f"{output_dir}/Uleyma-T.01.01.02_Крышка.png")

    part.close()
    log.info("=== ПОСТРОЕНИЕ ЗАВЕРШЕНО УСПЕШНО ===")


if __name__ == "__main__":
    main()