# kompas_core.py — Ядро управления КОМПАС-3D v16.1+ (чистый API7 для размеров + логирование)
import atexit
import logging
import math
import os
import sys
import traceback

import pythoncom
import win32com.client
from win32com.client import dynamic

from sdk_ref import kompas_api5_v16 as K5
from sdk_ref import kompas_api7_v16 as K7


def _setup_logger(log_path: str = "output/build_run.log") -> logging.Logger:
    """Настраивает двойное логирование: в консоль (stdout) и в файл output/build_run.log."""
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    logger = logging.getLogger("kompas_core")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )

    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = _setup_logger()


def _ole(obj):
    """Извлекает сырой PyIDispatch (_oleobj_) из обертки K5/K7."""
    return getattr(obj, "_oleobj_", obj)


def _wrap(cls, obj):
    """Безопасно оборачивает COM-объект в типизированный класс K5/K7."""
    if obj is None:
        return None
    return cls(_ole(obj))


def _connect_existing_or_new_kompas(visible: bool = True, task_access: int = 0):
    """Подключается к уже открытому окну КОМПАС-3D без создания дубликатов."""
    raw_api5 = None
    mode_str = "существующее окно"
    try:
        raw_api5 = win32com.client.GetActiveObject("KOMPAS.Application.5")
    except Exception:
        pass

    if raw_api5 is None:
        try:
            raw_api7 = win32com.client.GetActiveObject("KOMPAS.Application.7")
            app7 = _wrap(K7.IApplication, raw_api7)
            app7.Visible = visible
        except Exception:
            pass

    if raw_api5 is None:
        mode_str = "новый процесс Dispatch"
        raw_api5 = win32com.client.Dispatch("KOMPAS.Application.5")

    api5 = _wrap(K5.KompasObject, raw_api5)
    api5.Visible = visible
    api5.ksEnableTaskAccess(task_access)
    log.info(
        f"Подключение к КОМПАС-3D выполнено ({mode_str}, visible={visible}, task_access={task_access})"
    )
    return api5


# Константы КОМПАС-3D (из sdk_ref/include/ksConstants3D.h и ldefin2d.h)
PLANE_XY = 1  # o3d_planeXOY (Синяя в изометрии)
PLANE_XZ = 2  # o3d_planeXOZ (Зеленая в изометрии, она же Плоскость ZX)
PLANE_YZ = 3  # o3d_planeYOZ (Красная в изометрии)
OBJ_PLANE_OFFSET = 4  # o3d_planeOffset
OBJ_SKETCH = 5  # o3d_sketch
OBJ_FACE = 6  # o3d_face (Грань тела)
OBJ_AXIS_2PLANES = 9  # o3d_axis2Planes (Ось на пересечении двух плоскостей)
OBJ_AXIS_CONICAL = 11  # o3d_axisConeFace (Ось конической/цилиндрической грани)

OBJ_FILLET = 34  # o3d_fillet
OBJ_CHAMFER = 33  # o3d_chamfer
OBJ_POINT_PATTERN = 507  # o3d_PointDrivenPattern (Массив по точкам)
OBJ_POINT_3D = 70  # o3d_point3D (Пространственная точка)
OBJ_BASE_EXTRUDE = 24   # o3d_baseExtrusion
OBJ_BOSS_EXTRUDE = 25   # o3d_bossExtrusion (Приклеить выдавливанием)
OBJ_CUT_EXTRUDE = 26    # o3d_cutExtrusion (Вырезать выдавливанием)
OBJ_BASE_ROTATE = 27    # o3d_baseRotated (Операция вращения)
OBJ_BOSS_ROTATE = 28    # o3d_bossRotated (Приклеить вращением)
OBJ_CUT_ROTATE = 29     # o3d_cutRotated (Вырезать вращением)
OBJ_CIRCULAR_COPY = 36  # o3d_circularCopy (Массив по концентрической сетке)

# Additional objects
OBJ_LOFT = 30  # o3d_baseLoft
OBJ_RULED_SURFACE = 515  # o3d_RuledSurface
OBJ_SURFACE_SEW = 96  # o3d_SurfaceSewer

# Sheet Metal objects
OBJ_SHEET_METAL_BODY = 74      # o3d_sheetMetalBody
OBJ_SHEET_METAL_BEND = 75      # o3d_sheetMetalBend
OBJ_SHEET_METAL_LINE_BEND = 76 # o3d_sheetMetalLineBend
OBJ_SHEET_METAL_HOLE = 77      # o3d_sheetMetalHole
OBJ_SHEET_METAL_CUT = 78       # o3d_sheetMetalCut
OBJ_SHEET_METAL_CLOSED_CORNER = 539  # o3d_sheetMetalClosedCorner
OBJ_CORNER_RELIEF = 539        # o3d_sheetMetalClosedCorner (alias)

DT_NORMAL = 0  # Прямое направление (на расстояние)
DT_REVERSE = 1  # Обратное направление
DT_BOTH = 2  # В оба направления
DT_MIDDLE = 3  # Средняя плоскость

STYLE_MAIN = 1  # Основная линия контура (синяя)
STYLE_THIN = 2  # Тонкая/вспомогательная линия
STYLE_AXIS = 3  # Осевая линия (штрихпунктирная)

KO_PARAMETRIC_PARAM = 64  # ko_ParametrizationParam


class SketchBuilder:
    """Конструктор плоского 2D-эскиза с поддержкой ассоциативных размеров API7 и параметризации."""

    _logged_pp_props = False

    def __init__(self, doc2d, api5, part=None):
        self.doc2d = _wrap(K5.ksDocument2D, doc2d)
        self.api5 = api5
        self.part = part
        self.pending_expressions = []
        self.pending_diam_dims = []  # [(xc, yc, r, angle_deg, var_name)]
        self.pending_lin_dims = []  # [(x1, y1, x2, y2, px, py, expression)]

    def line(self, x1, y1=None, x2=None, y2=None, style: int = STYLE_MAIN):
        """Отрезок."""
        if isinstance(x1, (tuple, list)) and isinstance(y1, (tuple, list)):
            p1, p2 = x1, y1
            if x2 is not None:
                style = int(x2)
            x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
        ref = self.doc2d.ksLineSeg(
            float(x1), float(y1), float(x2), float(y2), int(style)
        )
        log.debug(
            f"  [2D] Отрезок style={style}: ({x1:.2f}, {y1:.2f}) -> ({x2:.2f}, {y2:.2f}), ref={ref}"
        )
        return self

    def axis(self, x1, y1=None, x2=None, y2=None):
        """Осевая линия (стиль 3)."""
        return self.line(x1, y1, x2, y2, style=STYLE_AXIS)

    def rect(
        self,
        x: float = 0.0,
        y: float = 0.0,
        w: float = 10.0,
        h: float = 10.0,
        centered: bool = False,
    ):
        """Прямоугольник."""
        x, y, w, h = float(x), float(y), float(w), float(h)
        if centered:
            x, y = x - w / 2.0, y - h / 2.0
        self.line(x, y, x + w, y)
        self.line(x + w, y, x + w, y + h)
        self.line(x + w, y + h, x, y + h)
        self.line(x, y + h, x, y)
        return self

    def circle(self, xc=0.0, yc=0.0, r=None, style: int = STYLE_MAIN, **kwargs):
        """Окружность по центру (xc, yc) и радиусу r."""
        if isinstance(xc, (tuple, list)):
            style = int(r) if r is not None else STYLE_MAIN
            r = yc
            xc, yc = xc[0], xc[1]
        if r is None:
            r = kwargs.get("radius") or (
                float(kwargs["d"]) / 2.0
                if "d" in kwargs
                else float(kwargs["diameter"]) / 2.0
            )
        ref = self.doc2d.ksCircle(float(xc), float(yc), float(r), int(style))
        log.debug(
            f"  [2D] Окружность style={style}: центр=({xc:.2f}, {yc:.2f}), R={float(r):.2f} (D={float(r) * 2:.2f}), ref={ref}"
        )
        return self

    def polygon(
        self,
        points: list[tuple[float, float]],
        closed: bool = True,
        style: int = STYLE_MAIN,
    ):
        """Замкнутый многоугольник или ломаная по точкам [(x, y), ...]."""
        if len(points) < 2:
            return self
        for i in range(len(points) - 1):
            self.line(
                points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], style
            )
        if closed and len(points) > 2:
            self.line(points[-1][0], points[-1][1], points[0][0], points[0][1], style)
        return self

    def point(self, x: float, y: float, style: int = STYLE_MAIN):
        """Создает 2D-точку (ksPoint)."""
        ref = self.doc2d.ksPoint(float(x), float(y), int(style))
        log.debug(f"  [2D] Точка: ({x:.2f}, {y:.2f}), ref={ref}")
        return self

    def dim_linear(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        px: float,
        py: float,
        expression: str = None,
    ):
        """Регистрирует линейный размер между (x1, y1) и (x2, y2) для создания через API7."""
        if abs(y2 - y1) < 1e-6:
            expected_val = abs(x2 - x1)
        elif abs(x2 - x1) < 1e-6:
            expected_val = abs(y2 - y1)
        else:
            expected_val = math.hypot(x2 - x1, y2 - y1)

        self.pending_lin_dims.append(
            (
                float(x1),
                float(y1),
                float(x2),
                float(y2),
                float(px),
                float(py),
                expression,
            )
        )
        if expression:
            self.pending_expressions.append((expected_val, expression))
        log.debug(
            f"  [2D DIM QUEUE] Линейный размер val={expected_val:.2f}, expr='{expression}'"
        )
        return self

    def dim_hor(
        self,
        y_line: float,
        x1: float,
        x2: float,
        var_name: str = None,
        y_pts: float = 0.0,
    ):
        return self.dim_linear(
            x1, y_pts, x2, y_pts, (x1 + x2) / 2.0, y_line, expression=var_name
        )

    def dim_ver(
        self,
        x_line: float,
        y1: float,
        y2: float,
        var_name: str = None,
        x_pts: float = 0.0,
    ):
        return self.dim_linear(
            x_pts, y1, x_pts, y2, x_line, (y1 + y2) / 2.0, expression=var_name
        )

    def dim_diam(
        self,
        xc: float,
        yc: float,
        r: float,
        angle_deg: float = 45.0,
        var_name: str = None,
    ):
        """Регистрирует ассоциативный диаметральный размер окружности (xc, yc, r) для создания через API7."""
        self.pending_diam_dims.append(
            (float(xc), float(yc), float(r), float(angle_deg), var_name)
        )
        if var_name:
            self.pending_expressions.append((float(r) * 2.0, var_name))
        log.debug(
            f"  [2D DIM QUEUE] Диаметральный размер D={float(r) * 2:.2f} в ({xc:.2f}, {yc:.2f}), expr='{var_name}'"
        )
        return self

    def parametrize(self):
        """Накладывает автоматические параметрические связи API5."""
        pp = _wrap(
            K5.ksParametrizationParam, self.api5.GetParamStruct(KO_PARAMETRIC_PARAM)
        )
        pp.Init()
        if not SketchBuilder._logged_pp_props:
            SketchBuilder._logged_pp_props = True
            props = list(getattr(pp, "_prop_map_put_", {}).keys())
            log.debug(
                f"  [2D PARAM PROPS] Доступные поля ksParametrizationParam: {props}"
            )
        pp.nearestPoints = True
        pp.pointsLimit = 1000
        pp.horizontal = True
        pp.vertical = True
        pp.parallel = True
        pp.perpendicular = True
        pp.angleLimit = 1.0
        for k in getattr(pp, "_prop_map_put_", {}).keys():
            if "dim" in k.lower() or "fix" in k.lower():
                try:
                    setattr(pp, k, True)
                    log.debug(f"  [2D PARAM] Включено свойство pp.{k} = True")
                except Exception:
                    pass
        res = self.doc2d.ksParametrizeObjects(0, _ole(pp))
        log.debug(f"  [2D PARAM] ksParametrizeObjects завершен (res={res})")


