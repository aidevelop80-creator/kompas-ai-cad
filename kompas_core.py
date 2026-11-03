# kompas_core.py вЂ” РЇРґСЂРѕ СѓРїСЂР°РІР»РµРЅРёСЏ РљРћРњРџРђРЎ-3D v16.1 (Р­С‚Р°Р»РѕРЅРЅР°СЏ РєРѕРЅСЃС‚СЂСѓРєС‚РѕСЂСЃРєР°СЏ РїР°СЂР°РјРµС‚СЂРёР·Р°С†РёСЏ)
import os
import math
import atexit
import pythoncom
import win32com.client

from sdk_ref import kompas_api5_v16 as K5
from sdk_ref import kompas_api7_v16 as K7


def _wrap(cls, obj):
    """Р‘РµР·РѕРїР°СЃРЅРѕ РѕР±РѕСЂР°С‡РёРІР°РµС‚ COM-РѕР±СЉРµРєС‚ РІ С‚РёРїРёР·РёСЂРѕРІР°РЅРЅС‹Р№ РєР»Р°СЃСЃ K5/K7."""
    if obj is None:
        return None
    ole = getattr(obj, "_oleobj_", obj)
    return cls(ole)


def _connect_existing_or_new_kompas(visible: bool = True):
    """РџРѕРґРєР»СЋС‡Р°РµС‚СЃСЏ Рє СѓР¶Рµ РѕС‚РєСЂС‹С‚РѕРјСѓ РѕРєРЅСѓ РљРћРњРџРђРЎ-3D Р±РµР· СЃРѕР·РґР°РЅРёСЏ РґСѓР±Р»РёРєР°С‚РѕРІ."""
    raw_api5 = None
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
        raw_api5 = win32com.client.Dispatch("KOMPAS.Application.5")

    api5 = _wrap(K5.KompasObject, raw_api5)
    api5.Visible = visible
    api5.ksEnableTaskAccess(1)
    return api5


# РљРѕРЅСЃС‚Р°РЅС‚С‹ РљРћРњРџРђРЎ-3D (РёР· sdk_ref/include/ksConstants3D.h Рё ldefin2d.h)
PLANE_XY = 1                 # o3d_planeXOY (РЎРёРЅСЏСЏ РІ РёР·РѕРјРµС‚СЂРёРё)
PLANE_XZ = 2                 # o3d_planeXOZ (Р—РµР»РµРЅР°СЏ РІ РёР·РѕРјРµС‚СЂРёРё)
PLANE_YZ = 3                 # o3d_planeYOZ (РљСЂР°СЃРЅР°СЏ РІ РёР·РѕРјРµС‚СЂРёРё)
OBJ_PLANE_OFFSET = 4         # o3d_planeOffset
OBJ_SKETCH = 5               # o3d_sketch
OBJ_AXIS_2PLANES = 6         # o3d_axis2Planes (РћСЃСЊ РЅР° РїРµСЂРµСЃРµС‡РµРЅРёРё РґРІСѓС… РїР»РѕСЃРєРѕСЃС‚РµР№)
OBJ_AXIS_CONICAL = 9         # o3d_axisConeFace (РћСЃСЊ РєРѕРЅРёС‡РµСЃРєРѕР№/С†РёР»РёРЅРґСЂРёС‡РµСЃРєРѕР№ РіСЂР°РЅРё)

OBJ_FILLET = 15              # o3d_fillet
OBJ_CHAMFER = 16             # o3d_chamfer
OBJ_BASE_EXTRUDE = 24        # o3d_baseExtrusion
OBJ_BASE_ROTATE = 25         # o3d_baseRotated (РћРїРµСЂР°С†РёСЏ РІСЂР°С‰РµРЅРёСЏ)
OBJ_CUT_EXTRUDE = 26         # o3d_cutExtrusion (Р’С‹СЂРµР·Р°С‚СЊ РІС‹РґР°РІР»РёРІР°РЅРёРµРј)
OBJ_CUT_ROTATE = 27          # o3d_cutRotated (Р’С‹СЂРµР·Р°С‚СЊ РІСЂР°С‰РµРЅРёРµРј)
OBJ_CIRCULAR_COPY = 30       # o3d_circularCopy (РњР°СЃСЃРёРІ РїРѕ РєРѕРЅС†РµРЅС‚СЂРёС‡РµСЃРєРѕР№ СЃРµС‚РєРµ)

DT_NORMAL = 0                # РџСЂСЏРјРѕРµ РЅР°РїСЂР°РІР»РµРЅРёРµ (РЅР° СЂР°СЃСЃС‚РѕСЏРЅРёРµ)
DT_REVERSE = 1               # РћР±СЂР°С‚РЅРѕРµ РЅР°РїСЂР°РІР»РµРЅРёРµ
DT_BOTH = 2                  # Р’ РѕР±Р° РЅР°РїСЂР°РІР»РµРЅРёСЏ
DT_MIDDLE = 3                # РЎСЂРµРґРЅСЏСЏ РїР»РѕСЃРєРѕСЃС‚СЊ

STYLE_MAIN = 1               # РћСЃРЅРѕРІРЅР°СЏ Р»РёРЅРёСЏ РєРѕРЅС‚СѓСЂР° (СЃРёРЅСЏСЏ)
STYLE_THIN = 2               # РўРѕРЅРєР°СЏ/РІСЃРїРѕРјРѕРіР°С‚РµР»СЊРЅР°СЏ Р»РёРЅРёСЏ
STYLE_AXIS = 3               # РћСЃРµРІР°СЏ Р»РёРЅРёСЏ (С€С‚СЂРёС…РїСѓРЅРєС‚РёСЂРЅР°СЏ)

