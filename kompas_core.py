# kompas_core.py — Ядро управления КОМПАС-3D v16.1+ (API5 + API7 + логирование)
import atexit
import logging
import math
import os
import sys
import traceback

import pythoncom
import win32com.client
from win32com.client import VARIANT, dynamic

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


# Константы КОМПАС-3D (из sdk_ref/include/ksConstants3D.h, ksConstants.h и ldefin2d.h)
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
OBJ_BASE_EXTRUDE = 24  # o3d_baseExtrusion
OBJ_BOSS_EXTRUDE = 25  # o3d_bossExtrusion (Приклеить выдавливанием)
OBJ_CUT_EXTRUDE = 26  # o3d_cutExtrusion (Вырезать выдавливанием)
OBJ_BASE_ROTATE = 27  # o3d_baseRotated (Операция вращения)
OBJ_BOSS_ROTATE = 28  # o3d_bossRotated (Приклеить вращением)
OBJ_CUT_ROTATE = 29  # o3d_cutRotated (Вырезать вращением)
OBJ_CIRCULAR_COPY = 36  # o3d_circularCopy (Массив по концентрической сетке)

# Дополнительные объекты и поверхности
OBJ_LOFT = 30  # o3d_baseLoft
OBJ_LOFT_SURFACE = 514  # o3d_LoftSurface
OBJ_RULED_SURFACE = 515  # o3d_RuledSurface
OBJ_SURFACE_SEW = 96  # o3d_SurfaceSewer

# Листовой металл
OBJ_SHEET_METAL_BODY = 74  # o3d_sheetMetalBody
OBJ_SHEET_METAL_BEND = 75  # o3d_sheetMetalBend
OBJ_SHEET_METAL_LINE_BEND = 76  # o3d_sheetMetalLineBend
OBJ_SHEET_METAL_HOLE = 77  # o3d_sheetMetalHole
OBJ_SHEET_METAL_CUT = 78  # o3d_sheetMetalCut
OBJ_SHEET_METAL_CLOSED_CORNER = 539  # o3d_sheetMetalClosedCorner
OBJ_CORNER_RELIEF = 539  # alias

DT_NORMAL = 0  # Прямое направление (на расстояние)
DT_REVERSE = 1  # Обратное направление
DT_BOTH = 2  # В оба направления
DT_MIDDLE = 3  # Средняя плоскость

STYLE_MAIN = 1  # Основная линия контура
STYLE_THIN = 2  # Тонкая/вспомогательная линия
STYLE_AXIS = 3  # Осевая линия (штрихпунктирная)

KO_PARAMETRIC_PARAM = 64  # ko_ParametrizationParam
KO_LDIM_PARAM = 45  # ko_LDimParam

# Точные коды ограничений ksConstraintTypeEnum (из sdk_ref/include/ksConstants.h)
KC_UNKNOWN = 0
KC_FIXED_POINT = 1  # ksCFixedPoint
KC_POINT_ON_CURVE = 2  # ksCPointOnCurve
KC_HORIZONTAL = 3  # ksCHorizontal
KC_VERTICAL = 4  # ksCVertical
KC_PARALLEL = 5  # ksCParallel
KC_PERPENDICULAR = 6  # ksCPerpendicular
KC_EQUAL_LENGTH = 7  # ksCEqualLength
KC_EQUAL_RADIUS = 8  # ksCEqualRadius
KC_H_ALIGN_POINTS = 9  # ksCHAlignPoints
KC_V_ALIGN_POINTS = 10  # ksCVAlignPoints
KC_MERGE_POINTS = 11  # ksCMergePoints
KC_ASSOCIATION = 12  # ksCAssociation
KC_DIM_WITH_VARIABLE = 13  # ksCDimWithVariable
KC_FIXED_DIM = 14  # ksCFixedDim
KC_TANGENT_TWO_CURVES = 15  # ksCTangentTwoCurves
KC_SYMMETRY_TWO_POINTS = 16  # ksCSymmetryTwoPoints
KC_COLLINEAR = 17  # ksCCollinear
KC_FIXED_ANGLE = 18  # ksCFixedAngle
KC_FIXED_LENGTH = 19  # ksCFixedLenght
KC_POINT_ON_CURVE_MID = 20  # ksCPointOnCurveMiddle
KC_BISECTOR = 21  # ksCBisector


