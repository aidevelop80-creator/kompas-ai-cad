# build_die_plate.py — Параметрическая нижняя плита штампа/приспособления
from kompas_core import DT_NORMAL, DT_REVERSE, STYLE_MAIN, STYLE_THIN, KompasPart, _wrap, _ole


def build_die_plate():
    part = KompasPart(name="Нижняя плита штампа", visible=True)

    # ------------------------------------------------------------------
    # 1. Таблица пользовательских переменных конструктора
    # ------------------------------------------------------------------
    L = 160.0      # Длина плиты
    W = 120.0      # Ширина плиты
    H = 25.0       # Толщина плиты
    f = 6.0        # Фаска на углах плиты (45°), по эталону die_plate_example
    a_win = 60.0   # Длина провального окна
    b_win = 40.0   # Ширина провального окна
    r_w = 5.0      # Радиус скругления углов провального окна
    d_col = 20.0   # Диаметр отверстий под направляющие колонки
    Lx = 120.0     # Межосевое расстояние колонок по X
    Ly = 80.0      # Межосевое расстояние колонок по Y
    fo = 1.0       # Заходная фаска отверстий направляющих

    part.create_variables_from_dict({
        "L": (L, "Длина плиты"),
        "W": (W, "Ширина плиты"),
        "H": (H, "Толщина плиты"),
        "f": (f, "Фаска на углах плиты"),
        "a_win": (a_win, "Длина провального окна"),
        "b_win": (b_win, "Ширина провального окна"),
        "r_w": (r_w, "Радиус скругления углов окна"),
        "d_col": (d_col, "Диаметр отверстий под направляющие колонки"),
        "Lx": (Lx, "Межосевое расстояние колонок по X"),
        "Ly": (Ly, "Межосевое расстояние колонок по Y"),
        "fo": (fo, "Заходная фаска отверстий направляющих"),
    })

    # ------------------------------------------------------------------
    # Шаг 1-2: Базовая плита — симметричный прямоугольник L x W на XY
    # Параметризация — переменными L, W в коде скрипта (центрированные координаты).
    # ------------------------------------------------------------------
    sk1 = part.create_sketch(
        "xy",
        lambda sk: sk.rect(0, 0, L, W, centered=True),
    )
    part.extrude(sk1, depth=H, direction=DT_NORMAL, expr="H")

    # ------------------------------------------------------------------
    # Шаг 3-4: Провальное окно a_win x b_win в центре плиты, сквозной вырез
    # ------------------------------------------------------------------
    face_front = part.get_planar_face_at(axis="z", coord=H)
    sk2 = part.create_sketch_on_face(
        face_front,
        lambda sk: sk.rect(0, 0, a_win, b_win, centered=True),
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
            # Управляющий диаметральный размер отверстия (по базовой окружности в I квадранте)
            sk.dim_diam(Lx / 2.0, Ly / 2.0, d_col / 2.0, var_name="d_col"),
        ),
    )
    part.cut(sk3, depth=H, direction=DT_NORMAL, expr="H", through_all=True)

    # ------------------------------------------------------------------
    # Шаг 7-8: Фаски и скругления (по требованию рецензента)
    # ------------------------------------------------------------------
    # 7а. Фаска 45° x f на 4 вертикальных углах плиты
    # ------------------------------------------------------------------
    # 7-8. Фаски и скругления (по требованию рецензента)
    # Плита лежит на XY и выдавлена по Z, поэтому «вертикальные» рёбра —
    # это рёбра, меняющиеся по Z (постоянные X и Y). Ищем их по координатам.
    # ------------------------------------------------------------------
    def _find_vert_edges_xy(target_x, target_y, tol=1.0):
        """Ищет рёбра, вертикальные по Z, чья середина близка к (target_x, target_y)."""
        from kompas_core import K5  # API5 модуль уже доступен в ядре
        res = []
        raw_collection = part.part.EntityCollection(6)  # OBJ_FACE=6
        if raw_collection is None:
            return res
        part_ents = _wrap(K5.ksEntityCollection, raw_collection)
        for i in range(part_ents.GetCount()):
            raw_f = part_ents.GetByIndex(i)
            if raw_f is None:
                continue
            f = _wrap(K5.ksEntity, raw_f)
            fdef = _wrap(K5.ksFaceDefinition, f.GetDefinition())
            if not fdef:
                continue
            loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
            if not loops:
                continue
            for li in range(loops.GetCount()):
                loop = _wrap(K5.ksLoop, loops.GetByIndex(li))
                loop_edges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
                if not loop_edges:
                    continue
                for j in range(loop_edges.GetCount()):
                    edge = _wrap(K5.ksEdgeDefinition, loop_edges.GetByIndex(j))
                    if not edge:
                        continue
                    v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
                    v2 = _wrap(K5.ksVertexDefinition, edge.GetVertex(False))
                    if not v1 or not v2:
                        continue
                    r1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                    r2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                    if not (r1 and r2):
                        continue
                    dx, dy, dz = abs(x1 - x2), abs(y1 - y2), abs(z1 - z2)
                    # вертикальное по Z: меняется только Z
                    if not (dx < 1e-4 and dy < 1e-4 and dz > 1e-4):
                        continue
                    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    if abs(mx - target_x) <= tol and abs(my - target_y) <= tol:
                        res.append(edge)
        return res

    # 7а. Фаска 45° x f на 4 вертикальных углах плиты (координаты ±L/2, ±W/2)
    plate_corners = []
    for cx, cy in [(L / 2, W / 2), (-L / 2, W / 2), (L / 2, -W / 2), (-L / 2, -W / 2)]:
        found = _find_vert_edges_xy(cx, cy, tol=1.0)
        if found:
            plate_corners.append(found[0])
    if plate_corners:
        part.chamfer(plate_corners, distance=f, angle=45.0, expr="f")
    else:
        print("[DIEPLATE] Не найдены рёбра углов плиты для фаски!")

    # 7б. Скругления углов провального окна радиусом r_w (координаты ±a_win/2, ±b_win/2)
    win_corners = []
    for cx, cy in [(a_win / 2, b_win / 2), (-a_win / 2, b_win / 2), (a_win / 2, -b_win / 2), (-a_win / 2, -b_win / 2)]:
        found = _find_vert_edges_xy(cx, cy, tol=1.0)
        if found:
            win_corners.append(found[0])
    if win_corners:
        part.fillet(win_corners, radius=r_w, expr="r_w")
    else:
        print("[DIEPLATE] Не найдены рёбра углов окна для скругления!")

    # 7в. Заходные фаски входов отверстий направляющих (fo), 4 отверстия (±Lx/2, ±Ly/2)
    # Ищем круговые рёбра (входы отверстий) на верхней грани плиты z=H.
    def _find_hole_entrance_edges():
        res = []
        from kompas_core import K5
        raw_collection = part.part.EntityCollection(6)
        if raw_collection is None:
            return res
        ents = _wrap(K5.ksEntityCollection, raw_collection)
        for i in range(ents.GetCount()):
            raw_f = ents.GetByIndex(i)
            if raw_f is None:
                continue
            f = _wrap(K5.ksEntity, raw_f)
            fdef = _wrap(K5.ksFaceDefinition, f.GetDefinition())
            if not fdef:
                continue
            loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
            if not loops:
                continue
            for li in range(loops.GetCount()):
                loop = _wrap(K5.ksLoop, loops.GetByIndex(li))
                ledges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
                if ledges is None or ledges.GetCount() != 1:
                    continue  # ищем замкнутые контуры из одного ребра (круг)
                edge = _wrap(K5.ksEdgeDefinition, ledges.GetByIndex(0))
                if not edge:
                    continue
                v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
                v2 = _wrap(K5.ksVertexDefinition, edge.GetVertex(False))
                if not v1 or not v2:
                    continue
                r1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                r2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                if not (r1 and r2):
                    continue
                # Круг входного ребра: лежит на верхней кромке z≈H, центр ≈ (±Lx/2, ±Ly/2)
                if abs(z1 - H) > 0.5 and abs(z2 - H) > 0.5:
                    continue
                cx, cy = x1, y1  # точка на окружности кругового ребра
                for hx, hy in [(Lx / 2, Ly / 2), (-Lx / 2, Ly / 2), (Lx / 2, -Ly / 2), (-Lx / 2, -Ly / 2)]:
                    # центр отверстия имеет расстояние d_col/2 от точки окружности (cx,cy)
                    dist = ((cx - hx) ** 2 + (cy - hy) ** 2) ** 0.5
                    if abs(dist - d_col / 2.0) < 0.5:
                        res.append(edge)
                        break
        return res

    hole_edges = _find_hole_entrance_edges()
    if len(hole_edges) >= 4:
        part.chamfer(hole_edges, distance=fo, angle=45.0, expr="fo")
    else:
        print(f"[DIEPLATE] Найдено рёбер входа отверстий: {len(hole_edges)}; заходные фаски пропущены.")

    # ------------------------------------------------------------------
    # Тройной контур самопроверки
    # ------------------------------------------------------------------
    part.rebuild()
    part.assert_bbox(L, W, H, tol=0.1)
    part.save_screenshot("output/die_plate.png")
    part.save("output/die_plate.m3d")


if __name__ == "__main__":
    build_die_plate()