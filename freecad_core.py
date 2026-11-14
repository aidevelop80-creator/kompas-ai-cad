# freecad_core.py — Ядро управления FreeCAD 1.1+ (зеркальный фасад к kompas_core.py)
import logging
import math
import os
import re
import sys

import FreeCAD as App
import MeshPart
import Part
import Sketcher

PLANE_XY = 1
PLANE_XZ = 2
PLANE_YZ = 3

DT_NORMAL = 0
DT_REVERSE = 1
DT_BOTH = 2
DT_MIDDLE = 3

STYLE_MAIN = 1
STYLE_THIN = 2
STYLE_AXIS = 3


def _setup_logger(log_path: str = "output/build_fc.log") -> logging.Logger:
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    logger = logging.getLogger("freecad_core")
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


class FreeCadSketchBuilder:
    """Конструктор плоского 2D-эскиза FreeCAD Sketcher с привязкой выражений VarSet."""

    def __init__(self, sketch_obj, part_wrapper):
        self.sk = sketch_obj
        self.part = part_wrapper
        self._circles = []  # [(gid, xc, yc, r, is_constr)]
        self._segments = []  # [(gid, x1, y1, x2, y2, is_constr)]
        self._arcs = []  # [(gid, x1, y1, x2, y2)]
        self._points = []  # [(gid, x, y)]
        self._pending_diam = []
        self._pending_lin = []
        self._pending_constraints = []

    def line(self, x1, y1=None, x2=None, y2=None, style: int = STYLE_MAIN):
        if isinstance(x1, (tuple, list)) and isinstance(y1, (tuple, list)):
            p1, p2 = x1, y1
            if x2 is not None:
                style = int(x2)
            x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
        x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
        is_constr = int(style) == STYLE_AXIS
        gid = self.sk.addGeometry(
            Part.LineSegment(App.Vector(x1, y1, 0.0), App.Vector(x2, y2, 0.0)),
            is_constr,
        )
        self._segments.append((gid, x1, y1, x2, y2, is_constr))
        return self

    def axis(self, x1, y1=None, x2=None, y2=None):
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
        x, y, w, h = float(x), float(y), float(w), float(h)
        if centered:
            x, y = x - w / 2.0, y - h / 2.0
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return self.polygon(pts, closed=True, style=style)

    def polygon(
        self,
        points: list[tuple[float, float]],
        closed: bool = True,
        style: int = STYLE_MAIN,
    ):
        if len(points) < 2:
            return self
        gids = []
        n = len(points)
        count = n if (closed and n > 2) else n - 1
        for i in range(count):
            p1 = points[i]
            p2 = points[(i + 1) % n]
            self.line(p1[0], p1[1], p2[0], p2[1], style=style)
            gids.append(self._segments[-1][0])
            if abs(p1[1] - p2[1]) < 1e-6:
                self.sk.addConstraint(Sketcher.Constraint("Horizontal", gids[-1]))
            elif abs(p1[0] - p2[0]) < 1e-6:
                self.sk.addConstraint(Sketcher.Constraint("Vertical", gids[-1]))
        for i in range(len(gids) - (0 if closed else 1)):
            g1 = gids[i]
            g2 = gids[(i + 1) % len(gids)]
            self.sk.addConstraint(Sketcher.Constraint("Coincident", g1, 2, g2, 1))
        return self

    def circle(self, xc=0.0, yc=0.0, r=None, style: int = STYLE_MAIN, **kwargs):
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
        xc, yc, r = float(xc), float(yc), float(r)
        is_constr = int(style) == STYLE_AXIS
        gid = self.sk.addGeometry(
            Part.Circle(App.Vector(xc, yc, 0.0), App.Vector(0.0, 0.0, 1.0), r),
            is_constr,
        )
        self._circles.append((gid, xc, yc, r, is_constr))
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
        """Создает дугу в Sketcher (CCW от angle1 до angle2 в градусах; если angle2 < angle1, добавляет 360°)."""
        xc, yc, r = float(xc), float(yc), float(r)
        a1, a2 = float(angle1), float(angle2)
        if not direction and a2 < a1:
            pass  # в Sketcher.ArcOfCircle перебор идёт против ЧС от rad1 к rad2
        if a2 < a1:
            a2 += 360.0
        r1, r2 = math.radians(a1), math.radians(a2)
        x1, y1 = xc + r * math.cos(r1), yc + r * math.sin(r1)
        x2, y2 = xc + r * math.cos(r2), yc + r * math.sin(r2)
        is_constr = int(style) == STYLE_AXIS
        gid = self.sk.addGeometry(
            Part.ArcOfCircle(
                Part.Circle(App.Vector(xc, yc, 0.0), App.Vector(0.0, 0.0, 1.0), r),
                r1,
                r2,
            ),
            is_constr,
        )
        self._arcs.append((gid, x1, y1, x2, y2))
        return self

    def point(self, x: float, y: float, style: int = STYLE_MAIN):
        gid = self.sk.addGeometry(Part.Point(App.Vector(float(x), float(y), 0.0)), True)
        self._points.append((gid, float(x), float(y)))
        return self

    def align_h(self, p1: tuple[float, float], p2: tuple[float, float]):
        self._pending_constraints.append(
            ("align_h", (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
        )
        return self

    def align_v(self, p1: tuple[float, float], p2: tuple[float, float]):
        self._pending_constraints.append(
            ("align_v", (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
        )
        return self

    def equal_length(
        self,
        seg1: tuple[float, float, float, float],
        seg2: tuple[float, float, float, float],
    ):
        self._pending_constraints.append(
            ("equal_len", tuple(float(v) for v in seg1), tuple(float(v) for v in seg2))
        )
        return self

    def center_on_origin(self, w: float, h: float):
        self._pending_constraints.append(("center_rect", float(w), float(h)))
        return self

    def fix_point(self, x: float, y: float):
        self._pending_constraints.append(("fix_pt", (float(x), float(y))))
        return self

    def equal_radius(self, c1: tuple[float, float], c2: tuple[float, float]):
        self._pending_constraints.append(
            ("equal_rad", (float(c1[0]), float(c1[1])), (float(c2[0]), float(c2[1])))
        )
        return self

    def symmetric_pts(
        self, p1: tuple[float, float], p2: tuple[float, float], axis: str = "y"
    ):
        """Симметрия двух точек относительно оси эскиза: axis='x' (-1) или 'y' (-2)."""
        self._pending_constraints.append(
            (
                "sym_axis",
                (float(p1[0]), float(p1[1])),
                (float(p2[0]), float(p2[1])),
                axis,
            )
        )
        return self

    def dim_diam(
        self,
        xc: float,
        yc: float,
        r: float,
        angle_deg: float = 45.0,
        var_name: str = None,
    ):
        self._pending_diam.append((float(xc), float(yc), float(r), var_name))
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
        if orientation is None:
            if abs(y2 - y1) < 1e-6 and abs(x2 - x1) > 1e-6:
                orientation = 1
            elif abs(x2 - x1) < 1e-6 and abs(y2 - y1) > 1e-6:
                orientation = 2
            else:
                orientation = 0
        self._pending_lin.append(
            (float(x1), float(y1), float(x2), float(y2), expression, int(orientation))
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

    def _find_pt_ref(self, px: float, py: float):
        if math.hypot(px, py) < 1e-2:
            return -1, 1  # Root origin
        for gid, xc, yc, _, _ in self._circles:
            if math.hypot(xc - px, yc - py) < 1e-2:
                return gid, 3
        for gid, x, y in self._points:
            if math.hypot(x - px, y - py) < 1e-2:
                return gid, 1
        for gid, x1, y1, x2, y2, _ in self._segments:
            if math.hypot(x1 - px, y1 - py) < 1e-2:
                return gid, 1
            if math.hypot(x2 - px, y2 - py) < 1e-2:
                return gid, 2
        return None, None

    def _find_seg_gid(self, x1s: float, y1s: float, x2s: float, y2s: float):
        for gid, x1, y1, x2, y2, _ in self._segments:
            d1 = math.hypot(x1 - x1s, y1 - y1s) + math.hypot(x2 - x2s, y2 - y2s)
            d2 = math.hypot(x1 - x2s, y1 - y2s) + math.hypot(x2 - x1s, y2 - y1s)
            if min(d1, d2) < 1e-2:
                return gid
        return None

    def _find_seg_by_midpoint(self, mx: float, my: float):
        for gid, x1, y1, x2, y2, _ in self._segments:
            if math.hypot((x1 + x2) / 2.0 - mx, (y1 + y2) / 2.0 - my) < 1e-2:
                return gid
        return None

    def finalize_constraints(self):
        # 1. Привязка окружностей в (0,0) и смещённых окружностей на делительной
        origin_circles = [c for c in self._circles if math.hypot(c[1], c[2]) < 1e-2]
        offset_circles = [c for c in self._circles if math.hypot(c[1], c[2]) >= 1e-2]
        for gid, *_ in origin_circles:
            self.sk.addConstraint(Sketcher.Constraint("Coincident", gid, 3, -1, 1))
        for gid_off, xc, yc, _, _ in offset_circles:
            dist = math.hypot(xc, yc)
            for gid0, _, _, r0, _ in origin_circles:
                if abs(dist - r0) < 1e-2:
                    self.sk.addConstraint(
                        Sketcher.Constraint("PointOnObject", gid_off, 3, gid0)
                    )
                    if abs(xc) < 1e-4:
                        self.sk.addConstraint(
                            Sketcher.Constraint("PointOnObject", gid_off, 3, -2)
                        )
                    elif abs(yc) < 1e-4:
                        self.sk.addConstraint(
                            Sketcher.Constraint("PointOnObject", gid_off, 3, -1)
                        )
                    break

        # 2. Диаметральные размеры
        for xc, yc, r, expr in self._pending_diam:
            target = None
            for gid, cx, cy, cr, _ in self._circles:
                if math.hypot(cx - xc, cy - yc) < 1e-2 and abs(cr - r) < 1e-2:
                    target = gid
                    break
            if target is not None:
                c_idx = self.sk.addConstraint(
                    Sketcher.Constraint("Diameter", target, float(2.0 * r))
                )
                if expr:
                    self.sk.setExpression(
                        f"Constraints[{c_idx}]", self.part._translate_expr(expr)
                    )

        # 3. Линейные размеры
        for x1, y1, x2, y2, expr, orient in self._pending_lin:
            g1, p1 = self._find_pt_ref(x1, y1)
            g2, p2 = self._find_pt_ref(x2, y2)
            if g1 is None or g2 is None:
                continue
            if orient == 1:
                val = abs(x2 - x1)
                if x2 < x1:
                    g1, p1, g2, p2 = g2, p2, g1, p1
                c_idx = self.sk.addConstraint(
                    Sketcher.Constraint("DistanceX", g1, p1, g2, p2, float(val))
                )
            elif orient == 2:
                val = abs(y2 - y1)
                if y2 < y1:
                    g1, p1, g2, p2 = g2, p2, g1, p1
                c_idx = self.sk.addConstraint(
                    Sketcher.Constraint("DistanceY", g1, p1, g2, p2, float(val))
                )
            else:
                val = math.hypot(x2 - x1, y2 - y1)
                c_idx = self.sk.addConstraint(
                    Sketcher.Constraint("Distance", g1, p1, g2, p2, float(val))
                )
            if expr:
                self.sk.setExpression(
                    f"Constraints[{c_idx}]", self.part._translate_expr(expr)
                )
        # 4. Геометрические ограничения
        for item in self._pending_constraints:
            kind = item[0]
            if kind == "equal_len":
                _, s1, s2 = item
                g1 = self._find_seg_gid(*s1)
                g2 = self._find_seg_gid(*s2)
                if g1 is not None and g2 is not None:
                    self.sk.addConstraint(Sketcher.Constraint("Equal", g1, g2))
            elif kind in ("align_h", "align_v"):
                _, p1, p2 = item
                if math.hypot(p2[0], p2[1]) < 1e-2:
                    p1, p2 = p1, (0.0, 0.0)
                elif math.hypot(p1[0], p1[1]) < 1e-2:
                    p1, p2 = p2, (0.0, 0.0)
                if math.hypot(p2[0], p2[1]) < 1e-2:
                    g_mid = self._find_seg_by_midpoint(*p1)
                    if g_mid is not None:
                        axis_id = -1 if kind == "align_h" else -2
                        dup_type = "Vertical" if kind == "align_h" else "Horizontal"
                        for idx in range(len(self.sk.Constraints) - 1, -1, -1):
                            con = self.sk.Constraints[idx]
                            if (
                                con.Type == dup_type
                                and con.First == g_mid
                                and con.FirstPos == 0
                            ):
                                self.sk.delConstraint(idx)
                        self.sk.addConstraint(
                            Sketcher.Constraint(
                                "Symmetric", g_mid, 1, g_mid, 2, axis_id
                            )
                        )
                        continue
                    g1, pos1 = self._find_pt_ref(*p1)
                    if g1 is not None:
                        axis_id = -1 if kind == "align_h" else -2
                        self.sk.addConstraint(
                            Sketcher.Constraint("PointOnObject", g1, pos1, axis_id)
                        )
                else:
                    g1, pos1 = self._find_pt_ref(*p1)
                    g2, pos2 = self._find_pt_ref(*p2)
                    if g1 is not None and g2 is not None:
                        cname = "Horizontal" if kind == "align_h" else "Vertical"
                        self.sk.addConstraint(
                            Sketcher.Constraint(cname, g1, pos1, g2, pos2)
                        )
            elif kind == "center_rect":
                _, w, h = item
                g1, pos1 = self._find_pt_ref(-w / 2.0, -h / 2.0)
                g2, pos2 = self._find_pt_ref(w / 2.0, h / 2.0)
                if g1 is not None and g2 is not None:
                    self.sk.addConstraint(
                        Sketcher.Constraint("Symmetric", g1, pos1, g2, pos2, -1, 1)
                    )
            elif kind == "fix_pt":
                g1, pos1 = self._find_pt_ref(*item[1])
                if g1 is not None and g1 >= 0:
                    self.sk.addConstraint(Sketcher.Constraint("Block", g1))
            elif kind == "equal_rad":
                _, c1, c2 = item
                g1, _ = self._find_pt_ref(*c1)
                g2, _ = self._find_pt_ref(*c2)
                if g1 is not None and g2 is not None:
                    self.sk.addConstraint(Sketcher.Constraint("Equal", g1, g2))
            elif kind == "sym_axis":
                _, p1, p2, axis = item
                g1, pos1 = self._find_pt_ref(*p1)
                g2, pos2 = self._find_pt_ref(*p2)
                if g1 is not None and g2 is not None:
                    axis_id = -1 if axis.lower() == "x" else -2
                    self.sk.addConstraint(
                        Sketcher.Constraint("Symmetric", g1, pos1, g2, pos2, axis_id)
                    )
        # 5. Автоматическая стыковка только дуг с отрезками/дугами (не трогая готовые углы rect/polygon)
        if self._arcs:
            arc_gids = {g for g, *_ in self._arcs}
            endpoints = []
            for gid, x1, y1, x2, y2, _ in self._segments:
                endpoints.append((gid, 1, x1, y1))
                endpoints.append((gid, 2, x2, y2))
            for gid, x1, y1, x2, y2 in self._arcs:
                endpoints.append((gid, 1, x1, y1))
                endpoints.append((gid, 2, x2, y2))
            for i in range(len(endpoints)):
                g1, p1, x1, y1 = endpoints[i]
                for j in range(i + 1, len(endpoints)):
                    g2, p2, x2, y2 = endpoints[j]
                    if (
                        g1 != g2
                        and (g1 in arc_gids or g2 in arc_gids)
                        and math.hypot(x1 - x2, y1 - y2) < 1e-2
                    ):
                        self.sk.addConstraint(
                            Sketcher.Constraint("Coincident", g1, p1, g2, p2)
                        )


class FreeCadPart:
    """Высокоуровневая обертка над FreeCAD 1.1 PartDesign::Body + App::VarSet."""

    def __init__(self, name: str = "Part", visible: bool = False):
        log.info("=" * 65)
        log.info(f"НАЧАЛО ПОСТРОЕНИЯ ДЕТАЛИ В FREECAD: '{name}'")
        log.info("=" * 65)
        self.doc = App.newDocument(name)
        self.vars = self.doc.addObject("App::VarSet", "Vars")
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self._var_map = {}  # user_name -> safe_varset_name
        self._sketch_counter = 0
        self._op_counter = 0
        self._sketch_axes = {}

    def add_variable(
        self, name: str, value: float, note: str = "", expression: str = None
    ):
        safe_name = f"v_{name}"
        self.vars.addProperty("App::PropertyLength", safe_name, "Params", str(note))
        setattr(self.vars, safe_name, f"{float(value)} mm")
        self._var_map[name] = safe_name
        if expression:
            self.vars.setExpression(safe_name, self._translate_expr(expression))
        log.info(f"[VAR ADD] {name} -> Vars.{safe_name} = {value} мм ({note})")
        return safe_name

    def create_variables_from_dict(self, variables: dict[str, tuple[float, str]]):
        return {
            n: self.add_variable(n, val, note) for n, (val, note) in variables.items()
        }

    def _translate_expr(self, expr: str) -> str:
        def _repl(m):
            tok = m.group(1)
            if tok in self._var_map:
                return f"Vars.{self._var_map[tok]}"
            return tok

        return re.sub(r"\b([A-Za-z_]\w*)\b", _repl, str(expr))

    def get_base_plane(self, plane: str | int):
        if isinstance(plane, int):
            role = {
                PLANE_XY: "XY_Plane",
                PLANE_XZ: "XZ_Plane",
                PLANE_YZ: "YZ_Plane",
            }.get(plane, "XY_Plane")
        else:
            p_map = {
                "xy": "XY_Plane",
                "xoy": "XY_Plane",
                "yx": "XY_Plane",
                "xz": "XZ_Plane",
                "xoz": "XZ_Plane",
                "zx": "XZ_Plane",
                "yz": "YZ_Plane",
                "yoz": "YZ_Plane",
                "zy": "YZ_Plane",
            }
            role = p_map.get(plane.lower().strip(), "XY_Plane")
        return next(f for f in self.body.Origin.OriginFeatures if f.Role == role)

    def create_axis_by_2_planes(
        self, plane1: str | int = "xy", plane2: str | int = "yz"
    ):
        p1 = self.get_base_plane(plane1).Role
        p2 = self.get_base_plane(plane2).Role
        pair = {p1, p2}
        if pair == {"XY_Plane", "YZ_Plane"}:
            role = "Y_Axis"
        elif pair == {"XY_Plane", "XZ_Plane"}:
            role = "X_Axis"
        else:
            role = "Z_Axis"
        return next(f for f in self.body.Origin.OriginFeatures if f.Role == role)

    def get_planar_face_at(
        self, axis: str = "y", coord: float = None, mode: str = "max", tol: float = 0.5
    ):
        axis_idx = {"x": 0, "y": 1, "z": 2}[axis.lower().strip()]
        tip = self.body.Tip
        if tip is None or tip.Shape.isNull():
            raise RuntimeError("[FAIL FACE] Тело детали пустое!")

        candidates = []
        for idx, face in enumerate(tip.Shape.Faces):
            if face.Surface.TypeId != "Part::GeomPlane":
                continue
            bb = face.BoundBox
            c_min = (bb.XMin, bb.YMin, bb.ZMin)[axis_idx]
            c_max = (bb.XMax, bb.YMax, bb.ZMax)[axis_idx]
            if abs(c_max - c_min) < 1e-3:
                pos = 0.5 * (c_min + c_max)
                candidates.append((pos, (tip, f"Face{idx + 1}")))

        avail = [round(p, 2) for p, _ in candidates]
        if not candidates:
            raise RuntimeError(
                f"[FAIL FACE] Не найдено плоских граней вдоль {axis.upper()}!"
            )

        if coord is not None:
            for pos, ref in candidates:
                if abs(pos - float(coord)) <= tol:
                    log.info(
                        f"[FACE SELECT] Выбрана грань {ref[1]} на {axis.upper()}={pos:.2f}"
                    )
                    return ref
            raise RuntimeError(
                f"[FAIL FACE] Грань на {axis.upper()}={coord} не найдена! Доступные: {avail}"
            )

        candidates.sort(key=lambda item: item[0])
        chosen_pos, chosen_ref = candidates[-1] if mode == "max" else candidates[0]
        log.info(
            f"[FACE SELECT] Выбрана грань ({mode}) {chosen_ref[1]} на {axis.upper()}={chosen_pos:.2f}"
        )
        return chosen_ref

    def create_sketch(self, plane="xy", draw_fn=None, auto_parametrize: bool = True):
        self._sketch_counter += 1
        sk = self.body.newObject(
            "Sketcher::SketchObject", f"Sketch_{self._sketch_counter}"
        )
        if isinstance(plane, tuple) and len(plane) == 2:
            feat, subname = plane
            sk.AttachmentSupport = [(feat, subname)]
        else:
            pl_obj = (
                self.get_base_plane(plane) if isinstance(plane, (str, int)) else plane
            )
            sk.AttachmentSupport = [(pl_obj, "")]
        sk.MapMode = "FlatFace"

        builder = FreeCadSketchBuilder(sk, self)
        if callable(draw_fn):
            draw_fn(builder)
        builder.finalize_constraints()
        constr_segs = [s for s in builder._segments if s[5]]
        if constr_segs:
            _, x1, y1, x2, y2, _ = constr_segs[0]
            if abs(x1) < 1e-4 and abs(x2) < 1e-4:
                self._sketch_axes[sk.Name] = "V_Axis"
            elif abs(y1) < 1e-4 and abs(y2) < 1e-4:
                self._sketch_axes[sk.Name] = "H_Axis"
            else:
                self._sketch_axes[sk.Name] = "Axis0"
        dof = sk.solve()
        self.doc.recompute()
        log.info(f"[SKETCH OK] '{sk.Name}' (DoF={dof})")
        return sk

    def create_sketch_on_face(
        self, face_ref, draw_fn=None, auto_parametrize: bool = True
    ):
        return self.create_sketch(
            plane=face_ref, draw_fn=draw_fn, auto_parametrize=auto_parametrize
        )

    def _sketch_normal(self, sketch_obj) -> App.Vector:
        return sketch_obj.Placement.Rotation.multVec(App.Vector(0.0, 0.0, 1.0))

    def extrude(
        self,
        sketch_ent,
        depth: float,
        direction: int = DT_NORMAL,
        draft_angle: float = 0.0,
        expr: str = None,
    ):
        vol_before = self.volume()
        self._op_counter += 1
        pad = self.body.newObject("PartDesign::Pad", f"Pad_{self._op_counter}")
        pad.Profile = sketch_ent
        pad.Length = float(depth)
        if abs(float(draft_angle)) > 1e-6:
            pad.TaperAngle = float(draft_angle)

        # Нормаль XZ_Plane в FreeCAD смотрит в -Y: разворачиваем, чтобы DT_NORMAL шёл в +Y (как в КОМПАС)
        n = self._sketch_normal(sketch_ent)
        is_xz_plane = abs(n.y) > 0.99 and n.y < 0.0
        if direction == DT_BOTH or direction == DT_MIDDLE:
            pad.Midplane = True
        elif direction == DT_REVERSE:
            pad.Reversed = not is_xz_plane
        else:
            pad.Reversed = is_xz_plane

        if expr:
            pad.setExpression("Length", self._translate_expr(expr))

        self.body.Tip = pad
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[PAD OK] '{pad.Name}': depth={depth} (expr='{expr}'), V={vol_before:.2f} -> {vol_after:.2f}"
        )
        if vol_after <= vol_before + 1e-9:
            raise RuntimeError(
                f"[FAIL PAD] Объём не увеличился ({vol_before:.2f} -> {vol_after:.2f})!"
            )
        return pad

    def cut(
        self,
        sketch_ent,
        depth: float = 100.0,
        direction: int = DT_NORMAL,
        draft_angle: float = 0.0,
        expr: str = None,
        through_all: bool = False,
    ):
        vol_before = self.volume()
        if vol_before <= 1e-9:
            raise RuntimeError("[FAIL POCKET] Нельзя резать пустое тело!")
        self._op_counter += 1
        pocket = self.body.newObject("PartDesign::Pocket", f"Pocket_{self._op_counter}")
        pocket.Profile = sketch_ent
        if through_all:
            pocket.Type = "ThroughAll"
        else:
            pocket.Type = "Length"
            pocket.Length = float(depth)
            if expr:
                pocket.setExpression("Length", self._translate_expr(expr))
        if abs(float(draft_angle)) > 1e-6:
            pocket.TaperAngle = float(draft_angle)

        if direction == DT_BOTH or direction == DT_MIDDLE:
            pocket.Midplane = True
        elif direction == DT_REVERSE:
            pocket.Reversed = True

        self.body.Tip = pocket
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[POCKET OK] '{pocket.Name}': through={through_all}, V={vol_before:.2f} -> {vol_after:.2f}"
        )
        if vol_after >= vol_before - 1e-9:
            raise RuntimeError(
                f"[FAIL POCKET] Вырез промахнулся мимо тела ({vol_before:.2f} -> {vol_after:.2f})!"
            )
        return pocket

    def revolve(
        self,
        sketch_ent,
        angle: float = 360.0,
        cut: bool = False,
        angle_expr: str = None,
    ):
        """Операция вращения (PartDesign::Revolution) или выреза вращением (PartDesign::Groove)."""
        vol_before = self.volume()
        self._op_counter += 1
        op_type = "PartDesign::Groove" if cut else "PartDesign::Revolution"
        op_name = (
            f"Groove_{self._op_counter}" if cut else f"Revolution_{self._op_counter}"
        )
        rev = self.body.newObject(op_type, op_name)
        rev.Profile = sketch_ent
        axis_sub = self._sketch_axes.get(sketch_ent.Name, "V_Axis")
        rev.ReferenceAxis = (sketch_ent, [axis_sub])
        rev.Angle = float(angle)
        if angle_expr:
            rev.setExpression("Angle", self._translate_expr(angle_expr))

        self.body.Tip = rev
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[REVOLVE OK] '{rev.Name}' (cut={cut}, axis={axis_sub}, angle={angle}): V={vol_before:.2f} -> {vol_after:.2f}"
        )
        if cut and vol_after >= vol_before - 1e-9:
            raise RuntimeError(
                f"[FAIL GROOVE] Вырез вращением не снял материал ({vol_before:.2f} -> {vol_after:.2f})!"
            )
        if not cut and vol_after <= vol_before + 1e-9:
            raise RuntimeError(
                f"[FAIL REVOLVE] Вращение не увеличило объём ({vol_before:.2f} -> {vol_after:.2f})!"
            )
        return rev

    def circular_pattern(
        self, features: list, axis_ent, count: int = 4, angle: float = 360.0
    ):
        vol_before = self.volume()
        self._op_counter += 1
        pat = self.body.newObject(
            "PartDesign::PolarPattern", f"PolarPattern_{self._op_counter}"
        )
        pat.Originals = list(features)
        pat.Axis = (axis_ent, [""])
        pat.Occurrences = int(count)
        pat.Angle = float(angle)
        self.body.Tip = pat  # обязательно для FreeCAD 1.1
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[POLAR OK] '{pat.Name}': count={count}, V={vol_before:.2f} -> {vol_after:.2f}"
        )
        return pat

    def _normalize_edges_arg(self, edges, prev_tip):
        if isinstance(edges, tuple) and len(edges) == 2:
            return edges
        return (prev_tip, list(edges))

    def fillet(self, edges, radius: float, expr: str = None):
        vol_before = self.volume()
        prev_tip = self.body.Tip
        self._op_counter += 1
        fil = self.body.newObject("PartDesign::Fillet", f"Fillet_{self._op_counter}")
        fil.Base = self._normalize_edges_arg(edges, prev_tip)
        fil.Radius = float(radius)
        if expr:
            fil.setExpression("Radius", self._translate_expr(expr))
        self.body.Tip = fil
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[FILLET OK] '{fil.Name}': R={radius} (expr='{expr}'), V={vol_before:.2f} -> {vol_after:.2f}"
        )
        if abs(vol_after - vol_before) < 1e-6:
            raise RuntimeError(
                f"[FAIL FILLET] Скругление '{fil.Name}' не изменило геометрию!"
            )
        return fil

    def chamfer(self, edges, distance: float, angle: float = 45.0, expr: str = None):
        vol_before = self.volume()
        prev_tip = self.body.Tip
        self._op_counter += 1
        ch = self.body.newObject("PartDesign::Chamfer", f"Chamfer_{self._op_counter}")
        ch.Base = self._normalize_edges_arg(edges, prev_tip)
        ch.ChamferType = 0  # Equal distance
        ch.Size = float(distance)
        if expr:
            ch.setExpression("Size", self._translate_expr(expr))
        self.body.Tip = ch
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[CHAMFER OK] '{ch.Name}': size={distance} (expr='{expr}'), V={vol_before:.2f} -> {vol_after:.2f}"
        )
        if abs(vol_after - vol_before) < 1e-6:
            raise RuntimeError(
                f"[FAIL CHAMFER] Фаска '{ch.Name}' не изменила геометрию!"
            )
        return ch

    def _find_vertical_edges_at_corners(
        self, corners: list[tuple[float, float]], tol: float = 2.0
    ):
        tip = self.body.Tip
        found = []
        for idx, edge in enumerate(tip.Shape.Edges):
            if len(edge.Vertexes) != 2:
                continue
            p1, p2 = edge.Vertexes[0].Point, edge.Vertexes[1].Point
            if (
                abs(p1.x - p2.x) < 1e-3
                and abs(p1.z - p2.z) < 1e-3
                and abs(p1.y - p2.y) > 1e-3
            ):
                mx, mz = 0.5 * (p1.x + p2.x), 0.5 * (p1.z + p2.z)
                if any(
                    abs(mx - cx) <= tol and abs(mz - cz) <= tol for cx, cz in corners
                ):
                    found.append(f"Edge{idx + 1}")
        return (tip, found)

    def get_window_vertical_edges(self, lo: float, bo: float):
        corners = [
            (-lo / 2.0, bo / 2.0),
            (lo / 2.0, bo / 2.0),
            (lo / 2.0, -bo / 2.0),
            (-lo / 2.0, -bo / 2.0),
        ]
        return self._find_vertical_edges_at_corners(corners)

    def get_plate_corner_edges(self, l: float, b: float):
        corners = [
            (-l / 2.0, b / 2.0),
            (l / 2.0, b / 2.0),
            (l / 2.0, -b / 2.0),
            (-l / 2.0, -b / 2.0),
        ]
        return self._find_vertical_edges_at_corners(corners)

    def get_hole_entrance_edges(
        self, face_ref, dk: float, lk: float, bk: float, centers: list = None
    ):
        tip = self.body.Tip
        feat, subname = face_ref
        face_shape = feat.Shape.getElement(subname)
        face_y = face_shape.BoundBox.YMin
        expected_centers = centers or [
            (-lk / 2.0, bk / 2.0),
            (lk / 2.0, bk / 2.0),
            (lk / 2.0, -bk / 2.0),
            (-lk / 2.0, -bk / 2.0),
        ]
        found = []
        for idx, edge in enumerate(tip.Shape.Edges):
            if edge.Curve.TypeId != "Part::GeomCircle":
                continue
            if abs(edge.Curve.Radius - dk / 2.0) > 0.5:
                continue
            c = edge.Curve.Center
            if abs(c.y - face_y) > 0.5:
                continue
            if any(math.hypot(c.x - ex, c.z - ez) < 1.0 for ex, ez in expected_centers):
                found.append(f"Edge{idx + 1}")
        return (tip, found)

    def add_sheet_bend(
        self,
        edge_names: list[str],
        length: float = 16.0,
        bend_radius: float = 2.0,
        angle: float = 90.0,
        k_factor: float = 0.4,
        bend_type: str = "Material Outside",
        length_spec: str = "Outer Sharp",
        auto_miter: bool = True,
        min_gap: float = 0.2,
        gap1: float = 0.0,
        gap2: float = 0.0,
        extend1: float = 0.0,
        extend2: float = 0.0,
        invert: bool = False,
        length_expr: str = None,
        radius_expr: str = None,
    ):
        """Сгиб по рёбрам (или сразу по нескольким рёбрам с AutoMiter) через FreeCAD_SheetMetal."""
        from SheetMetalCmd import SMBendWall

        vol_before = self.volume()
        prev_tip = self.body.Tip
        self._op_counter += 1
        bend = self.doc.addObject(
            "PartDesign::FeaturePython", f"Bend_{self._op_counter}"
        )
        SMBendWall(bend, prev_tip, list(edge_names), None, False)
        self.body.addObject(bend)

        bend.radius = float(bend_radius)
        bend.length = float(length)
        bend.angle = float(angle)
        bend.kfactor = float(k_factor)
        bend.BendType = str(bend_type)
        bend.LengthSpec = str(length_spec)
        bend.AutoMiter = bool(auto_miter)
        bend.minGap = float(min_gap)
        bend.gap1 = float(gap1)
        bend.gap2 = float(gap2)
        bend.extend1 = float(extend1)
        bend.extend2 = float(extend2)
        bend.invert = bool(invert)

        if length_expr:
            bend.setExpression("length", self._translate_expr(length_expr))
        if radius_expr:
            bend.setExpression("radius", self._translate_expr(radius_expr))

        self.body.Tip = bend
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[SM BEND OK] '{bend.Name}': edges={len(edge_names)}, L={length}, R={bend_radius}, "
            f"AutoMiter={auto_miter}, V={vol_before:.2f} -> {vol_after:.2f}"
        )
        return bend

    def add_sheet_fold(
        self,
        face_ref,
        bend_line_sketch,
        bend_radius: float = 1.0,
        angle: float = 90.0,
        k_factor: float = 0.45,
        position: str = "forward",
        invert: bool = False,
        invert_bend: bool = False,
        radius_expr: str = None,
    ):
        """Сгиб по линии (SMFoldWall) через FreeCAD_SheetMetal."""
        from SheetMetalFoldCmd import SMFoldWall

        vol_before = self.volume()
        prev_tip = self.body.Tip
        _, face_sub = face_ref
        self._op_counter += 1
        fold = self.doc.addObject(
            "PartDesign::FeaturePython", f"Fold_{self._op_counter}"
        )
        SMFoldWall(fold, prev_tip, [face_sub], bend_line_sketch)
        self.body.addObject(fold)

        fold.radius = float(bend_radius)
        fold.angle = float(angle)
        fold.kfactor = float(k_factor)
        fold.Position = str(position)
        fold.invert = bool(invert)
        fold.invertbend = bool(invert_bend)
        if radius_expr:
            fold.setExpression("radius", self._translate_expr(radius_expr))

        self.body.Tip = fold
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[SM FOLD OK] '{fold.Name}': R={bend_radius}, Angle={angle}°, V={vol_before:.2f} -> {vol_after:.2f}"
        )
        return fold

    def get_outer_edges_at_z(
        self, z_coord: float, tol: float = 0.2, axis: str = None, min_len: float = 1.0
    ) -> list[str]:
        """Возвращает имена прямолинейных рёбер на высоте Z (опционально вдоль 'x' или 'y')."""
        tip = self.body.Tip
        found = []
        for idx, edge in enumerate(tip.Shape.Edges):
            if len(edge.Vertexes) != 2 or edge.Length < min_len:
                continue
            p1, p2 = edge.Vertexes[0].Point, edge.Vertexes[1].Point
            if abs(p1.z - z_coord) > tol or abs(p2.z - z_coord) > tol:
                continue
            if axis == "x" and abs(p1.y - p2.y) > tol:
                continue
            if axis == "y" and abs(p1.x - p2.x) > tol:
                continue
            found.append(f"Edge{idx + 1}")
        return found

    def find_wall_end_faces(
        self, normal_axis: str = "x", min_z_height: float = 8.0
    ) -> list[str]:
        """Находит вертикальные торцовые грани стенок (нормаль вдоль 'x' или 'y', толщина ~2 мм)."""
        tip = self.body.Tip
        found = []
        for idx, face in enumerate(tip.Shape.Faces):
            if face.Surface.TypeId != "Part::GeomPlane":
                continue
            bb = face.BoundBox
            if (bb.ZMax - bb.ZMin) < min_z_height or bb.ZMax < 10.0:
                continue
            if (
                normal_axis == "x"
                and bb.XLength < 0.05
                and 1.0 < bb.YLength < 3.0
                or normal_axis == "y"
                and bb.YLength < 0.05
                and 1.0 < bb.XLength < 3.0
            ):
                found.append(f"Face{idx + 1}")
        return found

    def add_sheet_extend(
        self,
        face_names: list[str],
        length: float = 2.0,
        gap1: float = 0.0,
        gap2: float = 0.0,
        use_subtraction: bool = True,
        offset: float = 0.2,
        refine: bool = True,
        reversed_dir: bool = False,
    ):
        """Нативное удлинение торцов стенок листового тела (SMExtrudeWall) для замыкания углов."""
        from SheetMetalExtendCmd import SMExtrudeWall

        vol_before = self.volume()
        prev_tip = self.body.Tip
        self._op_counter += 1
        ext = self.doc.addObject(
            "PartDesign::FeaturePython", f"Extend_{self._op_counter}"
        )
        SMExtrudeWall(ext, prev_tip, list(face_names), None)
        self.body.addObject(ext)

        ext.length = float(length)
        ext.gap1 = float(gap1)
        ext.gap2 = float(gap2)
        ext.reversed = bool(reversed_dir)
        ext.UseSubtraction = bool(use_subtraction)
        ext.Offset = float(offset)
        ext.Refine = bool(refine)

        self.body.Tip = ext
        self.doc.recompute()
        vol_after = self.volume()
        log.info(
            f"[SM EXTEND OK] '{ext.Name}': faces={len(face_names)}, L={length}, "
            f"Offset={offset}, V={vol_before:.2f} -> {vol_after:.2f}"
        )
        return ext

    def volume(self) -> float:
        self.doc.recompute()
        if self.body.Shape.isNull():
            return 0.0
        return float(self.body.Shape.Volume)

    def bbox(self) -> tuple[float, float, float]:
        self.doc.recompute()
        bb = self.body.Shape.BoundBox
        return float(bb.XLength), float(bb.YLength), float(bb.ZLength)

    def assert_bbox(self, exp_x: float, exp_y: float, exp_z: float, tol: float = 0.1):
        dx, dy, dz = self.bbox()
        actual_sorted = sorted([dx, dy, dz])
        exp_sorted = sorted([float(exp_x), float(exp_y), float(exp_z)])
        if any(abs(a - e) > tol for a, e in zip(actual_sorted, exp_sorted)):
            raise ValueError(
                f"[FAIL BBOX] Ожидалось ({exp_x:.2f}, {exp_y:.2f}, {exp_z:.2f}), "
                f"фактически ({dx:.2f} x {dy:.2f} x {dz:.2f}) мм"
            )
        log.info(
            f"[OK BBOX] Габариты подтверждены: {dx:.2f} x {dy:.2f} x {dz:.2f} мм | V = {self.volume():.2f} мм³"
        )

    def save(
        self,
        filepath: str,
        export_stl: bool = True,
        export_step: bool = False,
        linear_deflection: float = 0.001,
        angular_deflection_deg: float = 5.0,
    ):
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        self.doc.recompute()
        self.doc.saveAs(abs_path)
        log.info(f"[OK SAVE FCStd] {abs_path}")

        if export_stl:
            stl_path = os.path.splitext(abs_path)[0] + ".stl"
            mesh = MeshPart.meshFromShape(
                Shape=self.body.Shape,
                LinearDeflection=float(linear_deflection),
                AngularDeflection=math.radians(float(angular_deflection_deg)),
                Relative=False,
            )
            mesh.write(stl_path)
            log.info(
                f"[OK EXPORT STL] {stl_path} "
                f"(LinearDeflection={linear_deflection} мм, Angular={angular_deflection_deg}°, треугольников={len(mesh.Facets)})"
            )

        if export_step:
            step_path = os.path.splitext(abs_path)[0] + ".step"
            Part.export([self.body], step_path)
            log.info(f"[OK EXPORT STEP] {step_path}")

    def close(self):
        try:
            App.closeDocument(self.doc.Name)
        except Exception:
            pass
