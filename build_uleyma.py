# build_uleyma.py — Построение нативной листовой детали Uleyma-T.01.01.02_Крышка
import math

from kompas_core import (
    DT_NORMAL,
    OBJ_FACE,
    PLANE_XY,
    STYLE_MAIN,
    KompasPart,
    _ole,
    _wrap,
    log,
)
from sdk_ref import kompas_api5_v16 as K5


def _find_edge_at_z2(part: KompasPart, side: str, z_target: float = 2.0, tol: float = 0.5):
    """
    Находит нужное ребро ('bottom', 'left', 'top', 'right') на верхней плоскости Z=2.0
    листового тела для построения сгиба.
    """
    faces = _wrap(K5.ksEntityCollection, part.part.EntityCollection(OBJ_FACE))
    for i in range(faces.GetCount()):
        f_ent = _wrap(K5.ksEntity, faces.GetByIndex(i))
        fdef = _wrap(K5.ksFaceDefinition, f_ent.GetDefinition())
        if not fdef:
            continue
        loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
        if not loops:
            continue
        for li in range(loops.GetCount()):
            loop = _wrap(K5.ksLoop, loops.GetByIndex(li))
            edges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
            if not edges:
                continue
            for ei in range(edges.GetCount()):
                edge = _wrap(K5.ksEdgeDefinition, edges.GetByIndex(ei))
                if not edge or not edge.IsStraight():
                    continue
                v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
                v2 = _wrap(K5.ksVertexDefinition, edge.GetVertex(False))
                if not v1 or not v2:
                    continue
                r1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                r2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                if not (r1 and r2):
                    continue
                mx, my, mz = 0.5 * (x1 + x2), 0.5 * (y1 + y2), 0.5 * (z1 + z2)
                length = math.hypot(x2 - x1, y2 - y1)
                if abs(mz - z_target) > tol or length < 20.0:
                    continue

                if side == "bottom" and abs(my + 25.1) < 1.0 and abs(y1 - y2) < 0.1:
                    return edge
                if side == "top" and abs(my - 25.1) < 1.0 and abs(y1 - y2) < 0.1:
                    return edge
                if side == "left" and abs(mx + 40.1) < 1.0 and abs(x1 - x2) < 0.1:
                    return edge
                if side == "right" and abs(mx - 40.1) < 1.0 and abs(x1 - x2) < 0.1:
                    return edge

    raise RuntimeError(f"[FAIL EDGE] Не найдено ребро '{side}' на высоте Z={z_target}!")


def _find_corner_vertical_edges(part: KompasPart):
    """
    Находит два вертикальных ребра (Z = 4.0..16.0) в углу (-40.1..-42.1, -25.1..-27.1)
    для операции 'Замыкание углов:1':
      - edge1:(-40.1, -27.1, 4.0..16.0)
      - edge2:(-42.1, -25.1, 4.0..16.0)
    """
    faces = _wrap(K5.ksEntityCollection, part.part.EntityCollection(OBJ_FACE))
    edge1, edge2 = None, None
    for i in range(faces.GetCount()):
        f_ent = _wrap(K5.ksEntity, faces.GetByIndex(i))
        fdef = _wrap(K5.ksFaceDefinition, f_ent.GetDefinition())
        if not fdef:
            continue
        loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
        if not loops:
            continue
        for li in range(loops.GetCount()):
            loop = _wrap(K5.ksLoop, loops.GetByIndex(li))
            edges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
            if not edges:
                continue
            for ei in range(edges.GetCount()):
                edge = _wrap(K5.ksEdgeDefinition, edges.GetByIndex(ei))
                if not edge or not edge.IsStraight():
                    continue
                v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
                v2 = _wrap(K5.ksVertexDefinition, edge.GetVertex(False))
                if not v1 or not v2:
                    continue
                r1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                r2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                if not (r1 and r2):
                    continue
                if abs(x1 - x2) > 0.1 or abs(y1 - y2) > 0.1 or abs(abs(z2 - z1) - 12.0) > 0.5:
                    continue
                if abs(x1 + 40.1) < 0.5 and abs(y1 + 27.1) < 0.5 and edge1 is None:
                    edge1 = edge
                elif abs(x1 + 42.1) < 0.5 and abs(y1 + 25.1) < 0.5 and edge2 is None:
                    edge2 = edge
    if edge1 is None or edge2 is None:
        raise RuntimeError("[FAIL CORNER EDGES] Не найдены ребра для замыкания углов!")
    return edge1, edge2


