# build_housing.py — Параметрический листовой корпус
# Эталон: example/Корпус_example.m3d
# Запуск: .venv\Scripts\python.exe build_housing.py

from kompas_core import (
    DT_NORMAL,
    OBJ_FACE,
    PLANE_XZ,
    STYLE_MAIN,
    KompasPart,
    _wrap,
)
from sdk_ref import kompas_api5_v16 as K5

# ========================= КОНСТРУКТОРСКИЕ ПАРАМЕТРЫ =========================
VARIABLES = {
    "ro": (1.5, "Радиус технологического освобождения углов"),
    "r": (1.0, "Внутренний радиус сгибов стенок и полок"),
    "zv": (11.0, "Длина отгибной полки"),
    "tk": (133.0, "Межосевое расстояние крепёжных отверстий по ширине"),
    "dk": (2.5, "Диаметр крепёжных отверстий на полках"),
}

EXPECTED_VOLUME = 100703.89  # мм³ (из Корпус_example_blueprint.md)


def _find_top_inner_long_edge(part: KompasPart, target_z: float, min_y: float = 30.0):
    """Находит верхнее внутреннее ребро длинной стенки на заданном Z (вдоль оси X)."""
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
                if (
                    y1 > min_y
                    and abs(y1 - y2) < 0.2
                    and abs(z1 - target_z) < 0.5
                    and abs(z2 - target_z) < 0.5
                    and abs(x1 - x2) > 150.0
                ):
                    return ed
    raise RuntimeError(f"[FAIL EDGE] Не найдено верхнее ребро стенки при Z={target_z}!")


def _find_tab_top_face(part: KompasPart, target_y: float = 34.0):
    """Находит верхнюю плоскую грань полки Сгиб:2 (ширина ~90 мм, Z < -60)."""
    part_ents = _wrap(K5.ksEntityCollection, part.part.EntityCollection(OBJ_FACE))
    for i in range(part_ents.GetCount()):
        ent = _wrap(K5.ksEntity, part_ents.GetByIndex(i))
        fdef = _wrap(K5.ksFaceDefinition, ent.GetDefinition())
        if not fdef or not fdef.IsPlanar():
            continue
        bbox = part._get_face_bbox(fdef)
        if not bbox:
            continue
        if (
            abs(bbox[1] - target_y) < 0.5
            and abs(bbox[4] - target_y) < 0.5
            and (bbox[3] - bbox[0]) < 100.0
            and bbox[5] < -60.0
        ):
            return ent
    raise RuntimeError("[FAIL FACE] Не найдена верхняя грань полки Сгиб:2!")