# РЎС‚СЂСѓРєС‚СѓСЂС‹ РїР°СЂР°РјРµС‚СЂРѕРІ 2D (РёР· ksConstants.h)
KO_LDIM_PARAM = 19           # ko_LDimParam (РџР°СЂР°РјРµС‚СЂС‹ Р»РёРЅРµР№РЅРѕРіРѕ СЂР°Р·РјРµСЂР°)
KO_LDIM_SOURCE = 20          # ko_LDimSourceParam
KO_DIM_DRAW = 21             # ko_DimDrawingParam
KO_DIM_TEXT = 22             # ko_DimTextParam
KO_RADDIM_PARAM = 23         # ko_RDimParam (РџР°СЂР°РјРµС‚СЂС‹ СЂР°РґРёР°Р»СЊРЅРѕРіРѕ/РґРёР°РјРµС‚СЂР°Р»СЊРЅРѕРіРѕ СЂР°Р·РјРµСЂР°)
KO_RADDIM_SOURCE = 24        # ko_RDimSourceParam
KO_RADDIM_DRAW = 25          # ko_RDimDrawingParam
KO_PARAMETRIC_PARAM = 64     # ko_ParametrizationParam


class SketchBuilder:
    """РљРѕРЅСЃС‚СЂСѓРєС‚РѕСЂ РїР»РѕСЃРєРѕРіРѕ 2D-СЌСЃРєРёР·Р° СЃ РїРѕРґРґРµСЂР¶РєРѕР№ СЂРµР°Р»СЊРЅС‹С… СЂР°Р·РјРµСЂРѕРІ Рё РїР°СЂР°РјРµС‚СЂРёР·Р°С†РёРё."""
    def __init__(self, doc2d, api5, part=None):
        self.doc2d = _wrap(K5.ksDocument2D, doc2d)
        self.api5 = api5
        self.part = part
        self.pending_expressions = []  # РЎРїРёСЃРѕРє С„РѕСЂРјСѓР» (РЅР°РїСЂРёРјРµСЂ, ["D/2", "o1/2", ...]) РґР»СЏ СЃРѕР·РґР°РЅРЅС‹С… РІ СЌСЃРєРёР·Рµ СЂР°Р·РјРµСЂРѕРІ

    def line(self, x1, y1=None, x2=None, y2=None, style: int = STYLE_MAIN):
        """РћС‚СЂРµР·РѕРє."""
        if isinstance(x1, (tuple, list)) and isinstance(y1, (tuple, list)):
            p1, p2 = x1, y1
            if x2 is not None:
                style = int(x2)
            x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
        self.doc2d.ksLineSeg(float(x1), float(y1), float(x2), float(y2), int(style))
        return self

    def axis(self, x1, y1=None, x2=None, y2=None):
        """РћСЃРµРІР°СЏ Р»РёРЅРёСЏ (СЃС‚РёР»СЊ 3)."""
        return self.line(x1, y1, x2, y2, style=STYLE_AXIS)

    def rect(self, x: float = 0.0, y: float = 0.0, w: float = 10.0, h: float = 10.0, centered: bool = False):
        """РџСЂСЏРјРѕСѓРіРѕР»СЊРЅРёРє."""
        x, y, w, h = float(x), float(y), float(w), float(h)
        if centered:
            x, y = x - w / 2.0, y - h / 2.0
        self.line(x, y, x + w, y)
        self.line(x + w, y, x + w, y + h)
        self.line(x + w, y + h, x, y + h)
        self.line(x, y + h, x, y)
        return self

    def circle(self, xc=0.0, yc=0.0, r=None, style: int = STYLE_MAIN, **kwargs):
        """РћРєСЂСѓР¶РЅРѕСЃС‚СЊ РїРѕ С†РµРЅС‚СЂСѓ (xc, yc) Рё СЂР°РґРёСѓСЃСѓ r."""
        if isinstance(xc, (tuple, list)):
            style = int(r) if r is not None else STYLE_MAIN
            r = yc
            xc, yc = xc[0], xc[1]
        if r is None:
            r = kwargs.get("radius") or (float(kwargs["d"]) / 2.0 if "d" in kwargs else float(kwargs["diameter"]) / 2.0)
        self.doc2d.ksCircle(float(xc), float(yc), float(r), int(style))
        return self

    def polygon(self, points: list[tuple[float, float]], closed: bool = True, style: int = STYLE_MAIN):
        """Р—Р°РјРєРЅСѓС‚С‹Р№ РјРЅРѕРіРѕСѓРіРѕР»СЊРЅРёРє РёР»Рё Р»РѕРјР°РЅР°СЏ РїРѕ С‚РѕС‡РєР°Рј [(x, y), ...]."""
        for i in range(len(points) - 1):
            self.line(points[i][0], points[i][1], points[i+1][0], points[i+1][1], style)
        if closed and len(points) > 2:
            self.line(points[-1][0], points[-1][1], points[0][0], points[0][1], style)
        return self

    def dim_linear(self, x1: float, y1: float, x2: float, y2: float, px: float, py: float, expression: str = None):
        """
        РЎРѕР·РґР°РµС‚ Р»РёРЅРµР№РЅС‹Р№ СЂР°Р·РјРµСЂ РљРћРњРџРђРЎР° РјРµР¶РґСѓ С‚РѕС‡РєР°РјРё (x1, y1) Рё (x2, y2).
        (px, py) вЂ” С‚РѕС‡РєР° РїРѕР»РѕР¶РµРЅРёСЏ СЂР°Р·РјРµСЂРЅРѕР№ Р»РёРЅРёРё.
        expression вЂ” С„РѕСЂРјСѓР»Р° РїСЂРёРІСЏР·РєРё Рє РїРµСЂРµРјРµРЅРЅРѕР№ (РЅР°РїСЂРёРјРµСЂ, 'D/2', 'ds/2', 'o1/2', 's', 'h').
        """
        ldim = _wrap(K5.ksLDimParam, self.api5.GetParamStruct(KO_LDIM_PARAM))

        # Source param вЂ” РїСЂРёРІСЏР·РєР° СЂР°Р·РјРµСЂРЅС‹С… Р»РёРЅРёР№ Рє С‚РѕС‡РєР°Рј СЌСЃРєРёР·Р°
        try:
            src = _wrap(K5.ksLDimSourceParam, self.api5.GetParamStruct(KO_LDIM_SOURCE))
            src.basePoint = 1
            src.x1, src.y1 = float(x1), float(y1)
            src.x2, src.y2 = float(x2), float(y2)
            src.px, src.py = float(px), float(py)
            if abs(y2 - y1) < 1e-6 and abs(x2 - x1) > 1e-6:
                src.ps = 1  # Р“РѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅС‹Р№
            elif abs(x2 - x1) < 1e-6 and abs(y2 - y1) > 1e-6:
                src.ps = 2  # Р’РµСЂС‚РёРєР°Р»СЊРЅС‹Р№
            else:
                src.ps = 0  # РџР°СЂР°Р»Р»РµР»СЊРЅС‹Р№
            ldim.SetSPar(src)
        except Exception:
            pass

        # Drawing param вЂ” РїР°СЂР°РјРµС‚СЂС‹ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        try:
            draw = _wrap(K5.ksDimDrawingParam, self.api5.GetParamStruct(KO_DIM_DRAW))
            draw.textBase = 0
            draw.pt1 = 1
            draw.pt2 = 1
            ldim.SetDPar(draw)
        except Exception:
            pass

        # Text param вЂ” РїР°СЂР°РјРµС‚СЂС‹ С‚РµРєСЃС‚Р°
        try:
            txt = _wrap(K5.ksDimTextParam, self.api5.GetParamStruct(KO_DIM_TEXT))
            txt.SetBitFlagValue(0x1, True)  # РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРѕРµ Р·РЅР°С‡РµРЅРёРµ
            ldim.SetTPar(txt)
        except Exception:
            pass

        try:
            ref = self.doc2d.ksLinDimension(ldim)
        except Exception:
            ref = None

        if expression and ref is not None:
            if abs(y2 - y1) < 1e-6:
                expected_val = abs(x2 - x1)
            elif abs(x2 - x1) < 1e-6:
                expected_val = abs(y2 - y1)
            else:
                expected_val = math.hypot(x2 - x1, y2 - y1)
            self.pending_expressions.append((expected_val, expression))
        return ref

    def dim_hor(self, y_line: float, x1: float, x2: float, var_name: str = None, y_pts: float = 0.0):
        """РЈРґРѕР±РЅР°СЏ РѕР±РµСЂС‚РєР° РґР»СЏ РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕРіРѕ СЂР°Р·РјРµСЂР° РјРµР¶РґСѓ (x1, y_pts) Рё (x2, y_pts) СЃ РїРѕР»РєРѕР№ РЅР° РІС‹СЃРѕС‚Рµ y_line."""
        return self.dim_linear(x1, y_pts, x2, y_pts, (x1 + x2) / 2.0, y_line, expression=var_name)

    def dim_ver(self, x_line: float, y1: float, y2: float, var_name: str = None, x_pts: float = 0.0):
        """РЈРґРѕР±РЅР°СЏ РѕР±РµСЂС‚РєР° РґР»СЏ РІРµСЂС‚РёРєР°Р»СЊРЅРѕРіРѕ СЂР°Р·РјРµСЂР° РјРµР¶РґСѓ (x_pts, y1) Рё (x_pts, y2) СЃ РїРѕР»РєРѕР№ РЅР° X = x_line."""
        return self.dim_linear(x_pts, y1, x_pts, y2, x_line, (y1 + y2) / 2.0, expression=var_name)

    def dim_diam(self, xc: float, yc: float, r: float, angle_deg: float = 45.0, var_name: str = None):
        """
        РЎРѕР·РґР°РµС‚ РґРёР°РјРµС‚СЂР°Р»СЊРЅС‹Р№ СЂР°Р·РјРµСЂ РѕРєСЂСѓР¶РЅРѕСЃС‚Рё СЃ С†РµРЅС‚СЂРѕРј (xc, yc) Рё СЂР°РґРёСѓСЃРѕРј r.
        var_name вЂ” РёРјСЏ РїРµСЂРµРјРµРЅРЅРѕР№ РёР»Рё РІС‹СЂР°Р¶РµРЅРёРµ (РЅР°РїСЂРёРјРµСЂ, 'o2').
        """
        rdim = _wrap(K5.ksRDimParam, self.api5.GetParamStruct(KO_RADDIM_PARAM))

        # Source param
        try:
            src = _wrap(K5.ksRDimSourceParam, self.api5.GetParamStruct(KO_RADDIM_SOURCE))
            src.xc, src.yc = float(xc), float(yc)
            src.rad = float(r)
            ang = math.radians(angle_deg)
            src.px = float(xc + (r + 12.0) * math.cos(ang))
            src.py = float(yc + (r + 12.0) * math.sin(ang))
            rdim.SetSPar(src)
        except Exception:
            pass

        # Drawing param
        try:
            draw = _wrap(K5.ksRDimDrawingParam, self.api5.GetParamStruct(KO_RADDIM_DRAW))
            draw.textPos = 1  # РќР° РїРѕР»РєРµ
            draw.pt1 = 1
            draw.pt2 = 1
            draw.ang = float(angle_deg)
            rdim.SetDPar(draw)
        except Exception:
            pass

        # Text param
        try:
            txt = _wrap(K5.ksDimTextParam, self.api5.GetParamStruct(KO_DIM_TEXT))
            txt.SetBitFlagValue(0x1, True)
            txt.sign = 1  # Р—РЅР°С‡РѕРє РґРёР°РјРµС‚СЂР° вЊЂ
            rdim.SetTPar(txt)
        except Exception:
            pass

        try:
            ref = self.doc2d.ksDiamDimension(rdim)
        except Exception:
            ref = None

        if var_name and ref is not None:
            self.pending_expressions.append((float(r) * 2.0, var_name))
        return ref

    def parametrize(self):
        """РќР°РєР»Р°РґС‹РІР°РµС‚ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ РїР°СЂР°РјРµС‚СЂРёС‡РµСЃРєРёРµ СЃРІСЏР·Рё (СЃРѕРІРїР°РґРµРЅРёРµ С‚РѕС‡РµРє, РІРµСЂС‚РёРєР°Р»СЊРЅРѕСЃС‚СЊ, РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅРѕСЃС‚СЊ, С„РёРєСЃР°С†РёСЋ СЂР°Р·РјРµСЂРѕРІ)."""
        pp = _wrap(K5.ksParametrizationParam, self.api5.GetParamStruct(KO_PARAMETRIC_PARAM))
        try:
            pp.Init()
        except Exception:
            pass
        # РСЃРїРѕР»СЊР·СѓРµРј С‚РѕР»СЊРєРѕ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ СЃРІРѕР№СЃС‚РІР° ksParametrizationParam РІ API5 v16
        pp.nearestPoints = True     # РќР°Р№С‚Рё СЃРѕРІРїР°РґР°СЋС‰РёРµ С‚РѕС‡РєРё (Р·Р°РјРєРЅСѓС‚С‹Рµ РєРѕРЅС‚СѓСЂС‹)
        pp.pointsLimit = 1000       # Р›РёРјРёС‚ С‚РѕС‡РµРє РґР»СЏ РїРѕРёСЃРєР°
        pp.horizontal = True        # РќР°Р№С‚Рё РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅС‹Рµ РѕС‚СЂРµР·РєРё
        pp.vertical = True          # РќР°Р№С‚Рё РІРµСЂС‚РёРєР°Р»СЊРЅС‹Рµ РѕС‚СЂРµР·РєРё
        pp.parallel = True          # РќР°Р№С‚Рё РїР°СЂР°Р»Р»РµР»СЊРЅС‹Рµ РѕС‚СЂРµР·РєРё
        pp.perpendicular = True     # РќР°Р№С‚Рё РїРµСЂРїРµРЅРґРёРєСѓР»СЏСЂРЅС‹Рµ РѕС‚СЂРµР·РєРё
        pp.angleLimit = 1.0         # РџСЂРµРґРµР» СѓРіР»Р° РґР»СЏ РѕРїСЂРµРґРµР»РµРЅРёСЏ РїР°СЂР°Р»Р»РµР»СЊРЅРѕСЃС‚Рё/РїРµСЂРїРµРЅРґРёРєСѓР»СЏСЂРЅРѕСЃС‚Рё (РіСЂР°РґСѓСЃС‹)
        # ksParametrizeObjects(obj, par): obj=0 вЂ” РІСЃРµ РѕР±СЉРµРєС‚С‹ С‚РµРєСѓС‰РµРіРѕ РґРѕРєСѓРјРµРЅС‚Р°
        self.doc2d.ksParametrizeObjects(0, pp)


