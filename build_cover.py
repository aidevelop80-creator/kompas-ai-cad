# build_cover.py — Параметрическая листовая крышка
# Эталон: example/Крышка_example.m3d
# Запуск: .venv\Scripts\python.exe build_cover.py

import math

from kompas_core import (
    DT_NORMAL,
    OBJ_FACE,
    PLANE_XY,
    STYLE_MAIN,
    KompasPart,
    _wrap,
)
from sdk_ref import kompas_api5_v16 as K5

# ========================= КОНСТРУКТОРСКИЕ ПАРАМЕТРЫ =========================
VARIABLES = {
    "H": (16.0, "Высота бортов крышки"),
}

EXPECTED_VOLUME = (
    14650.56  # мм³ (эталон Крышка_example.m3d с операцией Замыкание углов)
)


def _find_base_edge(part: KompasPart, axis: str, pos: float, z_coord: float = 2.0):
    """Находит ребро базового листа на высоте z_coord:
    axis='y' — длинное ребро (вдоль X) при Y=pos;
    axis='x' — короткое ребро (вдоль Y) при X=pos.
    """
    part_ents = _wrap(K5.ksEntityCollection, part.part.EntityCollection(OBJ_FACE))
    for i in range(part_ents.GetCount()):
        f = _wrap(K5.ksEntity, part_ents.GetByIndex(i))
        fdef = _wrap(K5.ksFaceDefinition, f.GetDefinition())
        if not fdef:
            continue
        loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
        if not loops:
            continue
        for li in range(loops.GetCount()):
            edges = _wrap(
                K5.ksEdgeCollection,
                _wrap(K5.ksLoop, loops.GetByIndex(li)).EdgeCollection(),
            )
            if not edges:
                continue
            for j in range(edges.GetCount()):
                ed = _wrap(K5.ksEdgeDefinition, edges.GetByIndex(j))
                v1 = _wrap(K5.ksVertexDefinition, ed.GetVertex(True))
                v2 = _wrap(K5.ksVertexDefinition, ed.GetVertex(False))
                if not v1 or not v2:
                    continue
                ok1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                ok2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                if not (ok1 and ok2):
                    continue
                if abs(z1 - z_coord) > 0.2 or abs(z2 - z_coord) > 0.2:
                    continue
                if (
                    axis == "y"
                    and abs(y1 - pos) < 0.2
                    and abs(y2 - pos) < 0.2
                    and abs(x1 - x2) > 70.0
                ):
                    return ed
                if (
                    axis == "x"
                    and abs(x1 - pos) < 0.2
                    and abs(x2 - pos) < 0.2
                    and abs(y1 - y2) > 40.0
                ):
                    return ed
    raise RuntimeError(f"[FAIL EDGE] Не найдено ребро {axis}={pos} на Z={z_coord}!")