def build_housing(part: KompasPart):
    """Построение корпуса по эталонной модели Корпус_example.m3d."""
    ro = VARIABLES["ro"][0]
    r = VARIABLES["r"][0]
    zv = VARIABLES["zv"][0]
    tk = VARIABLES["tk"][0]
    dk = VARIABLES["dk"][0]

    W, H_base, flap = 190.0, 143.0, 35.0
    hw, hh = W / 2.0, H_base / 2.0

    # --- Шаг 1-2: Развёртка (крестообразный контур на ZX) и Листовое тело (T=2.0) ---
    def sketch_blank(b_sk):
        pts = [
            (-hw - flap, -hh),
            (-hw - flap, hh),
            (-hw, hh),
            (-hw, hh + flap),
            (hw, hh + flap),
            (hw, hh),
            (hw + flap, hh),
            (hw + flap, -hh),
            (hw, -hh),
            (hw, -hh - flap),
            (-hw, -hh - flap),
            (-hw, -hh),
        ]
        b_sk.polygon(pts, closed=True, style=STYLE_MAIN)
        b_sk.dim_hor(
            y_line=hh + flap + 12.0, x1=-hw, x2=hw, var_name="190", y_pts=hh + flap
        )
        b_sk.dim_ver(
            x_line=-hw - flap - 12.0, y1=-hh, y2=hh, var_name="143", x_pts=-hw - flap
        )
        b_sk.dim_ver(x_line=hw + 12.0, y1=hh, y2=hh + flap, var_name="35", x_pts=hw)
        b_sk.align_v((0.0, hh + flap), (0.0, 0.0))
        b_sk.align_h((-hw - flap, 0.0), (0.0, 0.0))

    sk1 = part.create_sketch(plane=PLANE_XZ, draw_fn=sketch_blank)
    part.create_sheet_metal_body(
        sk1,
        thickness=2.0,
        bend_radius=5.0,
        k_factor=0.45,
        thickness_direction=1,
        direction=1,
        unfold_type=0,
    )

    # --- Шаг 3-4: 4 угловых разгрузочных выреза диаметром 2*ro ---
    face_y0 = part.get_planar_face_at(axis="y", coord=0.0)

    def sketch_reliefs(b_sk):
        for sx in (-hw, hw):
            for sy in (-hh, hh):
                b_sk.circle(sx, sy, ro, style=STYLE_MAIN).dim_diam(
                    sx, sy, ro, var_name="2*ro"
                )

    sk2 = part.create_sketch_on_face(face_y0, draw_fn=sketch_reliefs)
    part.sheet_metal_cut(sk2, cut_type=0, depth=10.0, cut=True)

    # --- Шаг 5-9: Линии сгиба (прямоугольник 190x143) и 4 сгиба по линии вверх ---
    face_y0 = part.get_planar_face_at(axis="y", coord=0.0)

    def sketch_bend_lines(b_sk):
        b_sk.rect(0.0, 0.0, W, H_base, centered=True, style=STYLE_MAIN)
        b_sk.dim_hor(y_line=hh + 8.0, x1=-hw, x2=hw, var_name="190", y_pts=hh)
        b_sk.dim_ver(x_line=-hw - 8.0, y1=-hh, y2=hh, var_name="143", x_pts=-hw)
        b_sk.center_on_origin(W, H_base)

    sk3 = part.create_sketch_on_face(face_y0, draw_fn=sketch_bend_lines)
    bend_segs = part.get_sketch_line_segments(sk3)
    if len(bend_segs) != 4:
        raise RuntimeError(
            f"[FAIL] Ожидалось 4 линии сгиба в Эскиз:3, найдено {len(bend_segs)}!"
        )

    for seg in bend_segs:
        face_fixed = part.get_planar_face_at(axis="y", coord=0.0)
        part.add_line_bend(
            seg,
            face=face_fixed,
            bend_radius=r,
            angle=90.0,
            k_factor=0.45,
            direction=True,
            bend_left_fixed=True,
            internal_radius=True,
            bend_type=2,
            radius_expr="r",
        )

    # --- Шаг 10-11: Две внутренние полки Сгиб:1 (Z=+71.5) и Сгиб:2 (Z=-71.5) ---
    for z_edge in (71.5, -71.5):
        edge = _find_top_inner_long_edge(part, target_z=z_edge)
        part.add_bend(
            edge,
            length=zv,
            bend_radius=r,
            angle=90.0,
            k_factor=0.45,
            direction=True,
            disposal=1,
            length_type=1,
            offset_type=2,
            side_type=0,
            internal_radius=True,
            width=90.0,
            distance_left=50.0,
            distance_right=50.0,
            offset=0.0,
            length_expr="zv",
            radius_expr="r",
        )

    # --- Шаг 12-13: Базовый вырез под разъём на дне (Y=0.0) ---
    face_y0 = part.get_planar_face_at(axis="y", coord=0.0)

    def sketch_connector(b_sk):
        cx, cy = -25.0, 0.0
        b_sk.circle(cx, cy, 8.0, style=STYLE_MAIN).dim_diam(cx, cy, 8.0, var_name="16")
        for dx in (-9.1, 9.1):
            for dy in (-9.1, 9.1):
                b_sk.circle(cx + dx, cy + dy, 1.7, style=STYLE_MAIN).dim_diam(
                    cx + dx, cy + dy, 1.7, var_name="3.4"
                )

    sk4 = part.create_sketch_on_face(face_y0, draw_fn=sketch_connector)
    cut_conn = part.sheet_metal_cut(sk4, cut_type=0, depth=10.0, cut=True)

    # --- Шаг 14-15: Массив по точкам (6 разъёмов на дне) ---
    face_y0 = part.get_planar_face_at(axis="y", coord=0.0)

    def sketch_conn_points(b_sk):
        pts = [
            (-75.0, 50.0),
            (-75.0, -50.0),
            (25.0, 50.0),
            (25.0, -50.0),
            (75.0, 50.0),
            (75.0, -50.0),
        ]
        for px, py in pts:
            b_sk.point(px, py, style=STYLE_MAIN)
        b_sk.fix_point(-75.0, 50.0)
        b_sk.align_v((-75.0, 50.0), (-75.0, -50.0))
        b_sk.align_h((-75.0, 50.0), (25.0, 50.0))
        b_sk.align_h((25.0, 50.0), (75.0, 50.0))
        b_sk.align_v((25.0, 50.0), (25.0, -50.0))
        b_sk.align_v((75.0, 50.0), (75.0, -50.0))
        b_sk.align_h((-75.0, -50.0), (25.0, -50.0))
        b_sk.align_h((25.0, -50.0), (75.0, -50.0))
        b_sk.dim_hor(y_line=60.0, x1=-75.0, x2=25.0, var_name="100", y_pts=50.0)
        b_sk.dim_hor(y_line=60.0, x1=25.0, x2=75.0, var_name="50", y_pts=50.0)
        b_sk.dim_ver(x_line=-85.0, y1=-50.0, y2=50.0, var_name="100", x_pts=-75.0)

    sk5 = part.create_sketch_on_face(face_y0, draw_fn=sketch_conn_points)
    part.point_pattern(features=[cut_conn], driven_obj=sk5)

    # --- Шаг 16-17: 4 крепёжных отверстия D=dk на полках (Y=34.0) ---
    face_tab = _find_tab_top_face(part, target_y=34.0)

    def sketch_tab_holes(b_sk):
        for sx in (-30.0, 30.0):
            for sy in (-tk / 2.0, tk / 2.0):
                b_sk.circle(sx, sy, dk / 2.0, style=STYLE_MAIN).dim_diam(
                    sx, sy, dk / 2.0, var_name="dk"
                )
        b_sk.dim_hor(
            y_line=tk / 2.0 + 10.0, x1=-30.0, x2=30.0, var_name="60", y_pts=tk / 2.0
        )
        b_sk.dim_ver(x_line=45.0, y1=-tk / 2.0, y2=tk / 2.0, var_name="tk", x_pts=30.0)
        b_sk.dim_ver(
            x_line=-45.0, y1=0.0, y2=tk / 2.0, var_name="tk/2", x1=0.0, x2=-30.0
        )

    sk6 = part.create_sketch_on_face(face_tab, draw_fn=sketch_tab_holes)
    part.cut(sk6, depth=10.0, direction=DT_NORMAL)

    # --- Финальная валидация габаритов и объёма ---
    part.assert_bbox(exp_x=194.00, exp_y=36.02, exp_z=147.00, tol=0.2)
    vol = part.volume()
    print(
        f"[INFO VOLUME] Итоговый объём: {vol:.2f} мм³ (эталон: {EXPECTED_VOLUME:.2f} мм³)"
    )
    return part


if __name__ == "__main__":
    part = KompasPart(name="Housing", visible=True)
    part.create_variables_from_dict(VARIABLES)
    try:
        build_housing(part)
        part.save("output/Housing_194x36x147.m3d")
        part.save_screenshot("output/Housing_194x36x147.png")
        print("[SUCCESS] Деталь Housing_194x36x147 построена и провалидирована")
    except Exception:
        part.close()
        raise