class KompasPart:
    """Р’С‹СЃРѕРєРѕСѓСЂРѕРІРЅРµРІР°СЏ РѕР±РµСЂС‚РєР° РЅР°Рґ 3D-РґРµС‚Р°Р»СЊСЋ РљРћРњРџРђРЎ-3D v16.1."""
    def __init__(self, name: str = "Р”РµС‚Р°Р»СЊ", visible: bool = True):
        pythoncom.CoInitialize()
        self.api5 = _connect_existing_or_new_kompas(visible=visible)
        self._saved_successfully = False
        self._active_sketch_def = None
        self._variables = {}

        try:
            self.api7 = _wrap(K7.IApplication, self.api5.ksGetApplication7())
        except Exception:
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
            for i in range(docs.Count - 1, -1, -1):
                doc = _wrap(K7.IKompasDocument, docs.Item(i))
                path = getattr(doc, "PathName", "") or ""
                if not path.strip():
                    doc.Close(0)
        except Exception:
            pass

    def _cleanup_on_crash(self):
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
                "xy": PLANE_XY, "xoy": PLANE_XY,
                "xz": PLANE_XZ, "xoz": PLANE_XZ,
                "yz": PLANE_YZ, "yoz": PLANE_YZ,
            }
            plane = p_map.get(plane.lower().strip(), PLANE_XY)
        return _wrap(K5.ksEntity, self.part.GetDefaultEntity(plane))

    def create_offset_plane(self, base_plane: str | int, offset: float):
        """РЎРѕР·РґР°РµС‚ СЃРјРµС‰РµРЅРЅСѓСЋ РїР»РѕСЃРєРѕСЃС‚СЊ РїР°СЂР°Р»Р»РµР»СЊРЅРѕ Р±Р°Р·РѕРІРѕР№."""
        base_ent = self.get_base_plane(base_plane)
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_PLANE_OFFSET))
        defn = _wrap(K5.ksPlaneOffsetDefinition, ent.GetDefinition())
        defn.SetPlane(base_ent)
        defn.direction = True if offset >= 0 else False
        defn.offset = abs(float(offset))
        if not ent.Create():
            raise RuntimeError("[FAIL PLANE] РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ СЃРјРµС‰РµРЅРЅСѓСЋ РїР»РѕСЃРєРѕСЃС‚СЊ!")
        self.part.Update()
        return ent

    def create_axis_by_2_planes(self, plane1: str | int = "xy", plane2: str | int = "yz"):
        """
        РЎРѕР·РґР°РµС‚ РєРѕРЅСЃС‚СЂСѓРєС‚РёРІРЅСѓСЋ РѕСЃСЊ РЅР° РїРµСЂРµСЃРµС‡РµРЅРёРё РґРІСѓС… Р±Р°Р·РѕРІС‹С… РїР»РѕСЃРєРѕСЃС‚РµР№:
        - ('xy', 'xz') -> РћСЃСЊ X
        - ('xy', 'yz') -> РћСЃСЊ Y
        - ('xz', 'yz') -> РћСЃСЊ Z
        РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РґР»СЏ РєСЂСѓРіРѕРІС‹С… РјР°СЃСЃРёРІРѕРІ (РњР°СЃСЃРёРІ РїРѕ РєРѕРЅС†РµРЅС‚СЂРёС‡РµСЃРєРѕР№ СЃРµС‚РєРµ).
        """
        p1 = self.get_base_plane(plane1) if isinstance(plane1, (str, int)) else plane1
        p2 = self.get_base_plane(plane2) if isinstance(plane2, (str, int)) else plane2
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_AXIS_2PLANES))
        defn = _wrap(K5.ksAxis2PlanesDefinition, ent.GetDefinition())
        defn.SetPlane(1, p1)
        defn.SetPlane(2, p2)
        if not ent.Create():
            raise RuntimeError("[FAIL AXIS] РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ РѕСЃСЊ РЅР° РїРµСЂРµСЃРµС‡РµРЅРёРё РїР»РѕСЃРєРѕСЃС‚РµР№!")
        self.part.Update()
        return ent

    def create_sketch(self, plane="xy", draw_fn=None, auto_parametrize: bool = True):
        """РЎРѕР·РґР°РµС‚ СЌСЃРєРёР·, СЂРёСЃСѓРµС‚ РіРµРѕРјРµС‚СЂРёСЋ Рё СЂР°Р·РјРµСЂС‹, РІРєР»СЋС‡Р°РµС‚ РїР°СЂР°РјРµС‚СЂРёР·Р°С†РёСЋ Рё РїСЂРёРІСЏР·С‹РІР°РµС‚ РІС‹СЂР°Р¶РµРЅРёСЏ Рє РїРµСЂРµРјРµРЅРЅС‹Рј."""
        plane_ent = self.get_base_plane(plane) if isinstance(plane, (str, int)) else plane
        sk_ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_SKETCH))
        sk_def = _wrap(K5.ksSketchDefinition, sk_ent.GetDefinition())
        sk_def.SetPlane(plane_ent)
        sk_ent.Create()

        # Р—Р°РїРѕРјРёРЅР°РµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ РїРµСЂРµРјРµРЅРЅС‹Рµ СЌСЃРєРёР·Р° Р”Рћ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ
        vars_before = set(self._get_all_feature_var_names())

        doc2d = sk_def.BeginEdit()
        self._active_sketch_def = sk_def
        try:
            builder = SketchBuilder(doc2d, api5=self.api5, part=self)
            if callable(draw_fn):
                draw_fn(builder)
            if auto_parametrize and builder.pending_expressions:
                builder.parametrize()
        except Exception as e:
            try:
                sk_def.EndEdit()
                self._active_sketch_def = None
            except Exception:
                pass
            self.close()
            raise RuntimeError(f"[FAIL SKETCH] РћС€РёР±РєР° РїСЂРё РїРѕСЃС‚СЂРѕРµРЅРёРё СЌСЃРєРёР·Р°: {e}") from e
        else:
            sk_def.EndEdit()
            self._active_sketch_def = None
            self.part.Update()

        # РџСЂРёРІСЏР·С‹РІР°РµРј С„РѕСЂРјСѓР»С‹ (РЅР°РїСЂРёРјРµСЂ, 'D/2', 'o1/2', 's') Рє РЅРѕРІС‹Рј РїРµСЂРµРјРµРЅРЅС‹Рј СЌСЃРєРёР·Р° v9, v10...
        if builder.pending_expressions:
            self._bind_new_vars_to_expressions(vars_before, builder.pending_expressions)
            self.part.RebuildModel()
            self.part.Update()

        return sk_ent

    def extrude(self, sketch_ent, depth: float, direction: int = DT_NORMAL, draft_angle: float = 0.0, expr: str = None):
        """Р‘Р°Р·РѕРІРѕРµ РёР»Рё РґРѕР±Р°РІР»СЏСЋС‰РµРµ РІС‹РґР°РІР»РёРІР°РЅРёРµ. Р•СЃР»Рё Р·Р°РґР°РЅ expr (РЅР°РїСЂРёРјРµСЂ, 'h'), РїСЂРёРІСЏР·С‹РІР°РµС‚ РіР»СѓР±РёРЅСѓ Рє РїРµСЂРµРјРµРЅРЅРѕР№."""
        vol_before = self.volume()
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_BASE_EXTRUDE))
        defn = _wrap(K5.ksBaseExtrusionDefinition, ent.GetDefinition())
        defn.directionType = direction
        defn.SetSideParam(True, 0, float(depth), float(draft_angle), False)
        if direction in (DT_BOTH, DT_MIDDLE):
            defn.SetSideParam(False, 0, float(depth), float(draft_angle), False)
        defn.SetSketch(sketch_ent)
        if not ent.Create():
            self.close()
            raise RuntimeError("[FAIL EXTRUDE] РћРїРµСЂР°С†РёСЏ РІС‹РґР°РІР»РёРІР°РЅРёСЏ РЅРµ РїРѕСЃС‚СЂРѕРёР»Р°СЃСЊ!")
        self.part.Update()

        if expr:
            self._bind_new_vars_to_expressions(vars_before, [(float(depth), expr)])
            self.part.RebuildModel()

        if self.volume() <= vol_before + 1e-9:
            self.close()
            raise RuntimeError("[FAIL EXTRUDE] РћР±СЉРµРј РґРµС‚Р°Р»Рё РЅРµ СѓРІРµР»РёС‡РёР»СЃСЏ РїРѕСЃР»Рµ РІС‹РґР°РІР»РёРІР°РЅРёСЏ!")
        return ent

    def cut(self, sketch_ent, depth: float = 100.0, direction: int = DT_NORMAL, expr: str = None):
        """
        Р’С‹СЂРµР·Р°РЅРёРµ РІС‹РґР°РІР»РёРІР°РЅРёРµРј.
        Р•СЃР»Рё Р·Р°РґР°РЅ expr (РЅР°РїСЂРёРјРµСЂ, expr='s'), РІ С‚Р°Р±Р»РёС†Рµ РїРµСЂРµРјРµРЅРЅС‹С… РљРћРњРџРђРЎР° РґР»СЏ 'Р Р°СЃСЃС‚РѕСЏРЅРёРµ 1' Р±СѓРґРµС‚ Р·Р°РїРёСЃР°РЅР° С„РѕСЂРјСѓР»Р° 's'!
        """
        vol_before = self.volume()
        if vol_before <= 1e-9:
            self.close()
            raise RuntimeError("[FAIL CUT] РќРµР»СЊР·СЏ СЂРµР·Р°С‚СЊ РїСѓСЃС‚СѓСЋ РґРµС‚Р°Р»СЊ!")
        vars_before = set(self._get_all_feature_var_names())

        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_CUT_EXTRUDE))
        defn = _wrap(K5.ksCutExtrusionDefinition, ent.GetDefinition())
        defn.directionType = direction
        defn.SetSideParam(True, 0, float(depth), 0.0, False)
        if direction in (DT_BOTH, DT_MIDDLE):
            defn.SetSideParam(False, 0, float(depth), 0.0, False)
        defn.SetSketch(sketch_ent)
        if not ent.Create():
            self.close()
            raise RuntimeError("[FAIL CUT] РћРїРµСЂР°С†РёСЏ РІС‹СЂРµР·Р°РЅРёСЏ РЅРµ РїРѕСЃС‚СЂРѕРёР»Р°СЃСЊ!")
        self.part.Update()

        if expr:
            self._bind_new_vars_to_expressions(vars_before, [(float(depth), expr)])
            self.part.RebuildModel()

        vol_after = self.volume()
        if vol_after >= vol_before - 1e-9:
            self.close()
            raise RuntimeError(
                f"[FAIL CUT] Р’С‹СЂРµР· РїСЂРѕРјР°С…РЅСѓР»СЃСЏ РјРёРјРѕ С‚РµР»Р°! РћР±СЉРµРј РґРѕ={vol_before:.2f}, РїРѕСЃР»Рµ={vol_after:.2f}. "
                "РџСЂРѕРІРµСЂСЊ РЅР°РїСЂР°РІР»РµРЅРёРµ (DT_NORMAL / DT_REVERSE / DT_BOTH)."
            )
        return ent

    def revolve(self, sketch_ent, angle: float = 360.0, cut: bool = False):
        """РћРїРµСЂР°С†РёСЏ РІСЂР°С‰РµРЅРёСЏ (o3d_baseRotated = 25) РёР»Рё РІС‹СЂРµР·Р° РІСЂР°С‰РµРЅРёРµРј (o3d_cutRotated = 27)."""
        vol_before = self.volume()
        obj_type = OBJ_CUT_ROTATE if cut else OBJ_BASE_ROTATE
        ent = _wrap(K5.ksEntity, self.part.NewEntity(obj_type))
        if cut:
            defn = _wrap(K5.ksCutRotatedDefinition, ent.GetDefinition())
        else:
            defn = _wrap(K5.ksBaseRotatedDefinition, ent.GetDefinition())
        defn.directionType = DT_NORMAL
        # SetSketch — прямой COM вызов с raw объектом ksSketchDefinition
        sketch_def = _wrap(K5.ksSketchDefinition, sketch_ent.GetDefinition())
        defn._oleobj_.InvokeTypes(3, 0, 1, (11, 0), ((9, 0),), sketch_def._oleobj_)
        if not ent.Create():
            self.close()
            raise RuntimeError("[FAIL REVOLVE] Операция вращения не построилась! Убедись, что в эскизе есть осевая линия b.axis() и замкнутый контур НЕ накладывается на ось и не пересекает её.")
        self.part.Update()
        vol_after = self.volume()
        if cut and vol_after >= vol_before - 1e-9:
            self.close()
            raise RuntimeError("[FAIL REVOLVE CUT] Вырез вращением не снял материал!")
        if not cut and vol_after <= vol_before + 1e-9:
            self.close()
            raise RuntimeError("[FAIL REVOLVE] Операция вращения не увеличила объем!")
        return ent

    def circular_pattern(self, features: list, axis_ent, count: int = 4, angle: float = 360.0):
        """
        РњР°СЃСЃРёРІ РїРѕ РєРѕРЅС†РµРЅС‚СЂРёС‡РµСЃРєРѕР№ СЃРµС‚РєРµ (o3d_circularCopy = 30).
        features вЂ” СЃРїРёСЃРѕРє РѕРїРµСЂР°С†РёР№ РґР»СЏ СЂР°Р·РјРЅРѕР¶РµРЅРёСЏ (РЅР°РїСЂРёРјРµСЂ, [cut_hole_ent]).
        axis_ent вЂ” РѕСЃСЊ РІСЂР°С‰РµРЅРёСЏ РјР°СЃСЃРёРІР° (РЅР°РїСЂРёРјРµСЂ, СЃРѕР·РґР°РЅРЅР°СЏ С‡РµСЂРµР· create_axis_by_2_planes).
        count вЂ” РєРѕР»РёС‡РµСЃС‚РІРѕ СЌРєР·РµРјРїР»СЏСЂРѕРІ РїРѕ РѕРєСЂСѓР¶РЅРѕСЃС‚Рё (N2).
        angle вЂ” РїРѕР»РЅС‹Р№ СѓРіРѕР» (360.0 РіСЂР°РґСѓСЃРѕРІ РїСЂРё СЂР°РІРЅРѕРјРµСЂРЅРѕРј С€Р°РіРµ РїРѕ РєСЂСѓРіСѓ).
        """
        ent = _wrap(K5.ksEntity, self.part.NewEntity(OBJ_CIRCULAR_COPY))
        defn = _wrap(K5.ksCircularCopyDefinition, ent.GetDefinition())
        defn.SetAxis(axis_ent)
        defn.count1 = 1
        defn.step1 = 10.0
        defn.count2 = int(count)
        defn.step2 = float(angle)
        defn.factor2 = True  # True = С€Р°Рі Р·Р°РґР°РЅ РЅР° РІРµСЃСЊ РїРѕР»РЅС‹Р№ СѓРіРѕР» (360В°), Р РµР¶РёРј 2 = 1.0!
        defn.geomArray = False

        flist = _wrap(K5.ksEntityCollection, defn.OperationArray())
        flist.Clear()
        for f in features:
            flist.Add(f)

        if not ent.Create():
            self.close()
            raise RuntimeError("[FAIL PATTERN] РњР°СЃСЃРёРІ РїРѕ РєРѕРЅС†РµРЅС‚СЂРёС‡РµСЃРєРѕР№ СЃРµС‚РєРµ РЅРµ РїРѕСЃС‚СЂРѕРёР»СЃСЏ!")
        self.part.Update()
        return ent

    # ===================== РџР•Р Р•РњР•РќРќР«Р• Р Р’Р«Р РђР–Р•РќРРЇ (API5 + API7) =====================
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

    def add_variable(self, name: str, value: float, note: str = "", expression: str = None):
        """
        РЎРѕР·РґР°РµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєСѓСЋ РїРµСЂРµРјРµРЅРЅСѓСЋ РІ С‚Р°Р±Р»РёС†Рµ РїРµСЂРµРјРµРЅРЅС‹С… РґРµС‚Р°Р»Рё СЃ РєРѕРјРјРµРЅС‚Р°СЂРёРµРј.
        """
        part7 = self._get_part7()
        if not part7:
            raise RuntimeError("[FAIL VAR] РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ IPart7 РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РїРµСЂРµРјРµРЅРЅРѕР№.")
        var = _wrap(K7.IVariable7, part7.AddVariable(name, float(value), str(note)))
        # Р“Р°СЂР°РЅС‚РёСЂРѕРІР°РЅРЅРѕ Р·Р°РїРёСЃС‹РІР°РµРј РєРѕРјРјРµРЅС‚Р°СЂРёР№ РІ СЃРІРѕР№СЃС‚РІРѕ Note (С‡С‚РѕР±С‹ РЅРµ РґСѓР±Р»РёСЂРѕРІР°Р»РѕСЃСЊ РёРјСЏ РїРµСЂРµРјРµРЅРЅРѕР№!)
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
        return var

    def create_variables_from_dict(self, variables: dict[str, tuple[float, str]]):
        """РЎРѕР·РґР°РµС‚ С‡РёСЃС‚С‹Рµ РєРѕРЅСЃС‚СЂСѓРєС‚РѕСЂСЃРєРёРµ РїРµСЂРµРјРµРЅРЅС‹Рµ РёР· СЃР»РѕРІР°СЂСЏ {РёРјСЏ: (Р·РЅР°С‡РµРЅРёРµ, РєРѕРјРјРµРЅС‚Р°СЂРёР№)}."""
        result = {}
        for name, (value, note) in variables.items():
            result[name] = self.add_variable(name, value, note)
        return result

    def _get_all_feature_vars(self) -> list:
        """Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃРїРёСЃРѕРє РІСЃРµС… РІРЅСѓС‚СЂРµРЅРЅРёС… РїРµСЂРµРјРµРЅРЅС‹С… РјРѕРґРµР»Рё (v8, v9, v10...) С‡РµСЂРµР· VariableCollection."""
        res = []
        try:
            vcol = _wrap(K5.ksVariableCollection, self.part.VariableCollection())
            vcol.refresh()
            cnt = vcol.GetCount()
            for i in range(cnt):
                v = _wrap(K5.ksVariable, vcol.GetByIndex(i))
                res.append(v)
        except Exception:
            pass
        return res

    def _get_all_feature_var_names(self) -> list[str]:
        return [v.name for v in self._get_all_feature_vars()]

    def _bind_new_vars_to_expressions(self, vars_before: set[str], pending: list[tuple[float, str]]):
        """РќР°С…РѕРґРёС‚ РЅРѕРІС‹Рµ РїРµСЂРµРјРµРЅРЅС‹Рµ v..., РїРѕСЏРІРёРІС€РёРµСЃСЏ РїРѕСЃР»Рµ СЃРѕР·РґР°РЅРёСЏ СЌСЃРєРёР·Р°/РѕРїРµСЂР°С†РёРё, Рё РїСЂРѕРїРёСЃС‹РІР°РµС‚ РёРј С„РѕСЂРјСѓР»С‹ ('D/2', 's')."""
        all_vars = self._get_all_feature_vars()
        new_vars = [v for v in all_vars if v.name not in vars_before]
        used = set()
        for exp_val, expr_str in pending:
            # РС‰РµРј РЅРѕРІСѓСЋ РїРµСЂРµРјРµРЅРЅСѓСЋ СЃ СЃРѕРІРїР°РґР°СЋС‰РёРј С‡РёСЃР»РµРЅРЅС‹Рј Р·РЅР°С‡РµРЅРёРµРј
            best_v = None
            best_diff = 1e9
            for v in new_vars:
                if v.name in used:
                    continue
                diff = abs(float(v.value) - float(exp_val))
                if diff < best_diff and diff < 0.5:
                    best_diff = diff
                    best_v = v
            if best_v is not None:
                best_v.expression = str(expr_str)
                used.add(best_v.name)

    def rebuild(self):
        """РџРѕР»РЅРѕРµ РїРµСЂРµСЃС‚СЂРѕРµРЅРёРµ РјРѕРґРµР»Рё РїРѕ С‚Р°Р±Р»РёС†Рµ РїРµСЂРµРјРµРЅРЅС‹С…."""
        self.part.RebuildModel()
        self.part.Update()

    def volume(self) -> float:
        self.part.Update()
        mip = _wrap(K5.ksMassInertiaParam, self.part.CalcMassInertiaProperties(0x1))
        return float(mip.v)

    def bbox(self) -> tuple[float, float, float]:
        self.part.Update()
        res, x1, y1, z1, x2, y2, z2 = self.part.GetGabarit(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        if not res:
            raise RuntimeError("[FAIL BBOX] РќРµ СѓРґР°Р»РѕСЃСЊ РІС‹С‡РёСЃР»РёС‚СЊ РіР°Р±Р°СЂРёС‚ РґРµС‚Р°Р»Рё.")
        return abs(x2 - x1), abs(y2 - y1), abs(z2 - z1)

    def assert_bbox(self, exp_x: float, exp_y: float, exp_z: float, tol: float = 0.1):
        """РџСЂРѕРІРµСЂСЏРµС‚ РіР°Р±Р°СЂРёС‚С‹ РґРµС‚Р°Р»Рё (РІ Р»СЋР±РѕРј РїРѕСЂСЏРґРєРµ РѕСЃРµР№, РµСЃР»Рё РґРµС‚Р°Р»СЊ РѕСЂРёРµРЅС‚РёСЂРѕРІР°РЅР° РІРµСЂС‚РёРєР°Р»СЊРЅРѕ РїРѕ Y РёР»Рё Z)."""
        dx, dy, dz = self.bbox()
        actual_sorted = sorted([dx, dy, dz])
        exp_sorted = sorted([float(exp_x), float(exp_y), float(exp_z)])
        if any(abs(a - e) > tol for a, e in zip(actual_sorted, exp_sorted)):
            self.close()
            raise ValueError(
                f"[FAIL BBOX] Р“Р°Р±Р°СЂРёС‚С‹ РЅРµ СЃРѕРІРїР°Р»Рё! РћР¶РёРґР°Р»РѕСЃСЊ: ({exp_x:.2f}, {exp_y:.2f}, {exp_z:.2f}) РјРј, "
                f"Р¤Р°РєС‚РёС‡РµСЃРєРё РІ РљРћРњРџРђРЎРµ: ({dx:.2f} x {dy:.2f} x {dz:.2f}) РјРј."
            )
        print(f"[OK BBOX] Р“Р°Р±Р°СЂРёС‚С‹ РїРѕРґС‚РІРµСЂР¶РґРµРЅС‹: {dx:.2f} x {dy:.2f} x {dz:.2f} РјРј | V = {self.volume():.2f}")

    def close_if_already_open(self, filepath: str):
        if not self.api7:
            return
        try:
            abs_target = os.path.normcase(os.path.abspath(filepath))
            docs = _wrap(K7.IDocuments, self.api7.Documents)
            for i in range(docs.Count - 1, -1, -1):
                doc = _wrap(K7.IKompasDocument, docs.Item(i))
                doc_path = os.path.normcase(os.path.abspath(getattr(doc, "PathName", "") or ""))
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
        self.doc3d.SaveAsToRasterFormat(abs_path, raster)
        print(f"[OK RENDER] РЎРєСЂРёРЅС€РѕС‚ СЃРѕС…СЂР°РЅРµРЅ: {abs_path}")
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
        self.doc3d.SaveAs(abs_path)
        self._saved_successfully = True
        print(f"[OK SAVE] РњРѕРґРµР»СЊ СЃРѕС…СЂР°РЅРµРЅР°: {abs_path}")

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