def build_uleyma():
    part = KompasPart(name="Uleyma-T.01.01.02_Крышка", visible=True)

    # =========================================================================
    # 1. Таблица пользовательских переменных конструктора (строго по слепку)
    # =========================================================================
    part.create_variables_from_dict(
        {
            "SM_Thickness": (1.0, "Толщина листового тела"),
            "SM_Radius": (5.0, "Радиус сгиба"),
            "SM_K": (0.4, "Коэффициент"),
            "SM_BA": (10.0, "Величина сгиба"),
            "SM_BD": (0.0, "Уменьшение сгиба"),
            "SM_Angle": (90.0, "Угол сгиба"),
            "SM_H": (0.0, "Глубина освобождения сгиба"),
            "SM_W": (3.0, "Ширина освобождения сгиба"),
            "H": (16.0, ""),
        }
    )

    W_base = 80.2
    B_base = 50.2
    T_sheet = 2.0
    R_body = 5.0
    R_bend = 2.0
    K_val = 0.4
    H_bend = 16.0

    # =========================================================================
    # Шаг 1: Эскиз:1 на Плоскости XY (-40.1..40.1, -25.1..25.1)
    # =========================================================================
    def draw_sketch_1(b):
        b.rect(0.0, 0.0, W_base, B_base, centered=True)
        b.dim_ver(
            x_line=-48.0,
            y1=-B_base / 2.0,
            y2=B_base / 2.0,
            var_name="50.0+0.2",
            x_pts=-W_base / 2.0,
        )
        b.dim_hor(
            y_line=32.0,
            x1=-W_base / 2.0,
            x2=W_base / 2.0,
            var_name="80.0+0.2",
            y_pts=B_base / 2.0,
        )

    sk1 = part.create_sketch(plane=PLANE_XY, draw_fn=draw_sketch_1)

    # =========================================================================
    # Шаг 2: Листовое тело:1 (API7 ISheetMetalBody)
    # =========================================================================
    part.create_sheet_metal_body(
        sketch_ent=sk1,
        thickness=T_sheet,
        bend_radius=R_body,
        k_factor=K_val,
        thickness_direction=1,
        direction=0,
        unfold_type=0,
    )

    # =========================================================================
    # Шаги 3..6: Сгиб:1, Сгиб:2, Сгиб:3, Сгиб:4 (API7 ISheetMetalBend)
    # =========================================================================
    for side_name in ("bottom", "left", "top", "right"):
        edge_def = _find_edge_at_z2(part, side=side_name, z_target=2.0)
        part.add_bend(
            edge_or_face=edge_def,
            length=H_bend,
            bend_radius=R_bend,
            angle=90.0,
            k_factor=K_val,
            direction=True,
            disposal=0,
            length_type=1,
            offset_type=3,
            side_type=0,
            bend_release=0,
        )

    # =========================================================================
    # Шаг 7: Замыкание углов:1 (API7 ISheetMetalJointBend)
    # =========================================================================
    c_edge1, c_edge2 = _find_corner_vertical_edges(part)
    part.close_corners(c_edge1, c_edge2)

    # =========================================================================
    # Шаг 8 и Шаг 9: Эскиз:2 на грани Z=0.0 и Вырезать элемент выдавливания:1
    # =========================================================================
    face_z0 = part.get_planar_face_at(axis="z", coord=0.0, tol=0.5)

    def draw_sketch_2(b):
        # Прямоугольное окно: (11.30, -15.90) -> (23.40, -9.90)
        b.line(11.30, -15.90, 23.40, -15.90, style=STYLE_MAIN)
        b.line(23.40, -9.90, 11.30, -9.90, style=STYLE_MAIN)
        b.line(11.30, -9.90, 11.30, -15.90, style=STYLE_MAIN)
        b.line(23.40, -9.90, 23.40, -15.90, style=STYLE_MAIN)

        # 13 отверстий лицевой панели:
        circles_s2 = [
            (26.60, 5.10, 6.05),    # D=12.10
            (7.60, 5.10, 4.00),     # D=8.00
            (-8.40, 5.10, 4.00),    # D=8.00
            (-29.90, -12.90, 3.00), # D=6.00
            (-17.90, -12.90, 3.00), # D=6.00
            (-5.90, -12.90, 3.00),  # D=6.00
            (-25.90, 5.10, 6.05),   # D=12.10
            (31.60, -12.90, 1.80),  # D=3.60
            (3.10, -12.90, 1.80),   # D=3.60
            (-19.55, -1.25, 1.45),  # D=2.90
            (-32.25, -1.25, 1.45),  # D=2.90
            (-32.25, 11.45, 1.45),  # D=2.90
            (-19.55, 11.45, 1.45),  # D=2.90
        ]
        for xc, yc, r in circles_s2:
            b.circle(xc, yc, r, style=STYLE_MAIN)

    sk2 = part.create_sketch_on_face(
        face_z0, draw_fn=draw_sketch_2, auto_parametrize=False
    )
    part.cut(sk2, direction=DT_NORMAL, through_all=True)

    # =========================================================================
    # Шаг 10 и Шаг 11: Эскиз:3 на внешней грани Y=-27.1 и Вырез в листовом теле:1
    # =========================================================================
    face_y_min = part.get_planar_face_at(axis="y", coord=-27.1, tol=0.5)

    def draw_sketch_3(b):
        b.circle(-32.00, 10.00, 1.80, style=STYLE_MAIN)
        b.circle(32.00, 10.00, 1.80, style=STYLE_MAIN)

    sk3 = part.create_sketch_on_face(
        face_y_min, draw_fn=draw_sketch_3, auto_parametrize=False
    )
    part.sheet_metal_cut(sk3, cut_type=2, depth=54.2, cut=True)

    # =========================================================================
    # Финальное перестроение и Тройной контур проверки (Validation Pipeline)
    # =========================================================================
    part.rebuild()

    # Проверка точных габаритов из слепка: 84.20 x 54.20 x 16.00 мм
    part.assert_bbox(84.20, 54.20, 16.00, tol=0.1)

    # Сохранение модели .m3d и рендера .png
    out_m3d = "output/Uleyma-T.01.01.02_Крышка.m3d"
    out_png = "output/Uleyma-T.01.01.02_Крышка.png"
    part.save_screenshot(out_png)
    part.save(out_m3d)
    print(f"[SUCCESS] Нативная листовая модель крышки построена и сохранена в: {out_m3d}")


if __name__ == "__main__":
    build_uleyma()