def build_cover(part: KompasPart):
    """Построение крышки по эталонной модели Крышка_example.m3d."""
    H = VARIABLES["H"][0]
    w_base = 80.2
    h_base = 50.2

    # --- Шаг 1-2: Базовая пластина 80.2 x 50.2 на XY и Листовое тело (T=2.0) ---
    def sketch_base(b_sk):
        b_sk.rect(0.0, 0.0, w_base, h_base, centered=True, style=STYLE_MAIN)
        b_sk.dim_hor(
            y_line=h_base / 2.0 + 8.0,
            x1=-w_base / 2.0,
            x2=w_base / 2.0,
            var_name="80.0+0.2",
            y_pts=h_base / 2.0,
        )
        b_sk.dim_ver(
            x_line=-w_base / 2.0 - 8.0,
            y1=-h_base / 2.0,
            y2=h_base / 2.0,
            var_name="50.0+0.2",
            x_pts=-w_base / 2.0,
        )
        b_sk.center_on_origin(w_base, h_base)

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=sketch_base)
    part.create_sheet_metal_body(
        sk1,
        thickness=2.0,
        bend_radius=5.0,
        k_factor=0.4,
        thickness_direction=1,
        direction=0,
        unfold_type=0,
    )

    # --- Шаг 3-6: 4 сгиба (L=16, R=2.0, K=0.4, IntR=True, освобождение угла = только сгиб (0)) ---
    # Длинные борта (Y=±25.1): без уширения (side_type=0)
    for y_pos in (-h_base / 2.0, h_base / 2.0):
        ed = _find_base_edge(part, axis="y", pos=y_pos, z_coord=2.0)
        part.add_bend(
            ed,
            length=H,
            bend_radius=2.0,
            angle=90.0,
            k_factor=0.4,
            direction=True,
            disposal=0,
            length_type=1,
            offset_type=3,
            side_type=0,
            bend_release=0,
            internal_radius=True,
            without_bend_release=True,
            dismissal_angle_type=0,
            length_expr="H",
        )

    # Короткие борта (X=±40.1): уширение 2.0 мм слева и справа (side_type=1) для замыкания углов в V16
    for x_pos in (-w_base / 2.0, w_base / 2.0):
        ed = _find_base_edge(part, axis="x", pos=x_pos, z_coord=2.0)
        part.add_bend(
            ed,
            length=H,
            bend_radius=2.0,
            angle=90.0,
            k_factor=0.4,
            direction=True,
            disposal=0,
            length_type=1,
            offset_type=3,
            side_type=1,
            bend_release=0,
            internal_radius=True,
            widening_left=2.0,
            widening_right=2.0,
            without_bend_release=True,
            dismissal_angle_type=0,
            length_expr="H",
        )

    # --- Шаг 7-8: Вырезы в основании крышки (Z=0.0, через дно) ---
    face_bot = part.get_planar_face_at(axis="z", coord=0.0, mode="min")

    def sketch_cutouts(b_sk):
        # 1. Прямоугольное окно
        b_sk.rect(
            11.30,
            -16.10,
            23.40 - 11.30,
            -10.10 - (-16.10),
            centered=False,
            style=STYLE_MAIN,
        )

        # 2. Паз со скруглёнными боками (центр (26.60, 6.10), R=6.00, обрезка по Y=0.70 и 11.50)
        dx = math.sqrt(6.00**2 - 5.40**2)
        x_l, x_r = 26.60 - dx, 26.60 + dx
        ang = math.degrees(math.asin(5.40 / 6.00))
        b_sk.line(x_r, 0.70, x_l, 0.70, style=STYLE_MAIN)
        b_sk.line(x_l, 11.50, x_r, 11.50, style=STYLE_MAIN)
        b_sk.arc(26.60, 6.10, 6.00, 360.0 - ang, ang, direction=False, style=STYLE_MAIN)
        b_sk.arc(
            26.60,
            6.10,
            6.00,
            180.0 - ang,
            180.0 + ang,
            direction=False,
            style=STYLE_MAIN,
        )

        # 3. Круглые отверстия (D=8.0, 5.1, 11.3, 3.6)
        circles = [
            (7.60, 6.10, 4.00),
            (-8.40, 6.10, 4.00),
            (-27.90, -13.10, 2.55),
            (-17.40, -13.10, 2.55),
            (-6.90, -13.10, 2.55),
            (-25.90, 6.10, 5.65),
            (31.60, -13.10, 1.80),
            (3.10, -13.10, 1.80),
            (-19.55, -0.25, 1.80),
            (-32.25, -0.25, 1.80),
            (-32.25, 12.45, 1.80),
            (-19.55, 12.45, 1.80),
        ]
        for xc, yc, rad in circles:
            b_sk.circle(xc, yc, rad, style=STYLE_MAIN)

    sk2 = part.create_sketch_on_face(
        face_bot, draw_fn=sketch_cutouts, auto_parametrize=False
    )
    part.cut(sk2, depth=2.0, direction=DT_NORMAL)

    # --- Финальная валидация габаритов ---
    part.assert_bbox(exp_x=84.20, exp_y=54.20, exp_z=16.00, tol=0.2)
    vol = part.volume()
    print(
        f"[INFO VOLUME] Итоговый объём: {vol:.2f} мм³ (эталон с 539: {EXPECTED_VOLUME:.2f} мм³)"
    )
    return part


if __name__ == "__main__":
    part = KompasPart(name="Cover", visible=True)
    part.create_variables_from_dict(VARIABLES)
    try:
        build_cover(part)
        part.save("output/Cover_84x54x16.m3d")
        part.save_screenshot("output/Cover_84x54x16.png")
        print("[SUCCESS] Деталь Cover_84x54x16 построена и провалидирована")
    except Exception:
        part.close()
        raise