class KompasPart:
    """Высокоуровневая обертка над 3D-деталью КОМПАС-3D v16.1+."""

    def __init__(self, name: str = "Деталь", visible: bool = True):
        log.info("=" * 65)
        log.info(f"НАЧАЛО ПОСТРОЕНИЯ ДЕТАЛИ: '{name}'")
        log.info("=" * 65)
        pythoncom.CoInitialize()
        self.api5 = _connect_existing_or_new_kompas(visible=visible, task_access=0)
        self._saved_successfully = False
        self._active_sketch_def = None
        self._variables = {}

        try:
            self.api7 = _wrap(K7.IApplication, self.api5.ksGetApplication7())
        except Exception as e:
            log.warning(f"Не удалось получить IApplication API7: {e}")
            self.api7 = None

        self._cleanup_unsaved_tabs()

        self.doc3d = _wrap(K5.ksDocument3D, self.api5.Document3D())
        self.doc3d.Create(False, True)
        self.part = _wrap(K5.ksPart, self.doc3d.GetPart(-1))
        self.part.name = name
        self.part.Update()

        atexit.register(self._cleanup_on_crash)

    def _cleanup_unsaved_tabs(self):
        if not self.api7:
            return
        try:
            docs = _wrap(K7.IDocuments, self.api7.Documents)
            closed_cnt = 0
            for i in range(docs.Count - 1, -1, -1):
                doc = _wrap(K7.IKompasDocument, docs.Item(i))
                path = getattr(doc, "PathName", "") or ""
                if not path.strip():
                    doc.Close(0)
                    closed_cnt += 1
            if closed_cnt:
                log.debug(f"Закрыто несохраненных старых вкладок: {closed_cnt}")
        except Exception:
            pass

    def _cleanup_on_crash(self):
        try:
            self.api5.ksEnableTaskAccess(1)
        except Exception:
            pass
        if self._saved_successfully:
            return
        try:
            if self._active_sketch_def is not None:
                self._active_sketch_def.EndEdit()
                self._active_sketch_def = None
        except Exception:
            pass
        try:
            if self.volume() <= 1e-9:
                self.doc3d.close()
        except Exception:
            pass

    def get_base_plane(self, plane: str | int):
        if isinstance(plane, str):
            p_map = {
                "xy": PLANE_XY,
                "xoy": PLANE_XY,
                "yx": PLANE_XY,
                "xz": PLANE_XZ,
                "xoz": PLANE_XZ,
                "zx": PLANE_XZ,
                "yz": PLANE_YZ,
                "yoz": PLANE_YZ,
                "zy": PLANE_YZ,
            }
            plane = p_map.get(plane.lower().strip(), PLANE_XY)
        return _wrap(K5.ksEntity, self.part.GetDefaultEntity(plane))

    def create_offset_plane(self, base_plane: str | int | object, offset: float):
        """Создает смещенную плоскость параллельно базовой.
        base_plane: имя базовой плоскости ("xy", "xz", "yz"), её тип (int), или ksEntity грани/плоскости.
        """
        # Если передан ksEntity (грань или плоскость), используем его напрямую
        if not isinstance(base_plane, (str, int)):
            base_ent_raw = _ole(base_plane)
        else:
            # Получаем базовую плоскость как сырой COM-объект
            if isinstance(base_plane, str):
                p_map = {
                    "xy": PLANE_XY, "xoy": PLANE_XY, "yx": PLANE_XY,
                    "xz": PLANE_XZ, "xoz": PLANE_XZ, "zx": PLANE_XZ,
                    "yz": PLANE_YZ, "yoz": PLANE_YZ, "zy": PLANE_YZ,
                }
                plane_type = p_map.get(base_plane.lower().strip(), PLANE_XY)
            else:
                plane_type = base_plane
            base_ent_raw = self.part.GetDefaultEntity(plane_type)

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_PLANE_OFFSET))
        defn = _wrap(K5.ksPlaneOffsetDefinition, ent.GetDefinition())
        # Передаем сырой COM-объект базовой плоскости/грани
        defn.SetPlane(base_ent_raw)
        defn.direction = True if offset >= 0 else False
        defn.offset = abs(float(offset))
        if not ent.Create():
            log.error(
                f"[FAIL PLANE] Не удалось создать смещенную плоскость offset={offset}"
            )
            raise RuntimeError("[FAIL PLANE] Не удалось создать смещенную плоскость!")
        self.part.Update()
        log.info(f"Создана смещенная плоскость: '{ent.name}' (offset={offset})")
        return ent

    def create_axis_by_2_planes(
        self, plane1: str | int = "xy", plane2: str | int = "yz"
    ):
        """Создает конструктивную ось на пересечении двух базовых плоскостей."""
        p1 = self.get_base_plane(plane1) if isinstance(plane1, (str, int)) else plane1
        p2 = self.get_base_plane(plane2) if isinstance(plane2, (str, int)) else plane2
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_AXIS_2PLANES))
        defn = _wrap(K5.ksAxis2PlanesDefinition, ent.GetDefinition())
        defn.SetPlane(1, _ole(p1))
        defn.SetPlane(2, _ole(p2))
        if not ent.Create():
            log.error("[FAIL AXIS] Не удалось создать ось на пересечении плоскостей!")
            raise RuntimeError(
                "[FAIL AXIS] Не удалось создать ось на пересечении плоскостей!"
            )
        self.part.Update()
        log.info(f"Создана конструктивная ось: '{ent.name}' ({plane1} x {plane2})")
        return ent

    def create_axis_from_cylindrical_face(self, face_entity):
        """Создает конструктивную ось по цилиндрической грани (o3d_axisConeFace = 11)."""
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_AXIS_CONICAL))
        defn = _wrap(K5.ksAxisConefaceDefinition, ent.GetDefinition())
        defn.SetFace(_ole(face_entity))
        if not ent.Create():
            log.error("[FAIL AXIS] Не удалось создать ось по цилиндрической грани!")
            raise RuntimeError("[FAIL AXIS] Не удалось создать ось по цилиндрической грани!")
        self.part.Update()
        log.info(f"Создана конструктивная ось по цилиндрической грани: '{ent.name}'")
        return ent

    def create_plane_by_3_points(self, p1: tuple, p2: tuple, p3: tuple):
        """Создает плоскость по 3 точкам (o3d_plane3Points = 16).
        p1, p2, p3 — кортежи (x, y, z) координат точек.
        """
        ent = _wrap(K5.ksEntity, self.part.NewEntity(16))  # OBJ_PLANE_3POINTS = 16
        defn = _wrap(K5.ksPlane3PointsDefinition, ent.GetDefinition())
        # Создаем 3 точки
        pt1 = self.create_point3d(p1[0], p1[1], p1[2])
        pt2 = self.create_point3d(p2[0], p2[1], p2[2])
        pt3 = self.create_point3d(p3[0], p3[1], p3[2])
        defn.SetPoint(1, _ole(pt1))
        defn.SetPoint(2, _ole(pt2))
        defn.SetPoint(3, _ole(pt3))
        if not ent.Create():
            log.error(f"[FAIL PLANE 3PTS] Не удалось создать плоскость по 3 точкам!")
            self.close()
            raise RuntimeError("[FAIL PLANE 3PTS] Не удалось создать плоскость по 3 точкам!")
        self.part.Update()
        log.info(f"Создана плоскость по 3 точкам: '{ent.name}'")
        return ent

    def _find_feature7_by_name(self, name: str):
        """Находит IFeature7 в дереве модели по имени (очищенному от (+)/(-))."""
        part7 = self._get_part7()
        if not part7:
            return None
        feat7_root = _wrap(K7.IFeature7, part7)
        raw_sub = feat7_root.SubFeatures(0, True, False)
        sub_list = (
            raw_sub
            if isinstance(raw_sub, (list, tuple))
            else ([raw_sub] if raw_sub else [])
        )
        for item in sub_list:
            sf = _wrap(K7.IFeature7, item)
            clean = str(sf.Name or "").replace("(+)", "").replace("(-)", "").strip()
            if clean == name.strip():
                return sf
        return None

    def create_point3d(self, x: float, y: float, z: float):
        """Создает пространственную точку (o3d_point3D = 70) по координатам через API5 определение."""
        # 1. Создаём сущность через API5
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_POINT_3D))
        defn_raw = ent.GetDefinition()
        dyn_defn = dynamic.DumbDispatch(defn_raw)

        # 2. Настраиваем определение ТЕРЕД Create
        dyn_defn.ParameterType = 1  # ksPParamCoord = 1
        dyn_defn.X = float(x)
        dyn_defn.Y = float(y)
        dyn_defn.Z = float(z)

        # 3. Создаём точку
        if not ent.Create():
            log.error(f"[FAIL POINT3D] Не удалось создать сущность точки в ({x}, {y}, {z})!")
            raise RuntimeError("[FAIL POINT3D] Не удалось создать пространственную точку!")
        self.part.Update()

        log.info(f"Создана пространственная точка: '{ent.name}' ({x:.2f}, {y:.2f}, {z:.2f})")
        return ent

    def _get_face_bbox(
        self, face_def
    ) -> tuple[float, float, float, float, float, float] | None:
        """Вычисляет габаритный бокс (xmin, ymin, zmin, xmax, ymax, zmax) грани по её вершинам."""
        xs, ys, zs = [], [], []
        loops = _wrap(K5.ksLoopCollection, face_def.LoopCollection())
        if not loops:
            return None
        for i in range(loops.GetCount()):
            loop = _wrap(K5.ksLoop, loops.GetByIndex(i))
            edges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
            if not edges:
                continue
            for j in range(edges.GetCount()):
                edge = _wrap(K5.ksEdgeDefinition, edges.GetByIndex(j))
                if not edge:
                    continue
                for is_first in (True, False):
                    v = _wrap(K5.ksVertexDefinition, edge.GetVertex(is_first))
                    if v:
                        res, x, y, z = v.GetPoint(0.0, 0.0, 0.0)
                        if res:
                            xs.append(x)
                            ys.append(y)
                            zs.append(z)
        if not xs:
            return None
        return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)

    def get_planar_face_at(
        self, axis: str = "y", coord: float = None, mode: str = "max", tol: float = 0.5
    ):
        """Находит плоскую грань детали, перпендикулярную выбранной оси ('x', 'y' или 'z')."""
        axis_idx = {"x": 0, "y": 1, "z": 2}[axis.lower().strip()]
        part_ents = _wrap(K5.ksEntityCollection, self.part.EntityCollection(OBJ_FACE))
        candidates = []

        for i in range(part_ents.GetCount()):
            ent = _wrap(K5.ksEntity, part_ents.GetByIndex(i))
            fdef = _wrap(K5.ksFaceDefinition, ent.GetDefinition())
            if not fdef or not fdef.IsPlanar():
                continue
            bbox = self._get_face_bbox(fdef)
            if not bbox:
                continue
            c_min, c_max = bbox[axis_idx], bbox[axis_idx + 3]
            if abs(c_max - c_min) < 1e-3:
                pos = 0.5 * (c_min + c_max)
                candidates.append((pos, ent))

        avail = [round(p, 2) for p, _ in candidates]
        log.debug(
            f"[FACE SEARCH] Найдены плоские грани вдоль оси {axis.upper()}: {avail}"
        )

        if not candidates:
            log.error(
                f"[FAIL FACE] Не найдено плоских граней перпендикулярно оси {axis.upper()}!"
            )
            raise RuntimeError(
                f"[FAIL FACE] Не найдено плоских граней перпендикулярно оси {axis.upper()}!"
            )

        if coord is not None:
            for pos, ent in candidates:
                if abs(pos - float(coord)) <= tol:
                    log.info(
                        f"[FACE SELECT] Выбрана плоская грань на {axis.upper()}={pos:.2f} (запрошено {coord})"
                    )
                    return ent
            log.error(
                f"[FAIL FACE] Плоская грань на {axis.upper()}={coord} не найдена! Доступные: {avail}"
            )
            raise RuntimeError(
                f"[FAIL FACE] Плоская грань на {axis.upper()}={coord} не найдена! Доступные координаты: {avail}"
            )

        candidates.sort(key=lambda item: item[0])
        chosen_pos, chosen_ent = candidates[-1] if mode == "max" else candidates[0]
        log.info(
            f"[FACE SELECT] Выбрана плоская грань ({mode}) на {axis.upper()}={chosen_pos:.2f}"
        )
        return chosen_ent

    def get_cylindrical_face(self, radius: float = None, tol: float = 0.5):
        """Возвращает ksEntity цилиндрической грани."""
        part_ents = _wrap(K5.ksEntityCollection, self.part.EntityCollection(OBJ_FACE))
        found_radii = []
        for i in range(part_ents.GetCount()):
            ent = _wrap(K5.ksEntity, part_ents.GetByIndex(i))
            fdef = _wrap(K5.ksFaceDefinition, ent.GetDefinition())
            if fdef and fdef.IsCylinder():
                res, h, r = fdef.GetCylinderParam(0.0, 0.0)
                found_radii.append(round(r, 2) if res else None)
                if radius is not None and res and abs(r - float(radius)) > tol:
                    continue
                log.info(
                    f"[FACE SELECT] Выбрана цилиндрическая грань R={r:.2f} (H={h:.2f})"
                )
                return ent
        log.error(
            f"[FAIL FACE] Цилиндрическая грань R={radius} не найдена! Доступные радиусы: {found_radii}"
        )
        raise RuntimeError("[FAIL FACE] Цилиндрическая грань не найдена в теле детали!")

    def _find_sketch_feature7(self, sk_ent):
        """Находит IFeature7 соответствующего эскиза в дереве модели API7."""
        part7 = self._get_part7()
        if not part7:
            return None
        feat7_root = _wrap(K7.IFeature7, part7)
        raw_sub = feat7_root.SubFeatures(0, True, False)
        sub_list = (
            raw_sub
            if isinstance(raw_sub, (list, tuple))
            else ([raw_sub] if raw_sub else [])
        )
        target_name = (sk_ent.name or "").strip()
        for item in reversed(sub_list):
            sf = _wrap(K7.IFeature7, item)
            clean = str(sf.Name or "").replace("(+)", "").replace("(-)", "").strip()
            if clean == target_name:
                return sf
        return None

    def _make_dim_driving(self, dim_obj, expr_str: str):
        """Пытается сделать 2D-размер API7 управляющим (фиксированным) и назначить ему переменную.

        ВАЖНО: Размер в эскизе должен быть УПРАВЛЯЮЩИМ, а не информационным.
        Информационный размер не управляет геометрией и вызывает ошибку КОМПАСА
        при попытке привязать к нему формулу. Всегда задавай выражение через
        parametritic constraint, чтобы размер стал driving.
        """
        dobj = _wrap(K7.IDrawingObject1, dim_obj)
        # Пробуем все возможные коды параметрического ограничения для размера (0..100).
        # КРИТИЧНО: не прерываемся на первом Create() — ищем тип, где И Create(),
        # И Expression устанавливается. Только такой комбинацией размер становится
        # управляющим (driving), а не информационным.
        # Диаметральные размеры обычно принимают тип 1 (Horizontal),
        # линейные размеры могут требовать иные типы (0..100).
        best_ctype = None
        best_con = None
        for ctype in range(101):
            try:
                con = _wrap(K7.IParametriticConstraint, dobj.NewConstraint())
                con.ConstraintType = ctype
                if con.Create():
                    # Выражение задаём ПОСЛЕ Create(), т.к. для некоторых типов размеров
                    # (особенно линейных) свойство Expression доступно только после создания ограничения
                    if expr_str:
                        try:
                            con.Expression = str(expr_str)
                            best_ctype = ctype
                            best_con = con
                            break  # Нашли тип, где и Create, и Expression работают → размер управляющий
                        except Exception:
                            # Expression не применился для этого типа — пробуем следующий
                            continue
                    else:
                        best_ctype = ctype
                        best_con = con
                        break
            except Exception:
                continue
        if best_con is not None:
            dim_obj.Update()
            log.debug(
                f"  [API7 DIM CONSTRAINT] Размер сделан управляющим ConstraintType={best_ctype} (expr='{expr_str}')"
            )
        else:
            log.debug(
                f"  [API7 DIM CONSTRAINT] Не найден тип ограничения с поддержкой Expression для размера"
            )

    def _apply_api7_sketch_dims_and_constraints(self, sk_ent, builder: SketchBuilder):
        """
        Открывает эскиз в API7 (ISketch.BeginEdit) и:
        1. Создает ассоциативные диаметральные (IDiametralDimension) и линейные (ILineDimension) размеры.
        2. Накладывает параметрические связи API7 (Точка на кривой = 9, Выравнивание по вертикали = 10).
        """
        sk_feat7 = self._find_sketch_feature7(sk_ent)
        if sk_feat7 is None:
            log.warning(f"  [API7 SKETCH] Не найден IFeature7 для '{sk_ent.name}'")
            return

        try:
            sk7 = _wrap(K7.ISketch, sk_feat7)
            doc2d_7 = _wrap(K7.IKompasDocument2D, sk7.BeginEdit())
            try:
                v_mgr = _wrap(K7.IViewsAndLayersManager, doc2d_7.ViewsAndLayersManager)
                views = _wrap(K7.IViews, v_mgr.Views)
                v0 = _wrap(K7.IView, views.ActiveView)
                dc = _wrap(K7.IDrawingContainer, v0)
                sym_c = _wrap(K7.ISymbols2DContainer, v0)

                circs = _wrap(K7.ICircles, dc.Circles)
                all_circles = [
                    _wrap(K7.ICircle, circs.Circle(i)) for i in range(circs.Count)
                ]

                # 1. Создаем ассоциативные диаметральные размеры (IDiametralDimensions)
                if builder.pending_diam_dims:
                    ddims = _wrap(K7.IDiametralDimensions, sym_c.DiametralDimensions)
                    for xc, yc, r, angle_deg, var_name in builder.pending_diam_dims:
                        target_c = None
                        for c in all_circles:
                            if (
                                math.hypot(c.Xc - xc, c.Yc - yc) < 1e-2
                                and abs(c.Radius - r) < 1e-2
                            ):
                                target_c = c
                                break
                        if target_c is None:
                            log.warning(
                                f"  [API7 DIM] Не найдена окружность R={r} в ({xc},{yc}) для размера '{var_name}'"
                            )
                            continue

                        dd = _wrap(K7.IDiametralDimension, ddims.Add())
                        dd.BaseObject = _ole(target_c)
                        dd.DimensionType = True
                        dd.Angle = float(angle_deg)
                        ok_dd = dd.Update()
                        log.debug(
                            f"  [API7 DIM] Создан IDiametralDimension для R={r:.2f} (D={r * 2:.2f}), "
                            f"expr='{var_name}' -> update={ok_dd}"
                        )
                        self._make_dim_driving(dd, var_name)

                # 2. Создаем линейные размеры (ILineDimensions), если есть
                if builder.pending_lin_dims:
                    ldims = _wrap(K7.ILineDimensions, sym_c.LineDimensions)
                    for x1, y1, x2, y2, px, py, expr in builder.pending_lin_dims:
                        ld = _wrap(K7.ILineDimension, ldims.Add())
                        ld.X1, ld.Y1 = x1, y1
                        ld.X2, ld.Y2 = x2, y2
                        ld.X3, ld.Y3 = px, py
                        if abs(y2 - y1) < 1e-6 and abs(x2 - x1) > 1e-6:
                            ld.Orientation = 1
                        elif abs(x2 - x1) < 1e-6 and abs(y2 - y1) > 1e-6:
                            ld.Orientation = 2
                        else:
                            ld.Orientation = 0
                        ok_ld = ld.Update()
                        log.debug(
                            f"  [API7 DIM] Создан ILineDimension expr='{expr}' -> update={ok_ld}"
                        )
                        self._make_dim_driving(ld, expr)

                # 3. Накладываем параметрические ограничения на окружности
                # Порог для определения окружностей в начале координат (увеличен для устойчивости к погрешностям)
                ORIGIN_THRESHOLD = 1e-2
                origin_circles = [
                    c for c in all_circles if math.hypot(c.Xc, c.Yc) < ORIGIN_THRESHOLD
                ]
                offset_circles = [
                    c for c in all_circles if math.hypot(c.Xc, c.Yc) >= ORIGIN_THRESHOLD
                ]
                log.info(f"  [API7 CONSTRAINTS] Origin circles: {len(origin_circles)}, Offset circles: {len(offset_circles)}")
                for c in origin_circles:
                    log.info(f"    Origin circle: R={c.Radius:.2f}, center=({c.Xc:.6f}, {c.Yc:.6f})")
                for c in offset_circles:
                    log.info(f"    Offset circle: R={c.Radius:.2f}, center=({c.Xc:.6f}, {c.Yc:.6f}), dist={math.hypot(c.Xc, c.Yc):.6f}")

                # Создаём точку в начале координат (0,0) и фиксируем её через Horizontal+Vertical
                # Это даст нам опорную точку для привязки центров окружностей
                origin_point = None
                if origin_circles:
                    try:
                        points = _wrap(K7.IPoints, dc.Points)
                        origin_point = _wrap(K7.IPoint, points.Add())
                        # Устанавливаем координаты точки в (0,0)
                        origin_point.X = 0.0
                        origin_point.Y = 0.0
                        origin_point.Update()
                        # Фиксируем точку через Horizontal (1) + Vertical (2) на самой точке
                        # Fix (0) на точке не работает, но Horizontal+Vertical зафиксируют X и Y
                        dobj_pt = _wrap(K7.IDrawingObject1, origin_point)
                        for fix_code, name in [(1, "Horizontal"), (2, "Vertical")]:
                            con_fix_pt = _wrap(K7.IParametriticConstraint, dobj_pt.NewConstraint())
                            con_fix_pt.ConstraintType = fix_code
                            con_fix_pt.Index = 0
                            if con_fix_pt.Create():
                                log.info(f"  [API7 CONSTRAINTS] Точка в (0,0) зафиксирована через {name} (ConstraintType={fix_code})")
                            else:
                                log.warning(f"  [API7 CONSTRAINTS] {name} constraint на точке не применился (Create вернул False)")
                        origin_point.Update()
                        log.info("  [API7 CONSTRAINTS] Создана и зафиксирована точка в начале координат (0,0)")
                    except Exception as e:
                        log.warning(f"  [API7 CONSTRAINTS] Не удалось создать точку в (0,0): {e}")
                        origin_point = None

                # Фиксируем центры окружностей в начале координат через выравнивание с точкой
                for c0 in origin_circles:
                    dobj0 = _wrap(K7.IDrawingObject1, c0)
                    if origin_point:
                        # Выравнивание по вертикали (X = 0)
                        con_al_v = _wrap(K7.IParametriticConstraint, dobj0.NewConstraint())
                        con_al_v.ConstraintType = 10  # Vertical alignment
                        con_al_v.Index = 0
                        con_al_v.Partner = _ole(origin_point)
                        con_al_v.PartnerIndex = 0
                        al_v_created = con_al_v.Create()
                        if al_v_created:
                            log.info(f"  [API7 CONSTRAINTS] Центр R={c0.Radius:.2f} выравнен по вертикали с точкой (0,0)")
                        else:
                            log.warning(f"  [API7 CONSTRAINTS] Vertical alignment для R={c0.Radius:.2f} не применился (Create вернул False)")
                        # Выравнивание по горизонтали (Y = 0)
                        con_al_h = _wrap(K7.IParametriticConstraint, dobj0.NewConstraint())
                        con_al_h.ConstraintType = 11  # Horizontal alignment
                        con_al_h.Index = 0
                        con_al_h.Partner = _ole(origin_point)
                        con_al_h.PartnerIndex = 0
                        al_h_created = con_al_h.Create()
                        if al_h_created:
                            log.info(f"  [API7 CONSTRAINTS] Центр R={c0.Radius:.2f} выравнен по горизонтали с точкой (0,0)")
                        else:
                            log.warning(f"  [API7 CONSTRAINTS] Horizontal alignment для R={c0.Radius:.2f} не применился (Create вернул False)")
                        c0.Update()
                    else:
                        # Fallback: пробуем Horizontal (1) если точка не создалась
                        for fix_code in (1,):
                            try:
                                con_fix = _wrap(
                                    K7.IParametriticConstraint, dobj0.NewConstraint()
                                )
                                con_fix.ConstraintType = fix_code
                                con_fix.Index = 0
                                if con_fix.Create():
                                    c0.Update()
                                    log.info(
                                        f"  [API7 CONSTRAINTS] Центр окружности R={c0.Radius:.2f} ограничен ConstraintType={fix_code} (fallback)"
                                    )
                                    break
                            except Exception:
                                continue

                for c_off in offset_circles:
                    dobj_off = _wrap(K7.IDrawingObject1, c_off)
                    dist = math.hypot(c_off.Xc, c_off.Yc)
                    for c0 in origin_circles:
                        if abs(dist - c0.Radius) < 1e-2:
                            con_poc = _wrap(
                                K7.IParametriticConstraint, dobj_off.NewConstraint()
                            )
                            con_poc.ConstraintType = 9  # Точка на кривой
                            con_poc.Index = 0
                            con_poc.Partner = _ole(c0)
                            ok_poc = con_poc.Create()
                            log.info(
                                f"  [API7 CONSTRAINTS] 'Точка на кривой' (code=9) -> ok={ok_poc}"
                            )

                            if abs(c_off.Xc - c0.Xc) < 1e-4:
                                con_al = _wrap(
                                    K7.IParametriticConstraint, dobj_off.NewConstraint()
                                )
                                con_al.ConstraintType = 10  # Выравнивание по вертикали
                                con_al.Index = 0
                                con_al.Partner = _ole(c0)
                                con_al.PartnerIndex = 0
                                ok_al = con_al.Create()
                                log.info(
                                    f"  [API7 CONSTRAINTS] 'Выравнивание по вертикали' (code=10) -> ok={ok_al}"
                                )
                            elif abs(c_off.Yc - c0.Yc) < 1e-4:
                                con_al = _wrap(
                                    K7.IParametriticConstraint, dobj_off.NewConstraint()
                                )
                                con_al.ConstraintType = (
                                    11  # Выравнивание по горизонтали
                                )
                                con_al.Index = 0
                                con_al.Partner = _ole(c0)
                                con_al.PartnerIndex = 0
                                ok_al = con_al.Create()
                                log.info(
                                    f"  [API7 CONSTRAINTS] 'Выравнивание по горизонтали' (code=11) -> ok={ok_al}"
                                )
                            c_off.Update()
                            break
            finally:
                sk7.EndEdit()
        except Exception as e:
            log.error(
                f"  [API7 SKETCH ERROR] Исключение при создании размеров/связей: {e}\n{traceback.format_exc()}"
            )

    def create_sketch(self, plane="xy", draw_fn=None, auto_parametrize: bool = True):
        """Создает эскиз на базовой плоскости или плоской грани, рисует геометрию и размеры, привязывает формулы."""
        plane_ent = (
            self.get_base_plane(plane)
            if isinstance(plane, (str, int))
            else _wrap(K5.ksEntity, plane)
        )
        sk_ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_SKETCH))
        sk_def = _wrap(K5.ksSketchDefinition, sk_ent.GetDefinition())
        sk_def.SetPlane(_ole(plane_ent))
        sk_ent.Create()

        pl_label = (
            plane
            if isinstance(plane, str)
            else (plane_ent.name or f"Грань(type={plane_ent.type})")
        )
        log.info(
            f"[SKETCH START] Создан '{sk_ent.name}' на базовой поверхности: {pl_label}"
        )

        vars_before = set(self._get_all_feature_var_names())

        # Шаг 1: Рисуем геометрию в 2D-редакторе API5
        doc2d = sk_def.BeginEdit()
        self._active_sketch_def = sk_def
        try:
            builder = SketchBuilder(doc2d, api5=self.api5, part=self)
            if callable(draw_fn):
                draw_fn(builder)
        except Exception as e:
            log.error(
                f"[FAIL SKETCH] Ошибка внутри '{sk_ent.name}': {e}\n{traceback.format_exc()}"
            )
            try:
                sk_def.EndEdit()
                self._active_sketch_def = None
            except Exception:
                pass
            self.close()
            raise RuntimeError(
                f"[FAIL SKETCH] Ошибка при построении эскиза: {e}"
            ) from e
        else:
            sk_def.EndEdit()
            self._active_sketch_def = None
            self.part.Update()

        # Шаг 2: Создаем размеры и накладываем ограничения через API7 (включая привязку к точке (0,0))
        if auto_parametrize or builder.pending_diam_dims or builder.pending_lin_dims:
            self._apply_api7_sketch_dims_and_constraints(sk_ent, builder)
            self.part.Update()

        # Шаг 3: Запускаем ksParametrizeObjects ПОСЛЕ создания размеров и ограничений — автоналожение оставшихся связей
        if auto_parametrize:
            doc2d = sk_def.BeginEdit()
            try:
                builder.doc2d = _wrap(K5.ksDocument2D, doc2d)
                builder.parametrize()
            finally:
                sk_def.EndEdit()
            self.part.Update()

        # Шаг 4: Привязываем формулы ('D', 'ds', 'o1', 'do', 'o2') к новым переменным v...
        if builder.pending_expressions:
            self._bind_new_vars_to_expressions(
                vars_before, builder.pending_expressions, context=sk_ent.name
            )
            self.part.RebuildModel()
            self.part.Update()

        sf7 = self._find_sketch_feature7(sk_ent)
        tree_name = str(sf7.Name).strip() if sf7 else sk_ent.name
        log.info(f"[SKETCH DONE] Статус в дереве модели: '{tree_name}'")
        return sk_ent

    def create_sketch_on_face(
        self, face_entity, draw_fn=None, auto_parametrize: bool = True
    ):
        """Создает эскиз на указанной плоской грани детали."""
        return self.create_sketch(
            plane=face_entity, draw_fn=draw_fn, auto_parametrize=auto_parametrize
        )

    def extrude(
        self,
        sketch_ent,
        depth: float,
        direction: int = DT_NORMAL,
        draft_angle: float = 0.0,
        expr: str = None,
    ):
        """Базовое или добавляющее выдавливание."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_BASE_EXTRUDE))
        defn = _wrap(K5.ksBaseExtrusionDefinition, ent.GetDefinition())
        defn.directionType = direction
        defn.SetSideParam(True, 0, float(depth), float(draft_angle), False)
        if direction in (DT_BOTH, DT_MIDDLE):
            defn.SetSideParam(False, 0, float(depth), float(draft_angle), False)
        defn.SetSketch(_ole(sketch_ent))
        if not ent.Create():
            log.error(
                f"[FAIL EXTRUDE] Операция выдавливания '{ent.name}' не построилась!"
            )
            self.close()
            raise RuntimeError("[FAIL EXTRUDE] Операция выдавливания не построилась!")
        self.part.Update()

        if expr:
            self._bind_new_vars_to_expressions(
                vars_before, [(float(depth), expr)], context=ent.name
            )
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[EXTRUDE OK] '{ent.name}': depth={depth} (expr='{expr}'), "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV=+{vol_after - vol_before:.2f} мм³)"
        )
        if vol_after <= vol_before + 1e-9:
            log.error("[FAIL EXTRUDE] Объем детали не увеличился после выдавливания!")
            self.close()
            raise RuntimeError(
                "[FAIL EXTRUDE] Объем детали не увеличился после выдавливания!"
            )
        return ent

    def cut(
        self,
        sketch_ent,
        depth: float = 100.0,
        direction: int = DT_NORMAL,
        expr: str = None,
        through_all: bool = False,
    ):
        """Вырезание выдавливанием (на расстояние или «Через всё» при through_all=True)."""
        vol_before = self.volume()
        if vol_before <= 1e-9:
            log.error("[FAIL CUT] Попытка резать пустую деталь (V=0)!")
            self.close()
            raise RuntimeError("[FAIL CUT] Нельзя резать пустую деталь!")
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_CUT_EXTRUDE))
        defn = _wrap(K5.ksCutExtrusionDefinition, ent.GetDefinition())
        defn.directionType = direction
        depth_type = 1 if through_all else 0
        # Для DT_REVERSE нужно задавать параметры обратной стороны (side=False)
        if direction == DT_REVERSE:
            defn.SetSideParam(False, depth_type, float(depth), 0.0, False)
        else:
            defn.SetSideParam(True, depth_type, float(depth), 0.0, False)
        if direction in (DT_BOTH, DT_MIDDLE):
            defn.SetSideParam(False, depth_type, float(depth), 0.0, False)
        defn.SetSketch(_ole(sketch_ent))
        if not ent.Create():
            log.error(f"[FAIL CUT] Операция вырезания '{ent.name}' не построилась!")
            self.close()
            raise RuntimeError("[FAIL CUT] Операция вырезания не построилась!")
        self.part.Update()

        if expr and not through_all:
            self._bind_new_vars_to_expressions(
                vars_before, [(float(depth), expr)], context=ent.name
            )
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        mode_label = "Через всё" if through_all else f"depth={depth} (expr='{expr}')"
        log.info(
            f"[CUT OK] '{ent.name}': {mode_label}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        if vol_after >= vol_before - 1e-9:
            log.error(
                f"[FAIL CUT] Вырез промахнулся мимо тела! V_before={vol_before:.2f}, V_after={vol_after:.2f}"
            )
            self.close()
            raise RuntimeError(
                f"[FAIL CUT] Вырез промахнулся мимо тела! Объем до={vol_before:.2f}, после={vol_after:.2f}. "
                "Проверь направление (DT_NORMAL / DT_REVERSE / DT_BOTH)."
            )
        return ent

    def revolve(self, sketch_ent, angle: float = 360.0, cut: bool = False):
        """Операция вращения (o3d_baseRotated = 27) или выреза вращением (o3d_cutRotated = 29)."""
        vol_before = self.volume()
        obj_type = OBJ_CUT_ROTATE if cut else OBJ_BASE_ROTATE
        ent = _wrap(K5.ksEntity, self.part.NewEntity(obj_type))
        if cut:
            defn = _wrap(K5.ksCutRotatedDefinition, ent.GetDefinition())
        else:
            defn = _wrap(K5.ksBaseRotatedDefinition, ent.GetDefinition())
        # Для выреза вращением направление должно быть обратным (DT_REVERSE),
        # чтобы контур определял удаляемый материал, а не оставляемый
        defn.directionType = DT_REVERSE if cut else DT_NORMAL
        # ksBaseRotatedDefinition.SetSideParam(side, angle) — 2 параметра (как у cut)
        # ksCutRotatedDefinition.SetSideParam(side, angle) — 2 параметра
        dyn_defn = dynamic.DumbDispatch(defn._oleobj_)
        dyn_defn.SetSideParam(True, float(angle))
        # Назначаем эскиз — передаем саму сущность эскиза (ksEntity)
        dyn_defn.SetSketch(_ole(sketch_ent))
        if not ent.Create():
            log.error(f"[FAIL REVOLVE] Операция вращения '{ent.name}' не построилась!")
            self.close()
            raise RuntimeError(
                "[FAIL REVOLVE] Операция вращения не построилась! "
                "Убедись, что в эскизе есть осевая линия b.axis() и замкнутый контур лежит строго по одну сторону от оси."
            )
        self.part.Update()
        vol_after = self.volume()
        log.info(
            f"[REVOLVE OK] '{ent.name}' (cut={cut}, angle={angle}): "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f}"
        )
        if cut and vol_after >= vol_before - 1e-9:
            self.close()
            raise RuntimeError("[FAIL REVOLVE CUT] Вырез вращением не снял материал!")
        if not cut and vol_after <= vol_before + 1e-9:
            self.close()
            raise RuntimeError("[FAIL REVOLVE] Операция вращения не увеличила объем!")
        return ent

    def _set_circular_axis(self, defn, axis_ent):
        """Безопасно устанавливает ось кругового массива.

        Принимает либо готовую осевую сущность (o3d_axis2Planes=9, o3d_axisConeFace=11),
        либо цилиндрическую грань (o3d_face=6) — в последнем случае создает ось по ней.
        """
        # Если передана грань (type=6), создаем из неё ось
        if hasattr(axis_ent, 'type') and axis_ent.type == OBJ_FACE:
            fdef = _wrap(K5.ksFaceDefinition, axis_ent.GetDefinition())
            if fdef and fdef.IsCylinder():
                axis_ent = self.create_axis_from_cylindrical_face(axis_ent)
                log.debug(f"  [PATTERN AXIS] Создана ось из цилиндрической грани: {axis_ent.name}")

        ole_defn = _ole(defn)
        ole_axis = _ole(axis_ent)
        # Способ 1: штатный SetAxis с распакованным _ole(axis_ent)
        try:
            defn.SetAxis(ole_axis)
            log.debug("  [PATTERN AXIS] defn.SetAxis(_ole(axis_ent)) выполнен успешно")
            return
        except Exception as e0:
            log.debug(f"  [PATTERN AXIS] defn.SetAxis(_ole) вернул: {e0}")

        # Способ 2: через динамический IDispatch
        try:
            dyn_defn = dynamic.DumbDispatch(ole_defn)
            dyn_defn.SetAxis(ole_axis)
            log.debug("  [PATTERN AXIS] SetAxis выполнен через dynamic.DumbDispatch")
            return
        except Exception as e1:
            log.debug(f"  [PATTERN AXIS] dynamic.DumbDispatch.SetAxis вернул: {e1}")

        # Способ 3: перебор DISPID в vtable ksCircularCopyDefinition
        for dispid in range(1, 20):
            try:
                res = ole_defn.InvokeTypes(dispid, 0, 1, (11, 0), ((9, 0),), ole_axis)
                log.debug(
                    f"  [PATTERN AXIS] SetAxis выполнен через InvokeTypes(dispid={dispid}) -> res={res}"
                )
                return
            except Exception:
                continue

        raise RuntimeError(
            "[FAIL PATTERN AXIS] Не удалось вызвать SetAxis на ksCircularCopyDefinition!"
        )

    def circular_pattern(
        self, features: list, axis_ent, count: int = 4, angle: float = 360.0
    ):
        """Массив по концентрической сетке (o3d_circularCopy = 36)."""
        vol_before = self.volume()
        try:
            ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_CIRCULAR_COPY))
            # Получаем определение как raw COM object
            defn_raw = ent.GetDefinition()
            ole_defn = defn_raw._oleobj_ if hasattr(defn_raw, '_oleobj_') else defn_raw
            log.info(f"  [PATTERN] Definition raw object: {type(ole_defn)}")

            # Пытаемся получить массив операций через перебор DISPID
            op_array = None
            for dispid in range(0, 50):
                try:
                    # Пробуем как метод (INVOKE_FUNC = 1)
                    result = ole_defn.InvokeTypes(dispid, 0, 1, (9, 0), ())
                    if result is not None and hasattr(result, '_oleobj_'):
                        log.info(f"  [PATTERN] DISPID {dispid} как метод вернул COM object: {type(result)}")
                        op_array = result
                        break
                except Exception:
                    pass
                try:
                    # Пробуем как свойство (PROPGET = 2)
                    result = ole_defn.InvokeTypes(dispid, 0, 2, (9, 0), ())
                    if result is not None and hasattr(result, '_oleobj_'):
                        log.info(f"  [PATTERN] DISPID {dispid} как свойство вернул COM object: {type(result)}")
                        op_array = result
                        break
                except Exception:
                    pass

            if op_array is None:
                # Fallback: пробуем dynamic dispatch
                dyn_defn = dynamic.DumbDispatch(defn_raw)
                try:
                    op_array = dyn_defn.OperationArray
                    if op_array is not None and hasattr(op_array, '_oleobj_'):
                        log.info("  [PATTERN] Получен OperationArray через dynamic dispatch .OperationArray")
                except Exception:
                    pass
                if op_array is None:
                    try:
                        op_array = dyn_defn.GetOperationArray
                        if op_array is not None and hasattr(op_array, '_oleobj_'):
                            log.info("  [PATTERN] Получен OperationArray через dynamic dispatch .GetOperationArray")
                    except Exception:
                        pass

            if op_array is None or not hasattr(op_array, '_oleobj_'):
                log.error("  [PATTERN] Не удалось получить OperationArray ни одним способом")
                raise RuntimeError("[FAIL PATTERN] Не удалось получить массив операций для кругового массива")

            log.info(f"  [PATTERN] Получен OperationArray: {type(op_array)}")

            # Устанавливаем параметры массива через InvokeTypes на raw COM object
            # DISPID из SDK: count1=1, step1=2, count2=4, step2=5, factor1=3, factor2=6, geomArray=14, inverce=7
            # Для PROPPUT (4): resultType=0 (VT_EMPTY), argTypes=(VARTYPE,) для аргумента
            try:
                # count1 = 1 (int, VT_I4=3)
                ole_defn.InvokeTypes(1, 0, 4, 0, (3,), 1)
                # step1 = 10.0 (double, VT_R8=5)
                ole_defn.InvokeTypes(2, 0, 4, 0, (5,), 10.0)
                # count2 = count (int, VT_I4=3)
                ole_defn.InvokeTypes(4, 0, 4, 0, (3,), int(count))
                # step2 = angle (double, VT_R8=5)
                ole_defn.InvokeTypes(5, 0, 4, 0, (5,), float(angle))
                # factor2 = True (bool, VT_BOOL=11)
                ole_defn.InvokeTypes(6, 0, 4, 0, (11,), True)
                # geomArray = False (bool, VT_BOOL=11)
                ole_defn.InvokeTypes(14, 0, 4, 0, (11,), False)
                log.info("  [PATTERN] Параметры установлены через InvokeTypes")
            except Exception as e:
                log.warning(f"  [PATTERN] Установка параметров через InvokeTypes не удалась: {e}")

            flist = _wrap(K5.ksEntityCollection, op_array)
            flist.Clear()
            for f in features:
                flist.Add(_ole(f))

            # Устанавливаем ось через определение (передаем raw definition)
            self._set_circular_axis(defn_raw, axis_ent)
            created = ent.Create()

            if not created:
                log.warning(
                    "[PATTERN] ent.Create() с переданной гранью вернул False, пробуем ось пересечения XY x YZ..."
                )
                axis_fallback = self.create_axis_by_2_planes("xy", "yz")
                self._set_circular_axis(defn_raw, axis_fallback)
                created = ent.Create()

            if not created:
                log.error(
                    f"[FAIL PATTERN] Массив по концентрической сетке '{ent.name}' не построился!"
                )
                self.close()
                raise RuntimeError(
                    "[FAIL PATTERN] Массив по концентрической сетке не построился!"
                )
            self.part.Update()
        except Exception as e:
            log.error(f"[FAIL PATTERN EXCEPTION] {e}\n{traceback.format_exc()}")
            self.close()
            raise

        vol_after = self.volume()
        log.info(
            f"[PATTERN OK] '{ent.name}': count={count}, angle={angle}°, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    # ===================== SHEET METAL (ЛИСТОВЫЙ МЕТАЛЛ) =====================

    def create_sheet_metal_body(
        self,
        sketch_ent,
        thickness_var: str = "t",
        bend_radius_var: str = "R_bend",
        k_factor_var: str = "K_factor",
        thickness_direction: bool = True,
        thickness_expr: str = None,
        bend_radius_expr: str = None,
        k_factor_expr: str = None,
    ):
        """Создает тело листового металла (o3d_sheetMetalBody = 74) из эскиза."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        raw_ent = self.part.NewEntity(OBJ_SHEET_METAL_BODY)
        ole_ent = _ole(raw_ent)

        # Получаем определение через InvokeTypes (DISPID 6 — Definition)
        defn_raw = None
        for dispid in (6, 11):
            try:
                result = ole_ent.InvokeTypes(dispid, 0, 2, (9, 0), ())  # PROPGET
                if result is not None and hasattr(result, '_oleobj_'):
                    defn_raw = result
                    log.info(f"  [SHEET METAL] Получено определение через DISPID {dispid}: {type(defn_raw)}")
                    break
            except Exception as e:
                log.debug(f"  [SHEET METAL] DISPID {dispid} error: {e}")
                pass

        if defn_raw is None:
            log.error("  [SHEET METAL] Не удалось получить определение через InvokeTypes!")
            raise RuntimeError("[FAIL SHEET METAL] Не удалось получить определение тела листового металла!")

        dyn_defn = dynamic.DumbDispatch(defn_raw)
        ole_ent = _ole(raw_ent)
        ent = _wrap(K5.ksEntity, raw_ent)

        # Настраиваем базовые параметры через сырой COM
        dyn_defn.SetSketch(_ole(sketch_ent))
        dyn_defn.ThicknessDirection = thickness_direction
        dyn_defn.Straighten = False

        if not ent.Create():
            log.error(f"[FAIL SHEET METAL] Тело листового металла '{ent.name}' не построилось!")
            self.close()
            raise RuntimeError("[FAIL SHEET METAL] Тело листового металла не построилось!")
        self.part.Update()

        # Привязываем формулы к переменным толщины, радиуса, K-factor
        if thickness_expr:
            thickness_val = float(dyn_defn.Thickness)
            self._bind_new_vars_to_expressions(
                vars_before, [(thickness_val, thickness_expr)], context=f"{ent.name}.Thickness"
            )
        if bend_radius_expr:
            radius_val = float(dyn_defn.BendRadius)
            self._bind_new_vars_to_expressions(
                vars_before, [(radius_val, bend_radius_expr)], context=f"{ent.name}.Radius"
            )
        if k_factor_expr:
            k_val = float(dyn_defn.KFactor)
            self._bind_new_vars_to_expressions(
                vars_before, [(k_val, k_factor_expr)], context=f"{ent.name}.KFactor"
            )

        self.part.RebuildModel()
        self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[SHEET METAL BODY OK] '{ent.name}': thickness={thickness_expr}, "
            f"radius={bend_radius_expr}, k_factor={k_factor_expr}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def add_bend(
        self,
        face_entity,
        length_var: str = "H_flange",
        bend_radius_var: str = "R_bend",
        angle_var: str = "Bend_Angle",
        k_factor_var: str = "K_factor",
        bend_allowance_var: str = "BA",
        bend_deduction_var: str = "BD",
        relief_h_var: str = "Relief_H",
        relief_w_var: str = "Relief_W",
        direction: bool = True,
        disposal: int = 0,
        length_type: int = 0,
        offset_type: int = 0,
        side_type: int = 0,
        bend_release: int = 0,
        dismissal_width: float = None,
        dismissal_depth: float = None,
        dismissal_angle_type: int = 0,
        length_expr: str = None,
        radius_expr: str = None,
        angle_expr: str = None,
        k_factor_expr: str = None,
        ba_expr: str = None,
        bd_expr: str = None,
        relief_h_expr: str = None,
        relief_w_expr: str = None,
    ):
        """Добавляет сгиб (o3d_sheetMetalBend = 75) к грани листового тела."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        raw_ent = self.part.NewEntity(OBJ_SHEET_METAL_BEND)
        defn_raw = raw_ent.GetDefinition()
        dyn_defn = dynamic.DumbDispatch(defn_raw)
        ent = _wrap(K5.ksEntity, raw_ent)

        defn_raw.SetBendObject(_ole(face_entity))
        dyn_defn.Direction = direction
        dyn_defn.Disposal = disposal
        dyn_defn.LengthType = length_type
        dyn_defn.OffsetType = offset_type
        dyn_defn.LeftSideType = side_type
        dyn_defn.RightSideType = side_type
        dyn_defn.BendRelease = bend_release
        dyn_defn.Straighten = False

        if dismissal_width is not None:
            dyn_defn.DismissalWidth = dismissal_width
            dyn_defn.DismissalWithWidth = True
        if dismissal_depth is not None:
            dyn_defn.DismissalDepth = dismissal_depth
        dyn_defn.DismissalAngleType = dismissal_angle_type

        if not ent.Create():
            log.error(f"[FAIL BEND] Сгиб '{ent.name}' не построился!")
            self.close()
            raise RuntimeError("[FAIL BEND] Сгиб не построился!")
        self.part.Update()

        # Привязываем формулы
        pending = []
        if length_expr:
            pending.append((float(dyn_defn.Length), length_expr))
        if radius_expr:
            pending.append((float(dyn_defn.BendRadius), radius_expr))
        if angle_expr:
            pending.append((float(dyn_defn.BendAngle), angle_expr))
        if k_factor_expr:
            pending.append((float(dyn_defn.KFactor), k_factor_expr))
        if ba_expr:
            pending.append((float(dyn_defn.BendAllowance), ba_expr))
        if bd_expr:
            pending.append((float(dyn_defn.BendDeduction), bd_expr))
        if relief_h_expr:
            pending.append((float(dyn_defn.DismissalDepth), relief_h_expr))
        if relief_w_expr:
            pending.append((float(dyn_defn.DismissalWidth), relief_w_expr))

        if pending:
            self._bind_new_vars_to_expressions(vars_before, pending, context=ent.name)
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[BEND OK] '{ent.name}': length={length_expr}, radius={radius_expr}, angle={angle_expr}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def close_corners(self, corner_type: int = 0, gap: float = 0.1):
        """Замыкает углы листового тела (o3d_sheetMetalClosedCorner = 539)."""
        vol_before = self.volume()

        raw_ent = self.part.NewEntity(OBJ_SHEET_METAL_CLOSED_CORNER)
        defn_raw = raw_ent.GetDefinition()
        dyn_defn = dynamic.DumbDispatch(defn_raw)
        ent = _wrap(K5.ksEntity, raw_ent)

        # Получаем все сгибы для замыкания
        container = _wrap(K5.ksEntity, self.part.GetSheetMetalContainer())
        dyn_container = dynamic.DumbDispatch(container._oleobj_)
        bends = dyn_container.SheetMetalBends

        bend_collection = dyn_defn.Bends
        for i in range(bends.Count):
            bend = bends.Item(i)
            bend_collection.Add(_ole(bend))

        dyn_defn.Gap = gap

        if not ent.Create():
            log.error(f"[FAIL CLOSE CORNERS] Замыкание углов '{ent.name}' не построилось!")
            self.close()
            raise RuntimeError("[FAIL CLOSE CORNERS] Замыкание углов не построилось!")
        self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[CLOSE CORNERS OK] '{ent.name}': gap={gap}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def sheet_metal_cut(
        self,
        sketch_ent,
        cut_type: int = 0,
        depth: float = 10.0,
        depth_expr: str = None,
        body_entity: any = None,
    ):
        """Вырезает в листовом теле по эскизу (o3d_sheetMetalCut = 78)."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        raw_ent = self.part.NewEntity(OBJ_SHEET_METAL_CUT)
        defn_raw = raw_ent.GetDefinition()
        dyn_defn = dynamic.DumbDispatch(defn_raw)
        ent = _wrap(K5.ksEntity, raw_ent)

        defn_raw.SetSketch(_ole(sketch_ent))
        dyn_defn.CutType = cut_type
        dyn_defn.Depth = float(depth)
        dyn_defn.Cut = True

        if body_entity:
            defn_raw.SetBody(_ole(body_entity))

        if not ent.Create():
            log.error(f"[FAIL SHEET METAL CUT] Вырез в листовом теле '{ent.name}' не построился!")
            self.close()
            raise RuntimeError("[FAIL SHEET METAL CUT] Вырез в листовом теле не построился!")
        self.part.Update()

        if depth_expr:
            self._bind_new_vars_to_expressions(
                vars_before, [(float(depth), depth_expr)], context=ent.name
            )
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[SHEET METAL CUT OK] '{ent.name}': depth={depth_expr or depth}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def fillet(self, edges: list, radius: float, expr: str = None):
        """Скругление ребер (o3d_fillet = 34)."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_FILLET))
        defn = _wrap(K5.ksFilletDefinition, ent.GetDefinition())
        defn.radius = float(radius)
        defn.tangent = True  # распространять по касательным

        edge_collection = _wrap(K5.ksEntityCollection, defn.array())
        for edge in edges:
            edge_collection.Add(_ole(edge))

        if not ent.Create():
            log.error(f"[FAIL FILLET] Операция скругления '{ent.name}' не построилась!")
            self.close()
            raise RuntimeError("[FAIL FILLET] Операция скругления не построилась!")
        self.part.Update()

        if expr:
            self._bind_new_vars_to_expressions(
                vars_before, [(float(radius), expr)], context=ent.name
            )
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[FILLET OK] '{ent.name}': radius={radius} (expr='{expr}'), "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def chamfer(self, edges: list, distance: float, angle: float = 45.0, expr: str = None):
        """Фаска ребер (o3d_chamfer = 33). distance — длина фаски, angle — угол (обычно 45°).
        В API5 фаска задается двумя расстояниями distance1, distance2 и флагом transfer.
        Для симметричной фаски 45°: distance1 = distance2 = distance, transfer = False.
        """
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_CHAMFER))
        defn = _wrap(K5.ksChamferDefinition, ent.GetDefinition())
        # Для симметричной фаски 45°: distance1 = distance2 = distance, transfer = False
        defn.SetChamferParam(False, float(distance), float(distance))
        defn.tangent = True

        edge_collection = _wrap(K5.ksEntityCollection, defn.array())
        for edge in edges:
            edge_collection.Add(_ole(edge))

        if not ent.Create():
            log.error(f"[FAIL CHAMFER] Операция фаски '{ent.name}' не построилась!")
            self.close()
            raise RuntimeError("[FAIL CHAMFER] Операция фаски не построилась!")
        self.part.Update()

        if expr:
            self._bind_new_vars_to_expressions(
                vars_before, [(float(distance), expr)], context=ent.name
            )
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[CHAMFER OK] '{ent.name}': distance={distance}, angle={angle} (expr='{expr}'), "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def create_connection_surface(self, edges, tension1: float = 50.0, tension2: float = 50.0):
        """Поверхность соединения (Connection Surface / Lofted Surface) по ребрам.
        edges — список ребер, по которым строится поверхность.
        tension1, tension2 — натяжение (0-100)."""
        vol_before = self.volume()

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_LOFT))
        defn = _wrap(K5.ksLoftDefinition, ent.GetDefinition())
        # Добавление сечений (ребер) через array()
        dyn_defn = dynamic.DumbDispatch(defn._oleobj_)
        arr = dyn_defn.array()
        for edge in edges:
            arr.Add(_ole(edge))
        dyn_defn.Tension1 = tension1
        dyn_defn.Tension2 = tension2

        if not ent.Create():
            log.error(f"[FAIL CONNECTION SURFACE] Поверхность соединения не построилась!")
            self.close()
            raise RuntimeError("[FAIL CONNECTION SURFACE] Поверхность соединения не построилась!")
        self.part.Update()
        log.info(f"[CONNECTION SURFACE OK] '{ent.name}' создана")
        return ent

    def create_ruled_surface(self, edges, tension1: float = 50.0, tension2: float = 50.0):
        """Линейчатая поверхность (Ruled Surface) по ребрам (o3d_RuledSurface = 515)."""
        vol_before = self.volume()
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_RULED_SURFACE))
        defn = _wrap(K5.ksRuledSurfaceDefinition, ent.GetDefinition())
        dyn_defn = dynamic.DumbDispatch(defn._oleobj_)
        arr = dyn_defn.array()
        for edge in edges:
            arr.Add(_ole(edge))
        dyn_defn.Tension1 = tension1
        dyn_defn.Tension2 = tension2

        if not ent.Create():
            log.error(f"[FAIL RULED SURFACE] Линейчатая поверхность не построилась!")
            self.close()
            raise RuntimeError("[FAIL RULED SURFACE] Линейчатая поверхность не построилась!")
        self.part.Update()
        log.info(f"[RULED SURFACE OK] '{ent.name}' создана")
        return ent

    def sew_surfaces(self, surfaces, tolerance: float = 0.01):
        """Сшивка поверхностей (Surface Sew) (o3d_SurfaceSewer = 96).
        surfaces — список поверхностей (faces/surfaces) для сшивки.
        tolerance — точность сшивки."""
        vol_before = self.volume()
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_SURFACE_SEW))
        defn = _wrap(K5.ksSurfaceSewerDefinition, ent.GetDefinition())
        dyn_defn = dynamic.DumbDispatch(defn._oleobj_)
        arr = dyn_defn.array()
        for surf in surfaces:
            arr.Add(_ole(surf))
        dyn_defn.Tolerance = tolerance

        if not ent.Create():
            log.error(f"[FAIL SURFACE SEW] Сшивка поверхностей не построилась!")
            self.close()
            raise RuntimeError("[FAIL SURFACE SEW] Сшивка поверхностей не построилась!")
        self.part.Update()
        log.info(f"[SURFACE SEW OK] Сшивка '{ent.name}' создана")
        return ent

    def point_pattern(self, features: list, points: list):
        """Массив по точкам (o3d_PointDrivenPattern = 507).
        points — список 2D-точек эскиза (IPoint) или 3D-точек/вершин.
        Работает через API5 определение (получаемое через InvokeTypes на сырой сущности).
        """
        vol_before = self.volume()

        try:
            # 1. Создаём СЫРУЮ сущность через API5 части (как в рабочем тесте: part.part.NewEntity)
            raw_ent = self.part.NewEntity(OBJ_POINT_PATTERN)
            ole_ent = _ole(raw_ent)  # получаем сырой COM

            # 2. Получаем определение через InvokeTypes на сырой сущности (DISPID 6 — Definition)
            defn_raw = None
            for dispid in (6, 11):
                try:
                    result = ole_ent.InvokeTypes(dispid, 0, 2, (9, 0), ())  # PROPGET
                    if result is not None and hasattr(result, '_oleobj_'):
                        defn_raw = result
                        log.info(f"  [POINT PATTERN] Получено определение через DISPID {dispid}: {type(defn_raw)}")
                        break
                except Exception as e:
                    log.debug(f"  [POINT PATTERN] DISPID {dispid} error: {e}")
                    pass

            if defn_raw is None:
                log.error("  [POINT PATTERN] Не удалось получить определение через InvokeTypes!")
                raise RuntimeError("[FAIL POINT PATTERN] Не удалось получить определение массива по точкам!")

            ole_defn = defn_raw._oleobj_ if hasattr(defn_raw, '_oleobj_') else defn_raw
            log.info(f"  [POINT PATTERN] Definition raw object: {type(ole_defn)}")

            # 3. Получаем массив исходных объектов (InitialObjects) через DISPID
            op_array = None
            for dispid in range(0, 50):
                try:
                    result = ole_defn.InvokeTypes(dispid, 0, 1, (9, 0), ())
                    if result is not None and hasattr(result, '_oleobj_'):
                        log.info(f"  [POINT PATTERN] DISPID {dispid} как метод вернул COM object: {type(result)}")
                        op_array = result
                        break
                except Exception:
                    pass
                try:
                    result = ole_defn.InvokeTypes(dispid, 0, 2, (9, 0), ())
                    if result is not None and hasattr(result, '_oleobj_'):
                        log.info(f"  [POINT PATTERN] DISPID {dispid} как свойство вернул COM object: {type(result)}")
                        op_array = result
                        break
                except Exception:
                    pass

            if op_array is None:
                dyn_defn = dynamic.DumbDispatch(defn_raw)
                try:
                    op_array = dyn_defn.InitialObjects
                    if op_array is not None and hasattr(op_array, '_oleobj_'):
                        log.info("  [POINT PATTERN] Получен InitialObjects через dynamic dispatch .InitialObjects")
                except Exception:
                    pass
                if op_array is None:
                    try:
                        op_array = dyn_defn.GetInitialObjects
                        if op_array is not None and hasattr(op_array, '_oleobj_'):
                            log.info("  [POINT PATTERN] Получен InitialObjects через dynamic dispatch .GetInitialObjects")
                    except Exception:
                        pass

            if op_array is None or not hasattr(op_array, '_oleobj_'):
                log.error("  [POINT PATTERN] Не удалось получить InitialObjects ни одним способом")
                raise RuntimeError("[FAIL POINT PATTERN] Не удалось получить массив исходных объектов для массива по точкам")

            log.info(f"  [POINT PATTERN] Получен InitialObjects: {type(op_array)}")

            flist = _wrap(K5.ksEntityCollection, op_array)
            flist.Clear()
            for f in features:
                flist.Add(_ole(f))

            # 4. Получаем коллекцию DrivenObjects (управляющие объекты/точки) — DISPID 101
            driven_objects = None
            dyn_defn = dynamic.DumbDispatch(defn_raw)
            try:
                driven_objects = dyn_defn.DrivenObjects
                if driven_objects is not None and hasattr(driven_objects, '_oleobj_'):
                    log.info("  [POINT PATTERN] Получен DrivenObjects через dynamic dispatch .DrivenObjects")
            except Exception:
                pass

            if driven_objects is None:
                try:
                    result = ole_defn.InvokeTypes(101, 0, 2, (9, 0), ())  # PROPGET
                    if result is not None and hasattr(result, '_oleobj_'):
                        driven_objects = result
                        log.info("  [POINT PATTERN] Получен DrivenObjects через InvokeTypes(101)")
                except Exception:
                    pass

            if driven_objects is None:
                for dispid in range(0, 150):
                    try:
                        result = ole_defn.InvokeTypes(dispid, 0, 2, (9, 0), ())
                        if result is not None and hasattr(result, '_oleobj_'):
                            log.info(f"  [POINT PATTERN] DISPID {dispid} как свойство вернул: {type(result)}")
                            driven_objects = result
                            break
                    except Exception:
                        pass

            if driven_objects is None or not hasattr(driven_objects, '_oleobj_'):
                log.error("  [POINT PATTERN] Не удалось получить DrivenObjects ни одним способом")
                raise RuntimeError("[FAIL POINT PATTERN] Не удалось получить коллекцию управляющих объектов для массива по точкам")

            log.info(f"  [POINT PATTERN] Получен DrivenObjects: {type(driven_objects)}")

            dlist = _wrap(K5.ksEntityCollection, driven_objects)
            dlist.Clear()
            for pt in points:
                dlist.Add(_ole(pt))

            # 5. Базовая точка и тип массива
            try:
                # BasePointType (DISPID 9) = 0 (ksCRAuto)
                ole_defn.InvokeTypes(9, 0, 4, 0, (3,), 0)
                # GeometryPattern (DISPID 8) = False
                ole_defn.InvokeTypes(8, 0, 4, 0, (11,), False)
            except Exception as e:
                log.warning(f"  [POINT PATTERN] Не удалось установить доп. параметры: {e}")

            # 6. Теперь оборачиваем сущность и вызываем Create()
            ent = _wrap(K5.ksEntity, raw_ent)
            created = ent.Create()

            if not created:
                log.error(f"[FAIL POINT PATTERN] Массив по точкам '{ent.name}' не построился!")
                self.close()
                raise RuntimeError("[FAIL POINT PATTERN] Массив по точкам не построился!")
            self.part.Update()
        except Exception as e:
            log.error(f"[FAIL POINT PATTERN EXCEPTION] {e}\n{traceback.format_exc()}")
            self.close()
            raise

        vol_after = self.volume()
        log.info(
            f"[POINT PATTERN OK] '{ent.name}': count={len(features)} features, {len(points)} points, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def _find_edges_by_midpoint(self, target_x: float, target_z: float, tol: float = 1.0, vertical_only: bool = True, cylindrical_only: bool = False):
        """Находит ребра, чьи середины близки к заданным (X, Z) координатам.
        vertical_only=True — только вертикальные ребра (постоянные X,Z, меняющееся Y).
        cylindrical_only=True — только цилиндрические ребра (входы в отверстия).
        """
        edges = []
        raw_collection = self.part.EntityCollection(6)  # OBJ_FACE=6
        if raw_collection is None:
            log.warning("  [FIND EDGES] EntityCollection(6) returned None")
            return edges
        part_ents = _wrap(K5.ksEntityCollection, raw_collection)
        if part_ents is None:
            log.warning("  [FIND EDGES] Failed to wrap EntityCollection")
            return edges
        count = part_ents.GetCount()
        for i in range(count):
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
                    # Проверяем цилиндричность если нужно
                    is_cyl = False
                    r = 0.0
                    try:
                        res, h, r = edge.GetCylinderParam(0.0, 0.0)
                        is_cyl = res and r > 0
                    except Exception:
                        pass
                    if cylindrical_only and not is_cyl:
                        continue
                    # Находим середину ребра
                    v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
                    v2 = _wrap(K5.ksVertexDefinition, edge.GetVertex(False))
                    if not v1 or not v2:
                        continue
                    res1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                    res2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                    if not (res1 and res2):
                        continue
                    mx, my, mz = (x1 + x2) / 2.0, (y1 + y2) / 2.0, (z1 + z2) / 2.0
                    # Проверяем вертикальность если нужно
                    dx, dy, dz = abs(x1 - x2), abs(y1 - y2), abs(z1 - z2)
                    is_vert = dx < 1e-4 and dz < 1e-4 and dy > 1e-4
                    if vertical_only and not is_vert:
                        continue
                    # Проверяем близость к целевой точке
                    if abs(mx - target_x) <= tol and abs(mz - target_z) <= tol:
                        edges.append(edge)
        return edges

    def get_window_vertical_edges(self, lo: float, bo: float):
        """Возвращает 4 вертикальных ребра углов провального окна (скругление ro).
        Окно центрировано: углы при X=±lo/2, Z=±bo/2.
        """
        edges = []
        corners = [
            (-lo / 2.0,  bo / 2.0),
            ( lo / 2.0,  bo / 2.0),
            ( lo / 2.0, -bo / 2.0),
            (-lo / 2.0, -bo / 2.0),
        ]
        for cx, cz in corners:
            found = self._find_edges_by_midpoint(cx, cz, tol=2.0, vertical_only=True)
            if found:
                edges.append(found[0])
            else:
                log.warning(f"  [WINDOW EDGES] Не найдено вертикальное ребро угла окна ({cx:.1f}, {cz:.1f})")
        return edges

    def get_plate_corner_edges(self, l: float, b: float):
        """Возвращает 4 вертикальных ребра углов плиты (фаска f).
        Плита центрирована: углы при X=±l/2, Z=±b/2.
        """
        edges = []
        corners = [
            (-l / 2.0,  b / 2.0),
            ( l / 2.0,  b / 2.0),
            ( l / 2.0, -b / 2.0),
            (-l / 2.0, -b / 2.0),
        ]
        for cx, cz in corners:
            found = self._find_edges_by_midpoint(cx, cz, tol=2.0, vertical_only=True)
            if found:
                edges.append(found[0])
            else:
                log.warning(f"  [PLATE EDGES] Не найдено вертикальное ребро угла плиты ({cx:.1f}, {cz:.1f})")
        return edges

    def get_hole_entrance_edges(self, face_top, dk: float, lk: float, bk: float):
        """Возвращает 4 круговые ребра входов в отверстия на верхней грани (фаска fo).
        Ищет круговые ребра во внутренних контурах верхней грани.
        """
        edges = []
        fdef = _wrap(K5.ksFaceDefinition, face_top.GetDefinition())
        if not fdef:
            return edges
        loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
        if not loops:
            return edges

        # Ожидаемые центры отверстий
        expected_centers = [
            (-lk / 2.0,  bk / 2.0),
            ( lk / 2.0,  bk / 2.0),
            ( lk / 2.0, -bk / 2.0),
            (-lk / 2.0, -bk / 2.0),
        ]
        expected_radius = dk / 2.0

        for li in range(loops.GetCount()):
            loop = _wrap(K5.ksLoop, loops.GetByIndex(li))
            loop_edges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
            if not loop_edges or loop_edges.GetCount() != 1:
                continue  # Ищем контуры из одного ребра (круговые)

            edge = _wrap(K5.ksEdgeDefinition, loop_edges.GetByIndex(0))
            if not edge:
                continue

            # Проверяем, что ребро круговое и находится в ожидаемом месте
            v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
            v2 = _wrap(K5.ksVertexDefinition, edge.GetVertex(False))
            if not v1 or not v2:
                continue
            res1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
            res2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
            if not (res1 and res2):
                continue

            # Для кругового ребра вершины совпадают (замкнутое ребро)
            cx, cz = x1, z1
            # Для кругового ребра вершины совпадают (замкнутое ребро) - точка на окружности
            cx, cz = x1, z1
            # Проверяем, близко ли к ожидаемым центрам с учетом радиуса
            # Точка на окружности находится на расстоянии expected_radius от центра
            expected_radius = dk / 2.0
            for exp_cx, exp_cz in expected_centers:
                dist = ((cx - exp_cx) ** 2 + (cz - exp_cz) ** 2) ** 0.5
                if abs(dist - expected_radius) < 1.0:  # расстояние до центра ~ радиус
                    edges.append(edge)
                    break
        return edges

    def _get_var_value(self, var_name: str) -> float:
        """Получить значение переменной по имени (из таблицы переменных детали)."""
        part7 = self._get_part7()
        if not part7:
            raise RuntimeError(f"[FAIL VAR] Не удалось получить IPart7 для чтения переменной '{var_name}'")
        try:
            var = part7.Variable(var_name)
            if var is None:
                raise RuntimeError(f"[FAIL VAR] Переменная '{var_name}' не найдена в таблице переменных")
            return float(var.Value)
        except Exception as e:
            raise RuntimeError(f"[FAIL VAR] Ошибка чтения переменной '{var_name}': {e}")

    # ===================== ПЕРЕМЕННЫЕ И ВЫРАЖЕНИЯ (API7 IFeature7.Variables) =====================
    def _get_part7(self):
        if not self.api7:
            return None
        try:
            doc7 = self.api7.ActiveDocument
            if doc7 is None:
                return None
            doc7_3d = _wrap(K7.IKompasDocument3D, doc7)
            return _wrap(K7.IPart7, doc7_3d.TopPart)
        except Exception:
            return None

    def add_variable(
        self, name: str, value: float, note: str = "", expression: str = None
    ):
        """Создает пользовательскую переменную в таблице переменных детали с комментарием."""
        part7 = self._get_part7()
        if not part7:
            raise RuntimeError(
                "[FAIL VAR] Не удалось получить IPart7 для создания переменной."
            )
        var = _wrap(K7.IVariable7, part7.AddVariable(name, float(value), str(note)))
        try:
            var.Note = str(note)
        except Exception:
            pass
        if expression:
            try:
                var.Expression = str(expression)
            except Exception:
                pass
        part7.Update()
        self._variables[name] = var
        log.info(f"[VAR ADD] {name} = {value} ({note})")
        return var

    def create_variables_from_dict(self, variables: dict[str, tuple[float, str]]):
        """Создает чистые конструкторские переменные из словаря {имя: (значение, комментарий)}."""
        result = {}
        for name, (value, note) in variables.items():
            result[name] = self.add_variable(name, value, note)
        return result

    def _collect_vars_from_feat7(self, feat7, seen: set, out_list: list):
        """Извлекает все IVariable7 из заданного IFeature7."""
        for ext_flag in (True, False):
            for sketch_flag in (False, True):
                try:
                    raw_vars = feat7.Variables(ext_flag, sketch_flag)
                except Exception:
                    continue
                if raw_vars is None:
                    continue
                items = raw_vars if isinstance(raw_vars, (list, tuple)) else [raw_vars]
                for item in items:
                    try:
                        v = _wrap(K7.IVariable7, item)
                        name = str(v.Name or "")
                        if not name or name in seen:
                            continue
                        seen.add(name)
                        out_list.append(v)
                    except Exception:
                        pass

    def _get_all_feature_vars(self) -> list:
        """
        Возвращает список всех внутренних переменных модели (v382, v386...) через API7 IFeature7,
        включая переменные всех эскизов и 3D-операций!
        """
        out_list = []
        seen = set()
        part7 = self._get_part7()
        if not part7:
            return out_list
        try:
            feat7_root = _wrap(K7.IFeature7, part7)
            self._collect_vars_from_feat7(feat7_root, seen, out_list)
            raw_sub = feat7_root.SubFeatures(0, True, False)
            sub_list = (
                raw_sub
                if isinstance(raw_sub, (list, tuple))
                else ([raw_sub] if raw_sub else [])
            )
            for item in sub_list:
                sf = _wrap(K7.IFeature7, item)
                self._collect_vars_from_feat7(sf, seen, out_list)
        except Exception as e:
            log.debug(f"Ошибка при чтении переменных API7: {e}")
        return out_list

    def _get_all_feature_var_names(self) -> list[str]:
        return [str(v.Name) for v in self._get_all_feature_vars()]

    def _bind_new_vars_to_expressions(
        self, vars_before: set[str], pending: list[tuple[float, str]], context: str = ""
    ):
        """Находит новые переменные v..., появившиеся после создания эскиза/операции, и прописывает им формулы."""
        all_vars = self._get_all_feature_vars()
        new_vars = [v for v in all_vars if str(v.Name) not in vars_before]
        new_summary = [
            f"{v.Name}={float(v.Value):.2f}({getattr(v, 'ParameterNote', '')})"
            for v in new_vars
        ]
        log.debug(f"  [VARS NEW in {context}] Появились переменные: {new_summary}")

        used = set()
        for exp_val, expr_str in pending:
            best_v = None
            best_diff = 1e9
            for v in new_vars:
                vname = str(v.Name)
                if vname in used:
                    continue
                pnote = str(getattr(v, "ParameterNote", "") or "")
                if pnote.startswith("Исключить"):
                    continue
                diff = abs(float(v.Value) - float(exp_val))
                if diff < best_diff and diff < 0.05:
                    best_diff = diff
                    best_v = v
            if best_v is not None:
                vname = str(best_v.Name)
                val_before = float(best_v.Value)
                best_v.Expression = str(expr_str)
                used.add(vname)
                log.info(
                    f"  [VAR BIND] {vname} ({getattr(best_v, 'ParameterNote', '')}, val={val_before:.2f}) "
                    f"<= формула '{expr_str}'"
                )
            else:
                log.warning(
                    f"  [VAR BIND MISS] Не найдена переменная со значением ~{exp_val:.2f} для формулы '{expr_str}'! "
                    f"Доступные новые: {new_summary}"
                )

    def rebuild(self):
        """Полное перестроение модели по таблице переменных."""
        part7 = self._get_part7()
        if part7:
            part7.Update()
        self.part.RebuildModel()
        self.part.Update()
        log.info("[REBUILD] Модель перестроена по таблице переменных.")

    def volume(self) -> float:
        self.part.Update()
        mip = _wrap(K5.ksMassInertiaParam, self.part.CalcMassInertiaProperties(0x1))
        return float(mip.v)

    def bbox(self) -> tuple[float, float, float]:
        self.part.Update()
        res, x1, y1, z1, x2, y2, z2 = self.part.GetGabarit(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        if not res:
            raise RuntimeError("[FAIL BBOX] Не удалось вычислить габарит детали.")
        return abs(x2 - x1), abs(y2 - y1), abs(z2 - z1)

    def assert_bbox(self, exp_x: float, exp_y: float, exp_z: float, tol: float = 0.1):
        """Проверяет габариты детали (в любом порядке осей)."""
        dx, dy, dz = self.bbox()
        actual_sorted = sorted([dx, dy, dz])
        exp_sorted = sorted([float(exp_x), float(exp_y), float(exp_z)])
        if any(abs(a - e) > tol for a, e in zip(actual_sorted, exp_sorted)):
            log.error(
                f"[FAIL BBOX] Габариты не совпали! Ожидалось: ({exp_x:.2f}, {exp_y:.2f}, {exp_z:.2f}) мм, "
                f"Фактически: ({dx:.2f} x {dy:.2f} x {dz:.2f}) мм."
            )
            self.close()
            raise ValueError(
                f"[FAIL BBOX] Габариты не совпали! Ожидалось: ({exp_x:.2f}, {exp_y:.2f}, {exp_z:.2f}) мм, "
                f"Фактически в КОМПАСе: ({dx:.2f} x {dy:.2f} x {dz:.2f}) мм."
            )
        log.info(
            f"[OK BBOX] Габариты подтверждены: {dx:.2f} x {dy:.2f} x {dz:.2f} мм | V = {self.volume():.2f} мм³"
        )

    def close_if_already_open(self, filepath: str):
        if not self.api7:
            return
        try:
            abs_target = os.path.normcase(os.path.abspath(filepath))
            docs = _wrap(K7.IDocuments, self.api7.Documents)
            for i in range(docs.Count - 1, -1, -1):
                doc = _wrap(K7.IKompasDocument, docs.Item(i))
                doc_path = os.path.normcase(
                    os.path.abspath(getattr(doc, "PathName", "") or "")
                )
                if doc_path == abs_target:
                    doc.Close(0)
        except Exception:
            pass

    def save_screenshot(self, filepath: str):
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except PermissionError:
                pass
        raster = _wrap(K5.ksRasterFormatParam, self.doc3d.RasterFormatParam())
        raster.Init()
        raster.format = 4
        raster.colorBPP = 24
        raster.colorType = 3
        raster.extResolution = 150
        ok = self.doc3d.SaveAsToRasterFormat(abs_path, _ole(raster))
        log.info(f"[OK RENDER] Скриншот сохранен (ok={ok}): {abs_path}")
        return abs_path

    def save(self, filepath: str):
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        self.close_if_already_open(abs_path)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except PermissionError:
                pass
        ok = self.doc3d.SaveAs(abs_path)
        self._saved_successfully = True
        self.api5.ksEnableTaskAccess(1)
        log.info(f"[OK SAVE] Модель сохранена (ok={ok}): {abs_path}")

    def close(self):
        try:
            if self._active_sketch_def is not None:
                self._active_sketch_def.EndEdit()
                self._active_sketch_def = None
        except Exception:
            pass
        try:
            self.doc3d.close()
        except Exception:
            pass
        try:
            self.api5.ksEnableTaskAccess(1)
        except Exception:
            pass