class SketchBuilder:
    """Конструктор плоского 2D-эскиза с поддержкой ассоциативных размеров API7 и параметризации."""

    _logged_pp_props = False

    def __init__(self, doc2d, api5, part=None):
        self.doc2d = _wrap(K5.ksDocument2D, doc2d)
        self.api5 = api5
        self.part = part
        self.pending_expressions = []
        self.pending_diam_dims = []  # [(xc, yc, r, angle_deg, var_name)]
        self.pending_lin_dims = []  # [(x1, y1, x2, y2, px, py, expression, orientation)]
        self.pending_arcs = []  # [(xc, yc, r, angle1, angle2, direction, style)]
        self.api5_dims_to_bind = []
        self.pending_constraints = []  # [("align_h"|"align_v", p1, p2), ("equal_len", seg1, seg2)]

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
            f"  [2D] Отрезок style={style}: ({float(x1):.2f}, {float(y1):.2f}) -> ({float(x2):.2f}, {float(y2):.2f}), ref={ref}"
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
        style: int = STYLE_MAIN,
    ):
        """Прямоугольник."""
        x, y, w, h = float(x), float(y), float(w), float(h)
        if centered:
            x, y = x - w / 2.0, y - h / 2.0
        self.line(x, y, x + w, y, style=style)
        self.line(x + w, y, x + w, y + h, style=style)
        self.line(x + w, y + h, x, y + h, style=style)
        self.line(x, y + h, x, y, style=style)
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
            f"  [2D] Окружность style={style}: центр=({float(xc):.2f}, {float(yc):.2f}), R={float(r):.2f} (D={float(r) * 2:.2f}), ref={ref}"
        )
        return self

    def arc(
        self,
        xc: float,
        yc: float,
        r: float,
        angle1: float,
        angle2: float,
        direction: bool = True,
        style: int = STYLE_MAIN,
    ):
        """Регистрирует дугу (xc, yc, r, angle1, angle2) для создания через API7 IArcs."""
        self.pending_arcs.append(
            (
                float(xc),
                float(yc),
                float(r),
                float(angle1),
                float(angle2),
                bool(direction),
                int(style),
            )
        )
        log.debug(
            f"  [2D ARC QUEUE] Дуга style={style}: центр=({xc:.2f}, {yc:.2f}), R={r:.2f}, углы=({angle1:.1f}, {angle2:.1f})"
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
        log.debug(f"  [2D] Точка: ({float(x):.2f}, {float(y):.2f}), ref={ref}")
        return self

    def align_h(self, p1: tuple[float, float], p2: tuple[float, float]):
        """Выравнивание двух точек (включая середины отрезков и (0,0)) по горизонтали (KC_H_ALIGN_POINTS=9)."""
        self.pending_constraints.append(
            ("align_h", (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
        )
        return self

    def align_v(self, p1: tuple[float, float], p2: tuple[float, float]):
        """Выравнивание двух точек (включая середины отрезков и (0,0)) по вертикали (KC_V_ALIGN_POINTS=10)."""
        self.pending_constraints.append(
            ("align_v", (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
        )
        return self

    def equal_length(
        self,
        seg1: tuple[float, float, float, float],
        seg2: tuple[float, float, float, float],
    ):
        """Равенство длин двух отрезков (KC_EQUAL_LENGTH=7)."""
        self.pending_constraints.append(
            ("equal_len", tuple(float(v) for v in seg1), tuple(float(v) for v in seg2))
        )
        return self

    def center_on_origin(self, w: float, h: float):
        """Центрирует симметричный прямоугольник (w x h) относительно (0, 0) через середины сторон."""
        self.align_v((0.0, float(h) / 2.0), (0.0, 0.0))
        self.align_h((-float(w) / 2.0, 0.0), (0.0, 0.0))
        return self

    def fix_point(self, x: float, y: float):
        """Фиксирует точку или вершину отрезка в координатах (x, y) (KC_FIXED_POINT=1)."""
        self.pending_constraints.append(("fix_pt", (float(x), float(y))))
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
        orientation: int = None,
    ):
        """Регистрирует линейный размер между (x1, y1) и (x2, y2) для создания через API7.
        orientation: 0 — параллельный, 1 — горизонтальный, 2 — вертикальный, None — автоопределение.
        """
        x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
        if orientation is None:
            if abs(y2 - y1) < 1e-6 and abs(x2 - x1) > 1e-6:
                orientation = 1
            elif abs(x2 - x1) < 1e-6 and abs(y2 - y1) > 1e-6:
                orientation = 2
            else:
                orientation = 0

        if orientation == 1:
            expected_val = abs(x2 - x1)
        elif orientation == 2:
            expected_val = abs(y2 - y1)
        else:
            expected_val = math.hypot(x2 - x1, y2 - y1)

        self.pending_lin_dims.append(
            (x1, y1, x2, y2, float(px), float(py), expression, int(orientation))
        )
        if expression:
            self.pending_expressions.append((expected_val, expression))
        log.debug(
            f"  [2D DIM QUEUE] Линейный размер val={expected_val:.2f}, orient={orientation}, expr='{expression}'"
        )
        return self

    def dim_hor(
        self,
        y_line: float,
        x1: float,
        x2: float,
        var_name: str = None,
        y_pts: float = 0.0,
        y1: float = None,
        y2: float = None,
    ):
        """Горизонтальный линейный размер. Поддерживает разные Y точек привязки через y1/y2."""
        yy1 = float(y_pts if y1 is None else y1)
        yy2 = float(y_pts if y2 is None else y2)
        return self.dim_linear(
            x1,
            yy1,
            x2,
            yy2,
            (x1 + x2) / 2.0,
            y_line,
            expression=var_name,
            orientation=1,
        )

    def dim_ver(
        self,
        x_line: float,
        y1: float,
        y2: float,
        var_name: str = None,
        x_pts: float = 0.0,
        x1: float = None,
        x2: float = None,
    ):
        """Вертикальный линейный размер. Поддерживает разные X точек привязки через x1/x2."""
        xx1 = float(x_pts if x1 is None else x1)
        xx2 = float(x_pts if x2 is None else x2)
        return self.dim_linear(
            xx1,
            y1,
            xx2,
            y2,
            x_line,
            (y1 + y2) / 2.0,
            expression=var_name,
            orientation=2,
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

    def dim_linear_api5(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        px: float,
        py: float,
        expression: str = None,
        is_horizontal: bool = None,
    ):
        """Создает линейный размер через API5 (ksLinDimension)."""
        if is_horizontal is None:
            is_horizontal = abs(y2 - y1) < abs(x2 - x1)

        ldim_param = self.api5.GetParamStruct(KO_LDIM_PARAM)
        spar = ldim_param.GetSPar()
        spar.Init()
        spar.x1 = float(x1)
        spar.y1 = float(y1)
        spar.x2 = float(x2)
        spar.y2 = float(y2)
        spar.basePoint = 1
        spar.dx = float(px - (x1 + x2) / 2.0)
        spar.dy = float(py - (y1 + y2) / 2.0)
        ldim_param.SetSPar(spar)

        dpar = ldim_param.GetDPar()
        dpar.Init()
        ldim_param.SetDPar(dpar)

        dim_ref = self.doc2d.ksLinDimension(ldim_param)
        log.debug(
            f"  [2D API5] Линейный размер {'H' if is_horizontal else 'V'}: "
            f"({x1:.2f},{y1:.2f})->({x2:.2f},{y2:.2f}) pt=({px:.2f},{py:.2f}), ref={dim_ref}, expr='{expression}'"
        )
        if expression and dim_ref:
            self.api5_dims_to_bind.append(
                (dim_ref, float(x1), float(y1), float(x2), float(y2), expression)
            )
        return self

    def dim_hor_api5(
        self,
        y_line: float,
        x1: float,
        x2: float,
        var_name: str = None,
        y_pts: float = 0.0,
    ):
        """Создает горизонтальный линейный размер через API5."""
        return self.dim_linear_api5(
            x1,
            y_pts,
            x2,
            y_pts,
            (x1 + x2) / 2.0,
            y_line,
            expression=var_name,
            is_horizontal=True,
        )

    def dim_ver_api5(
        self,
        x_line: float,
        y1: float,
        y2: float,
        var_name: str = None,
        x_pts: float = 0.0,
    ):
        """Создает вертикальный линейный размер через API5."""
        return self.dim_linear_api5(
            x_pts,
            y1,
            x_pts,
            y2,
            x_line,
            (y1 + y2) / 2.0,
            expression=var_name,
            is_horizontal=False,
        )

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
                setattr(pp, k, True)
                log.debug(f"  [2D PARAM] Включено свойство pp.{k} = True")
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
        """Создает смещенную плоскость параллельно базовой."""
        if not isinstance(base_plane, (str, int)):
            base_ent = _wrap(K5.ksEntity, base_plane)
        else:
            base_ent = self.get_base_plane(base_plane)

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_PLANE_OFFSET))
        defn = _wrap(K5.ksPlaneOffsetDefinition, ent.GetDefinition())
        base_ent_raw = _ole(base_ent)
        try:
            defn.SetPlane(base_ent_raw)
        except Exception:
            dyn_defn = dynamic.DumbDispatch(defn._oleobj_)
            dyn_defn.SetPlane(base_ent_raw)
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
            raise RuntimeError(
                "[FAIL AXIS] Не удалось создать ось по цилиндрической грани!"
            )
        self.part.Update()
        log.info(f"Создана конструктивная ось по цилиндрической грани: '{ent.name}'")
        return ent

    def create_plane_by_3_points(self, p1: tuple, p2: tuple, p3: tuple):
        """Создает плоскость по 3 точкам (o3d_plane3Points = 16)."""
        ent = _wrap(K5.ksEntity, self.part.NewEntity(16))
        defn = _wrap(K5.ksPlane3PointsDefinition, ent.GetDefinition())
        pt1 = self.create_point3d(p1[0], p1[1], p1[2])
        pt2 = self.create_point3d(p2[0], p2[1], p2[2])
        pt3 = self.create_point3d(p3[0], p3[1], p3[2])
        defn.SetPoint(1, _ole(pt1))
        defn.SetPoint(2, _ole(pt2))
        defn.SetPoint(3, _ole(pt3))
        if not ent.Create():
            log.error("[FAIL PLANE 3PTS] Не удалось создать плоскость по 3 точкам!")
            self.close()
            raise RuntimeError(
                "[FAIL PLANE 3PTS] Не удалось создать плоскость по 3 точкам!"
            )
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
        """Создает пространственную точку (o3d_point3D = 70) через API7 IPoint3D."""
        if not self.api7:
            raise RuntimeError(
                "[FAIL POINT3D] API7 недоступен для создания пространственных точек!"
            )

        part7 = self._get_part7()
        if not part7:
            raise RuntimeError("[FAIL POINT3D] Не удалось получить IPart7!")

        dyn_part7 = dynamic.DumbDispatch(_ole(part7))
        points3d = _wrap(K7.IPoints3D, dyn_part7.Points3D)
        if points3d is None:
            raise RuntimeError("[FAIL POINT3D] Не удалось получить коллекцию Points3D!")

        point3d = _wrap(K7.IPoint3D, points3d.Add())
        if not point3d:
            raise RuntimeError("[FAIL POINT3D] Points3D.Add() вернул None!")

        point3d.ParameterType = 1  # ksPParamCoord
        point3d.X = float(x)
        point3d.Y = float(y)
        point3d.Z = float(z)

        if not point3d.Update():
            log.error(
                f"[FAIL POINT3D] Не удалось создать пространственную точку в ({x}, {y}, {z})!"
            )
            raise RuntimeError(
                "[FAIL POINT3D] Не удалось создать пространственную точку!"
            )

        self.part.Update()
        log.info(f"Создана пространственная точка: ({x:.2f}, {y:.2f}, {z:.2f})")
        return point3d

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

        raw_collection = self.part.EntityCollection(OBJ_FACE)
        if raw_collection is None:
            raise RuntimeError("[FAIL FACE] EntityCollection(OBJ_FACE) returned None!")
        part_ents = _wrap(K5.ksEntityCollection, raw_collection)

        candidates = []
        count = part_ents.GetCount()
        log.debug(f"[FACE SEARCH] EntityCollection count: {count}")

        for i in range(count):
            raw_ent = part_ents.GetByIndex(i)
            if raw_ent is None:
                continue
            ent = _wrap(K5.ksEntity, raw_ent)
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

    def _attach_line_dim_to_objects(
        self,
        ld,
        all_lsegs: list,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        extra_pts: list = None,
    ):
        """Привязывает ножки линейного размера (Index=1 и Index=2) к вершинам отрезков,
        2D-точкам или центрам окружностей через KC_MERGE_POINTS (11).
        """
        dobj_ld = _wrap(K7.IDrawingObject1, ld)
        candidates = []
        for ls in all_lsegs:
            candidates.append((ls.X1, ls.Y1, ls, 0))
            candidates.append((ls.X2, ls.Y2, ls, 1))
        if extra_pts:
            candidates.extend(extra_pts)

        for pt_idx, (px, py) in ((0, (x1, y1)), (1, (x2, y2))):
            attached = False
            for vx, vy, partner, p_idx in candidates:
                if math.hypot(vx - px, vy - py) < 1e-2:
                    con = _wrap(K7.IParametriticConstraint, dobj_ld.NewConstraint())
                    con.ConstraintType = KC_MERGE_POINTS  # 11
                    con.Index = pt_idx
                    con.Partner = _ole(partner)
                    con.PartnerIndex = p_idx
                    if con.Create():
                        attached = True
                        break
            if not attached:
                log.debug(
                    f"  [API7 DIM ATTACH] Точка размера Index={pt_idx} ({px:.2f}, {py:.2f}) не привязана к геометрии"
                )
        ld.Update()

    def _make_dim_driving(self, dim_obj, expr_str: str = None):
        """Делает 2D-размер API7 управляющим через KC_DIM_WITH_VARIABLE (13).
        Если присвоить con_var.Expression на месте не удаётся, формулу задаст _bind_new_vars_to_expressions() через IVariable7.
        """
        dobj = _wrap(K7.IDrawingObject1, dim_obj)
        con_var = _wrap(K7.IParametriticConstraint, dobj.NewConstraint())
        con_var.ConstraintType = KC_DIM_WITH_VARIABLE  # 13 — Размер с переменной
        con_var.Index = 0
        if con_var.Create():
            if expr_str:
                try:
                    con_var.Expression = str(expr_str)
                except Exception as e:
                    log.debug(
                        f"  [API7 DIM CONSTRAINT] con_var.Expression('{expr_str}') пропущено ({e}), привяжем через IVariable7"
                    )
            dim_obj.Update()
            log.info(
                f"  [API7 DIM CONSTRAINT] Размер сделан управляющим KC_DIM_WITH_VARIABLE=13 (expr='{expr_str}')"
            )
            return True

        log.warning(
            f"  [API7 DIM CONSTRAINT] Не удалось сделать размер управляющим (expr='{expr_str}')"
        )
        return False

    def _apply_api7_sketch_dims_and_constraints(self, sk_ent, builder: SketchBuilder):
        """
        Открывает эскиз в API7 (ISketch.BeginEdit) и:
        1. Создает дуги (IArcs), если они запланированы.
        2. Создает ассоциативные диаметральные (IDiametralDimension) и линейные (ILineDimension) размеры.
        3. Накладывает параметрические связи API7 по точным константам ksConstraintTypeEnum.
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

                # 0. Создаем дуги (IArcs), если есть
                if builder.pending_arcs:
                    arcs = _wrap(K7.IArcs, dc.Arcs)
                    for xc, yc, r, a1, a2, d_dir, st in builder.pending_arcs:
                        a = _wrap(K7.IArc, arcs.Add())
                        a.Xc = xc
                        a.Yc = yc
                        a.Radius = r
                        a.Angle1 = a1
                        a.Angle2 = a2
                        a.Direction = d_dir
                        a.Style = st
                        a.Update()

                circs = _wrap(K7.ICircles, dc.Circles)
                all_circles = [
                    _wrap(K7.ICircle, circs.Circle(i)) for i in range(circs.Count)
                ]
                lsegs = _wrap(K7.ILineSegments, dc.LineSegments)
                all_lsegs = [
                    _wrap(K7.ILineSegment, lsegs.LineSegment(i))
                    for i in range(lsegs.Count)
                ]
                pts_col = _wrap(K7.IPoints, dc.Points)
                all_points = [
                    _wrap(K7.IPoint, pts_col.Point(i)) for i in range(pts_col.Count)
                ]

                # Проверяем необходимость опорной точки в начале координат (0, 0)
                ORIGIN_THRESHOLD = 1e-2
                origin_circles = [
                    c for c in all_circles if math.hypot(c.Xc, c.Yc) < ORIGIN_THRESHOLD
                ]
                offset_circles = [
                    c for c in all_circles if math.hypot(c.Xc, c.Yc) >= ORIGIN_THRESHOLD
                ]
                con_uses_origin = any(
                    item[0] in ("align_h", "align_v")
                    and (
                        math.hypot(item[1][0], item[1][1]) < ORIGIN_THRESHOLD
                        or math.hypot(item[2][0], item[2][1]) < ORIGIN_THRESHOLD
                    )
                    for item in builder.pending_constraints
                )
                lin_uses_origin = con_uses_origin or any(
                    math.hypot(x1, y1) < ORIGIN_THRESHOLD
                    or math.hypot(x2, y2) < ORIGIN_THRESHOLD
                    for x1, y1, x2, y2, *_ in builder.pending_lin_dims
                )

                origin_point = None
                for p in all_points:
                    if math.hypot(p.X, p.Y) < ORIGIN_THRESHOLD:
                        origin_point = p
                        break

                if origin_point is None and (origin_circles or lin_uses_origin):
                    origin_point = _wrap(K7.IPoint, pts_col.Add())
                    origin_point.X = 0.0
                    origin_point.Y = 0.0
                    origin_point.Update()
                    all_points.append(origin_point)

                if origin_point is not None:
                    dobj_pt = _wrap(K7.IDrawingObject1, origin_point)
                    con_fix_pt = _wrap(
                        K7.IParametriticConstraint, dobj_pt.NewConstraint()
                    )
                    con_fix_pt.ConstraintType = KC_FIXED_POINT  # 1
                    con_fix_pt.Index = 0
                    if con_fix_pt.Create():
                        log.info(
                            "  [API7 CONSTRAINTS] Точка в (0,0) зафиксирована через KC_FIXED_POINT (1)"
                        )
                    origin_point.Update()

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
                            matches = [
                                c for c in all_circles if abs(c.Radius - r) < 1e-2
                            ]
                            if len(matches) == 1:
                                target_c = matches[0]
                            elif len(matches) > 1:
                                target_c = min(
                                    matches,
                                    key=lambda c: math.hypot(c.Xc - xc, c.Yc - yc),
                                )
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
                            f"  [API7 DIM] IDiametralDimension R={r:.2f} (D={r * 2:.2f}), expr='{var_name}' -> update={ok_dd}"
                        )
                        self._make_dim_driving(dd, var_name)

                # 2. Создаем линейные размеры (ILineDimensions)
                if builder.pending_lin_dims:
                    extra_pts = [(p.X, p.Y, p, 0) for p in all_points]
                    extra_pts.extend((c.Xc, c.Yc, c, 0) for c in all_circles)

                    ldims = _wrap(K7.ILineDimensions, sym_c.LineDimensions)
                    for (
                        x1,
                        y1,
                        x2,
                        y2,
                        px,
                        py,
                        expr,
                        orient,
                    ) in builder.pending_lin_dims:
                        ld = _wrap(K7.ILineDimension, ldims.Add())
                        if ld is None:
                            log.error(
                                f"  [API7 DIM LIN] ldims.Add() вернул None для expr='{expr}'"
                            )
                            continue
                        ld.X1, ld.Y1 = x1, y1
                        ld.X2, ld.Y2 = x2, y2
                        ld.X3, ld.Y3 = px, py
                        ld.Orientation = int(orient)
                        if not ld.Update():
                            log.error(
                                f"  [API7 DIM LIN] ld.Update() вернул False для expr='{expr}'"
                            )
                            continue
                        self._attach_line_dim_to_objects(
                            ld, all_lsegs, x1, y1, x2, y2, extra_pts=extra_pts
                        )
                        self._make_dim_driving(ld, expr)

                # 3. Ограничения на окружности
                for c0 in origin_circles:
                    dobj0 = _wrap(K7.IDrawingObject1, c0)
                    if origin_point is not None:
                        con_merge = _wrap(
                            K7.IParametriticConstraint, dobj0.NewConstraint()
                        )
                        con_merge.ConstraintType = KC_MERGE_POINTS  # 11
                        con_merge.Index = 0
                        con_merge.Partner = _ole(origin_point)
                        con_merge.PartnerIndex = 0
                        if con_merge.Create():
                            log.info(
                                f"  [API7 CONSTRAINTS] Центр R={c0.Radius:.2f} совмещен с (0,0) (KC_MERGE_POINTS=11)"
                            )
                        c0.Update()

                for c_off in offset_circles:
                    dobj_off = _wrap(K7.IDrawingObject1, c_off)
                    dist = math.hypot(c_off.Xc, c_off.Yc)
                    for c0 in origin_circles:
                        if abs(dist - c0.Radius) < 1e-2:
                            con_poc = _wrap(
                                K7.IParametriticConstraint, dobj_off.NewConstraint()
                            )
                            con_poc.ConstraintType = KC_POINT_ON_CURVE  # 2
                            con_poc.Index = 0
                            con_poc.Partner = _ole(c0)
                            ok_poc = con_poc.Create()
                            log.info(
                                f"  [API7 CONSTRAINTS] KC_POINT_ON_CURVE (2) -> ok={ok_poc}"
                            )

                            if abs(c_off.Xc - c0.Xc) < 1e-4:
                                con_al = _wrap(
                                    K7.IParametriticConstraint, dobj_off.NewConstraint()
                                )
                                con_al.ConstraintType = KC_V_ALIGN_POINTS  # 10
                                con_al.Index = 0
                                con_al.Partner = _ole(c0)
                                con_al.PartnerIndex = 0
                                ok_al = con_al.Create()
                                log.info(
                                    f"  [API7 CONSTRAINTS] KC_V_ALIGN_POINTS (10) -> ok={ok_al}"
                                )
                            elif abs(c_off.Yc - c0.Yc) < 1e-4:
                                con_al = _wrap(
                                    K7.IParametriticConstraint, dobj_off.NewConstraint()
                                )
                                con_al.ConstraintType = KC_H_ALIGN_POINTS  # 9
                                con_al.Index = 0
                                con_al.Partner = _ole(c0)
                                con_al.PartnerIndex = 0
                                ok_al = con_al.Create()
                                log.info(
                                    f"  [API7 CONSTRAINTS] KC_H_ALIGN_POINTS (9) -> ok={ok_al}"
                                )
                            c_off.Update()
                            break
                # 4. Явные геометрические ограничения (align_h, align_v, equal_len)
                if builder.pending_constraints:
                    pt_pool = [(p.X, p.Y, p, 0) for p in all_points]
                    pt_pool.extend((c.Xc, c.Yc, c, 0) for c in all_circles)
                    for ls in all_lsegs:
                        pt_pool.append((ls.X1, ls.Y1, ls, 0))
                        pt_pool.append((ls.X2, ls.Y2, ls, 1))
                        pt_pool.append(
                            ((ls.X1 + ls.X2) / 2.0, (ls.Y1 + ls.Y2) / 2.0, ls, 2)
                        )

                    def _find_pt(pt_xy):
                        for vx, vy, obj, idx in pt_pool:
                            if math.hypot(vx - pt_xy[0], vy - pt_xy[1]) < 1e-2:
                                return obj, idx
                        return None, None

                    def _find_seg(seg_pts):
                        x1s, y1s, x2s, y2s = seg_pts
                        for ls in all_lsegs:
                            d1 = math.hypot(ls.X1 - x1s, ls.Y1 - y1s) + math.hypot(
                                ls.X2 - x2s, ls.Y2 - y2s
                            )
                            d2 = math.hypot(ls.X1 - x2s, ls.Y1 - y2s) + math.hypot(
                                ls.X2 - x1s, ls.Y2 - y1s
                            )
                            if min(d1, d2) < 1e-2:
                                return ls
                        return None

                    for item in builder.pending_constraints:
                        kind = item[0]
                        if kind in ("align_h", "align_v"):
                            o1, i1 = _find_pt(item[1])
                            o2, i2 = _find_pt(item[2])
                            if o1 is not None and o2 is not None:
                                dobj1 = _wrap(K7.IDrawingObject1, o1)
                                con = _wrap(
                                    K7.IParametriticConstraint, dobj1.NewConstraint()
                                )
                                con.ConstraintType = (
                                    KC_H_ALIGN_POINTS
                                    if kind == "align_h"
                                    else KC_V_ALIGN_POINTS
                                )
                                con.Index = i1
                                con.Partner = _ole(o2)
                                con.PartnerIndex = i2
                                ok = con.Create()
                                o1.Update()
                                log.debug(
                                    f"  [API7 CONSTRAINTS] {kind} {item[1]}<->{item[2]} -> ok={ok}"
                                )
                        elif kind == "equal_len":
                            s1 = _find_seg(item[1])
                            s2 = _find_seg(item[2])
                            if s1 is not None and s2 is not None:
                                dobj1 = _wrap(K7.IDrawingObject1, s1)
                                con = _wrap(
                                    K7.IParametriticConstraint, dobj1.NewConstraint()
                                )
                                con.ConstraintType = KC_EQUAL_LENGTH
                                con.Index = -1
                                con.Partner = _ole(s2)
                                con.PartnerIndex = -1
                                ok = con.Create()
                                s1.Update()
                                log.debug(f"  [API7 CONSTRAINTS] equal_len -> ok={ok}")
                        elif kind == "fix_pt":
                            o1, i1 = _find_pt(item[1])
                            if o1 is not None:
                                dobj1 = _wrap(K7.IDrawingObject1, o1)
                                con = _wrap(
                                    K7.IParametriticConstraint, dobj1.NewConstraint()
                                )
                                con.ConstraintType = KC_FIXED_POINT
                                con.Index = i1
                                ok = con.Create()
                                o1.Update()
                                log.debug(
                                    f"  [API7 CONSTRAINTS] fix_pt {item[1]} -> ok={ok}"
                                )
            finally:
                sk7.EndEdit()
        except Exception as e:
            log.error(
                f"  [API7 SKETCH ERROR] Исключение при создании размеров/связей: {e}\n{traceback.format_exc()}"
            )

    def _finalize_api7_driving_dims(self, sk_ent):
        """Добавляет KC_FIXED_DIM (14) ко всем размерам эскиза ПОСЛЕ появления type=13 и переменных v...,
        чтобы размеры стали управляющими (не информационными).
        """
        sk_feat7 = self._find_sketch_feature7(sk_ent)
        if sk_feat7 is None:
            return
        sk7 = _wrap(K7.ISketch, sk_feat7)
        doc2d_7 = _wrap(K7.IKompasDocument2D, sk7.BeginEdit())
        try:
            v_mgr = _wrap(K7.IViewsAndLayersManager, doc2d_7.ViewsAndLayersManager)
            views = _wrap(K7.IViews, v_mgr.Views)
            v0 = _wrap(K7.IView, views.ActiveView)
            sym_c = _wrap(K7.ISymbols2DContainer, v0)
            ddims = _wrap(K7.IDiametralDimensions, sym_c.DiametralDimensions)
            ldims = _wrap(K7.ILineDimensions, sym_c.LineDimensions)

            dims = [ddims.DiametralDimension(i) for i in range(ddims.Count)]
            dims.extend(ldims.LineDimension(i) for i in range(ldims.Count))

            for dim_obj in dims:
                dobj = _wrap(K7.IDrawingObject1, dim_obj)
                raw_cons = dobj.Constraints
                cons_list = (
                    list(raw_cons)
                    if isinstance(raw_cons, (list, tuple))
                    else ([raw_cons] if raw_cons is not None else [])
                )
                has_fixed = any(
                    _wrap(K7.IParametriticConstraint, c).ConstraintType == KC_FIXED_DIM
                    for c in cons_list
                )
                if not has_fixed:
                    con = _wrap(K7.IParametriticConstraint, dobj.NewConstraint())
                    con.ConstraintType = KC_FIXED_DIM  # 14
                    con.Index = 0
                    ok = con.Create()
                    dim_obj.Update()
                    log.info(f"  [API7 DIM FINALIZE] KC_FIXED_DIM (14) -> ok={ok}")
        finally:
            sk7.EndEdit()

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

        # Шаг 2: Создаем дуги, размеры и накладываем ограничения через API7
        if (
            auto_parametrize
            or builder.pending_diam_dims
            or builder.pending_lin_dims
            or builder.pending_arcs
            or builder.pending_constraints
        ):
            self._apply_api7_sketch_dims_and_constraints(sk_ent, builder)
            self.part.Update()

        # Шаг 3: Запускаем ksParametrizeObjects ПОСЛЕ размеров и ограничений
        if auto_parametrize:
            doc2d = sk_def.BeginEdit()
            try:
                builder.doc2d = _wrap(K5.ksDocument2D, doc2d)
                builder.parametrize()
            finally:
                sk_def.EndEdit()
            self.part.Update()
        # Шаг 3.2: Делаем все размеры управляющими (добавляем KC_FIXED_DIM=14 поверх type=13)
        if builder.pending_diam_dims or builder.pending_lin_dims:
            self._finalize_api7_driving_dims(sk_ent)
            self.part.Update()

        # Шаг 3.5: Привязываем выражения к размерам API5, если использовались
        if builder.api5_dims_to_bind:
            self._bind_api5_dimension_expressions(sk_ent, builder.api5_dims_to_bind)
            self.part.Update()

        # Шаг 4: Привязываем формулы к новым переменным v...
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
        draft_angle: float = 0.0,
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
        if direction == DT_REVERSE:
            defn.SetSideParam(
                False, depth_type, float(depth), float(draft_angle), False
            )
        else:
            defn.SetSideParam(True, depth_type, float(depth), float(draft_angle), False)
        if direction in (DT_BOTH, DT_MIDDLE):
            defn.SetSideParam(
                False, depth_type, float(depth), float(draft_angle), False
            )
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

    def revolve(
        self,
        sketch_ent,
        angle: float = 360.0,
        cut: bool = False,
        angle_expr: str = None,
    ):
        """Операция вращения (o3d_baseRotated = 27) или выреза вращением (o3d_cutRotated = 29)."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        obj_type = OBJ_CUT_ROTATE if cut else OBJ_BASE_ROTATE
        ent = _wrap(K5.ksEntity, self.part.NewEntity(obj_type))
        if cut:
            defn = _wrap(K5.ksCutRotatedDefinition, ent.GetDefinition())
        else:
            defn = _wrap(K5.ksBaseRotatedDefinition, ent.GetDefinition())

        defn.directionType = DT_REVERSE if cut else DT_NORMAL
        dyn_defn = dynamic.DumbDispatch(defn._oleobj_)
        dyn_defn.SetSideParam(True, float(angle))
        dyn_defn.SetSketch(_ole(sketch_ent))
        if not ent.Create():
            log.error(f"[FAIL REVOLVE] Операция вращения '{ent.name}' не построилась!")
            self.close()
            raise RuntimeError(
                "[FAIL REVOLVE] Операция вращения не построилась! "
                "Убедись, что в эскизе есть осевая линия b.axis() и замкнутый контур лежит строго по одну сторону от оси."
            )
        self.part.Update()

        if angle_expr:
            self._bind_new_vars_to_expressions(
                vars_before, [(float(angle), angle_expr)], context=ent.name
            )
            self.part.RebuildModel()
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
        """Устанавливает ось кругового массива (ось или цилиндрическая грань)."""
        if hasattr(axis_ent, "type") and axis_ent.type == OBJ_FACE:
            fdef = _wrap(K5.ksFaceDefinition, axis_ent.GetDefinition())
            if fdef and fdef.IsCylinder():
                axis_ent = self.create_axis_from_cylindrical_face(axis_ent)

        ole_axis = _ole(axis_ent)
        try:
            defn.SetAxis(ole_axis)
            return
        except Exception:
            dyn_defn = dynamic.DumbDispatch(_ole(defn))
            dyn_defn.SetAxis(ole_axis)

    def _get_circular_op_array(self, cc_def, defn_raw):
        """Извлекает коллекцию операций из ksCircularCopyDefinition."""
        for attr in ("GetOperationArray", "OperationArray"):
            try:
                member = getattr(cc_def, attr)
                res = member() if callable(member) else member
                if res is not None:
                    return res
            except Exception:
                pass

        dyn_defn = dynamic.DumbDispatch(defn_raw)
        for attr in ("GetOperationArray", "OperationArray"):
            try:
                member = getattr(dyn_defn, attr)
                res = member() if callable(member) else member
                if res is not None:
                    return res
            except Exception:
                pass
        raise RuntimeError(
            "[FAIL PATTERN] Не удалось получить массив операций из ksCircularCopyDefinition"
        )

    def circular_pattern(
        self, features: list, axis_ent, count: int = 4, angle: float = 360.0
    ):
        """Массив по концентрической сетке (o3d_circularCopy = 36)."""
        vol_before = self.volume()
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_CIRCULAR_COPY))
        defn_raw = ent.GetDefinition()
        cc_def = _wrap(K5.ksCircularCopyDefinition, defn_raw)

        op_array = self._get_circular_op_array(cc_def, defn_raw)
        cc_def.count1 = 1
        cc_def.step1 = 10.0
        cc_def.count2 = int(count)
        cc_def.step2 = float(angle)
        cc_def.factor2 = True
        cc_def.geomArray = False

        flist = _wrap(K5.ksEntityCollection, op_array)
        flist.Clear()
        for f in features:
            flist.Add(_ole(f))

        self._set_circular_axis(cc_def, axis_ent)
        created = ent.Create()
        if not created:
            log.warning(
                "[PATTERN] ent.Create() вернул False, пробуем ось пересечения XY x YZ..."
            )
            axis_fallback = self.create_axis_by_2_planes("xy", "yz")
            self._set_circular_axis(cc_def, axis_fallback)
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
        vol_after = self.volume()
        log.info(
            f"[PATTERN OK] '{ent.name}': count={count}, angle={angle}°, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    # ===================== ЛИСТОВОЙ МЕТАЛЛ (API7 ISheetMetalContainer) =====================

    def _to_model_object7(self, ent_or_def):
        """Конвертирует объект API5 (ksEntity, ksEdgeDefinition, ksFaceDefinition) или API7 в IModelObject."""
        if isinstance(ent_or_def, K7.IModelObject):
            return ent_or_def
        raw = _ole(ent_or_def)
        if hasattr(ent_or_def, "GetEntity"):
            ent5 = ent_or_def.GetEntity()
            if ent5 is not None:
                raw = _ole(ent5)
        mo_disp = self.api5.TransferInterface(raw, 2, 0)
        if mo_disp is None:
            raise RuntimeError(
                "[FAIL TRANSFER] Не удалось перевести объект API5 в API7 IModelObject!"
            )
        return _wrap(K7.IModelObject, mo_disp)

    def create_sheet_metal_body(
        self,
        sketch_ent,
        thickness: float = 2.0,
        bend_radius: float = 5.0,
        k_factor: float = 0.4,
        thickness_direction: int = 1,
        direction: int = 0,
        unfold_type: int = 0,
        thickness_expr: str = None,
        bend_radius_expr: str = None,
        k_factor_expr: str = None,
    ):
        """Создает нативное листовое тело (Листовое тело:1) через API7 ISheetMetalBodies."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        part7 = self._get_part7()
        smc = _wrap(K7.ISheetMetalContainer, part7)
        bodies = _wrap(K7.ISheetMetalBodies, smc.SheetMetalBodies)
        sm_body = _wrap(K7.ISheetMetalBody, bodies.Add())

        sk_feat7 = self._find_sketch_feature7(sketch_ent)
        if sk_feat7 is None:
            sk_feat7 = self._to_model_object7(sketch_ent)
        sk7 = _wrap(K7.ISketch, sk_feat7)

        sm_body.Sketch = _ole(sk7)
        sm_body.Thickness = float(thickness)
        sm_body.Radius = float(bend_radius)
        sm_body.BendCoefficient = float(k_factor)
        sm_body.ThicknessDirection = bool(thickness_direction)
        sm_body.Direction = int(direction)
        sm_body.UnfoldType = int(unfold_type)
        sm_body.Straighten = False

        if not sm_body.Update():
            log.error("[FAIL SHEET METAL] Листовое тело API7 не построилось!")
            self.close()
            raise RuntimeError("[FAIL SHEET METAL] Листовое тело API7 не построилось!")

        self.part.Update()

        pending = []
        if thickness_expr:
            pending.append((float(thickness), thickness_expr))
        if bend_radius_expr:
            pending.append((float(bend_radius), bend_radius_expr))
        if k_factor_expr:
            pending.append((float(k_factor), k_factor_expr))
        if pending:
            self._bind_new_vars_to_expressions(
                vars_before, pending, context=sm_body.Name
            )
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[SHEET METAL BODY OK] '{sm_body.Name}': T={thickness}, R={bend_radius}, K={k_factor}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV=+{vol_after - vol_before:.2f} мм³)"
        )
        return sm_body

    def add_bend(
        self,
        edge_or_face,
        length: float = 16.0,
        bend_radius: float = 2.0,
        angle: float = 90.0,
        k_factor: float = 0.4,
        direction: bool = True,
        disposal: int = 0,
        length_type: int = 1,
        offset_type: int = 3,
        side_type: int = 0,
        bend_release: int = 0,
        internal_radius: bool = False,
        width: float = None,
        distance_left: float = None,
        distance_right: float = None,
        widening_left: float = None,
        widening_right: float = None,
        without_angle_release: bool = False,
        without_bend_release: bool = False,
        dismissal_angle_type: int = 0,
        offset: float = 0.0,
        length_expr: str = None,
        radius_expr: str = None,
        angle_expr: str = None,
        k_factor_expr: str = None,
        width_expr: str = None,
    ):
        """Добавляет нативный сгиб (Сгиб:N) к ребру листового тела через API7 ISheetMetalBends."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        part7 = self._get_part7()
        smc = _wrap(K7.ISheetMetalContainer, part7)
        bends = _wrap(K7.ISheetMetalBends, smc.SheetMetalBends)
        bend = _wrap(K7.ISheetMetalBend, bends.Add())

        mo_edge = self._to_model_object7(edge_or_face)
        bend.BendObject = _ole(mo_edge)
        bend.Direction = bool(direction)
        bend.Disposal = int(disposal)
        bend.Angle = float(angle)
        bend.Radius = float(bend_radius)
        bend.InternalRadius = bool(internal_radius)
        bend.BendCoefficient = float(k_factor)
        bend.LengthType = int(length_type)
        bend.LengthType1 = int(length_type)
        bend.Length = float(length)
        bend.Length1 = float(length)
        bend.OffsetType = int(offset_type)
        bend.Offset = float(offset)
        bend.LeftSideType = int(side_type)
        bend.RightSideType = int(side_type)
        if widening_left is not None:
            bend.WideningLeftSide = float(widening_left)
        if widening_right is not None:
            bend.WideningRightSide = float(widening_right)
        if width is not None:
            bend.Width = float(width)
        if distance_left is not None:
            bend.DistanceLeftSide = float(distance_left)
        if distance_right is not None:
            bend.DistanceRightSide = float(distance_right)
        bend.BendRelease = int(bend_release)
        bend.DismissalAngleType = int(dismissal_angle_type)
        bend.WithoutAngleRelease = bool(without_angle_release)
        bend.WithoutBendRelease = bool(without_bend_release)
        bend.Straighten = False

        if not bend.Update():
            log.error(f"[FAIL BEND] Сгиб '{bend.Name}' не построился!")
            self.close()
            raise RuntimeError("[FAIL BEND] Сгиб листового тела не построился!")

        self.part.Update()

        pending = []
        if length_expr:
            pending.append((float(length), length_expr))
        if radius_expr:
            pending.append((float(bend_radius), radius_expr))
        if angle_expr:
            pending.append((float(angle), angle_expr))
        if k_factor_expr:
            pending.append((float(k_factor), k_factor_expr))
        if width_expr and width is not None:
            pending.append((float(width), width_expr))
        if pending:
            self._bind_new_vars_to_expressions(vars_before, pending, context=bend.Name)
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[BEND OK] '{bend.Name}': L={length}, R={bend_radius}, Angle={angle}°, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return bend

    def add_line_bend(
        self,
        bend_object,
        face=None,
        bend_radius: float = 1.0,
        angle: float = 90.0,
        k_factor: float = 0.4,
        direction: bool = True,
        bend_left_fixed: bool = False,
        internal_radius: bool = True,
        bend_type: int = 2,
        angle_type: bool = True,
        unfold_type: int = 0,
        dismissal_angle_type: int = 0,
        radius_expr: str = None,
        angle_expr: str = None,
        k_factor_expr: str = None,
    ):
        """Добавляет нативный 'Сгиб по линии' (ISheetMetalLineBend) через API7 ISheetMetalLineBends."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        part7 = self._get_part7()
        smc = _wrap(K7.ISheetMetalContainer, part7)
        bodies = _wrap(K7.ISheetMetalBodies, smc.SheetMetalBodies)
        if bodies.Count > 0:
            sm_body = _wrap(K7.ISheetMetalBody, bodies.Item(0))
            if sm_body.Straighten:
                sm_body.Straighten = False
                self.part.Update()

        line_bends = _wrap(K7.ISheetMetalLineBends, smc.SheetMetalLineBends)
        lb = _wrap(K7.ISheetMetalLineBend, line_bends.Add())

        if hasattr(bend_object, "X1") and hasattr(bend_object, "Y1"):
            mo_disp = self.api5.TransferInterface(_ole(bend_object), 2, 0)
            if mo_disp is None:
                raise RuntimeError(
                    "[FAIL LINE BEND] TransferInterface(ILineSegment) вернул None!"
                )
            mo_line = _wrap(K7.IModelObject, mo_disp)
        else:
            mo_line = self._to_model_object7(bend_object)

        lb.Line = _ole(mo_line)
        if face is not None:
            mo_face = self._to_model_object7(face)
            lb.Faces = VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [_ole(mo_face)]
            )
        lb.Direction = bool(direction)
        lb.Radius = float(bend_radius)
        lb.InternalRadius = bool(internal_radius)
        lb.Angle = float(angle)
        lb.AngleType = bool(angle_type)
        lb.BendCoefficient = float(k_factor)
        lb.BendLeftSideFixed = bool(bend_left_fixed)
        lb.BendType = int(bend_type)
        lb.UnfoldType = int(unfold_type)
        lb.DismissalAngleType = int(dismissal_angle_type)
        lb.Straighten = False

        if not lb.Update():
            log.error(f"[FAIL LINE BEND] Сгиб по линии '{lb.Name}' не построился!")
            self.close()
            raise RuntimeError("[FAIL LINE BEND] Сгиб по линии не построился!")

        self.part.Update()

        pending = []
        if radius_expr:
            pending.append((float(bend_radius), radius_expr))
        if angle_expr:
            pending.append((float(angle), angle_expr))
        if k_factor_expr:
            pending.append((float(k_factor), k_factor_expr))
        if pending:
            self._bind_new_vars_to_expressions(vars_before, pending, context=lb.Name)
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[LINE BEND OK] '{lb.Name}': R={bend_radius}, Angle={angle}°, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return lb

    def get_sketch_line_segments(self, sketch_ent):
        """Возвращает список 3D IModelObject линий эскиза (ModelObjectType == 7) для 'Сгиб по линии'."""
        sk_feat7 = self._find_sketch_feature7(sketch_ent)
        if sk_feat7 is None:
            log.warning(
                f"[GET SEGMENTS] Не найден IFeature7 для эскиза {sketch_ent.name}"
            )
            return []

        raw_mos = sk_feat7.ModelObjects(0)
        mos = (
            list(raw_mos)
            if isinstance(raw_mos, (list, tuple))
            else ([raw_mos] if raw_mos else [])
        )
        segments = []
        for m in mos:
            mo = _wrap(K7.IModelObject, m)
            if mo is not None and mo.ModelObjectType == 7:
                segments.append(mo)
        log.info(
            f"[GET SEGMENTS] Найдено {len(segments)} 3D-линий в эскизе {sketch_ent.name}"
        )
        return segments

    def close_corners(self, *args, **kwargs):
        """Заглушка совместимости: в КОМПАС-3D V16 o3d_sheetMetalClosedCorner (539)
        не экспортируется в COM API5/API7 (GetDefinition() == None).
        """
        log.warning(
            "[CLOSE CORNERS] В КОМПАС-3D V16 операция 'Замыкание углов' не имеет COM-интерфейса (Def=None). "
            "Операция пропущена — для замыкания стыка используйте параметры ширины/расширения сгибов."
        )

    def sheet_metal_cut(
        self,
        sketch_ent,
        cut_type: int = 2,
        depth: float = 54.2,
        cut: bool = True,
        depth_expr: str = None,
    ):
        """Создает нативный 'Вырез в листовом теле' через API7 ISheetMetalCuts."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        part7 = self._get_part7()
        smc = _wrap(K7.ISheetMetalContainer, part7)
        cuts = _wrap(K7.ISheetMetalCuts, smc.SheetMetalCuts)
        sm_cut = _wrap(K7.ISheetMetalCut, cuts.Add())

        sk_feat7 = self._find_sketch_feature7(sketch_ent)
        if sk_feat7 is None:
            sk_feat7 = self._to_model_object7(sketch_ent)
        sk7 = _wrap(K7.ISketch, sk_feat7)

        sm_cut.Sketch = _ole(sk7)
        sm_cut.CutType = int(cut_type)
        if cut_type == 0:
            sm_cut.Depth = float(depth)
        sm_cut.Cut = bool(cut)

        if not sm_cut.Update():
            log.error(
                f"[FAIL SHEET METAL CUT] Вырез в листовом теле '{sm_cut.Name}' не построился!"
            )
            self.close()
            raise RuntimeError(
                "[FAIL SHEET METAL CUT] Вырез в листовом теле не построился!"
            )

        self.part.Update()

        if depth_expr and cut_type == 0:
            self._bind_new_vars_to_expressions(
                vars_before, [(float(depth), depth_expr)], context=sm_cut.Name
            )
            self.part.RebuildModel()
            self.part.Update()

        vol_after = self.volume()
        log.info(
            f"[SHEET METAL CUT OK] '{sm_cut.Name}': CutType={cut_type}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return sm_cut

    def fillet(self, edges: list, radius: float, expr: str = None):
        """Скругление ребер (o3d_fillet = 34)."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_FILLET))
        defn = _wrap(K5.ksFilletDefinition, ent.GetDefinition())
        defn.radius = float(radius)
        defn.tangent = True

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

    def chamfer(
        self, edges: list, distance: float, angle: float = 45.0, expr: str = None
    ):
        """Фаска ребер (o3d_chamfer = 33)."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_CHAMFER))
        defn = _wrap(K5.ksChamferDefinition, ent.GetDefinition())
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

    def point_pattern(
        self,
        features: list,
        driven_obj,
        base_point=None,
        projection: bool = True,
        deleted_indexes: list[int] = None,
    ):
        """Массив по точкам (o3d_PointDrivenPattern = 507) через API7 IPointDrivenPattern.
        driven_obj: эскиз с 2D-точками (ksEntity) либо список пространственных/управляющих объектов.
        """
        vol_before = self.volume()
        if not self.api7:
            raise RuntimeError("[FAIL POINT PATTERN] API7 недоступен!")

        raw_ent = self.part.NewEntity(OBJ_POINT_PATTERN)
        if raw_ent is None:
            raise RuntimeError("[FAIL POINT PATTERN] NewEntity(507) вернул None!")

        mo_disp = self.api5.TransferInterface(_ole(raw_ent), 2, 0)
        if mo_disp is None:
            raise RuntimeError("[FAIL POINT PATTERN] TransferInterface вернул None!")
        pt_pattern = _wrap(K7.IPointDrivenPattern, mo_disp)

        # 1. Исходные операции (вырезы, фаски, сгибы и т.д.)
        pt_pattern.Clear()
        mo_objs = [_ole(self._to_model_object7(f)) for f in features]
        pt_pattern.AddInitialObjects(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, mo_objs)
        )

        # 2. Управляющие объекты (эскиз с 2D-точками или 3D-точки)
        pt_pattern.ClearDrivenObjects()
        drv_items = (
            driven_obj if isinstance(driven_obj, (list, tuple)) else [driven_obj]
        )
        drv_ole_list = []
        for item in drv_items:
            sf7 = self._find_sketch_feature7(item) if hasattr(item, "name") else None
            mo = sf7 if sf7 is not None else self._to_model_object7(item)
            if not pt_pattern.IsSuitableDrivenObject(_ole(mo)):
                log.warning(
                    f"[POINT PATTERN] Объект '{getattr(mo, 'Name', item)}' не отмечен как подходящий в IsSuitableDrivenObject"
                )
            drv_ole_list.append(_ole(mo))

        pt_pattern.DrivenObjects = VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, drv_ole_list
        )
        pt_pattern.BasePointType = 1 if base_point is not None else 0
        if base_point is not None:
            pt_pattern.BasePoint = _ole(self._to_model_object7(base_point))
        pt_pattern.ProjectionPoints = bool(projection)
        pt_pattern.GeometryPattern = False
        if deleted_indexes is not None:
            pt_pattern.InstanceDeletedIndexes = VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_I4, [int(i) for i in deleted_indexes]
            )

        if not pt_pattern.Update():
            self.close()
            raise RuntimeError(
                "[FAIL POINT PATTERN] IPointDrivenPattern.Update() вернул False!"
            )

        ent = _wrap(K5.ksEntity, raw_ent)
        if not ent.Create():
            log.error(
                f"[FAIL POINT PATTERN] Массив по точкам '{ent.name}' не построился!"
            )
            self.close()
            raise RuntimeError("[FAIL POINT PATTERN] Массив по точкам не построился!")

        self.part.Update()
        vol_after = self.volume()
        log.info(
            f"[POINT PATTERN OK] '{ent.name}': features={len(features)}, driven={len(drv_ole_list)}, "
            f"V_before={vol_before:.2f} -> V_after={vol_after:.2f} (ΔV={vol_after - vol_before:.2f} мм³)"
        )
        return ent

    def _find_edges_by_midpoint(
        self,
        target_x: float,
        target_z: float,
        tol: float = 1.0,
        vertical_only: bool = True,
        cylindrical_only: bool = False,
    ):
        """Находит ребра, чьи середины близки к заданным (X, Z) координатам."""
        edges = []
        raw_collection = self.part.EntityCollection(OBJ_FACE)
        if raw_collection is None:
            return edges
        part_ents = _wrap(K5.ksEntityCollection, raw_collection)
        for i in range(part_ents.GetCount()):
            f = _wrap(K5.ksEntity, part_ents.GetByIndex(i))
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
                    is_cyl = False
                    try:
                        res, h, r = edge.GetCylinderParam(0.0, 0.0)
                        is_cyl = bool(res and r > 0)
                    except Exception:
                        pass
                    if cylindrical_only and not is_cyl:
                        continue
                    v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
                    v2 = _wrap(K5.ksVertexDefinition, edge.GetVertex(False))
                    if not v1 or not v2:
                        continue
                    res1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
                    res2, x2, y2, z2 = v2.GetPoint(0.0, 0.0, 0.0)
                    if not (res1 and res2):
                        continue
                    mx, mz = (x1 + x2) / 2.0, (z1 + z2) / 2.0
                    dx, dy, dz = abs(x1 - x2), abs(y1 - y2), abs(z1 - z2)
                    is_vert = dx < 1e-4 and dz < 1e-4 and dy > 1e-4
                    if vertical_only and not is_vert:
                        continue
                    if abs(mx - target_x) <= tol and abs(mz - target_z) <= tol:
                        edges.append(edge)
        return edges

    def get_window_vertical_edges(self, lo: float, bo: float):
        """Возвращает 4 вертикальных ребра углов провального окна (скругление ro)."""
        edges = []
        corners = [
            (-lo / 2.0, bo / 2.0),
            (lo / 2.0, bo / 2.0),
            (lo / 2.0, -bo / 2.0),
            (-lo / 2.0, -bo / 2.0),
        ]
        for cx, cz in corners:
            found = self._find_edges_by_midpoint(cx, cz, tol=2.0, vertical_only=True)
            if found:
                edges.append(found[0])
            else:
                log.warning(
                    f"  [WINDOW EDGES] Не найдено вертикальное ребро ({cx:.1f}, {cz:.1f})"
                )
        return edges

    def get_plate_corner_edges(self, l: float, b: float):
        """Возвращает 4 вертикальных ребра углов плиты (фаска f)."""
        edges = []
        corners = [
            (-l / 2.0, b / 2.0),
            (l / 2.0, b / 2.0),
            (l / 2.0, -b / 2.0),
            (-l / 2.0, -b / 2.0),
        ]
        for cx, cz in corners:
            found = self._find_edges_by_midpoint(cx, cz, tol=2.0, vertical_only=True)
            if found:
                edges.append(found[0])
            else:
                log.warning(
                    f"  [PLATE EDGES] Не найдено вертикальное ребро ({cx:.1f}, {cz:.1f})"
                )
        return edges

    def get_hole_entrance_edges(
        self, face_top, dk: float, lk: float, bk: float, centers: list = None
    ):
        """Возвращает круговые ребра входов в отверстия на плоской грани."""
        edges = []
        fdef = _wrap(K5.ksFaceDefinition, face_top.GetDefinition())
        if not fdef:
            return edges
        loops = _wrap(K5.ksLoopCollection, fdef.LoopCollection())
        if not loops:
            return edges

        expected_centers = centers or [
            (-lk / 2.0, bk / 2.0),
            (lk / 2.0, bk / 2.0),
            (lk / 2.0, -bk / 2.0),
            (-lk / 2.0, -bk / 2.0),
        ]
        expected_radius = dk / 2.0

        for li in range(loops.GetCount()):
            loop = _wrap(K5.ksLoop, loops.GetByIndex(li))
            loop_edges = _wrap(K5.ksEdgeCollection, loop.EdgeCollection())
            if not loop_edges or loop_edges.GetCount() != 1:
                continue
            edge = _wrap(K5.ksEdgeDefinition, loop_edges.GetByIndex(0))
            if not edge:
                continue
            v1 = _wrap(K5.ksVertexDefinition, edge.GetVertex(True))
            if not v1:
                continue
            res1, x1, y1, z1 = v1.GetPoint(0.0, 0.0, 0.0)
            if not res1:
                continue
            for exp_cx, exp_cz in expected_centers:
                dist = math.hypot(x1 - exp_cx, z1 - exp_cz)
                if abs(dist - expected_radius) < 1.0:
                    edges.append(edge)
                    break
        return edges

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

    def _get_var_value(self, var_name: str) -> float:
        """Получить значение переменной по имени из таблицы переменных детали."""
        part7 = self._get_part7()
        if not part7:
            raise RuntimeError(
                f"[FAIL VAR] Не удалось получить IPart7 для '{var_name}'"
            )
        var = part7.Variable(var_name)
        if var is None:
            raise RuntimeError(f"[FAIL VAR] Переменная '{var_name}' не найдена")
        return float(var.Value)

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
        """Возвращает список всех переменных модели через API7 IFeature7."""
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

    def _bind_api5_dimension_expressions(self, sk_ent, dims_to_bind: list):
        """Привязывает выражения к линейным размерам API5, сопоставляя их по координатам точек (X1, Y1, X2, Y2)."""
        if not self.api7:
            return
        sk_feat7 = self._find_sketch_feature7(sk_ent)
        if not sk_feat7:
            return

        sk7 = _wrap(K7.ISketch, sk_feat7)
        doc2d_7 = _wrap(K7.IKompasDocument2D, sk7.BeginEdit())
        try:
            v_mgr = _wrap(K7.IViewsAndLayersManager, doc2d_7.ViewsAndLayersManager)
            views = _wrap(K7.IViews, v_mgr.Views)
            v0 = _wrap(K7.IView, views.ActiveView)
            sym_c = _wrap(K7.ISymbols2DContainer, v0)
            ldims = _wrap(K7.ILineDimensions, sym_c.LineDimensions)
            all_ldims = [
                _wrap(K7.ILineDimension, ldims.LineDimension(i))
                for i in range(ldims.Count)
            ]

            used_ld = set()
            for _, x1, y1, x2, y2, expression in dims_to_bind:
                best_idx = None
                best_dist = 1e9
                for idx, ld in enumerate(all_ldims):
                    if idx in used_ld:
                        continue
                    d_direct = math.hypot(ld.X1 - x1, ld.Y1 - y1) + math.hypot(
                        ld.X2 - x2, ld.Y2 - y2
                    )
                    d_swap = math.hypot(ld.X1 - x2, ld.Y1 - y2) + math.hypot(
                        ld.X2 - x1, ld.Y2 - y1
                    )
                    d = min(d_direct, d_swap)
                    if d < best_dist and d < 0.5:
                        best_dist = d
                        best_idx = idx
                if best_idx is not None:
                    used_ld.add(best_idx)
                    self._make_dim_driving(all_ldims[best_idx], expression)
        finally:
            sk7.EndEdit()

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
